import socket
import threading
import time
from dataclasses import dataclass, field

HOST_DEFAULT = "0.0.0.0"
PORT_DEFAULT = 5555

TICK_HZ = 60
DT = 1.0 / TICK_HZ

# game field (logical units)
WIDTH = 800
HEIGHT = 500

PADDLE_H = 90
PADDLE_W = 12
PADDLE_MARGIN = 24
PADDLE_SPEED = 360.0  # units/s

BALL_R = 8
BALL_SPEED = 360.0

WIN_SCORE = 7

@dataclass
class Conn:
    sock: socket.socket
    addr: tuple
    name: str = ""
    role: str = "SPECTATOR"   # LEFT/RIGHT/SPECTATOR
    status: str = "WAITING"   # WAITING/QUEUED/PLAYING
    up: int = 0
    down: int = 0
    buf: bytearray = field(default_factory=bytearray)

    def send_line(self, line: str):
        self.sock.sendall((line + "\n").encode("utf-8"))

class PongServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((host, port))
        self.srv.listen(32)

        self.lock = threading.Lock()
        self.conns: dict[socket.socket, Conn] = {}
        self.name_map: dict[str, Conn] = {}

        self.queue: list[Conn] = []
        self.left: Conn | None = None
        self.right: Conn | None = None

        self.ly = HEIGHT/2 - PADDLE_H/2
        self.ry = HEIGHT/2 - PADDLE_H/2
        self.bx = WIDTH/2
        self.by = HEIGHT/2
        self.vx = BALL_SPEED
        self.vy = BALL_SPEED * 0.3

        self.sl = 0
        self.sr = 0
        self.match_state = "WAITING"  # WAITING/PLAYING/ENDED
        self._ended_at = 0.0

        self.running = True

    def start(self):
        print(f"[SERVER] Listening on {self.host}:{self.port}")
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self._game_loop()

    def _accept_loop(self):
        while self.running:
            try:
                cs, addr = self.srv.accept()
                cs.setblocking(False)
            except Exception:
                continue

            c = Conn(sock=cs, addr=addr)
            with self.lock:
                self.conns[cs] = c

            print(f"[SERVER] New connection: {addr}")
            try:
                c.send_line("ROLE SPECTATOR")
                c.send_line(f"MATCH {self.match_state}")
            except Exception:
                self._drop_conn(cs)

    def _drop_conn(self, cs: socket.socket):
        with self.lock:
            c = self.conns.pop(cs, None)
            if not c:
                return
            if c.name and self.name_map.get(c.name) is c:
                self.name_map.pop(c.name, None)
            if c in self.queue:
                try:
                    self.queue.remove(c)
                except ValueError:
                    pass

            was_left = (self.left is c)
            was_right = (self.right is c)
            if was_left or was_right:
                other = self.right if was_left else self.left
                self.left = None
                self.right = None
                if other:
                    other.role = "SPECTATOR"
                    other.status = "WAITING"
                    try:
                        other.send_line("ROLE SPECTATOR")
                        other.send_line("MATCH WAITING")
                        other.send_line("CHAT Server: Opponent disconnected. Back to lobby.")
                    except Exception:
                        pass
                self._reset_game(full=True)
                self.match_state = "WAITING"

        try:
            cs.close()
        except Exception:
            pass

        self._broadcast_lobby()

    def _recv_lines(self, c: Conn) -> list[str]:
        lines = []
        try:
            data = c.sock.recv(4096)
            if not data:
                raise ConnectionError("closed")
            c.buf.extend(data)
            while b"\n" in c.buf:
                i = c.buf.index(b"\n")
                raw = c.buf[:i]
                del c.buf[:i+1]
                lines.append(raw.decode("utf-8", errors="ignore").strip())
        except BlockingIOError:
            pass
        return lines

    def _broadcast(self, line: str):
        dead = []
        with self.lock:
            for cs, c in self.conns.items():
                try:
                    c.send_line(line)
                except Exception:
                    dead.append(cs)
        for cs in dead:
            self._drop_conn(cs)

    def _broadcast_lobby(self):
        with self.lock:
            items = []
            for c in self.conns.values():
                if not c.name:
                    continue
                items.append(f"{c.name}|{c.role}|{c.status}")
        self._broadcast(f"LOBBY {';'.join(items)}")

    def _maybe_start_match(self):
        with self.lock:
            if self.match_state == "PLAYING":
                return
            self.queue = [c for c in self.queue if c.sock in self.conns and c.name]
            if len(self.queue) < 2:
                return

            self.left = self.queue.pop(0)
            self.right = self.queue.pop(0)

            self.left.role = "LEFT"
            self.right.role = "RIGHT"
            self.left.status = "PLAYING"
            self.right.status = "PLAYING"

            self.match_state = "PLAYING"
            self._reset_game(full=True)

            try:
                self.left.send_line("ROLE LEFT")
                self.right.send_line("ROLE RIGHT")
                self.left.send_line("MATCH PLAYING")
                self.right.send_line("MATCH PLAYING")
            except Exception:
                pass

        self._broadcast_lobby()

    def _reset_game(self, full: bool):
        self.ly = HEIGHT/2 - PADDLE_H/2
        self.ry = HEIGHT/2 - PADDLE_H/2
        self.bx = WIDTH/2
        self.by = HEIGHT/2

        sign = 1 if int(time.time()*1000) % 2 == 0 else -1
        self.vx = BALL_SPEED * sign
        self.vy = BALL_SPEED * (0.15 + (int(time.time()*1000) % 30)/100.0) * (1 if sign == 1 else -1)

        if full:
            self.sl = 0
            self.sr = 0

    def _clamp(self, v, lo, hi):
        return lo if v < lo else hi if v > hi else v

    def _game_loop(self):
        last = time.time()
        acc = 0.0

        while self.running:
            now = time.time()
            dt = now - last
            last = now
            acc += dt

            with self.lock:
                conns_list = list(self.conns.values())
            for c in conns_list:
                try:
                    for line in self._recv_lines(c):
                        self._handle_line(c, line)
                except Exception:
                    self._drop_conn(c.sock)

            self._maybe_start_match()

            while acc >= DT:
                acc -= DT
                self._step(DT)

            self._broadcast_state()

            time.sleep(0.004)

    def _broadcast_state(self):
        if self.match_state in ("PLAYING", "ENDED"):
            line = f"STATE ly={self.ly:.2f} ry={self.ry:.2f} bx={self.bx:.2f} by={self.by:.2f} sl={self.sl} sr={self.sr}"
            dead = []
            with self.lock:
                for cs, c in self.conns.items():
                    try:
                        c.send_line(line)
                    except Exception:
                        dead.append(cs)
            for cs in dead:
                self._drop_conn(cs)

    def _handle_line(self, c: Conn, line: str):
        if not line:
            return
        if line.startswith("HELLO "):
            name = line[6:].strip()
            if not name:
                return
            with self.lock:
                if name in self.name_map:
                    try:
                        c.send_line("ERROR NameTaken")
                    except Exception:
                        pass
                    return
                c.name = name
                self.name_map[name] = c
            try:
                c.send_line("ROLE SPECTATOR")
                c.send_line(f"MATCH {self.match_state}")
                c.send_line("CHAT Server: Welcome! Click 'Request to play' to join queue.")
            except Exception:
                pass
            self._broadcast_lobby()
            return

        if not c.name:
            return

        if line == "REQ_PLAY":
            with self.lock:
                if c.status == "PLAYING":
                    return
                if c not in self.queue:
                    self.queue.append(c)
                c.status = "QUEUED"
            self._broadcast_lobby()
            return

        if line == "CANCEL_PLAY":
            with self.lock:
                if c in self.queue:
                    try:
                        self.queue.remove(c)
                    except ValueError:
                        pass
                if c.status != "PLAYING":
                    c.status = "WAITING"
            self._broadcast_lobby()
            return

        if line.startswith("INPUT "):
            parts = line.split()
            if len(parts) >= 3:
                key = parts[1].upper()
                val = 1 if parts[2] == "1" else 0
                if key == "UP":
                    c.up = val
                elif key == "DOWN":
                    c.down = val
            return

        if line.startswith("CHAT "):
            msg = line[5:].strip()
            if msg:
                self._broadcast(f"CHAT {c.name}: {msg}")
            return

    def _step(self, dt: float):
        if self.match_state == "ENDED":
            if time.time() - self._ended_at > 0.8:
                with self.lock:
                    if self.left:
                        self.left.role = "SPECTATOR"
                        self.left.status = "WAITING"
                        try:
                            self.left.send_line("ROLE SPECTATOR")
                            self.left.send_line("MATCH WAITING")
                        except Exception:
                            pass
                    if self.right:
                        self.right.role = "SPECTATOR"
                        self.right.status = "WAITING"
                        try:
                            self.right.send_line("ROLE SPECTATOR")
                            self.right.send_line("MATCH WAITING")
                        except Exception:
                            pass
                    self.left = None
                    self.right = None
                    self.match_state = "WAITING"
                    self._reset_game(full=True)
                self._broadcast_lobby()
            return

        if self.match_state != "PLAYING":
            return

        left = self.left
        right = self.right
        if not left or not right:
            self.match_state = "WAITING"
            return

        self.ly += (left.down - left.up) * PADDLE_SPEED * dt
        self.ry += (right.down - right.up) * PADDLE_SPEED * dt
        self.ly = self._clamp(self.ly, 0, HEIGHT - PADDLE_H)
        self.ry = self._clamp(self.ry, 0, HEIGHT - PADDLE_H)

        self.bx += self.vx * dt
        self.by += self.vy * dt

        if self.by - BALL_R <= 0:
            self.by = BALL_R
            self.vy *= -1
        elif self.by + BALL_R >= HEIGHT:
            self.by = HEIGHT - BALL_R
            self.vy *= -1

        lx = PADDLE_MARGIN
        rx = WIDTH - PADDLE_MARGIN - PADDLE_W

        if self.vx < 0 and self.bx - BALL_R <= lx + PADDLE_W:
            if self.ly <= self.by <= self.ly + PADDLE_H:
                self.bx = lx + PADDLE_W + BALL_R
                self.vx *= -1
                rel = (self.by - (self.ly + PADDLE_H/2)) / (PADDLE_H/2)
                self.vy = BALL_SPEED * 0.65 * rel

        if self.vx > 0 and self.bx + BALL_R >= rx:
            if self.ry <= self.by <= self.ry + PADDLE_H:
                self.bx = rx - BALL_R
                self.vx *= -1
                rel = (self.by - (self.ry + PADDLE_H/2)) / (PADDLE_H/2)
                self.vy = BALL_SPEED * 0.65 * rel

        if self.bx < -30:
            self.sr += 1
            if self.sr >= WIN_SCORE:
                self._end_match(winner="RIGHT")
            else:
                self._reset_game(full=False)
                self.vx = abs(self.vx)
            return

        if self.bx > WIDTH + 30:
            self.sl += 1
            if self.sl >= WIN_SCORE:
                self._end_match(winner="LEFT")
            else:
                self._reset_game(full=False)
                self.vx = -abs(self.vx)
            return

    def _end_match(self, winner: str):
        self.match_state = "ENDED"
        self._ended_at = time.time()
        self._broadcast(f"END winner={winner} sl={self.sl} sr={self.sr}")
        with self.lock:
            if self.left:
                try:
                    self.left.send_line("MATCH ENDED")
                except Exception:
                    pass
            if self.right:
                try:
                    self.right.send_line("MATCH ENDED")
                except Exception:
                    pass

def main():
    import sys
    host = HOST_DEFAULT
    port = PORT_DEFAULT
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        port = int(sys.argv[2])
    PongServer(host, port).start()

if __name__ == "__main__":
    main()

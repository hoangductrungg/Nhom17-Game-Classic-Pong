from __future__ import annotations

import time
from tkinter import messagebox

from state.game_state import GameState, NetState
from net.client_net import ClientNet

def parse_lobby(payload: str):
    items = []
    statuses = []
    if not payload:
        return items, statuses
    for chunk in payload.split(";"):
        parts = [x.strip() for x in chunk.split("|")]
        if len(parts) >= 3:
            name, role, st = parts[0], parts[1], parts[2]
            items.append(f"{name:<10} | {role:<9} | {st}")
            statuses.append(st)
    return items, statuses

def parse_kv(line: str) -> dict:
    parts = line.strip().split()
    out = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out

class GameController:
    INTERP_DELAY_MS = 100

    def __init__(self, master, state: GameState):
        self.master = master
        self.state = state
        self.net = ClientNet()

        self._current_view = None
        self.login_view = None
        self.game_view = None

        self._prev_dx = None
        self._prev_dy = None
        self._window_positioned = False

        self._poll_job = None
        self._render_job = None

    def _set_view(self, view):
        try:
            if self._current_view is not None:
                self._current_view.destroy()
        except Exception:
            pass
        self._current_view = view
        self._current_view.pack(fill="both", expand=True)

    def show_login(self):
        from ui.login_view import LoginView
        self.login_view = LoginView(self.master, self.connect)
        self._set_view(self.login_view)

    def show_game(self):
        from ui.game_view import GameView
        self.game_view = GameView(
            self.master,
            self.disconnect,
            self.send_input,
            self.request_play,
            self.cancel_play,
            self.send_chat
        )
        try:
            self.game_view.set_play_again_callback(self.request_play)
        except Exception:
            pass
        self._set_view(self.game_view)

    def connect(self, ip: str, port: int, username: str):
        try:
            self.net.connect(ip, port)
        except Exception as e:
            raise RuntimeError(f"Cannot connect: {e}")

        self.state.connected = True
        self.state.role = "SPECTATOR"
        self.state.match_state = "WAITING"
        self.state.sl = 0
        self.state.sr = 0
        self.state.prev_net = None
        self.state.curr_net = None
        self._prev_dx = None
        self._prev_dy = None
        self._window_positioned = False

        self.show_game()
        self.net.send_line(f"HELLO {username.strip()}")

        if self._poll_job is None:
            self._schedule_poll()
        if self._render_job is None:
            self._schedule_render()

    def disconnect(self):
        try:
            self.net.close()
        except Exception:
            pass
        self.state.connected = False

        if self._poll_job is not None:
            try:
                self.master.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

        if self._render_job is not None:
            try:
                self.master.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        self.show_login()

    def request_play(self):
        if self.state.connected:
            try:
                self.net.send_line("REQ_PLAY")
            except Exception:
                pass

    def cancel_play(self):
        if self.state.connected:
            try:
                self.net.send_line("CANCEL_PLAY")
            except Exception:
                pass

    def send_chat(self, msg: str):
        if not self.state.connected:
            return
        msg = (msg or "").strip()
        if not msg:
            return
        try:
            self.net.send_line(f"CHAT {msg}")
        except Exception:
            pass

    def send_input(self, key: str, is_down: int):
        if not self.state.connected:
            return
        try:
            self.net.send_line(f"INPUT {key} {int(is_down)}")
        except Exception:
            pass

    def _schedule_poll(self):
        self._poll_job = self.master.after(16, self._poll_net)

    def _poll_net(self):
        if not self.state.connected:
            return
        try:
            lines = self.net.recv_lines()
        except Exception:
            self.disconnect()
            return

        for line in lines:
            self._handle_line(line)

        self._schedule_poll()

    def _schedule_render(self):
        self._render_job = self.master.after(16, self._render_tick)

    def _render_tick(self):
        if not self.state.connected or not self.game_view:
            self._schedule_render()
            return

        ns = self._interpolate()
        if ns:
            try:
                self.game_view.update_scene(ns.ly, ns.ry, ns.bx, ns.by)
                self.game_view.set_score(ns.sl, ns.sr)
            except Exception:
                pass

        try:
            self.game_view.render()
        except Exception:
            pass

        self._schedule_render()

    def _interpolate(self):
        pn = self.state.prev_net
        cn = self.state.curr_net
        if not pn or not cn:
            return None

        render_t = time.time() - (self.INTERP_DELAY_MS / 1000.0)

        if render_t <= pn.t:
            return pn
        if render_t >= cn.t:
            return cn

        span = max(1e-6, cn.t - pn.t)
        a = (render_t - pn.t) / span

        ly = pn.ly + (cn.ly - pn.ly) * a
        ry = pn.ry + (cn.ry - pn.ry) * a
        bx = pn.bx + (cn.bx - pn.bx) * a
        by = pn.by + (cn.by - pn.by) * a
        return NetState(render_t, ly, ry, bx, by, cn.sl, cn.sr)

    def _apply_window_position(self, role: str):
        if self._window_positioned:
            return
        role = (role or "").upper()
        if role not in ("LEFT", "RIGHT"):
            return

        top = self.master.winfo_toplevel()
        top.update_idletasks()

        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        left = 0
        top_y = 0
        right = sw
        bottom = sh

        try:
            import ctypes
            from ctypes import wintypes
            SPI_GETWORKAREA = 0x0030
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
            left, top_y, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass

        work_w = max(400, right - left)
        work_h = max(300, bottom - top_y)

        w_left = work_w // 2
        w_right = work_w - w_left

        if role == "LEFT":
            w = w_left
            x = left
        else:
            w = w_right
            x = left + w_left

        h = work_h
        y = top_y

        top.geometry(f"{w}x{h}+{x}+{y}")
        self._window_positioned = True

    def _handle_line(self, line: str):
        line = (line or "").strip()
        if not line:
            return

        if line.startswith("ERROR"):
            err = line.split(maxsplit=1)[1].strip() if len(line.split(maxsplit=1)) > 1 else "UnknownError"
            if err == "NameTaken":
                try:
                    messagebox.showerror("Name", "Username is taken. Please choose another name.")
                except Exception:
                    pass
                try:
                    self.net.close()
                except Exception:
                    pass
                self.state.connected = False
                self.show_login()
                try:
                    self.login_view.set_status("Username is taken. Try another name.")
                    self.login_view.focus_username(select_all=True)
                except Exception:
                    pass
                return
            try:
                messagebox.showerror("Error", err)
            except Exception:
                pass
            return

        if line.startswith("CHAT "):
            msg = line[5:]
            if self.game_view:
                self.game_view.append_chat(msg)
            return

        if line.startswith("LOBBY "):
            items, statuses = parse_lobby(line[6:].strip())
            if self.game_view:
                self.game_view.set_lobby(items)
                self.game_view.highlight_lobby(statuses)
            return

        if line.startswith("ROLE "):
            role = line.split(maxsplit=1)[1].strip()
            self.state.role = role
            if self.game_view:
                self.game_view.set_role(role)
                self.game_view.append_log(f"Role: {role}")
            self._apply_window_position(role)
            return

        if line.startswith("MATCH "):
            ms = line.split(maxsplit=1)[1].strip()
            self.state.match_state = ms
            if self.game_view:
                self.game_view.set_match_state(ms)
                try:
                    self.game_view.hide_end_banner()
                except Exception:
                    pass
            return

        if line.startswith("STATE"):
            kv = parse_kv(line)
            try:
                ns = NetState(
                    time.time(),
                    float(kv.get("ly", "0")),
                    float(kv.get("ry", "0")),
                    float(kv.get("bx", "0")),
                    float(kv.get("by", "0")),
                    int(kv.get("sl", "0")),
                    int(kv.get("sr", "0")),
                )
            except Exception:
                return

            if self.state.curr_net is None:
                self.state.prev_net = ns
                self.state.curr_net = ns
            else:
                self.state.prev_net = self.state.curr_net
                self.state.curr_net = ns

            try:
                pn = self.state.prev_net
                cn = self.state.curr_net
                dx = cn.bx - pn.bx
                dy = cn.by - pn.by
                bounced = False
                if self._prev_dx is not None and dx != 0 and (dx > 0) != (self._prev_dx > 0):
                    bounced = True
                if self._prev_dy is not None and dy != 0 and (dy > 0) != (self._prev_dy > 0):
                    bounced = True
                if dx != 0:
                    self._prev_dx = dx
                if dy != 0:
                    self._prev_dy = dy
                if bounced and self.game_view:
                    self.game_view.trigger_bounce_fx()
            except Exception:
                pass
            return

        if line.startswith("END"):
            kv = parse_kv(line)
            winner = kv.get("winner", "?")
            try:
                sl = int(kv.get("sl", "0"))
            except Exception:
                sl = 0
            try:
                sr = int(kv.get("sr", "0"))
            except Exception:
                sr = 0

            self.state.match_state = "ENDED"
            self.state.sl = sl
            self.state.sr = sr

            if self.game_view:
                self.game_view.set_match_state("ENDED")
                self.game_view.set_score(sl, sr)
                self.game_view.append_log(line)
                self.game_view.show_end_banner(f"Winner: {winner}   Final: {sl} : {sr}")
            return

        if self.game_view:
            self.game_view.append_log(line)

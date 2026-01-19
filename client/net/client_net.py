import socket
from typing import List

class ClientNet:
    def __init__(self):
        self.sock: socket.socket | None = None
        self.buf = bytearray()

    def connect(self, host: str, port: int) -> bool:
        self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.setblocking(False)
        self.sock = s
        return True

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.buf = bytearray()

    def send_line(self, line: str):
        if not self.sock:
            return
        self.sock.sendall((line + "\n").encode("utf-8"))

    def recv_lines(self) -> List[str]:
        if not self.sock:
            return []
        out: List[str] = []
        try:
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionError("closed")
            self.buf.extend(data)
            while b"\n" in self.buf:
                i = self.buf.index(b"\n")
                raw = self.buf[:i]
                del self.buf[:i+1]
                out.append(raw.decode("utf-8", errors="ignore").strip())
        except BlockingIOError:
            pass
        return out

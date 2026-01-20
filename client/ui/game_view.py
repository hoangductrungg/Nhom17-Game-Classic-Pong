import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import random
import time

from .widgets import WIDTH, HEIGHT, LEFT_X, RIGHT_X

def _try_beep():
    try:
        import winsound
        winsound.Beep(900, 35)
        return True
    except Exception:
        return False

class GameView(ttk.Frame):
    def __init__(self, master, on_disconnect, on_input_change, on_req_play, on_cancel_play, on_send_chat):
        super().__init__(master, padding=10)
        self.on_disconnect = on_disconnect
        self.on_input_change = on_input_change
        self.on_req_play = on_req_play
        self.on_cancel_play = on_cancel_play
        self.on_send_chat = on_send_chat

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        main = ttk.Frame(self)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(main, bg="#0b0f14", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        side = ttk.Frame(main)
        side.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        side.columnconfigure(0, weight=1)
        side.rowconfigure(5, weight=1)

        header = ttk.Frame(side)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        self.lbl_role = ttk.Label(header, text="Role: SPECTATOR", font=("Segoe UI", 12, "bold"))
        self.lbl_role.grid(row=0, column=0, sticky="w")

        self.lbl_status = ttk.Label(header, text="Match: WAITING", font=("Segoe UI", 11))
        self.lbl_status.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.lbl_score = ttk.Label(side, text="Score 0 : 0", font=("Segoe UI", 18, "bold"))
        self.lbl_score.grid(row=1, column=0, sticky="w", pady=(10, 6))

        self._end_banner = ttk.Frame(side)
        self._end_banner.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._end_banner.columnconfigure(0, weight=1)
        self._end_label = ttk.Label(self._end_banner, text="", font=("Segoe UI", 11, "bold"))
        self._end_label.grid(row=0, column=0, sticky="w")
        self._btn_play_again = ttk.Button(self._end_banner, text="Play again", command=self._on_play_again)
        self._btn_play_again.grid(row=0, column=1, sticky="e")
        self._end_banner.grid_remove()
        self._play_again_cb = None

        btns = ttk.Frame(side)
        btns.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(btns, text="Request to play", command=self.on_req_play).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=self.on_cancel_play).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="Disconnect", command=self.on_disconnect).grid(row=0, column=2)

        lobby_frame = ttk.LabelFrame(side, text="Lobby")
        lobby_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        lobby_frame.columnconfigure(0, weight=1)
        self.lobby = tk.Listbox(lobby_frame, width=42, height=9, activestyle="none", bd=0, highlightthickness=0)
        self.lobby.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        chat_frame = ttk.LabelFrame(side, text="Chat")
        chat_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 10))
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)

        self.chat_log = ScrolledText(chat_frame, width=42, height=10, state="disabled", wrap="word", bd=0)
        self.chat_log.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=(10, 6))

        self.chat_var = tk.StringVar()
        self.chat_entry = ttk.Entry(chat_frame, textvariable=self.chat_var)
        self.chat_entry.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 10))
        ttk.Button(chat_frame, text="Send", command=self._send_chat).grid(row=1, column=1, padx=(0, 10), pady=(0, 10))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())

        log_frame = ttk.LabelFrame(side, text="System")
        log_frame.grid(row=6, column=0, sticky="ew")
        log_frame.columnconfigure(0, weight=1)

        self.log = ScrolledText(log_frame, width=42, height=6, state="disabled", wrap="word", bd=0)
        self.log.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.bind_all("<KeyPress>", self._on_key_press)
        self.bind_all("<KeyRelease>", self._on_key_release)
        self._keys_down = set()
        self._control_enabled = False

        self._ly = 205.0
        self._ry = 205.0
        self._bx = 400.0
        self._by = 250.0

        self._shake_until = 0.0
        self._shake_amp = 0
        self._last_beep_t = 0.0

    def set_play_again_callback(self, cb):
        self._play_again_cb = cb

    def show_end_banner(self, text: str):
        self._end_label.config(text=text)
        self._end_banner.grid()

    def hide_end_banner(self):
        self._end_banner.grid_remove()

    def _on_play_again(self):
        try:
            self.hide_end_banner()
        except Exception:
            pass
        if self._play_again_cb:
            self._play_again_cb()

    def set_role(self, role: str):
        self.lbl_role.config(text=f"Role: {role}")
        self._control_enabled = (role in ("LEFT", "RIGHT"))

    def set_match_state(self, ms: str):
        self.lbl_status.config(text=f"Match: {ms}")

    def set_score(self, sl: int, sr: int):
        self.lbl_score.config(text=f"Score {sl} : {sr}")

    def update_scene(self, ly: float, ry: float, bx: float, by: float):
        self._ly, self._ry, self._bx, self._by = ly, ry, bx, by

    def trigger_bounce_fx(self):
        self._shake_until = time.time() + 0.10
        self._shake_amp = 4
        now = time.time()
        if now - self._last_beep_t > 0.05:
            ok = _try_beep()
            if not ok:
                try:
                    self.winfo_toplevel().bell()
                except Exception:
                    pass
            self._last_beep_t = now

    def highlight_lobby(self, statuses: list[str]):
        for i in range(self.lobby.size()):
            try:
                self.lobby.itemconfig(i, bg="white", fg="black")
            except Exception:
                pass
        for i, st in enumerate(statuses):
            st = (st or "").upper()
            if st == "PLAYING":
                self.lobby.itemconfig(i, bg="#d1f7d1", fg="black")
            elif st == "QUEUED":
                self.lobby.itemconfig(i, bg="#fff2cc", fg="black")
            else:
                self.lobby.itemconfig(i, bg="white", fg="black")

    def set_lobby(self, items: list[str]):
        self.lobby.delete(0, "end")
        for it in items:
            self.lobby.insert("end", it)

    def append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def append_chat(self, text: str):
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", text + "\n")
        self.chat_log.see("end")
        self.chat_log.configure(state="disabled")

    def _send_chat(self):
        msg = self.chat_var.get().strip()
        if not msg:
            return
        self.chat_var.set("")
        self.on_send_chat(msg)

    def render(self):
        c = self.canvas
        c.delete("all")

        cw = max(1, int(c.winfo_width()))
        ch = max(1, int(c.winfo_height()))

        ox = oy = 0
        if time.time() < self._shake_until and self._shake_amp > 0:
            ox = random.randint(-self._shake_amp, self._shake_amp)
            oy = random.randint(-self._shake_amp, self._shake_amp)

        sx = cw / WIDTH
        sy = ch / HEIGHT
        s = sx if sx < sy else sy

        draw_w = int(WIDTH * s)
        draw_h = int(HEIGHT * s)
        pad_x = (cw - draw_w) // 2
        pad_y = (ch - draw_h) // 2

        def tx(x): return pad_x + int((x + ox) * s)
        def ty(y): return pad_y + int((y + oy) * s)

        c.create_rectangle(pad_x, pad_y, pad_x + draw_w, pad_y + draw_h, outline="", fill="#0b0f14")

        cx = WIDTH / 2
        seg_h = 18
        gap = 14
        y = 10
        while y < HEIGHT:
            c.create_rectangle(tx(cx) - max(1, int(1*s)), ty(y), tx(cx) + max(1, int(1*s)), ty(y + seg_h),
                               fill="#2a3441", outline="")
            y += seg_h + gap

        c.create_rectangle(tx(LEFT_X), ty(self._ly), tx(LEFT_X + 12), ty(self._ly + 90),
                           fill="#e8edf2", outline="#e8edf2")
        c.create_rectangle(tx(RIGHT_X), ty(self._ry), tx(RIGHT_X + 12), ty(self._ry + 90),
                           fill="#e8edf2", outline="#e8edf2")
        r = 8
        c.create_oval(tx(self._bx - r), ty(self._by - r), tx(self._bx + r), ty(self._by + r),
                      fill="#e8edf2", outline="#e8edf2")

        if not self._control_enabled:
            c.create_text(tx(WIDTH/2), ty(20), fill="#e8edf2",
                          text="SPECTATOR MODE (Request to play to join queue)",
                          font=("Segoe UI", 12, "bold"))

    def _on_key_press(self, event):
        if not self._control_enabled:
            return
        k = event.keysym.lower()
        if k in self._keys_down:
            return
        self._keys_down.add(k)
        if k in ("w", "up"):
            self.on_input_change("UP", 1)
        elif k in ("s", "down"):
            self.on_input_change("DOWN", 1)



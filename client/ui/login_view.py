import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

class LoginView(ttk.Frame):
    def __init__(self, master, on_connect):
        super().__init__(master, padding=18)
        self.on_connect = on_connect
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Game Classic Pong ", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 12))

        card = ttk.Frame(self, padding=14)
        card.grid(row=1, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="Server IP:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Label(card, text="Port:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Label(card, text="Username:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))

        self.ip_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="5555")
        self.name_var = tk.StringVar(value="player")

        self.ip_entry = ttk.Entry(card, textvariable=self.ip_var)
        self.port_entry = ttk.Entry(card, textvariable=self.port_var)
        self.name_entry = ttk.Entry(card, textvariable=self.name_var)

        self.ip_entry.grid(row=0, column=1, sticky="ew", pady=6)
        self.port_entry.grid(row=1, column=1, sticky="ew", pady=6)
        self.name_entry.grid(row=2, column=1, sticky="ew", pady=6)

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, sticky="w", pady=(14, 0))

        ttk.Button(btns, text="Connect", command=self._connect).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(btns, text="Exit", command=self._exit).grid(row=0, column=1)

        self.status = ttk.Label(self, text="", foreground="#b00020")
        self.status.grid(row=3, column=0, sticky="w", pady=(10, 0))

        for w in (self.ip_entry, self.port_entry, self.name_entry):
            w.bind("<Return>", lambda e: self._connect())
            w.bind("<Key>", lambda e: self.set_status(""))

        self.name_entry.focus_set()
        self.name_entry.selection_range(0, "end")

    def _connect(self):
        ip = self.ip_var.get().strip()
        port_s = self.port_var.get().strip()
        name = self.name_var.get().strip()

        if not ip or not port_s or not name:
            self.set_status("Please fill all fields.")
            return

        try:
            port = int(port_s)
        except ValueError:
            self.set_status("Port must be a number.")
            return

        try:
            self.on_connect(ip, port, name)
        except Exception as e:
            messagebox.showerror("Connect failed", str(e))

    def _exit(self):
        self.winfo_toplevel().destroy()

    def set_status(self, text: str):
        self.status.config(text=text)

    def focus_username(self, select_all: bool = True):
        try:
            self.name_entry.focus_set()
            if select_all:
                self.name_entry.selection_range(0, "end")
        except Exception:
            pass

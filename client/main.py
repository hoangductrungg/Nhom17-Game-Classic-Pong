import os
import sys

# Run either:
#   python client/main.py   (from pong_socket/)
# or
#   python -m client.main   (from pong_socket/)
if __package__ is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

import tkinter as tk
from tkinter import ttk

from state.game_state import GameState
from controller.game_controller import GameController

def main():
    root = tk.Tk()
    root.title("Nhom 17 - Game Classic Pong")
    root.geometry("1100x700")
    root.minsize(980, 620)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    state = GameState()
    controller = GameController(root, state)
    controller.show_login()

    root.mainloop()

if __name__ == "__main__":
    main()

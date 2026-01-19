from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class NetState:
    t: float
    ly: float
    ry: float
    bx: float
    by: float
    sl: int
    sr: int

class GameState:
    def __init__(self):
        self.connected: bool = False
        self.role: str = "SPECTATOR"
        self.match_state: str = "WAITING"
        self.sl: int = 0
        self.sr: int = 0

        self.prev_net: Optional[NetState] = None
        self.curr_net: Optional[NetState] = None

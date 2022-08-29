from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LEDBLEState:

    power: bool = False
    rgb: tuple[int, int, int] = (0, 0, 0)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LEDBLEState:

    power: bool = False
    rgb: tuple[int, int, int] = (0, 0, 0)
    w: int = 0
    model_num: int = 0
    preset_pattern: int = 0
    mode: int = 0
    speed: int = 0
    version_num: int = 0

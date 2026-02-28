"""固定帧率时钟。"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class FrameClock:
    """以固定 FPS 控制循环节奏。"""

    fps: float = 16.0

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps 必须大于 0")
        self._interval = 1.0 / self.fps
        self._next_tick = time.monotonic()

    def tick(self) -> None:
        """等待直到下一帧时间点。"""
        now = time.monotonic()
        if now < self._next_tick:
            time.sleep(self._next_tick - now)
        self._next_tick = max(self._next_tick + self._interval, time.monotonic())

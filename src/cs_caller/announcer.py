"""报点播报控制：稳定性过滤 + 冷却。"""

from __future__ import annotations

import time
from dataclasses import dataclass

from cs_caller.tts.base import BaseTTS


@dataclass
class Announcer:
    """在稳定并且不在冷却期时触发 TTS。"""

    tts: BaseTTS
    cooldown_sec: float = 2.0
    stable_frames: int = 3

    def __post_init__(self) -> None:
        if self.stable_frames <= 0:
            raise ValueError("stable_frames 必须大于 0")
        self._candidate: str | None = None
        self._candidate_count = 0
        self._last_announced_at: dict[str, float] = {}

    def process(self, callout: str | None, now: float | None = None) -> str | None:
        """输入当前帧 callout，满足条件则播报并返回文本，否则返回 None。"""
        ts = time.monotonic() if now is None else now

        if callout is None:
            self._candidate = None
            self._candidate_count = 0
            return None

        if callout == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = callout
            self._candidate_count = 1

        if self._candidate_count < self.stable_frames:
            return None

        last_at = self._last_announced_at.get(callout, float("-inf"))
        if ts - last_at < self.cooldown_sec:
            return None

        text = f"敌人可能在 {callout}"
        self.tts.say(text)
        self._last_announced_at[callout] = ts
        return text

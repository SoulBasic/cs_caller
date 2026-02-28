"""控制台 TTS：以打印代替真实语音。"""

from __future__ import annotations

from cs_caller.tts.base import BaseTTS


class ConsoleTTS(BaseTTS):
    def say(self, text: str) -> None:
        print(f"[TTS] {text}")

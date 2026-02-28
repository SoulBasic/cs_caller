"""pyttsx3 TTS 后端实现。"""

from __future__ import annotations

from cs_caller.tts.base import BaseTTS


class Pyttsx3TTS(BaseTTS):
    """使用 pyttsx3 执行离线语音播报。"""

    def __init__(self) -> None:
        import pyttsx3

        self._engine = pyttsx3.init()

    def say(self, text: str) -> None:
        self._engine.say(text)
        self._engine.runAndWait()

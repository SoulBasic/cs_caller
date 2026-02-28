"""TTS 实现集合与工厂函数。"""

from __future__ import annotations

from cs_caller.tts.base import BaseTTS
from cs_caller.tts.console_tts import ConsoleTTS


def create_tts(backend: str = "auto") -> BaseTTS:
    """按 backend 创建 TTS：auto / pyttsx3 / console。"""
    normalized = backend.strip().lower()

    if normalized == "console":
        return ConsoleTTS()

    if normalized in {"auto", "pyttsx3"}:
        try:
            from cs_caller.tts.pyttsx3_tts import Pyttsx3TTS

            return Pyttsx3TTS()
        except Exception as exc:
            if normalized == "pyttsx3":
                raise RuntimeError("pyttsx3 初始化失败") from exc
            return ConsoleTTS()

    raise ValueError(f"未知 tts backend: {backend}")


__all__ = ["BaseTTS", "ConsoleTTS", "create_tts"]

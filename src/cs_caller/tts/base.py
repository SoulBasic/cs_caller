"""TTS 抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTTS(ABC):
    @abstractmethod
    def say(self, text: str) -> None:
        """播报文本。"""

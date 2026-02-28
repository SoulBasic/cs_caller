"""帧源抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class FrameSource(ABC):
    """统一帧源接口。"""

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        """读取一帧 BGR 图像。返回 None 表示结束。"""


class NDISource(FrameSource):
    """NDI 帧源占位实现（TODO）。"""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    def read(self) -> Optional[np.ndarray]:
        raise NotImplementedError("TODO: 接入 NDI SDK 并实现实时取帧")

"""Mock 帧源：重复输出本地图片。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from cs_caller.sources.base import FrameSource


class MockImageSource(FrameSource):
    """反复返回同一张图片，用于离线演示。"""

    def __init__(self, image_path: str | Path) -> None:
        path = Path(image_path)
        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            raise FileNotFoundError(f"无法读取图片: {path}")
        self._frame = frame

    def read(self) -> Optional[np.ndarray]:
        return self._frame.copy()

"""帧源抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import cv2
import numpy as np


class FrameSource(ABC):
    """统一帧源接口。"""

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        """读取一帧 BGR 图像。返回 None 表示结束。"""

    def close(self) -> None:
        """释放资源（默认空实现）。"""


class SourceError(RuntimeError):
    """帧源运行期异常基类。"""


class SourceConnectError(SourceError):
    """连接帧源失败。"""


class SourceReadError(SourceError):
    """读取帧失败。"""


class OpenCVCaptureSource(FrameSource):
    """通用 OpenCV 帧源（摄像头编号/本地视频/网络流）。"""

    def __init__(self, source: str | int) -> None:
        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            raise RuntimeError(f"无法打开视频源: {source}")

    def read(self) -> Optional[np.ndarray]:
        ok, frame = self._cap.read()
        if not ok:
            return None
        return frame

    def close(self) -> None:
        self._cap.release()


def _set_timeout_property(cap: cv2.VideoCapture, prop_name: str, value: float) -> None:
    prop_id = getattr(cv2, prop_name, None)
    if prop_id is not None:
        cap.set(prop_id, float(value))

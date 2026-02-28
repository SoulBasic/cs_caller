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


class NDISource(FrameSource):
    """NDI 帧源（当前通过 OpenCV VideoCapture URL 方式接入）。

    说明：
    - 这是单进程内实现，不拆前后端。
    - 依赖系统已正确安装 NDI Runtime / OpenCV 对应能力。
    - 当 NDI 未就绪时会抛出明确异常，便于 GUI 提示。
    """

    def __init__(self, source_url: str) -> None:
        self.source_url = source_url
        self._cap = cv2.VideoCapture(source_url)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"无法打开 NDI 源: {source_url}，请确认 NDI Runtime 和 source URL"
            )

    def read(self) -> Optional[np.ndarray]:
        ok, frame = self._cap.read()
        if not ok:
            return None
        return frame

    def close(self) -> None:
        self._cap.release()


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

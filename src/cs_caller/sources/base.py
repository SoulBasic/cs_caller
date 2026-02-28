"""帧源抽象。"""

from __future__ import annotations

import time
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


class NDISource(FrameSource):
    """NDI 帧源（当前通过 OpenCV VideoCapture URL 方式接入）。

    说明：
    - 这是单进程内实现，不拆前后端。
    - 依赖系统已正确安装 NDI Runtime / OpenCV 对应能力。
    - 当 NDI 未就绪时会抛出明确异常，便于 GUI 提示。
    """

    def __init__(
        self,
        source_url: str,
        connect_timeout_sec: float = 5.0,
        read_timeout_sec: float = 1.0,
        reconnect_attempts: int = 3,
        reconnect_backoff_sec: float = 0.3,
    ) -> None:
        self.source_url = source_url
        self.connect_timeout_sec = max(0.1, float(connect_timeout_sec))
        self.read_timeout_sec = max(0.1, float(read_timeout_sec))
        self.reconnect_attempts = max(1, int(reconnect_attempts))
        self.reconnect_backoff_sec = max(0.0, float(reconnect_backoff_sec))
        self._cap: cv2.VideoCapture | None = None
        self._connect_with_retry()

    def read(self) -> Optional[np.ndarray]:
        if self._cap is None:
            self._connect_with_retry()

        deadline = time.monotonic() + self.read_timeout_sec
        assert self._cap is not None

        while time.monotonic() < deadline:
            ok, frame = self._cap.read()
            if ok and frame is not None:
                return frame
            time.sleep(0.03)

        last_error = SourceReadError(
            f"读取 NDI 超时（{self.read_timeout_sec:.1f}s）：{self.source_url}"
        )
        if self._reconnect():
            ok, frame = self._cap.read() if self._cap is not None else (False, None)
            if ok and frame is not None:
                return frame

        raise SourceReadError(
            f"NDI 读取失败并且重连未恢复：{self.source_url}。"
            "请检查 OBS NDI 输出是否仍开启、源名称是否变化、网络是否可达。"
        ) from last_error

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _connect_with_retry(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.reconnect_attempts + 1):
            try:
                self._open_capture_once()
                return
            except Exception as exc:
                last_error = exc
                self.close()
                if attempt < self.reconnect_attempts:
                    time.sleep(self.reconnect_backoff_sec)

        raise SourceConnectError(
            f"无法连接 NDI 源：{self.source_url}。"
            "请确认 OBS 已开启 NDI 输出、source 文本正确、并已安装 NDI Runtime。"
        ) from last_error

    def _reconnect(self) -> bool:
        try:
            self._connect_with_retry()
            return True
        except SourceConnectError:
            return False

    def _open_capture_once(self) -> None:
        cap = cv2.VideoCapture(self.source_url)
        _set_timeout_property(cap, "CAP_PROP_OPEN_TIMEOUT_MSEC", self.connect_timeout_sec * 1000)
        _set_timeout_property(cap, "CAP_PROP_READ_TIMEOUT_MSEC", self.read_timeout_sec * 1000)
        if not cap.isOpened():
            cap.release()
            raise SourceConnectError(f"VideoCapture 打开失败：{self.source_url}")
        self._cap = cap


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

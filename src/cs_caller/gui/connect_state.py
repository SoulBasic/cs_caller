"""GUI 连接状态机纯逻辑：用于异步连接流程与单测。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectControls:
    """连接区控件状态。"""

    connect_enabled: bool
    cancel_enabled: bool
    connect_button_text: str


def build_connect_controls(*, connecting: bool, connected: bool) -> ConnectControls:
    """根据连接状态构建按钮展示逻辑。"""

    if connecting:
        return ConnectControls(
            connect_enabled=False,
            cancel_enabled=True,
            connect_button_text="连接中...",
        )
    return ConnectControls(
        connect_enabled=True,
        cancel_enabled=False,
        connect_button_text="重连源" if connected else "连接源",
    )


class ConnectAttemptTracker:
    """跟踪当前活跃连接尝试，屏蔽过期回调。"""

    def __init__(self) -> None:
        self._next_attempt_id = 0
        self._active_attempt_id: int | None = None

    @property
    def is_connecting(self) -> bool:
        return self._active_attempt_id is not None

    @property
    def active_attempt_id(self) -> int | None:
        return self._active_attempt_id

    def start(self) -> int:
        self._next_attempt_id += 1
        self._active_attempt_id = self._next_attempt_id
        return self._active_attempt_id

    def finish(self, attempt_id: int) -> bool:
        """完成尝试；仅活跃尝试可完成。"""

        if self._active_attempt_id != attempt_id:
            return False
        self._active_attempt_id = None
        return True

    def cancel(self) -> int | None:
        """取消活跃尝试。"""

        attempt_id = self._active_attempt_id
        self._active_attempt_id = None
        return attempt_id

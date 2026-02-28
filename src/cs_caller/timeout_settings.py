"""超时相关环境变量解析。"""

from __future__ import annotations

import os
from typing import Mapping


DEFAULT_GUI_CONNECT_TIMEOUT_MS = 10_000
MIN_GUI_CONNECT_TIMEOUT_MS = 3_000
MAX_GUI_CONNECT_TIMEOUT_MS = 30_000


def read_gui_connect_timeout_ms(env: Mapping[str, str] | None = None) -> int:
    """读取 GUI 连接超时配置（毫秒），非法值回退默认值。"""

    source = env if env is not None else os.environ
    raw = source.get("CS_CALLER_CONNECT_TIMEOUT_MS", "").strip()
    if not raw:
        return DEFAULT_GUI_CONNECT_TIMEOUT_MS
    try:
        timeout_ms = int(raw)
    except ValueError:
        return DEFAULT_GUI_CONNECT_TIMEOUT_MS
    if timeout_ms < MIN_GUI_CONNECT_TIMEOUT_MS or timeout_ms > MAX_GUI_CONNECT_TIMEOUT_MS:
        return DEFAULT_GUI_CONNECT_TIMEOUT_MS
    return timeout_ms

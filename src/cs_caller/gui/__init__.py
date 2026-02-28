"""GUI 模块。"""

from __future__ import annotations

from typing import Any


def run_region_editor(*args: Any, **kwargs: Any) -> None:
    from cs_caller.gui.app import run_region_editor as _run_region_editor

    _run_region_editor(*args, **kwargs)

__all__ = ["run_region_editor"]

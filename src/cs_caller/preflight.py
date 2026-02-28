"""运行前预检：依赖可用性与源输入提示。"""

from __future__ import annotations

import ctypes.util
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class PreflightItem:
    """单条预检结果。"""

    key: str
    label: str
    ok: bool
    detail: str
    blocking: bool = False


@dataclass(frozen=True)
class PreflightReport:
    """预检汇总。"""

    mode: str
    source_text: str
    items: tuple[PreflightItem, ...]

    @property
    def hints(self) -> list[str]:
        """提取失败项提示，供 GUI 横幅/说明区展示。"""
        return [item.detail for item in self.items if not item.ok]

    @property
    def has_blocking_error(self) -> bool:
        """是否存在阻断连接的问题。"""
        return any((not item.ok) and item.blocking for item in self.items)


def check_ndi_runtime_available(
    *,
    find_library: Callable[[str], str | None] | None = None,
    path_exists: Callable[[str], bool] = os.path.exists,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """检查系统是否可用 NDI Runtime。

    这是启发式检测：优先查找系统库，再回退到常见安装路径。
    """

    finder = find_library or ctypes.util.find_library
    env_vars = env or dict(os.environ)

    for lib_name in ("ndi", "ndi.6", "ndi.5", "Processing.NDI.Lib.x64"):
        if finder(lib_name):
            return True, "已检测到系统 NDI 库"

    env_paths = [
        env_vars.get("NDI_RUNTIME_DIR_V6", ""),
        env_vars.get("NDI_RUNTIME_DIR_V5", ""),
    ]
    for path in env_paths:
        if path and path_exists(path):
            return True, f"检测到 NDI Runtime 目录: {path}"

    windows_candidates = (
        r"C:\\Program Files\\NDI\\NDI 6 Runtime\\v6\\Processing.NDI.Lib.x64.dll",
        r"C:\\Program Files\\NDI\\NDI 5 Runtime\\v5\\Processing.NDI.Lib.x64.dll",
        r"C:\\Windows\\System32\\Processing.NDI.Lib.x64.dll",
    )
    for dll_path in windows_candidates:
        if path_exists(dll_path):
            return True, f"检测到 NDI 库文件: {dll_path}"

    return False, "未检测到 NDI Runtime（请先安装 NewTek/NDI Runtime）"


def collect_preflight_report(
    mode: str,
    source_text: str,
    *,
    ndi_runtime_checker: Callable[[], tuple[bool, str]] | None = None,
    path_exists: Callable[[Path], bool] = lambda p: p.exists(),
) -> PreflightReport:
    """根据当前模式与输入源生成预检报告。"""

    normalized_mode = (mode or "").strip().lower()
    source = (source_text or "").strip()
    items: list[PreflightItem] = []

    mode_ok = normalized_mode in {"mock", "ndi", "capture"}
    items.append(
        PreflightItem(
            key="mode_valid",
            label="模式合法",
            ok=mode_ok,
            detail="模式可用" if mode_ok else f"未知模式: {mode or '-'}（仅支持 mock/ndi/capture）",
            blocking=True,
        )
    )
    if not mode_ok:
        return PreflightReport(mode=normalized_mode, source_text=source, items=tuple(items))

    has_source = bool(source)
    source_detail_by_mode = {
        "mock": "已填写图片路径" if has_source else "未填写图片路径",
        "ndi": "已填写 NDI 源" if has_source else "未填写 NDI 源（示例: ndi://OBS）",
        "capture": "已填写采集源" if has_source else "未填写 capture 源",
    }
    items.append(
        PreflightItem(
            key="source_present",
            label="源已填写",
            ok=has_source,
            detail=source_detail_by_mode[normalized_mode],
            blocking=True,
        )
    )

    if normalized_mode == "mock":
        if has_source:
            file_exists = path_exists(Path(source))
            items.append(
                PreflightItem(
                    key="mock_path_exists",
                    label="图片路径存在",
                    ok=file_exists,
                    detail="图片路径可访问" if file_exists else f"图片不存在: {source}",
                    blocking=True,
                )
            )

    if normalized_mode == "ndi":
        checker = ndi_runtime_checker or check_ndi_runtime_available
        runtime_ok, runtime_detail = checker()
        items.append(
            PreflightItem(
                key="ndi_runtime",
                label="NDI Runtime",
                ok=runtime_ok,
                detail=runtime_detail,
                blocking=True,
            )
        )
        if has_source:
            ndi_format_ok = source.startswith("ndi://")
            items.append(
                PreflightItem(
                    key="ndi_source_format",
                    label="NDI 源格式",
                    ok=ndi_format_ok,
                    detail="源格式正确" if ndi_format_ok else "建议使用 ndi://<源名>（如 ndi://OBS）",
                    blocking=False,
                )
            )

    if normalized_mode == "capture" and has_source:
        is_int_like = bool(re.fullmatch(r"[+-]?\d+", source))
        index_ok = True
        detail = "使用路径/URL 作为 capture 源"
        if is_int_like:
            value = int(source)
            index_ok = value >= 0
            detail = (
                f"使用摄像头编号: {value}"
                if index_ok
                else "capture 摄像头编号必须是 >= 0 的整数"
            )
        items.append(
            PreflightItem(
                key="capture_index_valid",
                label="capture 编号合法",
                ok=index_ok,
                detail=detail,
                blocking=True,
            )
        )

    return PreflightReport(mode=normalized_mode, source_text=source, items=tuple(items))

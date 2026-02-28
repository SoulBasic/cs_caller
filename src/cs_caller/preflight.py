"""运行前预检：依赖可用性与源输入提示。"""

from __future__ import annotations

import ctypes.util
import importlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

WINDOWS_NDI_BACKEND_INSTALL_GUIDE = (
    "未安装 cyndilib。Windows 免编译安装步骤："
    "1) 进入项目目录并激活虚拟环境：.\\.venv\\Scripts\\Activate.ps1；"
    "2) 升级 pip：python -m pip install --upgrade pip；"
    "3) 安装预编译 NDI 后端：python -m pip install \"cyndilib==0.0.9\"。"
)

WINDOWS_NDI_RUNTIME_INSTALL_GUIDE = (
    "未检测到 NDI Runtime。Windows 安装步骤："
    "1) 打开 https://ndi.video/tools/ndi-core-suite/ 下载并安装 NDI Runtime/Core Suite；"
    "2) 安装后重启终端/GUI；"
    "3) 如仍失败，确认存在目录 C:\\Program Files\\NDI\\NDI 6 Runtime\\v6。"
)


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
    import_module: Callable[[str], Any] = importlib.import_module,
    find_library: Callable[[str], str | None] | None = None,
    path_exists: Callable[[str], bool] = os.path.exists,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """检查系统是否可用 NDI Runtime。

    这是启发式检测：优先查找系统库，再回退到常见安装路径。
    """

    finder = find_library or ctypes.util.find_library
    env_vars = env or dict(os.environ)

    # 优先通过 cyndilib Finder 探测（最接近实际运行可用性）
    try:
        ndi = import_module("cyndilib")
        finder_cls = getattr(ndi, "Finder", None)
        if finder_cls is None:
            finder_mod = getattr(ndi, "finder", None)
            finder_cls = getattr(finder_mod, "Finder", None) if finder_mod is not None else None
        if callable(finder_cls):
            finder = finder_cls()
            open_fn = getattr(finder, "open", None)
            close_fn = getattr(finder, "close", None)
            try:
                if callable(open_fn):
                    opened = open_fn()
                    if opened is False:
                        return False, WINDOWS_NDI_RUNTIME_INSTALL_GUIDE
                return True, "已通过 cyndilib Finder 验证 Runtime 可用"
            finally:
                if callable(close_fn):
                    close_fn()
    except Exception:
        pass

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

    return False, WINDOWS_NDI_RUNTIME_INSTALL_GUIDE


def check_ndi_backend_module_available(
    *,
    import_module: Callable[[str], Any] = importlib.import_module,
) -> tuple[bool, str]:
    """检查 cyndilib 模块可导入。"""

    try:
        import_module("cyndilib")
        return True, "已检测到 cyndilib 模块"
    except Exception:
        return False, WINDOWS_NDI_BACKEND_INSTALL_GUIDE


def check_ndi_python_module_available(
    *,
    import_module: Callable[[str], Any] = importlib.import_module,
) -> tuple[bool, str]:
    """兼容旧调用方：已切换到 cyndilib 检查。"""
    return check_ndi_backend_module_available(import_module=import_module)


def collect_preflight_report(
    mode: str,
    source_text: str,
    *,
    ndi_module_checker: Callable[[], tuple[bool, str]] | None = None,
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
        module_checker = ndi_module_checker or check_ndi_backend_module_available
        module_ok, module_detail = module_checker()
        items.append(
            PreflightItem(
                key="ndi_backend_module",
                label="cyndilib 模块",
                ok=module_ok,
                detail=module_detail,
                blocking=True,
            )
        )

        runtime_checker = ndi_runtime_checker or check_ndi_runtime_available
        runtime_ok, runtime_detail = runtime_checker()
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
            normalized = source[6:].strip() if source.lower().startswith("ndi://") else source
            ndi_format_ok = bool(normalized)
            items.append(
                PreflightItem(
                    key="ndi_source_format",
                    label="NDI 源解析",
                    ok=ndi_format_ok,
                    detail=(
                        f"将按源名匹配: {normalized}"
                        if ndi_format_ok
                        else "源名为空，请填写 OBS / ndi://OBS / 完整源名"
                    ),
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

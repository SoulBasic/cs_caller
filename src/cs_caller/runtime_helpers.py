"""GUI 运行态纯函数：便于单测覆盖。"""

from __future__ import annotations

MODE_LABELS = {
    "mock": "Mock 图片",
    "ndi": "NDI",
    "capture": "Capture",
}


def autofill_source_text(mode: str, source_text: str) -> str:
    """仅在输入为空时按模式回填默认源。"""
    normalized_mode = (mode or "").strip().lower()
    source = (source_text or "").strip()
    if source:
        return source
    if normalized_mode == "ndi":
        return "ndi://OBS"
    if normalized_mode == "capture":
        return "0"
    return ""


def build_operating_mode_hint(
    *,
    source_mode: str,
    source_connected: bool,
    detect_enabled: bool,
) -> str:
    mode = (source_mode or "").strip().lower()
    mode_label = MODE_LABELS.get(mode, mode or "未知模式")
    if not source_connected:
        return f"当前模式: {mode_label} 未连接（待连接）"
    if detect_enabled:
        return f"当前模式: {mode_label} 播报模式（检测+语音）"
    return f"当前模式: {mode_label} 仅预览（检测已关闭）"

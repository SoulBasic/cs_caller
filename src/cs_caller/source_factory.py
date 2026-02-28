"""帧源工厂：统一构建 source 并输出可读错误。"""

from __future__ import annotations

from cs_caller.preflight import check_ndi_python_module_available, check_ndi_runtime_available
from cs_caller.sources.base import FrameSource, OpenCVCaptureSource
from cs_caller.sources.mock_source import MockImageSource
from cs_caller.sources.ndi_native import NDISource


class SourceFactoryError(ValueError):
    """源工厂可预期错误，带错误码便于映射 GUI 提示。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def build_source(mode: str, source_text: str) -> FrameSource:
    """按模式构建帧源，并把常见错误转成清晰中文信息。"""

    normalized_mode = mode.strip().lower()
    source = source_text.strip()

    if normalized_mode not in {"mock", "ndi", "capture"}:
        raise SourceFactoryError(
            code="bad_mode",
            message=f"未知 source mode: {mode}（仅支持 mock/ndi/capture）",
        )

    if normalized_mode == "mock":
        if not source:
            raise SourceFactoryError(
                code="empty_source",
                message="mock 模式需要图片路径（可填 --image 或源输入框）",
            )
        return MockImageSource(source)

    if normalized_mode == "ndi":
        if not source:
            raise SourceFactoryError(
                code="empty_source",
                message="ndi 模式需要源文本（示例: OBS 或 ndi://OBS）",
            )
        module_ok, module_hint = check_ndi_python_module_available()
        if not module_ok:
            raise SourceFactoryError(
                code="ndi_python_missing",
                message=module_hint,
            )
        runtime_ok, runtime_hint = check_ndi_runtime_available()
        if not runtime_ok:
            raise SourceFactoryError(
                code="ndi_runtime_missing",
                message=runtime_hint,
            )
        try:
            return NDISource(source)
        except Exception as exc:
            raise SourceFactoryError(
                code="ndi_connect_failed",
                message=f"NDI 连接失败（{source}）：{exc}",
            ) from exc

    if normalized_mode == "capture":
        if not source:
            raise SourceFactoryError(
                code="empty_source",
                message="capture 模式需要摄像头编号/视频路径/流地址",
            )
        cap_source = parse_capture_source(source)
        try:
            return OpenCVCaptureSource(cap_source)
        except Exception as exc:
            raise SourceFactoryError(
                code="capture_open_failed",
                message=f"无法打开 capture 源（{source}）：{exc}",
            ) from exc

    raise SourceFactoryError(code="bad_mode", message=f"未知 source mode: {mode}")


def parse_capture_source(source: str) -> str | int:
    """解析 capture 输入，允许非负整数编号或路径/URL。"""

    raw = source.strip()
    if raw.lstrip("+-").isdigit():
        value = int(raw)
        if value < 0:
            raise SourceFactoryError(
                code="capture_index_invalid",
                message=f"capture 摄像头编号无效: {value}（必须 >= 0）",
            )
        return value
    return raw


def map_source_factory_error(exc: Exception, *, mode: str) -> str:
    """把工厂错误映射为 GUI 可直接展示的中文提示。"""

    if isinstance(exc, SourceFactoryError):
        prefix_map = {
            "empty_source": "源输入为空",
            "bad_mode": "模式错误",
            "capture_index_invalid": "采集编号错误",
            "ndi_python_missing": "ndi-python 缺失",
            "ndi_runtime_missing": "NDI 运行库缺失",
            "ndi_connect_failed": "NDI 连接失败",
            "capture_open_failed": "采集源打开失败",
        }
        prefix = prefix_map.get(exc.code, "连接失败")
        return f"[{mode}] {prefix}: {exc.message}"
    return f"[{mode}] 连接失败: {exc}"

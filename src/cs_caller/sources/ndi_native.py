"""原生 NDI 帧源（ndi-python/NDIlib）。"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from cs_caller.sources.base import FrameSource, SourceConnectError, SourceReadError


@dataclass(frozen=True)
class NDISourceInfo:
    """发现到的 NDI 源描述。"""

    name: str
    address: str
    raw: Any


@dataclass(frozen=True)
class NDIConnectionErrorDetails:
    """连接失败时用于 GUI 展示的上下文。"""

    requested: str
    normalized: str
    discovered: tuple[NDISourceInfo, ...]

    def format_for_human(self) -> str:
        names = [src.name for src in self.discovered if src.name]
        if not names:
            return (
                f"请求源: {self.requested}（归一化: {self.normalized or '-'}）；"
                "当前未发现任何 NDI 源。"
            )
        return (
            f"请求源: {self.requested}（归一化: {self.normalized or '-'}）；"
            f"当前发现 {len(names)} 个源: {', '.join(names)}"
        )


def normalize_requested_source_text(source_text: str) -> str:
    """归一化用户输入：支持 OBS / ndi://OBS / 全名。"""

    raw = (source_text or "").strip()
    if raw.lower().startswith("ndi://"):
        raw = raw[6:]
    return raw.strip()


def select_best_ndi_source(source_text: str, discovered: list[NDISourceInfo]) -> NDISourceInfo | None:
    """根据用户输入从发现列表中选取最佳匹配。"""

    if not discovered:
        return None

    normalized = normalize_requested_source_text(source_text)
    if not normalized:
        return discovered[0]

    normalized_l = normalized.casefold()

    def _aliases(info: NDISourceInfo) -> list[str]:
        name = (info.name or "").strip()
        if not name:
            return []
        aliases = [name]
        if "(" in name and name.endswith(")"):
            aliases.append(name.split("(", 1)[0].strip())
        if " - " in name:
            aliases.extend(part.strip() for part in name.split(" - ") if part.strip())
        return list(dict.fromkeys(aliases))

    # 1) 精确匹配（忽略大小写）
    for src in discovered:
        for alias in _aliases(src):
            if alias.casefold() == normalized_l:
                return src

    # 2) 包含匹配（忽略大小写）
    for src in discovered:
        for alias in _aliases(src):
            alias_l = alias.casefold()
            if normalized_l in alias_l or alias_l in normalized_l:
                return src

    return None


def _import_ndi_module(import_module: Callable[[str], Any] = importlib.import_module) -> Any:
    """导入 NDIlib 模块。"""

    errors: list[str] = []
    for name in ("NDIlib", "ndi"):
        try:
            return import_module(name)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise SourceConnectError("无法导入 ndi-python 模块（NDIlib）: " + " | ".join(errors))


def _call_first_callable(module: Any, names: tuple[str, ...], *args: Any, **kwargs: Any) -> Any:
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs)
            except TypeError:
                if args or kwargs:
                    continue
                raise
    return None


def discover_ndi_sources(
    ndi_module: Any,
    *,
    timeout_ms: int = 1500,
    wait_rounds: int = 2,
) -> list[NDISourceInfo]:
    """发现当前网络中的 NDI 源。"""

    finder = _create_finder(ndi_module)
    if finder is None:
        raise SourceConnectError("NDIlib 不支持源发现接口（find_create_v2/find_create）")

    wait_fn = getattr(ndi_module, "find_wait_for_sources", None)
    get_fn = getattr(ndi_module, "find_get_current_sources", None)
    destroy_fn = getattr(ndi_module, "find_destroy", None)
    if not callable(get_fn):
        if callable(destroy_fn):
            destroy_fn(finder)
        raise SourceConnectError("NDIlib 缺少 find_get_current_sources 接口")

    try:
        if callable(wait_fn):
            for _ in range(max(1, int(wait_rounds))):
                wait_fn(finder, int(timeout_ms))
        raw_sources = list(get_fn(finder) or [])
    finally:
        if callable(destroy_fn):
            destroy_fn(finder)

    parsed: list[NDISourceInfo] = []
    for src in raw_sources:
        name = _safe_decode(getattr(src, "ndi_name", "")) or _safe_decode(
            getattr(src, "p_ndi_name", "")
        )
        addr = _safe_decode(getattr(src, "url_address", "")) or _safe_decode(
            getattr(src, "p_url_address", "")
        )
        parsed.append(NDISourceInfo(name=name.strip(), address=addr.strip(), raw=src))
    return parsed


def _create_finder(ndi_module: Any) -> Any:
    create_v2 = getattr(ndi_module, "find_create_v2", None)
    if callable(create_v2):
        try:
            return create_v2()
        except TypeError:
            find_cfg = getattr(ndi_module, "FindCreateV2", None)
            if callable(find_cfg):
                return create_v2(find_cfg())

    create_v1 = getattr(ndi_module, "find_create", None)
    if callable(create_v1):
        return create_v1()

    return None


def _safe_decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


class NDISource(FrameSource):
    """原生 NDI 接收源。"""

    def __init__(
        self,
        source_text: str,
        *,
        connect_timeout_ms: int = 1500,
        read_timeout_ms: int = 1000,
        reconnect_attempts: int = 3,
        ndi_module: Any | None = None,
    ) -> None:
        self.source_text = (source_text or "").strip()
        self.normalized_source = normalize_requested_source_text(self.source_text)
        self.connect_timeout_ms = max(200, int(connect_timeout_ms))
        self.read_timeout_ms = max(50, int(read_timeout_ms))
        self.reconnect_attempts = max(1, int(reconnect_attempts))

        self._ndi = ndi_module or _import_ndi_module()
        self._receiver: Any | None = None
        self._active_source: NDISourceInfo | None = None
        self._initialize_ndi()
        self._connect_with_retry()

    def read(self) -> np.ndarray | None:
        if self._receiver is None:
            self._connect_with_retry()

        assert self._receiver is not None
        frame_type, video_frame = self._capture_video_frame()
        frame_type_video = getattr(self._ndi, "FRAME_TYPE_VIDEO", None)

        if frame_type != frame_type_video or video_frame is None:
            raise SourceReadError(
                f"NDI 未返回视频帧（type={frame_type}，源={self.source_text or '-'})"
            )

        return self._copy_video_frame_to_bgr(video_frame)

    def close(self) -> None:
        recv_destroy = getattr(self._ndi, "recv_destroy", None)
        if self._receiver is not None and callable(recv_destroy):
            recv_destroy(self._receiver)
        self._receiver = None

    def _initialize_ndi(self) -> None:
        init = getattr(self._ndi, "initialize", None)
        if callable(init):
            ok = bool(init())
            if not ok:
                raise SourceConnectError("NDI 初始化失败：请确认 NDI Runtime 已安装且可被 Python 进程加载")

    def _connect_with_retry(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.reconnect_attempts + 1):
            try:
                self._connect_once()
                return
            except Exception as exc:
                last_error = exc
                self.close()
                if attempt < self.reconnect_attempts:
                    time.sleep(0.2)

        raise SourceConnectError(f"原生 NDI 连接失败：{last_error}") from last_error

    def _connect_once(self) -> None:
        discovered = discover_ndi_sources(self._ndi, timeout_ms=self.connect_timeout_ms)
        selected = select_best_ndi_source(self.source_text, discovered)
        if selected is None:
            detail = NDIConnectionErrorDetails(
                requested=self.source_text,
                normalized=self.normalized_source,
                discovered=tuple(discovered),
            )
            raise SourceConnectError(f"未匹配到 NDI 源。{detail.format_for_human()}")

        receiver = self._create_receiver()
        if receiver is None:
            raise SourceConnectError("NDI 接收器创建失败（recv_create_v3/recv_create_v2 不可用）")

        connect_fn = getattr(self._ndi, "recv_connect", None)
        if not callable(connect_fn):
            raise SourceConnectError("NDIlib 缺少 recv_connect 接口")
        connect_fn(receiver, selected.raw)

        self._receiver = receiver
        self._active_source = selected

    def _create_receiver(self) -> Any:
        create_v3 = getattr(self._ndi, "recv_create_v3", None)
        recv_create_v3_cfg = getattr(self._ndi, "RecvCreateV3", None)
        if callable(create_v3) and callable(recv_create_v3_cfg):
            cfg = recv_create_v3_cfg()
            color_format = getattr(self._ndi, "RECV_COLOR_FORMAT_BGRX_BGRA", None)
            if color_format is not None and hasattr(cfg, "color_format"):
                setattr(cfg, "color_format", color_format)
            return create_v3(cfg)

        create_v2 = getattr(self._ndi, "recv_create_v2", None)
        if callable(create_v2):
            return create_v2()

        create_v1 = getattr(self._ndi, "recv_create", None)
        if callable(create_v1):
            return create_v1()

        return None

    def _capture_video_frame(self) -> tuple[Any, Any]:
        capture_v3 = getattr(self._ndi, "recv_capture_v3", None)
        capture_v2 = getattr(self._ndi, "recv_capture_v2", None)
        capture_v1 = getattr(self._ndi, "recv_capture", None)

        if callable(capture_v3):
            result = capture_v3(self._receiver, int(self.read_timeout_ms))
        elif callable(capture_v2):
            result = capture_v2(self._receiver, int(self.read_timeout_ms))
        elif callable(capture_v1):
            result = capture_v1(self._receiver, int(self.read_timeout_ms))
        else:
            raise SourceReadError("NDIlib 缺少 recv_capture_v2/recv_capture_v3 接口")

        if not isinstance(result, tuple) or len(result) < 2:
            raise SourceReadError("NDI recv_capture 返回值格式异常")
        return result[0], result[1]

    def _copy_video_frame_to_bgr(self, video_frame: Any) -> np.ndarray:
        try:
            data = getattr(video_frame, "data")
            xres = int(getattr(video_frame, "xres"))
            yres = int(getattr(video_frame, "yres"))
        except Exception as exc:
            raise SourceReadError(f"NDI 视频帧字段缺失: {exc}") from exc

        try:
            if isinstance(data, np.ndarray):
                arr = np.array(data, copy=True)
            else:
                stride = int(getattr(video_frame, "line_stride_in_bytes", xres * 4))
                row_pixels = max(xres, abs(stride) // 4)
                expected = row_pixels * yres * 4
                arr = np.frombuffer(data, dtype=np.uint8, count=expected)
                arr = np.array(arr, copy=True).reshape((yres, row_pixels, 4))

            if arr.ndim != 3 or arr.shape[2] < 3:
                raise SourceReadError(f"NDI 视频帧格式异常: shape={getattr(arr, 'shape', None)}")

            return np.ascontiguousarray(arr[:, :xres, :3])
        except SourceReadError:
            raise
        except Exception as exc:
            raise SourceReadError(f"NDI 视频帧转换失败: {exc}") from exc
        finally:
            _call_first_callable(
                self._ndi,
                ("recv_free_video_v2", "recv_free_video_v3", "recv_free_video"),
                self._receiver,
                video_frame,
            )

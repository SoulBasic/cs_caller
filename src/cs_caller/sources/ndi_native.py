"""原生 NDI 帧源（cyndilib）。"""

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
    """导入 cyndilib 模块。"""

    try:
        return import_module("cyndilib")
    except Exception as exc:
        raise SourceConnectError(f"无法导入 cyndilib 模块: {exc}") from exc


def _resolve_attr(module: Any, dotted_name: str) -> Any:
    current = module
    for part in dotted_name.split("."):
        current = getattr(current, part, None)
        if current is None:
            return None
    return current


def _resolve_first(module: Any, names: tuple[str, ...]) -> Any:
    for name in names:
        value = _resolve_attr(module, name)
        if value is not None:
            return value
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
        raise SourceConnectError("cyndilib 不支持源发现接口（Finder）")

    wait_fn = getattr(finder, "wait_for_sources", None)
    get_names_fn = getattr(finder, "get_source_names", None)
    get_source_fn = getattr(finder, "get_source", None)
    get_sources_fn = getattr(finder, "get_sources", None)
    close_fn = getattr(finder, "close", None)
    try:
        if callable(wait_fn):
            for _ in range(max(1, int(wait_rounds))):
                wait_fn(int(timeout_ms))

        raw_sources: list[Any] = []
        if callable(get_names_fn) and callable(get_source_fn):
            for name in list(get_names_fn() or []):
                try:
                    src = get_source_fn(name)
                except Exception:
                    src = None
                if src is not None:
                    raw_sources.append(src)
        elif callable(get_sources_fn):
            raw_sources = list(get_sources_fn() or [])
        else:
            raise SourceConnectError("cyndilib Finder 缺少 get_source_names/get_source 接口")
    finally:
        if callable(close_fn):
            close_fn()

    parsed: list[NDISourceInfo] = []
    for src in raw_sources:
        name = (
            _safe_decode(getattr(src, "name", ""))
            or _safe_decode(getattr(src, "ndi_name", ""))
            or _safe_decode(getattr(src, "p_ndi_name", ""))
        )
        addr = (
            _safe_decode(getattr(src, "url_address", ""))
            or _safe_decode(getattr(src, "address", ""))
            or _safe_decode(getattr(src, "p_url_address", ""))
        )
        parsed.append(NDISourceInfo(name=name.strip(), address=addr.strip(), raw=src))
    return parsed


def _create_finder(ndi_module: Any) -> Any:
    finder_cls = _resolve_first(ndi_module, ("Finder", "finder.Finder"))
    if not callable(finder_cls):
        return None
    finder = finder_cls()
    open_fn = getattr(finder, "open", None)
    if callable(open_fn):
        try:
            opened = open_fn()
            if opened is False:
                raise SourceConnectError("NDI Finder 初始化失败，请确认 NDI Runtime 已安装")
        except TypeError:
            open_fn(True)
    return finder


def _safe_decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


class NDISource(FrameSource):
    """cyndilib NDI 接收源。"""

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
        self._frame_sync: Any | None = None
        self._active_source: NDISourceInfo | None = None
        self._initialize_ndi()
        self._connect_with_retry()

    def read(self) -> np.ndarray | None:
        if self._receiver is None:
            self._connect_with_retry()

        assert self._receiver is not None
        video_frame = self._capture_video_frame()
        if video_frame is None:
            raise SourceReadError(f"NDI 未返回视频帧（源={self.source_text or '-'}）")
        return self._copy_video_frame_to_bgr(video_frame)

    def close(self) -> None:
        fs_close = getattr(self._frame_sync, "close", None)
        if self._frame_sync is not None and callable(fs_close):
            fs_close()
        self._frame_sync = None

        recv_close = getattr(self._receiver, "close", None)
        if self._receiver is not None and callable(recv_close):
            recv_close()
        self._receiver = None

    def _initialize_ndi(self) -> None:
        init = _resolve_first(self._ndi, ("initialize", "ndi.initialize"))
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
            raise SourceConnectError("NDI 接收器创建失败（Receiver 不可用）")

        set_source_fn = getattr(receiver, "set_source", None)
        if callable(set_source_fn):
            set_source_fn(selected.raw)
        elif hasattr(receiver, "source"):
            setattr(receiver, "source", selected.raw)
        else:
            raise SourceConnectError("cyndilib Receiver 缺少 set_source/source 接口")

        connect_fn = getattr(receiver, "connect", None)
        if callable(connect_fn):
            try:
                connect_fn()
            except TypeError:
                connect_fn(int(self.connect_timeout_ms))

        self._receiver = receiver
        self._frame_sync = self._create_frame_sync(receiver)
        self._active_source = selected

    def _create_receiver(self) -> Any:
        receiver_cls = _resolve_first(self._ndi, ("Receiver", "receiver.Receiver"))
        if not callable(receiver_cls):
            return None
        try:
            return receiver_cls()
        except TypeError:
            # 兼容需要配置对象的版本
            cfg_cls = _resolve_first(self._ndi, ("RecvCreate", "receiver.RecvCreate"))
            if callable(cfg_cls):
                return receiver_cls(cfg_cls())
            raise

    def _create_frame_sync(self, receiver: Any) -> Any | None:
        framesync_cls = _resolve_first(
            self._ndi,
            ("FrameSync", "framesync.FrameSync", "video_frame.FrameSync"),
        )
        if not callable(framesync_cls):
            return None
        try:
            return framesync_cls(receiver)
        except TypeError:
            return None

    def _capture_video_frame(self) -> Any | None:
        if self._frame_sync is not None:
            capture_video = getattr(self._frame_sync, "capture_video", None)
            if callable(capture_video):
                try:
                    result = capture_video()
                except TypeError:
                    result = capture_video(int(self.read_timeout_ms))
                if result is False:
                    return None
                if result not in (None, True):
                    return result
            frame = getattr(self._frame_sync, "video_frame", None)
            if frame is not None:
                return frame

        capture_names = ("capture_video", "receive_video", "recv_capture")
        for name in capture_names:
            fn = getattr(self._receiver, name, None)
            if not callable(fn):
                continue
            try:
                result = fn(int(self.read_timeout_ms))
            except TypeError:
                result = fn()

            if isinstance(result, tuple):
                if len(result) >= 2:
                    return result[1]
                return None
            if result is False:
                return None
            if result is True:
                return getattr(self._receiver, "video_frame", None)
            return result

        raise SourceReadError("cyndilib 缺少可用的视频帧采集接口")

    def _copy_video_frame_to_bgr(self, video_frame: Any) -> np.ndarray:
        arr = _extract_frame_array(video_frame)
        try:
            if arr.ndim == 2:
                arr = np.repeat(arr[:, :, None], 3, axis=2)
            if arr.ndim != 3:
                raise SourceReadError(f"NDI 视频帧格式异常: shape={getattr(arr, 'shape', None)}")
            if arr.shape[2] == 4:
                arr = arr[:, :, :3]
            if arr.shape[2] < 3:
                raise SourceReadError(f"NDI 视频帧通道异常: shape={arr.shape}")
            return np.ascontiguousarray(arr[:, :, :3])
        except SourceReadError:
            raise
        except Exception as exc:
            raise SourceReadError(f"NDI 视频帧转换失败: {exc}") from exc


def _extract_frame_array(video_frame: Any) -> np.ndarray:
    if isinstance(video_frame, np.ndarray):
        return np.array(video_frame, copy=True)

    for name in ("as_ndarray", "to_numpy", "get_array"):
        fn = getattr(video_frame, name, None)
        if callable(fn):
            arr = fn()
            if isinstance(arr, np.ndarray):
                return np.array(arr, copy=True)

    xres = int(getattr(video_frame, "xres", getattr(video_frame, "width", 0)))
    yres = int(getattr(video_frame, "yres", getattr(video_frame, "height", 0)))
    if xres <= 0 or yres <= 0:
        raise SourceReadError("NDI 视频帧尺寸缺失")

    data = getattr(video_frame, "data", video_frame)
    stride = int(getattr(video_frame, "line_stride_in_bytes", xres * 4))
    channels = 4 if abs(stride) >= (xres * 4) else 3
    row_pixels = max(xres, abs(stride) // max(channels, 1))
    expected = row_pixels * yres * channels
    try:
        view = memoryview(data)
    except TypeError as exc:
        raise SourceReadError(f"NDI 视频帧不可读: {exc}") from exc

    arr = np.frombuffer(view, dtype=np.uint8, count=expected)
    arr = np.array(arr, copy=True).reshape((yres, row_pixels, channels))
    return arr[:, :xres, :]

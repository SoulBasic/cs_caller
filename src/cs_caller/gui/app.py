"""可视化地图区域编辑器。"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

import cv2
import numpy as np

from cs_caller.announcer import Announcer
from cs_caller.app_settings import AppSettings, AppSettingsStore
from cs_caller.callout_mapper import CalloutMapper, Region
from cs_caller.detector import RedDotDetector
from cs_caller.map_config_store import MapConfig, MapConfigStore
from cs_caller.preflight import PreflightReport, collect_preflight_report
from cs_caller.region_editor import build_rect_region, normalize_rect, polygon_to_rect
from cs_caller.runtime_helpers import autofill_source_text, build_operating_mode_hint
from cs_caller.source_factory import build_source, map_source_factory_error
from cs_caller.timeout_settings import read_gui_connect_timeout_ms
from cs_caller.gui.connect_state import ConnectAttemptTracker, build_connect_controls
from cs_caller.sources.base import (
    FrameSource,
    SourceConnectError,
    SourceError,
    SourceReadError,
)
from cs_caller.tts import create_tts


class _ConnectCancelledError(RuntimeError):
    """连接任务被取消或已超时。"""


class RegionEditorApp:
    """实时帧预览 + 矩形区域编辑 + 运行时检测预览。"""

    def __init__(
        self,
        store: MapConfigStore,
        settings_store: AppSettingsStore,
        initial_map: str = "default",
        initial_source_mode: str = "mock",
        initial_source_text: str = "",
        fps: float = 16.0,
        tts_backend: str = "auto",
        initial_detect_enabled: bool = False,
    ) -> None:
        self.store = store
        self.settings_store = settings_store
        self.target_fps = max(1.0, fps)

        self.root = tk.Tk()
        self.root.title("CS Caller 地图区域编辑器")
        self.root.geometry("1240x860")

        self.map_name_var = tk.StringVar(value=initial_map)
        self.status_var = tk.StringVar(value="就绪")
        self.detect_var = tk.BooleanVar(value=initial_detect_enabled)

        self.source_mode_var = tk.StringVar(value=initial_source_mode)
        self.source_text_var = tk.StringVar(value=initial_source_text)
        self.source_status_var = tk.StringVar(value="未连接（请填写源并点击连接）")
        self.source_button_text_var = tk.StringVar(value="连接源")
        self.error_banner_var = tk.StringVar(value="")
        self.preflight_var = tk.StringVar(value="预检: 待检查")
        self.quick_step_obs_var = tk.StringVar(value="1. OBS 开 NDI: 待检查")
        self.quick_step_source_var = tk.StringVar(value="2. 输入源: 待检查")
        self.quick_step_connect_var = tk.StringVar(value="3. 点击连接: 待连接")
        self.operating_mode_var = tk.StringVar(value="当前模式: 未连接（待连接）")
        self.tts_backend_var = tk.StringVar(value=tts_backend)

        self._regions: list[Region] = []
        self._source: FrameSource | None = None
        self._frame: Optional[np.ndarray] = None
        self._photo: Optional[tk.PhotoImage] = None
        self._image_id: Optional[int] = None
        self._detector = RedDotDetector()
        self._announcer = Announcer(tts=create_tts(tts_backend), stable_frames=2)

        self._drag_start: tuple[float, float] | None = None
        self._draft_rect_id: Optional[int] = None
        self._last_detect_point: tuple[int, int] | None = None
        self._last_callout: str | None = None
        self._consecutive_read_failures = 0
        self._read_failure_disconnect_threshold = 3
        self._last_connect_error: str = ""
        self._preflight_report: PreflightReport | None = None
        self._connect_tracker = ConnectAttemptTracker()
        self._connect_cancel_event: threading.Event | None = None
        self._connect_future: Future[FrameSource] | None = None
        self._connect_enable_detect_on_success = False
        self._connect_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="source-connect")
        self._connect_timeout_ms = read_gui_connect_timeout_ms()
        self._is_closing = False

        self._build_layout()
        self.source_text_var.trace_add("write", self._on_source_text_change)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_map_list()
        self._try_load(initial_map)
        self._on_source_mode_change(None)
        if self.source_text_var.get().strip():
            self._connect_source(auto=True)

    def _on_close(self) -> None:
        self._is_closing = True
        self._cancel_connect(show_status=False)
        self._close_source()
        self._persist_settings()
        self._connect_executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="地图:").pack(side=tk.LEFT)
        self.map_combo = ttk.Combobox(top, textvariable=self.map_name_var, width=24)
        self.map_combo.pack(side=tk.LEFT, padx=(4, 8))

        ttk.Button(top, text="新建", command=self._new_map).pack(side=tk.LEFT)
        ttk.Button(top, text="载入", command=self._load_map).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(top, text="保存", command=self._save_map).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Checkbutton(
            top,
            text="运行检测并播报",
            variable=self.detect_var,
            command=self._toggle_detect,
        ).pack(side=tk.LEFT, padx=(16, 0))

        ttk.Button(top, text="清空区域", command=self._clear_regions).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(top, text="TTS:").pack(side=tk.LEFT, padx=(18, 4))
        tts_combo = ttk.Combobox(
            top,
            textvariable=self.tts_backend_var,
            values=["auto", "pyttsx3", "console"],
            width=10,
            state="readonly",
        )
        tts_combo.pack(side=tk.LEFT)
        tts_combo.bind("<<ComboboxSelected>>", self._on_tts_backend_change)

        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT)

        source_frame = ttk.LabelFrame(self.root, text="视频源连接", padding=8)
        source_frame.pack(fill=tk.X, padx=8, pady=(0, 6))

        ttk.Label(source_frame, text="模式:").pack(side=tk.LEFT)
        source_mode_combo = ttk.Combobox(
            source_frame,
            textvariable=self.source_mode_var,
            values=["mock", "ndi", "capture"],
            width=10,
            state="readonly",
        )
        source_mode_combo.pack(side=tk.LEFT, padx=(4, 10))
        source_mode_combo.bind("<<ComboboxSelected>>", self._on_source_mode_change)

        ttk.Label(source_frame, text="源:").pack(side=tk.LEFT)
        self.source_entry = ttk.Entry(source_frame, textvariable=self.source_text_var, width=48)
        self.source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))
        self.source_entry.bind("<Return>", self._on_source_entry_enter)

        self.connect_button = ttk.Button(
            source_frame,
            textvariable=self.source_button_text_var,
            command=self._connect_source,
        )
        self.connect_button.pack(side=tk.LEFT)
        self.cancel_connect_button = ttk.Button(
            source_frame,
            text="取消连接",
            command=self._cancel_connect,
            state=tk.DISABLED,
        )
        self.cancel_connect_button.pack(side=tk.LEFT, padx=(6, 0))
        self.connect_and_start_button = ttk.Button(
            source_frame,
            text="连接并开始播报",
            command=self._connect_and_start_detect,
        )
        self.connect_and_start_button.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(source_frame, textvariable=self.source_status_var).pack(side=tk.LEFT, padx=(12, 0))

        quick_start = ttk.LabelFrame(self.root, text="快速开始（单进程 OBS-NDI）", padding=8)
        quick_start.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Label(quick_start, textvariable=self.quick_step_obs_var).pack(anchor=tk.W)
        ttk.Label(quick_start, textvariable=self.quick_step_source_var).pack(anchor=tk.W)
        ttk.Label(quick_start, textvariable=self.quick_step_connect_var).pack(anchor=tk.W)
        ttk.Label(quick_start, textvariable=self.preflight_var, foreground="#37474f").pack(
            anchor=tk.W, pady=(4, 0)
        )
        action_row = ttk.Frame(quick_start)
        action_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(action_row, text="保存并开始播报", command=self._save_and_start_detect).pack(
            side=tk.LEFT
        )
        ttk.Button(action_row, text="仅预览", command=self._switch_to_preview_mode).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Label(action_row, textvariable=self.operating_mode_var, foreground="#455a64").pack(
            side=tk.RIGHT
        )

        self.error_banner = tk.Label(
            self.root,
            textvariable=self.error_banner_var,
            anchor=tk.W,
            fg="#b00020",
            bg="#ffe7eb",
            padx=8,
            pady=4,
        )
        self.error_banner.pack(fill=tk.X, padx=8)
        self.error_banner.pack_forget()

        center = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        center.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, bg="#1e1e1e", highlightthickness=1)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        side = ttk.Frame(center, width=280)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        side.pack_propagate(False)

        ttk.Label(side, text="区域列表").pack(anchor=tk.W)
        self.region_list = tk.Listbox(side, height=25)
        self.region_list.pack(fill=tk.BOTH, expand=True, pady=(6, 8))

        ttk.Button(side, text="删除选中区域", command=self._delete_selected_region).pack(
            fill=tk.X
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self._apply_connect_controls()

    def run(self) -> None:
        self._tick_frame()
        self.root.mainloop()

    def _tick_frame(self) -> None:
        frame = self._safe_read_frame()
        if frame is not None:
            self._frame = frame
            self._show_frame(frame)
            self._run_detection_if_enabled(frame)
            self._draw_overlays()

        interval_ms = int(1000 / self.target_fps)
        self.root.after(interval_ms, self._tick_frame)

    def _safe_read_frame(self) -> Optional[np.ndarray]:
        if self._source is None:
            return None

        try:
            frame = self._source.read()
        except SourceConnectError as exc:
            self._handle_source_error(str(exc))
            return None
        except (SourceReadError, SourceError) as exc:
            self._handle_source_read_failure(str(exc))
            return None
        except Exception as exc:  # pragma: no cover - 最后兜底
            self._handle_source_error(f"源读取出现未预期错误: {exc}")
            return None

        if frame is None:
            self._handle_source_read_failure("当前源未返回帧")
            return None
        self._consecutive_read_failures = 0
        self._clear_error_banner()
        return frame

    def _show_frame(self, frame: np.ndarray) -> None:
        photo = _bgr_to_photoimage(frame)
        self._photo = photo

        h, w = frame.shape[:2]
        self.canvas.config(width=w, height=h)
        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=photo)

    def _run_detection_if_enabled(self, frame: np.ndarray) -> None:
        self._last_detect_point = None
        self._last_callout = None

        if not self.detect_var.get():
            return

        point = self._detector.detect(frame)
        if point is None:
            return

        self._last_detect_point = point
        mapper = CalloutMapper(self._regions)
        callout = mapper.map_point((float(point[0]), float(point[1])))
        self._last_callout = callout
        self._announcer.process(callout)

    def _draw_overlays(self) -> None:
        self.canvas.delete("overlay")

        for region in self._regions:
            rect = polygon_to_rect(region.polygon)
            if rect is None:
                continue
            self.canvas.create_rectangle(
                rect.x1,
                rect.y1,
                rect.x2,
                rect.y2,
                outline="#00e676",
                width=2,
                tags="overlay",
            )
            self.canvas.create_text(
                rect.x1 + 4,
                rect.y1 + 4,
                text=region.name,
                anchor=tk.NW,
                fill="#00e676",
                tags="overlay",
            )

        if self._last_detect_point is not None:
            x, y = self._last_detect_point
            self.canvas.create_oval(
                x - 6,
                y - 6,
                x + 6,
                y + 6,
                outline="#ff5252",
                width=2,
                tags="overlay",
            )

        if self._last_callout:
            self.canvas.create_text(
                8,
                8,
                text=f"检测到: {self._last_callout}",
                anchor=tk.NW,
                fill="#ffeb3b",
                tags="overlay",
            )

    def _toggle_detect(self) -> None:
        self._set_detect_enabled(self.detect_var.get(), persist=True)

    def _on_press(self, event: tk.Event[tk.Misc]) -> None:
        self._drag_start = (float(event.x), float(event.y))
        if self._draft_rect_id is not None:
            self.canvas.delete(self._draft_rect_id)
            self._draft_rect_id = None

    def _on_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_start is None:
            return
        x1, y1 = self._drag_start
        x2, y2 = float(event.x), float(event.y)

        if self._draft_rect_id is None:
            self._draft_rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline="#40c4ff",
                width=2,
            )
        else:
            self.canvas.coords(self._draft_rect_id, x1, y1, x2, y2)

    def _on_release(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_start is None:
            return

        x1, y1 = self._drag_start
        x2, y2 = float(event.x), float(event.y)
        self._drag_start = None

        if self._draft_rect_id is not None:
            self.canvas.delete(self._draft_rect_id)
            self._draft_rect_id = None

        rect = normalize_rect(x1, y1, x2, y2)
        if rect.x2 - rect.x1 < 3 or rect.y2 - rect.y1 < 3:
            return

        name = simpledialog.askstring("区域名称", "输入 callout 文本:", parent=self.root)
        if name is None:
            self.status_var.set("已取消添加区域")
            return

        region_name = name.strip()
        if not region_name:
            messagebox.showwarning("输入错误", "区域名称不能为空")
            return

        self._regions.append(build_rect_region(region_name, rect.x1, rect.y1, rect.x2, rect.y2))
        self._refresh_region_list()
        self._draw_overlays()
        self.status_var.set(f"已添加区域: {region_name}")

    def _refresh_region_list(self) -> None:
        self.region_list.delete(0, tk.END)
        for i, region in enumerate(self._regions, start=1):
            self.region_list.insert(tk.END, f"{i}. {region.name}")

    def _delete_selected_region(self) -> None:
        selected = self.region_list.curselection()
        if not selected:
            return
        idx = selected[0]
        removed = self._regions.pop(idx)
        self._refresh_region_list()
        self._draw_overlays()
        self.status_var.set(f"已删除区域: {removed.name}")

    def _clear_regions(self) -> None:
        if not self._regions:
            return
        if not messagebox.askyesno("确认", "确定清空当前地图全部区域？"):
            return
        self._regions.clear()
        self._refresh_region_list()
        self._draw_overlays()
        self.status_var.set("已清空区域")

    def _new_map(self) -> None:
        map_name = simpledialog.askstring("新建地图", "输入地图名（如 de_inferno）:", parent=self.root)
        if map_name is None:
            return
        name = map_name.strip()
        if not name:
            messagebox.showwarning("输入错误", "地图名不能为空")
            return
        self.map_name_var.set(name)
        self._regions = []
        self._refresh_region_list()
        self._draw_overlays()
        self.status_var.set(f"新建地图: {name}")
        self._persist_settings()

    def _load_map(self) -> None:
        self._try_load(self.map_name_var.get())

    def _try_load(self, map_name: str) -> None:
        name = map_name.strip()
        if not name:
            return
        try:
            config = self.store.load(name)
        except FileNotFoundError:
            self._regions = []
            self._refresh_region_list()
            self._draw_overlays()
            self.status_var.set(f"未找到地图 {name}，已进入空白编辑")
            self._persist_settings()
            return

        self.map_name_var.set(config.map_name)
        self._regions = list(config.regions)
        self._refresh_region_list()
        self._draw_overlays()
        self.status_var.set(f"已加载地图: {config.map_name}")
        self._persist_settings()

    def _save_map(self) -> bool:
        name = self.map_name_var.get().strip()
        if not name:
            messagebox.showwarning("输入错误", "地图名不能为空")
            return False
        path = self.store.save(MapConfig(map_name=name, regions=list(self._regions)))
        self.status_var.set(f"已保存: {path}")
        self._refresh_map_list()
        self._persist_settings()
        return True

    def _save_and_start_detect(self) -> None:
        if not self._save_map():
            return
        self._connect_source(enable_detect_on_success=True)

    def _switch_to_preview_mode(self) -> None:
        self._set_detect_enabled(False, persist=True)

    def _connect_and_start_detect(self) -> None:
        self._connect_source(enable_detect_on_success=True)

    def _refresh_map_list(self) -> None:
        names = self.store.list_map_names()
        self.map_combo["values"] = names

    def _on_tts_backend_change(self, _: tk.Event[tk.Misc]) -> None:
        backend = self.tts_backend_var.get().strip().lower()
        if backend not in {"auto", "pyttsx3", "console"}:
            self._show_error_banner(f"未知 TTS 后端: {backend}")
            return
        try:
            self._announcer = Announcer(tts=create_tts(backend), stable_frames=2)
        except Exception as exc:
            self._show_error_banner(f"TTS 切换失败: {exc}")
            return
        self.status_var.set(f"已切换 TTS: {backend}")
        self._clear_error_banner()
        self._persist_settings()

    def _on_source_mode_change(self, _: tk.Event[tk.Misc] | None) -> None:
        mode = self.source_mode_var.get().strip().lower() or "mock"
        if mode not in {"mock", "ndi", "capture"}:
            mode = "mock"
            self.source_mode_var.set(mode)
        self._cancel_connect(show_status=False)
        self._close_source()
        self._apply_source_autofill(mode)
        self.source_status_var.set(f"未连接（当前模式: {mode}）")
        self.status_var.set("已切换源模式，点击“连接源”后生效")
        self._clear_error_banner()
        self._last_connect_error = ""
        self._apply_connect_controls()
        self._refresh_preflight_and_quickstart()
        self._update_operating_mode_hint()
        self._persist_settings()

    def _on_source_entry_enter(self, _: tk.Event[tk.Misc]) -> None:
        self._connect_source()

    def _on_source_text_change(self, *_: object) -> None:
        self._refresh_preflight_and_quickstart()

    def _connect_source(self, auto: bool = False, enable_detect_on_success: bool = False) -> None:
        if self._connect_tracker.is_connecting:
            return

        mode = self.source_mode_var.get().strip().lower()
        source_text = self._apply_source_autofill(mode)

        self._close_source()
        if auto and not source_text:
            self.source_status_var.set(f"未连接（当前模式: {mode}）")
            self.status_var.set("编辑器已就绪，可在下方输入源并连接")
            self._apply_connect_controls()
            self._update_operating_mode_hint()
            return

        self._connect_enable_detect_on_success = enable_detect_on_success
        attempt_id = self._connect_tracker.start()
        cancel_event = threading.Event()
        self._connect_cancel_event = cancel_event
        self._connect_future = self._connect_executor.submit(
            self._connect_source_worker,
            mode,
            source_text,
            cancel_event,
        )
        self._connect_future.add_done_callback(
            lambda fut, token=attempt_id: self.root.after(0, self._on_connect_done, token, fut)
        )
        self.root.after(self._connect_timeout_ms, lambda token=attempt_id: self._on_connect_timeout(token))
        self.source_status_var.set(
            f"连接中...（超时 {self._connect_timeout_ms / 1000.0:.1f}s）"
        )
        self._clear_error_banner()
        self._apply_connect_controls()
        self._refresh_preflight_and_quickstart()
        self._update_operating_mode_hint()
        if auto:
            self.status_var.set("正在自动连接源...")
        else:
            self.status_var.set("正在连接源，可继续编辑区域")
        self._persist_settings()

    def _cancel_connect(self, show_status: bool = True) -> None:
        attempt_id = self._connect_tracker.cancel()
        if attempt_id is None:
            return
        if self._connect_cancel_event is not None:
            self._connect_cancel_event.set()
        self._connect_cancel_event = None
        self._connect_future = None
        self._connect_enable_detect_on_success = False
        self.source_status_var.set("连接已取消")
        self._last_connect_error = "连接已取消"
        self._show_error_banner("连接已取消，可修改源后重试")
        self._apply_connect_controls()
        self._refresh_preflight_and_quickstart()
        self._update_operating_mode_hint()
        if show_status:
            self.status_var.set("已取消连接，可立即重试")
        self._persist_settings()

    def _connect_source_worker(
        self,
        mode: str,
        source_text: str,
        cancel_event: threading.Event,
    ) -> FrameSource:
        if cancel_event.is_set():
            raise _ConnectCancelledError("connect cancelled before start")
        source = build_source(mode, source_text)
        if cancel_event.is_set():
            close = getattr(source, "close", None)
            if callable(close):
                close()
            raise _ConnectCancelledError("connect cancelled after source opened")
        return source

    def _on_connect_timeout(self, attempt_id: int) -> None:
        if not self._connect_tracker.finish(attempt_id):
            return
        if self._connect_cancel_event is not None:
            self._connect_cancel_event.set()
        self._connect_cancel_event = None
        self._connect_future = None
        self._connect_enable_detect_on_success = False
        timeout_s = self._connect_timeout_ms / 1000.0
        message = f"连接超时（{self._connect_timeout_ms}ms / {timeout_s:.1f}s），请确认 OBS/NDI 源在线后重试"
        self.source_status_var.set(f"连接超时（{timeout_s:.1f}s）")
        self._last_connect_error = message
        self._show_error_banner(message)
        self.status_var.set(f"连接超时（{timeout_s:.1f}s），编辑器仍可继续使用")
        self._apply_connect_controls()
        self._refresh_preflight_and_quickstart()
        self._update_operating_mode_hint()
        self._persist_settings()

    def _on_connect_done(self, attempt_id: int, future: Future[FrameSource]) -> None:
        if self._is_closing:
            try:
                source = future.result()
            except Exception:
                return
            close = getattr(source, "close", None)
            if callable(close):
                close()
            return

        active = self._connect_tracker.finish(attempt_id)
        self._connect_future = None
        self._connect_cancel_event = None
        try:
            source = future.result()
        except _ConnectCancelledError:
            self._apply_connect_controls()
            return
        except Exception as exc:
            if not active:
                return
            self._source = None
            self.source_status_var.set("连接失败")
            message = map_source_factory_error(exc, mode=self.source_mode_var.get().strip().lower())
            self._last_connect_error = message
            self._show_error_banner(message)
            self._refresh_preflight_and_quickstart()
            self._update_operating_mode_hint()
            self._persist_settings()
            self.status_var.set("源连接失败，请修正参数后重试")
            self._apply_connect_controls()
            return

        if not active:
            close = getattr(source, "close", None)
            if callable(close):
                close()
            self._apply_connect_controls()
            return

        self._source = source
        self._consecutive_read_failures = 0
        self._last_connect_error = ""
        mode = self.source_mode_var.get().strip().lower()
        source_text = self.source_text_var.get().strip()
        self.source_status_var.set(f"已连接: {mode} / {source_text or '-'}")
        self._clear_error_banner()
        if self._connect_enable_detect_on_success or self.detect_var.get():
            self._set_detect_enabled(True, persist=False)
        else:
            self.status_var.set("源连接成功")
        self._connect_enable_detect_on_success = False
        self._apply_connect_controls()
        self._refresh_preflight_and_quickstart()
        self._update_operating_mode_hint()
        self._persist_settings()

    def _close_source(self) -> None:
        if self._source is None:
            return
        close = getattr(self._source, "close", None)
        if callable(close):
            close()
        self._source = None
        self._consecutive_read_failures = 0

    def _handle_source_read_failure(self, message: str) -> None:
        self._consecutive_read_failures += 1
        attempt = self._consecutive_read_failures
        threshold = self._read_failure_disconnect_threshold
        if attempt >= threshold:
            self._handle_source_error(f"{message}；连续失败 {attempt} 次，已自动断开，请点击“重连源”")
            return

        self.source_status_var.set(f"读取异常（{attempt}/{threshold}）")
        self._show_error_banner(f"{message}；可先重连或切换源模式")
        self.status_var.set("源读取异常，编辑器仍可继续操作")
        self._apply_connect_controls()
        self._update_operating_mode_hint()

    def _handle_source_error(self, message: str) -> None:
        self._cancel_connect(show_status=False)
        self._close_source()
        self.source_status_var.set("已断开")
        self._last_connect_error = message
        self._show_error_banner(message)
        self.status_var.set("源不可用，可切换到 mock 并重连")
        self._apply_connect_controls()
        self._refresh_preflight_and_quickstart()
        self._update_operating_mode_hint()
        self._persist_settings()

    def _refresh_preflight_and_quickstart(self) -> None:
        mode = self.source_mode_var.get().strip().lower()
        source_text = self.source_text_var.get().strip()
        report = collect_preflight_report(mode, source_text)
        self._preflight_report = report

        hints = report.hints
        if hints:
            self.preflight_var.set(f"预检: {hints[0]}")
        else:
            self.preflight_var.set("预检: 通过")

        if mode == "ndi":
            ndi_module_item = next((it for it in report.items if it.key == "ndi_backend_module"), None)
            ndi_runtime_item = next((it for it in report.items if it.key == "ndi_runtime"), None)
            if self._source is not None:
                self.quick_step_obs_var.set("1. OBS 开 NDI: 已完成")
            elif ndi_module_item is not None and not ndi_module_item.ok:
                self.quick_step_obs_var.set("1. OBS 开 NDI: 未完成（cyndilib 未安装）")
            elif ndi_runtime_item is not None and not ndi_runtime_item.ok:
                self.quick_step_obs_var.set("1. OBS 开 NDI: 未完成（NDI Runtime 缺失）")
            else:
                self.quick_step_obs_var.set("1. OBS 开 NDI: 待完成（OBS 工具 -> NDI 输出设置）")
        else:
            self.quick_step_obs_var.set("1. OBS 开 NDI: 当前模式可跳过")

        source_item = next((it for it in report.items if it.key == "source_present"), None)
        source_ok = bool(source_item and source_item.ok)
        capture_item = next((it for it in report.items if it.key == "capture_index_valid"), None)
        capture_ok = capture_item is None or capture_item.ok
        if source_ok and capture_ok:
            self.quick_step_source_var.set("2. 输入源: 已完成")
        else:
            detail = source_item.detail if source_item is not None else "请填写源"
            self.quick_step_source_var.set(f"2. 输入源: 未完成（{detail}）")

        if self._source is not None:
            self.quick_step_connect_var.set("3. 点击连接: 已完成")
        elif self._last_connect_error:
            self.quick_step_connect_var.set(f"3. 点击连接: 失败（{self._last_connect_error}）")
        else:
            self.quick_step_connect_var.set("3. 点击连接: 待执行")

    def _apply_source_autofill(self, mode: str) -> str:
        source_text = self.source_text_var.get()
        filled = autofill_source_text(mode, source_text)
        if filled != source_text:
            self.source_text_var.set(filled)
        return filled

    def _set_detect_enabled(self, enabled: bool, *, persist: bool) -> None:
        self.detect_var.set(enabled)
        if enabled:
            self.status_var.set("运行检测中（红点映射将触发语音播报）")
        else:
            self.status_var.set("仅预览模式（检测已关闭）")
        self._update_operating_mode_hint()
        if persist:
            self._persist_settings()

    def _apply_connect_controls(self) -> None:
        controls = build_connect_controls(
            connecting=self._connect_tracker.is_connecting,
            connected=self._source is not None,
        )
        self.source_button_text_var.set(controls.connect_button_text)
        self.connect_button.config(
            state=tk.NORMAL if controls.connect_enabled else tk.DISABLED
        )
        self.cancel_connect_button.config(
            state=tk.NORMAL if controls.cancel_enabled else tk.DISABLED
        )
        self.connect_and_start_button.config(
            state=tk.DISABLED if self._connect_tracker.is_connecting else tk.NORMAL
        )

    def _update_operating_mode_hint(self) -> None:
        self.operating_mode_var.set(
            build_operating_mode_hint(
                source_mode=self.source_mode_var.get(),
                source_connected=self._source is not None,
                detect_enabled=self.detect_var.get(),
            )
        )

    def _show_error_banner(self, message: str) -> None:
        self.error_banner_var.set(message)
        self.error_banner.pack(fill=tk.X, padx=8)

    def _clear_error_banner(self) -> None:
        self.error_banner_var.set("")
        self.error_banner.pack_forget()

    def _persist_settings(self) -> None:
        settings = AppSettings(
            map_name=self.map_name_var.get().strip() or "de_dust2",
            source_mode=self.source_mode_var.get().strip().lower() or "mock",
            source=self.source_text_var.get().strip(),
            tts_backend=self.tts_backend_var.get().strip().lower() or "auto",
            detect_enabled=self.detect_var.get(),
        )
        self.settings_store.save(settings)


def _bgr_to_photoimage(frame: np.ndarray) -> tk.PhotoImage:
    """将 OpenCV BGR 帧转为 Tk PhotoImage（PPM 内存格式）。"""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    header = f"P6\n{w} {h}\n255\n".encode("ascii")
    data = header + rgb.tobytes()
    return tk.PhotoImage(data=data, format="PPM")


def run_region_editor(
    maps_dir: str,
    map_name: str,
    fps: float,
    source_mode: str,
    source_text: str,
    tts_backend: str = "auto",
    detect_enabled: bool = False,
    settings_path: str = "config/app_settings.yaml",
) -> None:
    """启动可视化区域编辑器。"""
    store = MapConfigStore(maps_dir)
    settings_store = AppSettingsStore(settings_path)
    app = RegionEditorApp(
        store=store,
        settings_store=settings_store,
        initial_map=map_name,
        initial_source_mode=source_mode,
        initial_source_text=source_text,
        fps=fps,
        tts_backend=tts_backend,
        initial_detect_enabled=detect_enabled,
    )
    app.run()

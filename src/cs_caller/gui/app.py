"""可视化地图区域编辑器。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

import cv2
import numpy as np

from cs_caller.announcer import Announcer
from cs_caller.callout_mapper import CalloutMapper, Region
from cs_caller.detector import RedDotDetector
from cs_caller.map_config_store import MapConfig, MapConfigStore
from cs_caller.region_editor import build_rect_region, normalize_rect, polygon_to_rect
from cs_caller.sources.base import FrameSource
from cs_caller.tts import create_tts


class RegionEditorApp:
    """实时帧预览 + 矩形区域编辑 + 运行时检测预览。"""

    def __init__(
        self,
        source: FrameSource,
        store: MapConfigStore,
        initial_map: str = "default",
        fps: float = 16.0,
        tts_backend: str = "auto",
    ) -> None:
        self.source = source
        self.store = store
        self.target_fps = max(1.0, fps)

        self.root = tk.Tk()
        self.root.title("CS Caller 地图区域编辑器")
        self.root.geometry("1200x800")

        self.map_name_var = tk.StringVar(value=initial_map)
        self.status_var = tk.StringVar(value="就绪")
        self.detect_var = tk.BooleanVar(value=False)

        self._regions: list[Region] = []
        self._frame: Optional[np.ndarray] = None
        self._photo: Optional[tk.PhotoImage] = None
        self._image_id: Optional[int] = None
        self._detector = RedDotDetector()
        self._announcer = Announcer(tts=create_tts(tts_backend), stable_frames=2)

        self._drag_start: tuple[float, float] | None = None
        self._draft_rect_id: Optional[int] = None
        self._last_detect_point: tuple[int, int] | None = None
        self._last_callout: str | None = None

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_map_list()
        self._try_load(initial_map)

    def _on_close(self) -> None:
        close = getattr(self.source, "close", None)
        if callable(close):
            close()
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

        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT)

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

    def run(self) -> None:
        self._tick_frame()
        self.root.mainloop()

    def _tick_frame(self) -> None:
        frame = self.source.read()
        if frame is not None:
            self._frame = frame
            self._show_frame(frame)
            self._run_detection_if_enabled(frame)
            self._draw_overlays()

        interval_ms = int(1000 / self.target_fps)
        self.root.after(interval_ms, self._tick_frame)

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
        if self.detect_var.get():
            self.status_var.set("运行检测中（红点映射将触发语音播报）")
        else:
            self.status_var.set("检测已停止")

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
            return

        self.map_name_var.set(config.map_name)
        self._regions = list(config.regions)
        self._refresh_region_list()
        self._draw_overlays()
        self.status_var.set(f"已加载地图: {config.map_name}")

    def _save_map(self) -> None:
        name = self.map_name_var.get().strip()
        if not name:
            messagebox.showwarning("输入错误", "地图名不能为空")
            return
        path = self.store.save(MapConfig(map_name=name, regions=list(self._regions)))
        self.status_var.set(f"已保存: {path}")
        self._refresh_map_list()

    def _refresh_map_list(self) -> None:
        names = self.store.list_map_names()
        self.map_combo["values"] = names


def _bgr_to_photoimage(frame: np.ndarray) -> tk.PhotoImage:
    """将 OpenCV BGR 帧转为 Tk PhotoImage（PPM 内存格式）。"""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    header = f"P6\n{w} {h}\n255\n".encode("ascii")
    data = header + rgb.tobytes()
    return tk.PhotoImage(data=data, format="PPM")


def run_region_editor(
    source: FrameSource,
    maps_dir: str,
    map_name: str,
    fps: float,
    tts_backend: str = "auto",
) -> None:
    """启动可视化区域编辑器。"""
    store = MapConfigStore(maps_dir)
    app = RegionEditorApp(
        source=source,
        store=store,
        initial_map=map_name,
        fps=fps,
        tts_backend=tts_backend,
    )
    app.run()

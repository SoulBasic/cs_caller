"""矩形区域编辑工具函数。"""

from __future__ import annotations

from dataclasses import dataclass

from cs_caller.callout_mapper import Region


@dataclass(frozen=True)
class Rect:
    """轴对齐矩形。"""

    x1: float
    y1: float
    x2: float
    y2: float


def normalize_rect(x1: float, y1: float, x2: float, y2: float) -> Rect:
    """确保坐标顺序为左上->右下。"""
    left = min(x1, x2)
    right = max(x1, x2)
    top = min(y1, y2)
    bottom = max(y1, y2)
    return Rect(left, top, right, bottom)


def rect_to_polygon(rect: Rect) -> list[tuple[float, float]]:
    """矩形转四边形点集（顺时针）。"""
    return [
        (rect.x1, rect.y1),
        (rect.x2, rect.y1),
        (rect.x2, rect.y2),
        (rect.x1, rect.y2),
    ]


def build_rect_region(name: str, x1: float, y1: float, x2: float, y2: float) -> Region:
    """将拖拽矩形转换为 Region。"""
    rect = normalize_rect(x1, y1, x2, y2)
    return Region(name=name, polygon=rect_to_polygon(rect))


def polygon_to_rect(polygon: list[tuple[float, float]]) -> Rect | None:
    """将四边形近似还原为外接矩形（用于 GUI 叠加）。"""
    if len(polygon) < 4:
        return None
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return normalize_rect(min(xs), min(ys), max(xs), max(ys))

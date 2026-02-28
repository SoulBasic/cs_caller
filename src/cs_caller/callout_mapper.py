"""坐标到 callout 的映射模块。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


Point = tuple[float, float]
Polygon = list[Point]


@dataclass
class Region:
    name: str
    polygon: Polygon


class CalloutMapper:
    """根据地图区域多边形将点映射到 callout。"""

    def __init__(self, regions: Iterable[Region]) -> None:
        self.regions = list(regions)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CalloutMapper":
        import yaml

        with Path(path).open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_regions = data.get("regions", [])
        regions: list[Region] = []
        for item in raw_regions:
            regions.append(
                Region(
                    name=str(item["name"]),
                    polygon=[(float(x), float(y)) for x, y in item["polygon"]],
                )
            )
        return cls(regions)

    def map_point(self, point: Point) -> str | None:
        for region in self.regions:
            if point_in_polygon(point, region.polygon):
                return region.name
        return None


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """射线法判断点是否在多边形内部（边界视为内部）。"""
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        if _point_on_segment(point, (x1, y1), (x2, y2)):
            return True

        intersects = (y1 > y) != (y2 > y)
        if intersects:
            xin = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if xin >= x:
                inside = not inside
    return inside


def _point_on_segment(p: Point, a: Point, b: Point) -> bool:
    """判断点是否落在线段上。"""
    px, py = p
    ax, ay = a
    bx, by = b

    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > 1e-6:
        return False

    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    if dot < 0:
        return False

    length_sq = (bx - ax) ** 2 + (by - ay) ** 2
    return dot <= length_sq

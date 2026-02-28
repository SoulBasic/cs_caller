"""地图配置持久化：在 config/maps 下读写 YAML。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from cs_caller.callout_mapper import Region


@dataclass
class MapConfig:
    """单张地图配置。"""

    map_name: str
    regions: list[Region]


class MapConfigStore:
    """地图配置仓库，支持多地图的创建/加载/保存。"""

    def __init__(self, maps_dir: str | Path = "config/maps") -> None:
        self.maps_dir = Path(maps_dir)
        self.maps_dir.mkdir(parents=True, exist_ok=True)

    def list_map_names(self) -> list[str]:
        """返回可用地图名称（按文件名排序）。"""
        names = [p.stem for p in self.maps_dir.glob("*.yaml")]
        return sorted(names)

    def load(self, map_name: str) -> MapConfig:
        """按 map_name 加载配置，不存在则抛出 FileNotFoundError。"""
        path = self.path_for_map(map_name)
        if not path.exists():
            raise FileNotFoundError(f"地图配置不存在: {path}")
        return self.load_path(path)

    def load_path(self, path: str | Path) -> MapConfig:
        """按完整路径加载配置。"""
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        map_name = str(data.get("map_name") or p.stem)
        raw_regions = data.get("regions", [])
        regions: list[Region] = []
        for item in raw_regions:
            regions.append(
                Region(
                    name=str(item["name"]),
                    polygon=[(float(x), float(y)) for x, y in item["polygon"]],
                )
            )

        return MapConfig(map_name=map_name, regions=regions)

    def save(self, config: MapConfig) -> Path:
        """保存配置到 maps_dir，文件名为 <map_name>.yaml。"""
        path = self.path_for_map(config.map_name)
        payload = {
            "map_name": config.map_name,
            "regions": _regions_to_payload(config.regions),
        }
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
        return path

    def path_for_map(self, map_name: str) -> Path:
        """将 map_name 映射为配置文件路径。"""
        safe_name = map_name.strip().replace(" ", "_")
        if not safe_name:
            raise ValueError("map_name 不能为空")
        return self.maps_dir / f"{safe_name}.yaml"


def _regions_to_payload(regions: Iterable[Region]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for region in regions:
        polygon = [[float(x), float(y)] for x, y in region.polygon]
        payload.append({"name": region.name, "polygon": polygon})
    return payload

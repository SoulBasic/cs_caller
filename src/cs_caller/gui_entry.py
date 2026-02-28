"""Windows EXE GUI 入口（单进程）。"""

from __future__ import annotations

from pathlib import Path

from cs_caller.gui.app import run_region_editor
from cs_caller.sources.mock_source import MockImageSource


def main() -> None:
    # EXE 默认读取同目录下 assets/minimap_sample.png，可自行替换
    sample = Path('assets/minimap_sample.png')
    if not sample.exists():
        raise FileNotFoundError('缺少 assets/minimap_sample.png，请放入一张小地图样图')

    source = MockImageSource(sample)
    run_region_editor(source=source, maps_dir='config/maps', map_name='de_dust2', fps=16.0)


if __name__ == '__main__':
    main()

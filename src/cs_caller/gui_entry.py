"""Windows EXE GUI 入口（单进程）。"""

from __future__ import annotations

from pathlib import Path

from cs_caller.gui.app import run_region_editor


def main() -> None:
    # EXE 默认读取同目录下 assets/minimap_sample.png，可自行替换
    sample = Path('assets/minimap_sample.png')
    if not sample.exists():
        raise FileNotFoundError('缺少 assets/minimap_sample.png，请放入一张小地图样图')

    run_region_editor(
        maps_dir='config/maps',
        map_name='de_dust2',
        fps=16.0,
        source_mode='mock',
        source_text=str(sample),
        tts_backend='auto',
        settings_path='config/app_settings.yaml',
    )


if __name__ == '__main__':
    main()

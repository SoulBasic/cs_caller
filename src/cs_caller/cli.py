"""命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CS 报点原型 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    mock = sub.add_parser("mock", help="使用本地图片重复模拟帧源并执行检测")
    mock.add_argument("--image", required=True, help="本地小地图图片绝对路径")
    mock.add_argument("--map", default="de_dust2", help="地图名称")
    mock.add_argument("--maps-dir", default="config/maps", help="地图 YAML 目录")
    mock.add_argument(
        "--map-config",
        default=None,
        help="地图配置文件路径；设置后优先于 --map/--maps-dir",
    )
    mock.add_argument("--fps", type=float, default=16.0, help="处理帧率")
    mock.add_argument("--cooldown", type=float, default=2.0, help="播报冷却秒数")
    mock.add_argument(
        "--stable-frames", type=int, default=3, help="触发播报前稳定帧数"
    )
    mock.add_argument("--max-frames", type=int, default=120, help="最多处理帧数")
    mock.add_argument(
        "--tts-backend",
        default="auto",
        choices=["auto", "pyttsx3", "console"],
        help="TTS 后端",
    )

    gui = sub.add_parser("gui", help="启动可视化区域编辑器")
    gui.add_argument("--image", required=True, help="本地小地图图片绝对路径")
    gui.add_argument("--map", default="de_dust2", help="默认加载地图名")
    gui.add_argument("--maps-dir", default="config/maps", help="地图 YAML 目录")
    gui.add_argument("--fps", type=float, default=16.0, help="预览帧率")
    gui.add_argument(
        "--tts-backend",
        default="auto",
        choices=["auto", "pyttsx3", "console"],
        help="运行检测时使用的 TTS 后端",
    )
    return parser


def run_mock(args: argparse.Namespace) -> None:
    # 按需导入，避免在仅查看 --help 时要求完整三方依赖。
    from cs_caller.announcer import Announcer
    from cs_caller.callout_mapper import CalloutMapper
    from cs_caller.detector import RedDotDetector
    from cs_caller.frame_clock import FrameClock
    from cs_caller.map_config_store import MapConfigStore
    from cs_caller.pipeline import Pipeline
    from cs_caller.sources.mock_source import MockImageSource
    from cs_caller.tts import create_tts

    source = MockImageSource(args.image)
    detector = RedDotDetector()

    if args.map_config:
        mapper = CalloutMapper.from_yaml(Path(args.map_config))
        map_hint = args.map_config
    else:
        store = MapConfigStore(args.maps_dir)
        config = store.load(args.map)
        mapper = CalloutMapper(config.regions)
        map_hint = str(store.path_for_map(args.map))

    announcer = Announcer(
        tts=create_tts(args.tts_backend),
        cooldown_sec=args.cooldown,
        stable_frames=args.stable_frames,
    )
    clock = FrameClock(fps=args.fps)

    print(f"启动 mock 模式: map={args.map}, config={map_hint}")
    pipeline = Pipeline(source, detector, mapper, announcer, clock)
    pipeline.run(max_frames=args.max_frames)


def run_gui(args: argparse.Namespace) -> None:
    from cs_caller.gui.app import run_region_editor
    from cs_caller.sources.mock_source import MockImageSource

    source = MockImageSource(args.image)
    run_region_editor(
        source=source,
        maps_dir=args.maps_dir,
        map_name=args.map,
        fps=args.fps,
        tts_backend=args.tts_backend,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "mock":
        run_mock(args)
    elif args.command == "gui":
        run_gui(args)


if __name__ == "__main__":
    main()

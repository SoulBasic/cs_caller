"""命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CS 报点原型 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    mock = sub.add_parser("mock", help="使用本地图片重复模拟帧源")
    mock.add_argument("--image", required=True, help="本地小地图图片绝对路径")
    mock.add_argument("--map", default="de_dust2", help="地图名称（仅用于提示）")
    mock.add_argument(
        "--map-config",
        default="config/maps/de_dust2.yaml",
        help="地图多边形配置文件路径",
    )
    mock.add_argument("--fps", type=float, default=16.0, help="处理帧率")
    mock.add_argument("--cooldown", type=float, default=2.0, help="播报冷却秒数")
    mock.add_argument(
        "--stable-frames", type=int, default=3, help="触发播报前稳定帧数"
    )
    mock.add_argument("--max-frames", type=int, default=120, help="最多处理帧数")
    return parser


def run_mock(args: argparse.Namespace) -> None:
    # 按需导入，避免在仅查看 --help 时要求完整三方依赖。
    from cs_caller.announcer import Announcer
    from cs_caller.callout_mapper import CalloutMapper
    from cs_caller.detector import RedDotDetector
    from cs_caller.frame_clock import FrameClock
    from cs_caller.pipeline import Pipeline
    from cs_caller.sources.mock_source import MockImageSource
    from cs_caller.tts.console_tts import ConsoleTTS

    source = MockImageSource(args.image)
    detector = RedDotDetector()
    mapper = CalloutMapper.from_yaml(Path(args.map_config))
    announcer = Announcer(
        tts=ConsoleTTS(), cooldown_sec=args.cooldown, stable_frames=args.stable_frames
    )
    clock = FrameClock(fps=args.fps)

    print(f"启动 mock 模式: map={args.map}, config={args.map_config}")
    pipeline = Pipeline(source, detector, mapper, announcer, clock)
    pipeline.run(max_frames=args.max_frames)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "mock":
        run_mock(args)


if __name__ == "__main__":
    main()

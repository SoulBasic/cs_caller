"""端到端流水线。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cs_caller.announcer import Announcer
from cs_caller.callout_mapper import CalloutMapper
from cs_caller.detector import RedDotDetector
from cs_caller.frame_clock import FrameClock
from cs_caller.sources.base import FrameSource


@dataclass
class Pipeline:
    source: FrameSource
    detector: RedDotDetector
    mapper: CalloutMapper
    announcer: Announcer
    clock: FrameClock

    def run(self, max_frames: Optional[int] = None) -> None:
        """持续处理帧直到达到上限或帧源结束。"""
        frames = 0
        while True:
            frame = self.source.read()
            if frame is None:
                break

            point = self.detector.detect(frame)
            callout = self.mapper.map_point(point) if point else None
            announced = self.announcer.process(callout)

            print(
                f"frame={frames} point={point} callout={callout} announced={bool(announced)}"
            )

            frames += 1
            if max_frames is not None and frames >= max_frames:
                break

            self.clock.tick()

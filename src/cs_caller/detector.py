"""红点检测模块。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class RedDotDetector:
    """使用 HSV 阈值检测小地图红点并返回中心坐标。"""

    lower_red_1: tuple[int, int, int] = (0, 120, 80)
    upper_red_1: tuple[int, int, int] = (10, 255, 255)
    lower_red_2: tuple[int, int, int] = (170, 120, 80)
    upper_red_2: tuple[int, int, int] = (180, 255, 255)
    min_area: float = 8.0

    def detect(self, frame: np.ndarray) -> Optional[tuple[int, int]]:
        """返回面积最大的红点中心，未检测到则返回 None。"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask1 = cv2.inRange(hsv, np.array(self.lower_red_1), np.array(self.upper_red_1))
        mask2 = cv2.inRange(hsv, np.array(self.lower_red_2), np.array(self.upper_red_2))
        mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(best)
        if area < self.min_area:
            return None

        m = cv2.moments(best)
        if m["m00"] == 0:
            return None

        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        return (cx, cy)

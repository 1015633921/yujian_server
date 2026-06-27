from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


def read(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def main() -> None:
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    image = read(source)
    height, width = image.shape[:2]
    scale = 900 / max(height, width)
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 1.5)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.1,
        minDist=45,
        param1=100,
        param2=28,
        minRadius=max(20, int(min(small.shape[:2]) * 0.055)),
        maxRadius=int(min(small.shape[:2]) * 0.24),
    )
    annotated = small.copy()
    if circles is not None:
        for index, (x, y, radius) in enumerate(circles[0], start=1):
            center = (round(x), round(y))
            cv2.circle(annotated, center, round(radius), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                str(index),
                center,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
            print(index, round(x / scale), round(y / scale), round(radius / scale))
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(output)


if __name__ == "__main__":
    main()

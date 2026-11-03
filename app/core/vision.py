"""Matching de imagens e vínculo vertical entre ícone e botão.

É intencionalmente independente de Win32, PySide6, mss e pyautogui.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    x: int
    y: int
    width: int
    height: int
    confidence: float


def detect(frame, template, threshold: float = 0.83, roi: tuple[int, int, int, int] | None = None) -> Match | None:
    import cv2
    import numpy as np

    if frame is None or template is None or frame.size == 0 or template.size == 0:
        return None
    oy, ox = 0, 0
    if roi is not None:
        x0, y0, x1, y1 = roi
        ox, oy = max(0, x0), max(0, y0)
        frame = frame[oy:min(frame.shape[0], y1), ox:min(frame.shape[1], x1)]
    if frame.size == 0:
        return None
    height, width = template.shape[:2]
    if height > frame.shape[0] or width > frame.shape[1]:
        return None
    if float(np.std(template)) < 0.1:
        return None  # TM_CCOEFF_NORMED é degenerado com template uniforme
    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(result)
    if not np.isfinite(score) or score < threshold:
        return None
    return Match(x + ox, y + oy, width, height, float(score))


def same_row(frame, template, icon: Match, threshold: float, factor: float) -> Match | None:
    cy = icon.y + icon.height / 2
    half = icon.height * factor / 2
    return detect(frame, template, threshold,
                  roi=(0, max(0, int(cy - half)), frame.shape[1], min(frame.shape[0], int(cy + half))))

"""Matching de imagens e vínculo vertical entre ícone e botão.

É intencionalmente independente de Win32, PySide6, mss e pyautogui.
"""
from dataclasses import dataclass
from math import isfinite


_SAME_ROW_FACTOR = 1.6


@dataclass(frozen=True)
class Match:
    x: int
    y: int
    width: int
    height: int
    confidence: float


def detect(frame, template, threshold: float = 0.83, roi: tuple[int, int, int, int] | None = None) -> Match | None:
    match = best_match(frame, template, roi)
    return match if match is not None and match.confidence >= threshold else None


def best_match(frame, template, roi: tuple[int, int, int, int] | None = None) -> Match | None:
    import cv2

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
    _, deviation = cv2.meanStdDev(template)
    if deviation.max() < 0.1:
        return None  # TM_CCOEFF_NORMED é degenerado com template uniforme
    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(result)
    if not isfinite(score):
        return None
    return Match(x + ox, y + oy, width, height, float(score))


def same_row(frame, template, icon: Match, threshold: float) -> Match | None:
    cy = icon.y + icon.height / 2
    half = icon.height * _SAME_ROW_FACTOR / 2
    return detect(frame, template, threshold,
                  roi=(0, max(0, int(cy - half)), frame.shape[1], min(frame.shape[0], int(cy + half))))

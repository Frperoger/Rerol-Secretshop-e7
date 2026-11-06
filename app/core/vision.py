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


def same_row(frame, template, icon: Match, threshold: float, factor: float = 1.6) -> Match | None:
    """Localiza botão à DIREITA do ícone, na MESMA linha de item.

    O ROI acomoda o template inteiro, mas somente posições cujo CENTRO
    coincide com o centro vertical do ícone são elegíveis. Evita associar
    o botão visualmente idêntico da linha vizinha.
    """
    from math import ceil, floor

    if frame is None or template is None or icon is None or frame.size == 0 or template.size == 0:
        return None
    h, w = template.shape[:2]
    if h <= 0 or w <= 0 or icon.height <= 0 or icon.width <= 0:
        return None
    x0 = max(0, icon.x + icon.width)
    if x0 + w > frame.shape[1]:
        return None
    center_y = icon.y + icon.height / 2
    tolerance = max(6.0, icon.height * min(0.43, max(0.25, factor / 4)))
    top = max(0, floor(center_y - tolerance - h / 2))
    bottom = min(frame.shape[0], ceil(center_y + tolerance + h / 2) + 1)
    if bottom - top < h:
        return None
    button = detect(frame, template, threshold,
                    roi=(x0, top, frame.shape[1], bottom))
    if (button is None or button.x < x0 or
            abs(button.y + button.height / 2 - center_y) > tolerance + 1):
        return None
    return button

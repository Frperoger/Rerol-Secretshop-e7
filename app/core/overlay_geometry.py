"""Coordenadas normalizadas de uma região de acompanhamento sobre a janela do jogo."""
from __future__ import annotations
from app.models import BotError

DEFAULT_OVERLAY_AREA = (0.02, 0.025, 0.33, 0.245)


def validate_overlay_area(area):
    import math
    if len(area) != 4 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in area):
        raise BotError("Área azul do painel deve conter quatro proporções válidas.")
    x0, y0, x1, y1 = area
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise BotError("Área azul deve estar dentro da janela do jogo.")
    if x1 - x0 < 0.12 or y1 - y0 < 0.09:
        raise BotError("Área azul muito pequena (mínimo 12% da largura e 9% da altura).")
    return tuple(float(x) for x in area)


def rectangles_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def overlay_rect(game_rect, area):
    """Game rect: x, y, width, height (coordenadas de tela); retorna x, y, w, h."""
    x, y, width, height = game_rect
    x0, y0, x1, y1 = validate_overlay_area(area)
    if width <= 0 or height <= 0:
        raise BotError("Dimensões inválidas da janela do jogo.")
    left = x + round(x0 * width)
    top = y + round(y0 * height)
    right = x + round(x1 * width)
    bottom = y + round(y1 * height)
    return left, top, right-left, bottom-top

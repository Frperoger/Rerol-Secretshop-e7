"""Transformações puras para os retângulos normalizados da calibração.

As duas áreas podem ser arrastadas/redimensionadas na prévia sem acessar Qt.
"""
from __future__ import annotations


def drag_area(area: tuple[float, float, float, float], dx: float, dy: float,
              mode: str, *, min_width: float, min_height: float) -> tuple[float, float, float, float]:
    """Retorna a área limitada à imagem (valores de 0 a 1).

    ``move`` mantém as dimensões e ``resize`` move somente o canto inferior direito.
    ``dx``/``dy`` são deslocamentos normalizados relativos ao início do arraste.
    """
    if mode not in ("move", "resize"):
        raise ValueError("Modo de arraste inválido")
    x0, y0, x1, y1 = area
    if mode == "move":
        width, height = x1 - x0, y1 - y0
        x0 = max(0.0, min(1.0 - width, x0 + dx))
        y0 = max(0.0, min(1.0 - height, y0 + dy))
        result = (x0, y0, x0 + width, y0 + height)
    else:
        result = (x0, y0,
                  min(1.0, max(x0 + min_width, x1 + dx)),
                  min(1.0, max(y0 + min_height, y1 + dy)))
    return tuple(round(value, 4) for value in result)

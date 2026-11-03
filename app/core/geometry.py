"""Conversões geométricas puras e validação dos alvos de clique."""
from dataclasses import dataclass
from random import uniform


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Retângulo de janela inválido.")

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.left + self.width and self.top <= y < self.top + self.height

    def proportional(self, x: float, y: float) -> tuple[int, int]:
        return self.left + int(x * self.width), self.top + int(y * self.height)


def choose_match_point(rect: Rect, match, lower_half: bool = False) -> tuple[int, int]:
    """Seleciona ponto interno à caixa (match com x/y/width/height)."""
    x, y, w, h = match.x, match.y, match.width, match.height
    if w <= 0 or h <= 0:
        raise ValueError("Template sem dimensões.")
    mx, my = w * 0.2, h * 0.2
    px = rect.left + x + uniform(mx, w - mx)
    bottom_start = max(my, h / 2) if lower_half else my
    py = rect.top + y + uniform(bottom_start, h - my)
    ax, ay = int(px), int(py)
    if not rect.contains(ax, ay):
        raise ValueError("O ponto de clique está fora da janela alvo.")
    return ax, ay


def choose_safe_point(rect: Rect, area: tuple[float, float, float, float]) -> tuple[int, int]:
    x0, y0, x1, y1 = area
    x, y = rect.proportional(uniform(x0, x1), uniform(y0, y1))
    if not rect.contains(x, y):
        raise ValueError("Área segura produz ponto fora da janela.")
    return x, y

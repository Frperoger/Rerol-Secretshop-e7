"""Modelos de dados sem dependências de desktop ou Qt."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum


class BotError(RuntimeError):
    """Erro operacional que exige interrupção segura."""


class FocusLost(BotError):
    """A janela-alvo não está mais no primeiro plano."""


class WindowInvalid(BotError):
    """Janela fechada, minimizada ou reposicionada."""


class UncertainAction(BotError):
    """Ação disparada sem comprovação visual suficiente do resultado."""


class StopRequested(Exception):
    """Cancelamento cooperativo; não confundir com falha."""


class PurchaseStatus(str, Enum):
    NOT_FOUND = "nao_encontrado"
    VERIFIED = "verificado_visualmente"


@dataclass
class ItemConfig:
    id: str
    name: str
    price_gold: int
    enabled: bool = True
    lower_half: bool = True
    icon_template: str = ""
    buy_template: str = ""
    price_template: str = ""
    sold_template: str = ""  # opcional, evidência visual específica da compra

    @classmethod
    def standard(cls, ident: str, name: str, price: int) -> "ItemConfig":
        return cls(ident, name, price, icon_template=f"{ident}_icone.png",
                   buy_template=f"{ident}_comprar_qtd.png",
                   price_template=f"{ident}_comprar_preco.png")


@dataclass
class BudgetConfig:
    gems_available: int = 60
    gold_available: int = 2_000_000
    gems_limit: int = 30  # 0 significa usar o saldo disponível
    gold_limit: int = 1_000_000
    refresh_cost: int = 3


@dataclass
class CalibrationConfig:
    window_title: str = "Epic Seven"
    hotkey: str = "ctrl+alt+q"
    threshold: float = 0.83
    max_scrolls: int = 2
    same_row_factor: float = 1.6
    pause_min: float = 0.1
    pause_max: float = 0.3
    safe_area: tuple[float, float, float, float] = (0.72, 0.20, 0.79, 0.90)
    focus_timeout: float = 30.0
    modal_timeout: float = 2.5
    auto_overlay: bool = False
    overlay_area: tuple[float, float, float, float] = (0.02, 0.025, 0.33, 0.245)


@dataclass
class AppConfig:
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    items: list[ItemConfig] = field(default_factory=lambda: [
        ItemConfig.standard("item1", "Item 1", 184_000),
        ItemConfig.standard("item2", "Item 2", 280_000),
    ])
    templates_dir: str = ""  # vazio: diretório de dados do usuário

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        cal = dict(data.get("calibration", {}))
        if "safe_area" in cal:
            cal["safe_area"] = tuple(cal["safe_area"])
        if "overlay_area" in cal:
            cal["overlay_area"] = tuple(cal["overlay_area"])
        items = [ItemConfig(**d) for d in data.get("items", [])]
        return cls(budget=BudgetConfig(**data.get("budget", {})),
                   calibration=CalibrationConfig(**cal),
                   items=items if "items" in data else cls().items,
                   templates_dir=data.get("templates_dir", ""))


@dataclass
class RunState:
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: str = ""
    status: str = "preparando"
    reason: str = ""
    refreshes: int = 0
    gems_estimated: int = 0
    purchases_verified: int = 0
    gold_estimated: int = 0
    purchases_by_item: dict[str, int] = field(default_factory=dict)
    uncertain_actions: list[str] = field(default_factory=list)
    # Itens já comprados nesta rotação, inclusive após pausa por foco.
    purchased_in_rotation: set[str] = field(default_factory=set, repr=False)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("purchased_in_rotation", None)
        return data

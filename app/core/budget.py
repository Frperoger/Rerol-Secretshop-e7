"""Validação e cálculo de orçamento, sem efeitos colaterais."""
import math
import re
from app.models import AppConfig, BotError, RunState
from app.core.hotkeys import normalize_hotkey
from app.core.overlay_geometry import validate_overlay_area, rectangles_overlap


_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def validate_config(cfg: AppConfig) -> tuple[int, int]:
    b, c = cfg.budget, cfg.calibration
    values = (b.gems_available, b.gold_available, b.gems_limit,
              b.gold_limit, b.refresh_cost)
    if any(type(x) is not int for x in values):
        raise BotError("Os valores monetários devem ser números inteiros.")
    if any(v < 0 for v in values[:4]) or b.refresh_cost < 1:
        raise BotError("Saldos/limites devem ser positivos ou zero; renovação custa ao menos 1 gema.")
    gems_limit = b.gems_limit or b.gems_available
    gold_limit = b.gold_limit or b.gold_available
    if gems_limit > b.gems_available or gold_limit > b.gold_available:
        raise BotError("O limite de gastos não pode superar o saldo disponível.")
    if not c.window_title.strip() or not c.hotkey.strip():
        raise BotError("Título da janela e tecla de emergência são obrigatórios.")
    normalize_hotkey(c.hotkey)
    numeric = (c.threshold, c.pause_min, c.pause_max, c.focus_timeout, c.modal_timeout)
    if any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in numeric):
        raise BotError("Calibração contém valores não numéricos ou infinitos.")
    if not 0.6 <= c.threshold <= 0.99:
        raise BotError("Limiar de detecção inválido.")
    if type(c.max_scrolls) is not int or not 0 <= c.max_scrolls <= 8:
        raise BotError("Máximo de rolagens deve estar entre 0 e 8.")
    if not 0 <= c.pause_min <= c.pause_max <= 10 or not 1 <= c.focus_timeout <= 300:
        raise BotError("Tempo de pausa ou espera de foco inválido.")
    if not 0.5 <= c.modal_timeout <= 10:
        raise BotError("Timeout de modal deve estar entre 0,5 e 10 segundos.")
    if len(c.safe_area) != 4:
        raise BotError("Área segura precisa ter quatro proporções.")
    x0, y0, x1, y1 = c.safe_area
    if any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in c.safe_area):
        raise BotError("Área segura com valores inválidos.")
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise BotError("Área segura deve ser um retângulo válido dentro da janela.")
    if not isinstance(c.auto_overlay, bool):
        raise BotError("Modo de acompanhamento deve ser ligado ou desligado.")
    validate_overlay_area(c.overlay_area)
    if c.auto_overlay and rectangles_overlap(c.overlay_area, c.safe_area):
        raise BotError("Área azul do pop-up sobrepõe a área segura verde. Separe as regiões.")
    if not cfg.items or not any(item.enabled for item in cfg.items):
        raise BotError("Ative ao menos um item para comprar.")
    ids = set()
    for item in cfg.items:
        if not _ID.fullmatch(item.id):
            raise BotError(f"ID de item inválido: {item.id!r}.")
        if item.id in ids:
            raise BotError(f"ID duplicado: {item.id}.")
        ids.add(item.id)
        if not item.name.strip() or type(item.price_gold) is not int or item.price_gold <= 0:
            raise BotError(f"Nome/preço inválido para {item.id}.")
        for filename in (item.icon_template, item.buy_template, item.price_template, item.sold_template):
            if filename and (filename != filename.split("/")[-1] or "\\" in filename or ".." in filename):
                raise BotError(f"Template inválido em {item.id}: {filename}.")
        if item.enabled and not (item.icon_template and item.buy_template and item.price_template):
            raise BotError(f"Templates obrigatórios ausentes na configuração de {item.id}.")
    return gems_limit, gold_limit


def can_purchase(item_price: int, state: RunState, gold_limit: int) -> bool:
    return state.gold_estimated + item_price <= gold_limit


def can_refresh(refresh_cost: int, state: RunState, gems_limit: int) -> bool:
    return state.gems_estimated + refresh_cost <= gems_limit

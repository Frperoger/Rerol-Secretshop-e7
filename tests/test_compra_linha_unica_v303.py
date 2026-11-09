"""Regressões: PNG único para todos os itens e botão somente na linha certa."""
from pathlib import Path

import numpy as np

from app.core.vision import Match, same_row
from app.core.geometry import Rect, buy_button_action_region
import cv2


def _new_template():
    root = Path(__file__).resolve().parents[1]
    # O PNG de compra de linha única já faz parte dos templates distribuídos.
    name = root / 'templates' / 'item1_comprar_qtd.png'
    return cv2.imdecode(np.frombuffer(name.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)


def _two_rows():
    rng = np.random.default_rng(2026)
    frame = rng.integers(0, 40, size=(380, 900, 3), dtype=np.uint8)
    button = cv2.resize(_new_template(), None, fx=0.70, fy=0.70, interpolation=cv2.INTER_AREA)
    h, w = button.shape[:2]
    frame[40:40 + h, 580:580 + w] = button
    frame[220:220 + h, 580:580 + w] = button
    return frame, button, h, w


def test_template_e_identico_para_todos_os_itens_padrao():
    root = Path(__file__).resolve().parents[1]
    first = (root / 'templates/item1_comprar_qtd.png').read_bytes()
    second = (root / 'templates/item2_comprar_qtd.png').read_bytes()
    assert first == second
    assert _new_template().shape[:2] == (80, 272)


def test_mesmo_botao_em_duas_linhas_seleciona_somente_a_linha_do_item():
    frame, button, h, w = _two_rows()
    icon = Match(280, 210, 80, 75, 0.99)
    result = same_row(frame, button, icon, 0.85)
    assert result is not None
    assert (result.x, result.y, result.width, result.height) == (580, 220, w, h)
    assert result.confidence > 0.99


def test_botao_de_outra_linha_nao_e_aceito():
    frame, button, h, w = _two_rows()
    frame[220:220+h, 580:580+w] = 0
    icon = Match(280, 210, 80, 75, 0.99)
    assert same_row(frame, button, icon, 0.85) is None


def test_botao_a_esquerda_do_icone_nao_e_aceito():
    frame, button, h, w = _two_rows()
    frame[220:220+h, 580:580+w] = 0
    frame[220:220+h, 40:40+w] = button
    icon = Match(280, 210, 80, 75, 0.99)
    assert same_row(frame, button, icon, 0.85) is None


def test_clique_no_comprar_sem_atingir_o_seletor_1_1():
    match = Match(580, 220, 190, 56, 0.99)
    target = buy_button_action_region(match)
    assert match.x + match.width * .55 <= target.x
    assert target.x + target.width <= match.x + match.width * .93
    assert target.y > match.y
    assert target.y + target.height < match.y + match.height
    rect = Rect(0, 0, 900, 380)
    assert rect.contains(target.x + target.width//2, target.y + target.height//2)


def test_mesmo_codigo_para_item_1_2_e_3():
    frame, button, h, w = _two_rows()
    # A função não recebe ID/nome. Todos os itens usam a mesma regra.
    for item_id in ('item1', 'item2', 'item3'):
        assert same_row(frame, button, Match(280, 210, 80, 75, 0.98), 0.85) is not None, item_id

from pathlib import Path
import numpy as np
import cv2
import pytest

from app.models import AppConfig, BotError
from app.ui.diagnostics import analyze_image, validate_item_templates


def png(path, array):
    cv2.imwrite(str(path), array)


def test_missing_templates_blocks_save(tmp_path):
    with pytest.raises(BotError, match="Ausentes"):
        validate_item_templates(AppConfig().items, tmp_path)


def test_diagnostic_mentions_refresh_when_template_missing(tmp_path):
    image = np.zeros((110, 120, 3), dtype=np.uint8)
    png(tmp_path / "screen.png", image)
    cfg = AppConfig()
    cfg.items = []
    data, lines = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert data.startswith(b"\x89PNG")
    assert any("RENOVAR" in line and "ausente" in line for line in lines)


def test_diagnostic_detects_renew_button_and_shows_score(tmp_path):
    rng = np.random.default_rng(777)
    renew = rng.integers(0, 255, (16, 28, 3), dtype=np.uint8)
    screen = rng.integers(0, 60, (120, 190, 3), dtype=np.uint8)
    screen[48:64, 80:108] = renew
    png(tmp_path / "renovar.png", renew)
    png(tmp_path / "screen.png", screen)
    cfg = AppConfig()
    cfg.items = []
    _, lines = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert any("RENOVAR ENCONTRADO" in line and "confiança" in line for line in lines)


def test_diagnostic_reports_low_confidence(tmp_path):
    rng = np.random.default_rng(34)
    renew = rng.integers(0, 255, (14, 20, 3), dtype=np.uint8)
    screen = rng.integers(0, 255, (100, 150, 3), dtype=np.uint8)
    png(tmp_path / "renovar.png", renew)
    png(tmp_path / "screen.png", screen)
    cfg = AppConfig()
    cfg.items = []
    _, lines = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert any("RENOVAR NÃO ENCONTRADO" in line and "limiar" in line for line in lines)

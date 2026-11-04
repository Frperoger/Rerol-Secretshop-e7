from pathlib import Path
from types import SimpleNamespace
import numpy as np
import cv2
import pytest

from app.config import load_template_scale, save_template_scale
from app.core.geometry import Rect
from app.core.template_scale import resize_template
from app.models import AppConfig, BotError
from app.platform.desktop import DesktopIO
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
    data, lines, profile = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert data.startswith(b"\x89PNG")
    assert any("RENOVAR" in line and "ausente" in line for line in lines)
    assert profile is None


def test_diagnostic_detects_renew_button_and_shows_score(tmp_path):
    rng = np.random.default_rng(777)
    renew = rng.integers(0, 255, (16, 28, 3), dtype=np.uint8)
    screen = rng.integers(0, 60, (120, 190, 3), dtype=np.uint8)
    screen[48:64, 80:108] = renew
    png(tmp_path / "renovar.png", renew)
    png(tmp_path / "screen.png", screen)
    cfg = AppConfig()
    cfg.items = []
    _, lines, _ = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert any("RENOVAR ENCONTRADO" in line and "confiança" in line for line in lines)


def test_diagnostic_reports_low_confidence(tmp_path):
    rng = np.random.default_rng(34)
    renew = rng.integers(0, 255, (14, 20, 3), dtype=np.uint8)
    screen = rng.integers(0, 255, (100, 150, 3), dtype=np.uint8)
    png(tmp_path / "renovar.png", renew)
    png(tmp_path / "screen.png", screen)
    cfg = AppConfig()
    cfg.items = []
    _, lines, profile = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert any("RENOVAR NÃO ENCONTRADO" in line and "limiar" in line for line in lines)
    assert profile is None


@pytest.mark.parametrize("factor", [0.73, 1.37])
def test_diagnostic_scale_is_reused_in_physical_pixels(monkeypatch, tmp_path, factor):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    rng = np.random.default_rng(42)
    screen = rng.integers(0, 80, (560, 1040, 3), dtype=np.uint8)
    cfg = AppConfig()
    item = cfg.items[0]
    cfg.items = [item]
    anchor = rng.integers(0, 256, (58, 180, 3), dtype=np.uint8)
    icon = rng.integers(0, 256, (60, 56, 3), dtype=np.uint8)
    button = rng.integers(0, 256, (35, 85, 3), dtype=np.uint8)
    for template, filename, x, y in (
        (anchor, "renovar.png", 700, 390),
        (icon, item.icon_template, 280, 125),
        (button, item.buy_template, 700, 135),
    ):
        png(tmp_path / filename, template)
        scaled = resize_template(template, factor)
        height, width = scaled.shape[:2]
        screen[y:y+height, x:x+width] = scaled
    png(tmp_path / "confirmar.png", button)
    png(tmp_path / item.price_template, button)
    png(tmp_path / "screen.png", screen)
    _, lines, profile = analyze_image(tmp_path / "screen.png", cfg, tmp_path)
    assert profile is not None
    assert profile[1] == pytest.approx(factor, abs=0.01)
    assert any(item.name in line and "botão 1.00" in line for line in lines)
    save_template_scale(*profile)
    assert load_template_scale(profile[0]) == profile[1]

    rect = Rect(-20, 55, 1040, 560)
    monkeypatch.setattr("app.platform.desktop.Win32", lambda: None)
    monkeypatch.setattr("app.platform.desktop.TargetWindow.locate",
                        lambda *_: SimpleNamespace(hwnd=42, initial_rect=rect))
    driver = DesktopIO(cfg, tmp_path, lambda: None, lambda *_: None, lambda *_: None)
    driver.prepare()
    match = driver.match(screen, "renovar.png")
    assert (match.x, match.y) == (700, 390)
    assert match.confidence == pytest.approx(1)

    rect = Rect(-20, 55, 1060, 560)
    other_size = DesktopIO(cfg, tmp_path, lambda: None, lambda *_: None, lambda *_: None)
    other_size.prepare()
    assert other_size.templates["renovar.png"].shape == anchor.shape

    rect = Rect(-20, 55, 1040, 560)
    png(tmp_path / "confirmar.png", icon)
    changed_templates = DesktopIO(cfg, tmp_path, lambda: None, lambda *_: None, lambda *_: None)
    changed_templates.prepare()
    assert changed_templates.templates["renovar.png"].shape == anchor.shape


def test_legacy_row_factor_is_discarded():
    cfg = AppConfig.from_dict({"calibration": {"same_row_factor": 2.5, "pause_min": 0.15}})
    assert cfg.calibration.pause_min == 0.15
    assert "same_row_factor" not in cfg.to_dict()["calibration"]

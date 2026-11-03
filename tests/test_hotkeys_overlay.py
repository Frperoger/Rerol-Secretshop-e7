import json
import pytest

from app.config import load_config, save_config
from app.core.hotkeys import DEFAULT_HOTKEY, display_hotkey, normalize_hotkey
from app.core.overlay_geometry import overlay_rect, rectangles_overlap, validate_overlay_area
from app.core.budget import validate_config
from app.models import AppConfig, BotError


@pytest.mark.parametrize('value,result', [
    ('Ctrl+Alt+Q', DEFAULT_HOTKEY),
    ('Alt+Ctrl+f7', 'ctrl+alt+f7'),
    ('SHIFT + CTRL + 5', 'ctrl+shift+5'),
    ('ctrl + ALT + g', 'ctrl+alt+g'),
])
def test_hotkeys_capture_and_normalization(value, result):
    assert normalize_hotkey(value) == result


@pytest.mark.parametrize('value', [
    '', 'q', 'Ctrl+Q', 'Ctrl+Alt', 'Ctrl+Alt+Ctrl+Q',
    'Ctrl+Alt+Shift+Delete', 'Win+Ctrl+Q', 'Ctrl+Alt+F4',
    'Ctrl+Alt+Q, Ctrl+Alt+R', 'Ctrl+CTRL+X',
])
def test_invalid_hotkeys_are_rejected(value):
    with pytest.raises(BotError):
        normalize_hotkey(value)


def test_default_emergency_stays_fixed():
    assert DEFAULT_HOTKEY == 'ctrl+alt+q'
    assert display_hotkey(DEFAULT_HOTKEY) == 'Ctrl+Alt+Q'


def test_overlay_rect_proportional():
    assert overlay_rect((100, 200, 1000, 600), (0.1, 0.2, 0.4, 0.5)) == (
        200, 320, 300, 180)


def test_blue_overlay_and_green_safe_area_cannot_overlap_when_enabled():
    cfg = AppConfig()
    cfg.calibration.auto_overlay = True
    cfg.calibration.overlay_area = (0.65, 0.15, 0.90, 0.55)
    with pytest.raises(BotError, match='sobrepõe'):
        validate_config(cfg)
    cfg.calibration.auto_overlay = False
    validate_config(cfg)


def test_overlay_separated_from_safe_area():
    cfg = AppConfig()
    cfg.calibration.auto_overlay = True
    assert not rectangles_overlap(cfg.calibration.overlay_area, cfg.calibration.safe_area)
    validate_config(cfg)


@pytest.mark.parametrize('area', [
    (-0.1, 0.1, 0.4, 0.4), (0.1, 0.1, 1.1, 0.9),
    (0.1, 0.1, 0.2, 0.4), (0.1, 0.1, 0.5, 0.15),
    (0.5, 0.5, 0.2, 0.8), (float('nan'), 0, 0.5, 0.5)
])
def test_invalid_blue_area_rejected(area):
    with pytest.raises(BotError):
        validate_overlay_area(area)


def test_configuration_legacy_and_roundtrip(tmp_path):
    source = tmp_path / 'old.json'
    previous = AppConfig().to_dict()
    previous['calibration'].pop('auto_overlay')
    previous['calibration'].pop('overlay_area')
    source.write_text(json.dumps(previous), encoding='utf-8')
    legacy = load_config(source)
    assert legacy.calibration.auto_overlay is False
    legacy.calibration.auto_overlay = True
    legacy.calibration.overlay_area = (0.03, 0.04, 0.4, 0.3)
    legacy.calibration.hotkey = normalize_hotkey('Ctrl+Shift+F8')
    save_config(legacy, source)
    restored = load_config(source)
    assert restored.calibration.overlay_area == (0.03, 0.04, 0.4, 0.3)
    assert restored.calibration.hotkey == 'ctrl+shift+f8'

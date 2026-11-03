from pathlib import Path
import json
import pytest
from app.core.budget import can_purchase, can_refresh, validate_config
from app.config import load_config, save_config, prepare_templates
from app.models import AppConfig, BotError, RunState


def test_standard_budget():
    assert validate_config(AppConfig()) == (30, 1_000_000)


def test_zero_means_total_available():
    cfg = AppConfig()
    cfg.budget.gems_limit = 0
    cfg.budget.gold_limit = 0
    assert validate_config(cfg) == (60, 2_000_000)


@pytest.mark.parametrize("attribute,value", [
    ("gems_limit", 61), ("gold_limit", 2_000_001),
    ("refresh_cost", 0), ("gold_available", -1)])
def test_invalid_budget(attribute, value):
    cfg = AppConfig()
    setattr(cfg.budget, attribute, value)
    with pytest.raises(BotError):
        validate_config(cfg)


def test_invalid_area_and_duplicates():
    cfg = AppConfig()
    cfg.calibration.safe_area = (.8, .4, .4, .9)
    with pytest.raises(BotError):
        validate_config(cfg)
    cfg.calibration.safe_area = (.72, .2, .79, .9)
    cfg.items[1].id = cfg.items[0].id
    with pytest.raises(BotError):
        validate_config(cfg)


def test_budget_no_overspend():
    state = RunState(gold_estimated=900_000, gems_estimated=27)
    assert not can_purchase(184_000, state, 1_000_000)
    assert can_refresh(3, state, 30)
    assert not can_refresh(4, state, 30)


def test_config_save_and_reload(tmp_path):
    path = tmp_path / "prefs.json"
    cfg = AppConfig()
    cfg.items[0].name = "Covenant"
    save_config(cfg, path)
    got = load_config(path)
    assert got.items[0].name == "Covenant"
    assert got.calibration.safe_area == (.72, .2, .79, .9)
    assert json.loads(path.read_text())["items"][0]["name"] == "Covenant"


def test_corrupt_config_is_not_overwritten(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(BotError):
        load_config(path)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_templates_never_overwrite_customized_image(tmp_path):
    src = tmp_path / "bundle" / "templates"
    src.mkdir(parents=True)
    (src / "renovar.png").write_bytes(b"original")
    cfg = AppConfig()
    cfg.templates_dir = str(tmp_path / "user" / "templates")
    target = prepare_templates(cfg, tmp_path / "bundle")
    assert (target / "renovar.png").read_bytes() == b"original"
    (target / "renovar.png").write_bytes(b"custom")
    prepare_templates(cfg, tmp_path / "bundle")
    assert (target / "renovar.png").read_bytes() == b"custom"

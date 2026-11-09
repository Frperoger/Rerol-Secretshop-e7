"""Language affects presentation and its own preference, never bot settings."""
import json

import pytest

from app.config import (data_directory, load_interface_language, save_config,
                        save_interface_language)
from app.models import AppConfig
from app.ui.translations import translate_text


def test_language_preference_is_separate_from_bot_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_interface_language() == "pt"
    save_config(AppConfig())
    config = data_directory() / "config.json"
    before = config.read_bytes()
    save_interface_language("en")
    assert load_interface_language() == "en"
    assert config.read_bytes() == before
    with pytest.raises(ValueError):
        save_interface_language("invalid")
    assert load_interface_language() == "en"


@pytest.mark.parametrize("payload", [None, [], {"language": "unknown"}, {"language": []}])
def test_invalid_preferences_fall_back_to_portuguese(monkeypatch, tmp_path, payload):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    folder = data_directory()
    folder.mkdir(parents=True)
    (folder / "interface.json").write_text(json.dumps(payload), encoding="utf-8")
    assert load_interface_language() == "pt"


def test_translation_preserves_user_names_paths_and_source_messages():
    source = "Compra enviada · Parar / ação · 184.000 de ouro estimados."
    assert translate_text(source, "en") == "Purchase sent · Parar / ação · 184,000 estimated gold."
    assert translate_text(source, "pt") == source
    assert translate_text("C:/Users/Nome/Orçamento.png", "en") == "C:/Users/Nome/Orçamento.png"
    message = "Não foi possível confirmar a renovação. Confira os itens e saldos no jogo antes de reiniciar."
    assert translate_text(message, "en") == "Could not confirm the refresh. Check the items and balances in the game before restarting."
    assert translate_text("Item 1 · Confirmação de preço · reconhecido (confiança 0.999).", "en") == "Item 1 · Price confirmation · Recognized (confidence 0.999)."

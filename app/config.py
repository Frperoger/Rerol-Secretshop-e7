"""Configuração persistente e cópia não destrutiva dos templates do repositório."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from app.models import AppConfig, BotError
from app.core.budget import validate_config


def data_directory() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".config") / "Epic7ShopBot"


def bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def config_path() -> Path:
    return data_directory() / "config.json"


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    validate_config(cfg)
    path = Path(path or config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(cfg.to_dict(), output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_config(path: Path | None = None) -> AppConfig:
    path = Path(path or config_path())
    if not path.exists():
        return AppConfig()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cfg = AppConfig.from_dict(payload)
        validate_config(cfg)
        return cfg
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, BotError) as exc:
        raise BotError(f"Configuração inválida em {path}: {exc}. Corrija ou faça backup do arquivo.") from exc


def user_templates(cfg: AppConfig | None = None) -> Path:
    if cfg is not None and cfg.templates_dir:
        return Path(cfg.templates_dir).expanduser().resolve()
    return data_directory() / "templates"


def prepare_templates(cfg: AppConfig, source_root: Path | None = None) -> Path:
    """Adiciona somente PNGs faltantes. Nunca sobrescreve gabaritos calibrados."""
    target = user_templates(cfg)
    target.mkdir(parents=True, exist_ok=True)
    root = Path(source_root or bundled_root())
    source = root / "templates"
    if source.exists() and source.resolve() != target.resolve():
        for original in source.glob("*.png"):
            dest = target / original.name
            if not dest.exists():
                shutil.copy2(original, dest)
    return target


def add_history(result: dict, path: Path | None = None) -> None:
    path = Path(path or (data_directory() / "history.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(result, ensure_ascii=False) + "\n")
        out.flush()
        os.fsync(out.fileno())


def read_history(path: Path | None = None, limit: int = 100) -> list[dict]:
    path = Path(path or (data_directory() / "history.jsonl"))
    if not path.exists():
        return []
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # isolamos registros individuais incompletos
    return results[-limit:][::-1]

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
from app.core.template_scale import MIN_SCALE, MAX_SCALE


def data_directory() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".config") / "Epic7ShopBot"


def bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def config_path() -> Path:
    return data_directory() / "config.json"


def load_interface_language() -> str:
    try:
        data = json.loads((data_directory() / "interface.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "pt"
    language = data.get("language") if isinstance(data, dict) else None
    return language if language in ("pt", "en") else "pt"


def save_interface_language(language: str) -> None:
    if language not in ("pt", "en"):
        raise ValueError("Idioma não suportado.")
    _write_json(data_directory() / "interface.json", {"language": language})


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    validate_config(cfg)
    _write_json(Path(path or config_path()), cfg.to_dict())


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _template_scale_path(key: str) -> Path:
    return data_directory() / "escalas_templates" / f"{key}.json"


def load_template_scale(key: str) -> float | None:
    try:
        value = json.loads(_template_scale_path(key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if type(value) in (int, float) and MIN_SCALE <= value <= MAX_SCALE else None


def save_template_scale(key: str, scale: float) -> None:
    if not MIN_SCALE <= scale <= MAX_SCALE:
        raise ValueError("Escala de template fora do intervalo de calibração.")
    _write_json(_template_scale_path(key), scale)


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
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # isolamos registros individuais incompletos
        if isinstance(record, dict):
            results.append(record)
    return results[-limit:][::-1]


def remove_history_rows(rows: set[int] | list[int], path: Path | None = None,
                        limit: int = 100) -> int:
    """Remove linhas visíveis no relatório, sem apagar registros antigos/ilegíveis.

    A tabela exibe as últimas ``limit`` entradas JSON válidas em ordem reversa.
    Mapeamos os índices visíveis às linhas físicas do arquivo e regravamos
    atomicamente o JSONL para manter todos os demais registros intactos.
    """
    path = Path(path or (data_directory() / "history.jsonl"))
    if not path.exists() or not rows:
        return 0
    selected = set(rows)
    if any(type(row) is not int or row < 0 for row in selected):
        raise ValueError("Seleção inválida do histórico.")
    raw_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    valid_physical_rows = []
    for index, raw in enumerate(raw_lines):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            valid_physical_rows.append(index)
    visible = valid_physical_rows[-limit:][::-1]
    to_delete = {visible[index] for index in selected if index < len(visible)}
    if not to_delete:
        return 0
    fd, temporary = tempfile.mkstemp(prefix=".history-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.writelines(line for index, line in enumerate(raw_lines)
                              if index not in to_delete)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(to_delete)


def clear_history(path: Path | None = None) -> int:
    """Exclui todo o histórico salvo; retorna a quantidade de registros JSON."""
    path = Path(path or (data_directory() / "history.jsonl"))
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    count = 0
    for line in lines:
        try:
            if isinstance(json.loads(line), dict):
                count += 1
        except json.JSONDecodeError:
            pass
    path.unlink()
    return count

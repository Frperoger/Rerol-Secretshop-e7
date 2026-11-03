"""Validação independente de Qt de atalhos de parada de emergência.

O atalho fixo ctrl+alt+q nunca é substituído por um personalizado.
"""
from __future__ import annotations
import re

DEFAULT_HOTKEY = "ctrl+alt+q"
_MOD = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift"}
_ORDER = ("ctrl", "alt", "shift")


def normalize_hotkey(text: str) -> str:
    """Recebe uma sequência única gerada pelo QKeySequenceEdit.

    Exige duas teclas modificadoras e uma tecla final A-Z, 0-9 ou F1-F12.
    Não permite combinações reservadas ou que possam parar o programa por engano.
    """
    from app.models import BotError
    raw = str(text).strip()
    if not raw or "," in raw:
        raise BotError("Grave apenas uma combinação de teclas, não uma sequência.")
    parts = [p.strip().lower() for p in raw.split("+")]
    if len(parts) < 3 or any(not p for p in parts):
        raise BotError("Use pelo menos dois modificadores (Ctrl/Alt/Shift) e uma tecla.")
    modifiers = parts[:-1]
    keys = parts[-1]
    if len(set(modifiers)) != len(modifiers) or any(p not in _MOD for p in modifiers):
        raise BotError("Modificadores inválidos ou repetidos. Use Ctrl, Alt ou Shift.")
    canonical = {_MOD[p] for p in modifiers}
    if len(canonical) < 2:
        raise BotError("O atalho deve combinar pelo menos dois modificadores.")
    if not (re.fullmatch(r"[a-z0-9]", keys) or
            re.fullmatch(r"f(?:[1-9]|1[0-2])", keys)):
        raise BotError("Escolha uma letra, número ou tecla F1–F12 para concluir o atalho.")
    if keys == "f4" and "alt" in canonical:
        raise BotError("Alt+F4 é reservado para fechar janelas. Escolha outra tecla.")
    return "+".join([*[m for m in _ORDER if m in canonical], keys])


def display_hotkey(text: str) -> str:
    return "+".join(p.upper() if p not in ("ctrl", "alt", "shift") else
                    p.capitalize() for p in normalize_hotkey(text).split("+"))


def select_hotkey_for_save(draft: str, active: str) -> tuple[str, bool]:
    """Não aplica uma gravação incompleta; conserva o atalho ativo válido.

    Retorna (atalho, manteve_anterior). Assim outras abas nunca exigem
    que o usuário termine uma captura de teclas ainda em andamento.
    """
    from app.models import BotError
    previous = normalize_hotkey(active)
    try:
        return normalize_hotkey(draft), False
    except BotError:
        return previous, True

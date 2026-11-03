"""Overlay Win32: captura excluída e sem ativação, mas botão clicável.

Não usamos WS_EX_TRANSPARENT: esse estilo faz o clique atravessar TODOS os
widgets, inclusive o botão de retorno. A região azul é separada da área verde
usada pelo bot; clique nela intencionalmente para abrir a janela principal.
"""
from __future__ import annotations
import ctypes
import sys
from ctypes import wintypes

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x80
WDA_EXCLUDEFROMCAPTURE = 0x11


def action_overlay_style(original: int) -> int:
    """Conserva outros estilos e torna o botão clicável sem roubar o foco."""
    return (original | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) & ~WS_EX_TRANSPARENT


def enable_action_overlay(hwnd: int) -> bool:
    """Aplica estilos e exclusão de captura; falha fechada se não suportado."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_long = user32.GetWindowLongPtrW
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_long.restype = ctypes.c_ssize_t
    set_long = user32.SetWindowLongPtrW
    set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    set_long.restype = ctypes.c_ssize_t
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    old = get_long(hwnd, GWL_EXSTYLE)
    expected = action_overlay_style(old)
    ctypes.set_last_error(0)
    set_long(hwnd, GWL_EXSTYLE, expected)
    if ctypes.get_last_error():
        return False
    active = get_long(hwnd, GWL_EXSTYLE)
    if (active & (WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)) != (WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW):
        return False
    if active & WS_EX_TRANSPARENT:
        return False

    # Sincroniza os estilos Win32 sem ativar ou reposicionar a janela.
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    if not user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER |
                                SWP_NOACTIVATE | SWP_FRAMECHANGED):
        return False
    return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))

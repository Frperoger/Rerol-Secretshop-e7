"""Win32: DPI físico, HWND de destino, foco e hit-test do ponto de clique."""
from __future__ import annotations
import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

from app.core.geometry import Rect
from app.models import BotError, FocusLost, WindowInvalid


def enable_dpi_awareness() -> None:
    """Executar ANTES de importar/inicializar a interface Qt no Windows.

    -4 é DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (não é o inteiro 2 de shcore).
    """
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)  # fallback: per-monitor V1
    except (AttributeError, OSError):
        pass


class Win32:
    def __init__(self):
        if sys.platform != "win32":
            raise BotError("A automação desktop requer Microsoft Windows.")
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.api.GetWindowRect.restype = wintypes.BOOL
        self.api.IsWindow.argtypes = [wintypes.HWND]
        self.api.IsWindow.restype = wintypes.BOOL
        self.api.IsWindowVisible.argtypes = [wintypes.HWND]
        self.api.IsWindowVisible.restype = wintypes.BOOL
        self.api.IsIconic.argtypes = [wintypes.HWND]
        self.api.IsIconic.restype = wintypes.BOOL
        self.api.GetForegroundWindow.restype = wintypes.HWND
        self.api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.api.GetAncestor.restype = wintypes.HWND
        self.api.WindowFromPoint.argtypes = [wintypes.POINT]
        self.api.WindowFromPoint.restype = wintypes.HWND
        self.api.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.api.GetWindowTextLengthW.restype = ctypes.c_int
        self.api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.api.GetWindowTextW.restype = ctypes.c_int
        self.api.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.api.SetForegroundWindow.restype = wintypes.BOOL
        self.api.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

    def title(self, hwnd: int) -> str:
        n = self.api.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        self.api.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def find(self, title: str) -> int:
        matches: list[tuple[int, str]] = []
        callback_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, unused):
            if self.api.IsWindowVisible(hwnd):
                name = self.title(hwnd)
                if title.casefold() in name.casefold():
                    matches.append((int(hwnd), name))
            return True

        cb = callback_t(callback)
        self.api.EnumWindows.argtypes = [callback_t, wintypes.LPARAM]
        self.api.EnumWindows(cb, 0)
        exact = [(h, t) for h, t in matches if t.casefold() == title.casefold()]
        options = exact or matches
        if not options:
            raise BotError(f"Janela '{title}' não encontrada. Abra o jogo antes de iniciar.")
        if len(options) > 1:
            raise BotError("Mais de uma janela corresponde ao título. Torne o título mais específico.")
        return options[0][0]

    def rect(self, hwnd: int) -> Rect:
        r = wintypes.RECT()
        if not self.api.GetWindowRect(hwnd, ctypes.byref(r)):
            raise WindowInvalid("Não foi possível ler o retângulo da janela.")
        return Rect(int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))

    def visible(self, hwnd: int) -> bool:
        return bool(self.api.IsWindow(hwnd) and self.api.IsWindowVisible(hwnd)
                    and not self.api.IsIconic(hwnd))

    def foreground(self) -> int:
        hwnd = self.api.GetForegroundWindow()
        return int(self.api.GetAncestor(hwnd, 2) or hwnd or 0)

    def hit_root(self, x: int, y: int) -> int:
        hwnd = self.api.WindowFromPoint(wintypes.POINT(x, y))
        return int(self.api.GetAncestor(hwnd, 2) or hwnd or 0)

    def activate(self, hwnd: int):
        if self.api.IsIconic(hwnd):
            self.api.ShowWindow(hwnd, 9)  # SW_RESTORE
        self.api.SetForegroundWindow(hwnd)


@dataclass
class TargetWindow:
    api: Win32
    hwnd: int
    initial_rect: Rect

    @classmethod
    def locate(cls, api: Win32, title: str):
        hwnd = api.find(title)
        api.activate(hwnd)
        return cls(api, hwnd, api.rect(hwnd))

    def ensure(self, x: int | None = None, y: int | None = None) -> Rect:
        if not self.api.visible(self.hwnd):
            raise WindowInvalid("Janela do jogo fechada, invisível ou minimizada.")
        current = self.api.rect(self.hwnd)
        if current != self.initial_rect:
            raise WindowInvalid("Janela do jogo foi movida ou redimensionada: execução interrompida.")
        if self.api.foreground() != self.hwnd:
            raise FocusLost("Foco fora da janela do jogo.")
        if x is not None and y is not None:
            if not current.contains(x, y):
                raise WindowInvalid("Ponto calculado fora da janela do jogo.")
            if self.api.hit_root(x, y) != self.hwnd:
                raise BotError("Outra janela está cobrindo o ponto de clique. Deixe a loja desobstruída.")
        return current

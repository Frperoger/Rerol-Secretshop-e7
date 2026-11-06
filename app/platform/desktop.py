"""Captura de pixels e entrada física; todas as ações passam pelo Guard HWND."""
from __future__ import annotations
import random
import time
from pathlib import Path
from typing import Callable

from app.config import load_template_scale
from app.core.geometry import choose_match_point, choose_safe_point
from app.core.template_scale import load_templates, resize_template, scale_key, template_filenames
from app.core.vision import best_match, detect, same_row
from app.models import AppConfig, BotError, UncertainAction
from app.platform.windows import TargetWindow, Win32


class DesktopIO:
    def __init__(self, config: AppConfig, templates_dir: Path,
                 stop_check: Callable[[], None], pause: Callable[[float, float], None], log: Callable):
        self.config = config
        self.templates_dir = Path(templates_dir)
        self.stop_check = stop_check
        self.pause = pause
        self.log = log
        self.api = None
        self.target = None
        self.templates = {}
        self._check_cached_scale = False

    def prepare(self):
        import cv2
        self.cv2 = cv2
        required, optional = template_filenames(self.config.items)
        missing = [f for f in sorted(required) if not (self.templates_dir / f).is_file()]
        if missing:
            self.log(f"Templates ausentes em {self.templates_dir}: {', '.join(missing)}", "error")
            raise BotError("Faltam imagens obrigatórias. Confira a pasta de templates na aba Itens.")
        templates, fingerprint = load_templates(self.templates_dir, required | optional)
        for filename in sorted((required | optional) - templates.keys()):
            if filename in optional and not (self.templates_dir / filename).is_file():
                self.log(f"Template opcional ausente: {filename}", "warn")
                continue
            raise BotError(f"Template PNG inválido: {filename}")
        self.api = Win32()
        self.target = TargetWindow.locate(self.api, self.config.calibration.window_title)
        self.log(f"Janela localizada: HWND={self.target.hwnd}", "info")
        rect = self.target.initial_rect
        scale = load_template_scale(scale_key(rect.width, rect.height, fingerprint))
        if scale is None:
            self.log(f"Janela de {rect.width} × {rect.height} sem escala salva. Usando os PNGs originais.", "info")
            self.templates = templates
        else:
            self.templates = {name: resize_template(frame, scale) for name, frame in templates.items()}
            self._check_cached_scale = True
            self.log(f"Escala de {scale:.0%} carregada para {rect.width} × {rect.height} pixels.", "info")

    def supports_item(self, item):
        return all(name in self.templates for name in (
            item.icon_template, item.buy_template, item.price_template))

    def ensure_focus(self):
        self.stop_check()
        self.target.ensure()

    def capture(self):
        import mss
        import numpy as np
        self.ensure_focus()
        rect = self.target.initial_rect
        with mss.mss() as sct:
            image = np.asarray(sct.grab({"left": rect.left, "top": rect.top,
                                          "width": rect.width, "height": rect.height}))
        self.ensure_focus()
        return self.cv2.cvtColor(image, self.cv2.COLOR_BGRA2BGR)

    def match(self, frame, name: str, roi=None):
        return detect(frame, self.templates[name], self.config.calibration.threshold, roi)

    def same_row(self, frame, name: str, icon):
        return same_row(frame, self.templates[name], icon,
                        self.config.calibration.threshold)

    def _click_absolute(self, x: int, y: int, *, transaction: bool = False) -> None:
        import pyautogui
        self.stop_check()
        self.target.ensure(x, y)
        # Preservamos explicitamente o fail-safe de canto de tela.
        pyautogui.FAILSAFE = True
        pyautogui.moveTo(x, y, duration=random.uniform(0.15, 0.35))
        self.pause(0.03, 0.08)
        self.target.ensure(x, y)  # checagem após movimento + hit-test de oclusão
        self.stop_check()
        try:
            try:
                pyautogui.mouseDown()
                self.pause(0.05, 0.12)
            finally:
                pyautogui.mouseUp()  # liberar inclusive se mouseDown/pause falhar
        except Exception as exc:
            if transaction:
                raise UncertainAction(f"Falha durante o clique em ({x}, {y}): {exc}") from exc
            if isinstance(exc, pyautogui.FailSafeException):
                raise BotError("FailSafe acionado: cursor em um canto da tela.") from exc
            raise
        self.log(f"Clique enviado em ({x}, {y}) na tela (mouseDown/mouseUp).", "info")

    def click_match(self, match, lower_half: bool = False):
        x, y = choose_match_point(self.target.initial_rect, match, lower_half)
        self._click_absolute(x, y, transaction=True)

    def click_safe(self):
        if self._check_cached_scale:
            if self.wait_match("renovar.png", self.config.calibration.modal_timeout) is None:
                raise BotError("A escala salva não reconheceu o botão Renovar. "
                               "Abra a loja sem diálogos e recalibre se o zoom tiver mudado.")
            self._check_cached_scale = False
        x, y = choose_safe_point(self.target.initial_rect, self.config.calibration.safe_area)
        self._click_absolute(x, y)

    def _scroll(self, amount: int):
        import pyautogui
        self.ensure_focus()
        rect = self.target.initial_rect
        x, y = rect.proportional(0.5, 0.5)
        self.target.ensure(x, y)
        pyautogui.moveTo(x, y, duration=0.08)
        self.target.ensure(x, y)
        self.stop_check()
        pyautogui.scroll(amount)

    def scroll_down(self):
        self._scroll(-250)

    def wait_match(self, template_name: str, timeout: float, present: bool = True):
        """Aguarda um template aparecer/desaparecer. Não faz cliques."""
        deadline = time.monotonic() + timeout
        threshold = self.config.calibration.threshold
        peak = None
        while True:
            self.stop_check()
            candidate = best_match(self.capture(), self.templates[template_name])
            found = candidate is not None and candidate.confidence >= threshold
            if found is present:
                return candidate if present else True
            if candidate is not None and (peak is None or candidate.confidence > peak):
                peak = candidate.confidence
            if time.monotonic() >= deadline:
                if present:
                    score = f"{peak:.3f}" if peak is not None else "sem comparação válida"
                    self.log(f"{template_name} não encontrado em {timeout:.1f}s "
                             f"(melhor confiança {score}, limiar {threshold:.3f}).", "warn")
                return None if present else False
            self.pause(0.12, 0.15)

    def try_purchase(self, item) -> bool:
        """Envia a compra até o clique final na confirmação de preço."""
        frame = self.capture()
        icon = self.match(frame, item.icon_template)
        if not icon:
            return False
        button = self.same_row(frame, item.buy_template, icon)
        if not button:
            self.log(f"[{item.name}] Ícone presente, botão não alinhado: ignorado.", "warn")
            return False
        self.log(f"[{item.name}] Ícone e botão localizados "
                 f"(ícone {icon.confidence:.2f}, botão {button.confidence:.2f}).", "info")
        committed = False
        try:
            self.click_match(button, item.lower_half)
            committed = True
            confirm_price = self.wait_match(item.price_template,
                                            self.config.calibration.modal_timeout)
            if confirm_price is None:
                raise UncertainAction("A confirmação de preço não foi reconhecida após o clique.")
            self.log(f"[{item.name}] Confirmação de preço reconhecida "
                     f"(confiança {confirm_price.confidence:.3f}).", "info")
            self.click_match(confirm_price)
            return True
        except Exception as exc:
            if committed or isinstance(exc, UncertainAction):
                raise UncertainAction(f"[{item.name}] Compra potencialmente enviada, sem confirmação: {exc}",
                                      operation=f"a compra de {item.name}") from exc
            raise

    def refresh(self) -> None:
        renew = self.wait_match("renovar.png", self.config.calibration.modal_timeout)
        if renew is None:
            raise BotError("Botão Renovar não encontrado na posição atual da loja. "
                           "Use Calibração > Diagnóstico para medir a confiança do renovar.png; "
                           "confira zoom, idioma e recorte da imagem.")
        committed = False
        try:
            self.click_match(renew)
            committed = True
            modal = self.wait_match("confirmar.png", self.config.calibration.modal_timeout)
            if modal is None:
                raise UncertainAction("Clique em renovar executado, mas modal de confirmação não apareceu.")
            self.click_match(modal)
            if not self.wait_match("confirmar.png", self.config.calibration.modal_timeout, present=False):
                raise UncertainAction("Modal de renovação permaneceu aberta; resultado desconhecido.")
            # É uma ação verificada visualmente, não um saldo de gemas observado.
        except Exception as exc:
            if committed or isinstance(exc, UncertainAction):
                raise UncertainAction(f"Renovação possivelmente enviada, sem confirmação: {exc}",
                                      operation="a renovação") from exc
            raise

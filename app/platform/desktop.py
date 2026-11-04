"""Captura de pixels e entrada física; todas as ações passam pelo Guard HWND."""
from __future__ import annotations
import random
import time
from pathlib import Path
from typing import Callable

from app.config import load_template_scale
from app.core.geometry import choose_match_point, choose_safe_point
from app.core.template_scale import load_templates, resize_template, scale_key, template_filenames
from app.core.vision import detect, same_row
from app.models import AppConfig, BotError, FocusLost, StopRequested, UncertainAction
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
            raise BotError("Templates ausentes em " + str(self.templates_dir) + ": " + ", ".join(missing))
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

    def match(self, frame, name: str):
        return detect(frame, self.templates[name], self.config.calibration.threshold)

    def same_row(self, frame, name: str, icon):
        return same_row(frame, self.templates[name], icon,
                        self.config.calibration.threshold)

    def _click_absolute(self, x: int, y: int) -> None:
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
        except pyautogui.FailSafeException as exc:
            raise BotError("FailSafe acionado: cursor em um canto da tela.") from exc
        self.log(f"Clique enviado em ({x}, {y}) na tela (mouseDown/mouseUp).", "info")

    def click_match(self, match, lower_half: bool = False):
        x, y = choose_match_point(self.target.initial_rect, match, lower_half)
        self._click_absolute(x, y)

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
        while True:
            self.stop_check()
            frame = self.capture()
            result = self.match(frame, template_name)
            if bool(result) is present:
                return result if present else True
            if time.monotonic() >= deadline:
                return None if present else False
            self.pause(0.12, 0.15)

    def try_purchase(self, item) -> bool:
        """Somente confirma compra quando a interface demonstrar mudança pós-transação.

        Nunca retorna sucesso apenas porque o mouse clicou. Após o primeiro clique,
        qualquer falha torna a operação INCERTA e obriga parar a execução.
        """
        frame = self.capture()
        icon = self.match(frame, item.icon_template)
        if not icon:
            return False
        button = self.same_row(frame, item.buy_template, icon)
        if not button:
            self.log(f"[{item.name}] Ícone presente, botão não alinhado: ignorado.", "warn")
            return False
        self.log(f"[{item.name}] Ícone e botão localizados (conf. {icon.confidence:.2f}).", "info")
        committed = False
        try:
            committed = True  # conservador: até cancelamento durante mouseDown torna o resultado incerto
            self.click_match(button, item.lower_half)
            confirm_price = self.wait_match(item.price_template,
                                            self.config.calibration.modal_timeout)
            if confirm_price is None:
                raise UncertainAction(f"[{item.name}] Modal de preço não apareceu após clicar.")
            self.click_match(confirm_price)
            deadline = time.monotonic() + self.config.calibration.modal_timeout
            stable_confirmations = 0
            generic_clicked = False
            while True:
                frame = self.capture()
                generic = self.match(frame, "confirmar.png")
                if generic is not None and not generic_clicked:
                    self.click_match(generic)
                    generic_clicked = True
                    stable_confirmations = 0
                    deadline = time.monotonic() + self.config.calibration.modal_timeout
                    continue
                if (generic is None and self.match(frame, item.price_template) is None
                        and self._purchase_visible(frame, item, icon)):
                    stable_confirmations += 1
                    if stable_confirmations >= 2:
                        return True
                else:
                    stable_confirmations = 0
                if time.monotonic() >= deadline:
                    break
                self.pause(0.12, 0.15)
            raise UncertainAction(f"[{item.name}] Estado pós-compra não verificável; pare e confira no jogo.")
        except (StopRequested, FocusLost, BotError) as exc:
            if committed:
                raise UncertainAction(f"[{item.name}] Compra potencialmente enviada, sem confirmação: {exc}") from exc
            raise

    def _purchase_visible(self, frame, item, original_icon):
        if item.sold_template in self.templates and self.match(frame, item.sold_template):
            return True
        # A linha continua visível e o botão de compra correspondente desapareceu.
        icon = self.match(frame, item.icon_template)
        return (icon is not None
                and abs(icon.y - original_icon.y) <= max(4, original_icon.height // 2)
                and self.same_row(frame, item.buy_template, icon) is None)

    def refresh(self) -> None:
        renew = self.wait_match("renovar.png", self.config.calibration.modal_timeout)
        if renew is None:
            raise BotError("Botão Renovar não encontrado na posição atual da loja. "
                           "Use Calibração > Diagnóstico para medir a confiança do renovar.png; "
                           "confira zoom, idioma e recorte da imagem.")
        committed = False
        try:
            committed = True  # pode haver cancelamento entre mouseDown e mouseUp
            self.click_match(renew)
            modal = self.wait_match("confirmar.png", self.config.calibration.modal_timeout)
            if modal is None:
                raise UncertainAction("Clique em renovar executado, mas modal de confirmação não apareceu.")
            self.click_match(modal)
            if not self.wait_match("confirmar.png", self.config.calibration.modal_timeout, present=False):
                raise UncertainAction("Modal de renovação permaneceu aberta; resultado desconhecido.")
            # É uma ação verificada visualmente, não um saldo de gemas observado.
        except (StopRequested, FocusLost, BotError) as exc:
            if committed:
                raise UncertainAction(f"Renovação possivelmente enviada, sem confirmação: {exc}") from exc
            raise

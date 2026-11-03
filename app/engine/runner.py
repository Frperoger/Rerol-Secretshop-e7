"""Orquestração determinística. Sem Qt, Win32 ou chamadas diretas de mouse."""
from __future__ import annotations
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.budget import can_purchase, can_refresh, validate_config
from app.models import (AppConfig, BotError, FocusLost, RunState, StopRequested,
                        UncertainAction, WindowInvalid)


def _noop(*args):
    pass


class BotRunner:
    def __init__(self, config: AppConfig, templates_dir: Path,
                 on_log: Callable = _noop, on_status: Callable = _noop,
                 on_finished: Callable = _noop, driver_factory=None):
        self.config = config
        self.templates_dir = Path(templates_dir)
        self.on_log, self.on_status, self.on_finished = on_log, on_status, on_finished
        self._driver_factory = driver_factory
        self.stop_event = threading.Event()
        self.state = RunState()
        self._lock = threading.Lock()
        self._running = False

    @property
    def is_running(self):
        with self._lock:
            return self._running

    def stop(self):
        self.stop_event.set()

    def check_stop(self):
        if self.stop_event.is_set():
            raise StopRequested()

    def pause(self, minimum: float, maximum: float | None = None):
        import random
        duration = random.uniform(minimum, minimum if maximum is None else maximum)
        if self.stop_event.wait(max(0.0, duration)):
            raise StopRequested()

    def log(self, message: str, level: str = "info"):
        severity = {"info": logging.INFO, "warn": logging.WARNING,
                    "error": logging.ERROR, "ok": logging.INFO}.get(level, logging.INFO)
        logging.getLogger("epic7shop").log(severity, message)
        self.on_log(message, level)

    def notify(self, status: str):
        self.state.status = status
        self.on_status(self.state.to_dict())

    def _await_focus(self, driver):
        self.notify("pausado_por_foco")
        self.log("Jogo perdeu foco ou há outra janela sobre ele. Nenhum clique será enviado.", "warn")
        waited = 0.0
        limit = self.config.calibration.focus_timeout
        while waited < limit:
            self.check_stop()
            try:
                driver.ensure_focus()
                self.log("Foco recuperado; reiniciando varredura da loja.", "info")
                self.notify("executando")
                return
            except FocusLost:
                self.pause(0.1)
                waited += 0.1
        raise BotError(f"Foco não retornou em {limit:.0f}s; operação encerrada.")

    def _scan_shop(self, driver, gold_limit: int):
        items = [it for it in self.config.items if it.enabled]
        driver.scroll_top()
        self.pause(0.05, 0.15)
        for scroll in range(self.config.calibration.max_scrolls + 1):
            self.check_stop()
            for item in items:
                self.check_stop()
                if item.id in self.state.purchased_in_rotation:
                    continue
                if not can_purchase(item.price_gold, self.state, gold_limit):
                    continue
                if driver.try_purchase(item):
                    self.state.purchased_in_rotation.add(item.id)
                    self.state.gold_estimated += item.price_gold
                    self.state.purchases_verified += 1
                    self.state.purchases_by_item[item.name] = (
                        self.state.purchases_by_item.get(item.name, 0) + 1)
                    self.log(f"[{item.name}] Compra verificada na interface; custo estimado {item.price_gold:,} ouro.", "ok")
                    self.notify("executando")
            if len(self.state.purchased_in_rotation) == len(items):
                break
            if scroll < self.config.calibration.max_scrolls:
                driver.scroll_down()
                self.pause(0.05, 0.15)

    def _loop(self, driver, gems_limit: int, gold_limit: int):
        enabled = [item for item in self.config.items if item.enabled]
        while True:
            self.check_stop()
            try:
                driver.ensure_focus()
                if not any(can_purchase(item.price_gold, self.state, gold_limit)
                           for item in enabled):
                    self.state.reason = "ouro insuficiente para todos os itens ativos"
                    return
                self.log("Procurando itens na loja atual…")
                driver.click_safe()
                self.pause(self.config.calibration.pause_min, self.config.calibration.pause_max)
                self._scan_shop(driver, gold_limit)
                self.check_stop()
                if not any(can_purchase(item.price_gold, self.state, gold_limit)
                           for item in enabled):
                    self.state.reason = "limite de ouro / saldo insuficiente"
                    return
                if not can_refresh(self.config.budget.refresh_cost, self.state, gems_limit):
                    self.state.reason = "limite de gemas para renovar"
                    return
                self.log("Solicitando renovação da loja…")
                driver.refresh()
                self.state.gems_estimated += self.config.budget.refresh_cost
                self.state.refreshes += 1
                self.state.purchased_in_rotation.clear()
                self.notify("executando")
                self.pause(1.0, 1.8)
            except FocusLost:
                self._await_focus(driver)
                # Não renovamos ou validamos compra após perder foco: nova varredura.
                continue

    def run(self) -> dict:
        with self._lock:
            if self._running:
                raise RuntimeError("Já existe uma execução ativa.")
            self._running = True
        self.state = RunState()
        try:
            limits = validate_config(self.config)
            self.notify("preparando")
            self.log("Conferindo templates e janela…")
            if self._driver_factory is None:
                from app.platform.desktop import DesktopIO
                factory = DesktopIO
            else:
                factory = self._driver_factory
            driver = factory(self.config, self.templates_dir, self.check_stop, self.pause, self.log)
            driver.prepare()
            self.log("Automação inicializa em 2 segundos. Mantenha a loja visível.")
            self.pause(2.0)
            self.notify("executando")
            self._loop(driver, *limits)
            self.state.status = "concluido"
        except StopRequested:
            self.state.status = "cancelado"
            self.state.reason = "cancelado pelo usuário"
        except UncertainAction as exc:
            self.state.uncertain_actions.append(str(exc))
            self.state.reason = "transação/renovação com resultado incerto; conferir saldos no jogo"
            self.state.status = "resultado_incerto"
            self.log(f"AÇÃO INCERTA: {exc}", "error")
        except (WindowInvalid, BotError) as exc:
            self.state.reason = str(exc)
            self.state.status = "erro"
            self.log(f"Execução interrompida: {exc}", "error")
        except Exception as exc:
            self.state.reason = f"falha inesperada: {type(exc).__name__}: {exc}"
            self.state.status = "erro"
            self.log(self.state.reason, "error")
        finally:
            self.state.finished_at = datetime.now().isoformat(timespec="seconds")
            self.notify(self.state.status)
            final = self.state.to_dict()
            self.on_finished(final)
            with self._lock:
                self._running = False
        return final

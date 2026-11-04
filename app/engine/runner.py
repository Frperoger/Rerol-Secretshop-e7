"""Orquestração determinística. Sem Qt, Win32 ou chamadas diretas de mouse."""
from __future__ import annotations
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.budget import can_purchase, can_refresh, validate_config
from app.logging_setup import log_diagnostic
from app.models import (AppConfig, BotError, FocusLost, RunState, StopRequested,
                        UncertainAction, WindowInvalid)


def _noop(*args):
    pass


class BotRunner:
    def __init__(self, config: AppConfig, templates_dir: Path,
                 on_log: Callable = _noop, on_status: Callable = _noop,
                 on_finished: Callable = _noop, driver_factory=None):
        self.config = deepcopy(config)
        self._live_lock = threading.RLock()
        self._live_budget = deepcopy(config.budget)
        self._reserved_gold = 0
        self._reserved_gems = 0
        self._active_items = {it.id: it.enabled for it in config.items}
        self.templates_dir = Path(templates_dir)
        self.on_log, self.on_status, self.on_finished = on_log, on_status, on_finished
        self._driver_factory = driver_factory
        self.stop_event = threading.Event()
        self._ui_pause_event = threading.Event()
        self._pause_ack = threading.Event()
        self.state = RunState()
        self._lock = threading.Lock()
        self._running = False
        self._driver = None

    @property
    def is_running(self):
        with self._lock:
            return self._running

    def update_budget(self, budget, *, persist=None):
        """Valida o teto contra os gastos já estimados e os valores reservados."""
        new_budget = deepcopy(budget)
        with self._live_lock:
            probe = deepcopy(self.config)
            probe.budget = new_budget
            gems, gold = validate_config(probe)
            if (gems < self.state.gems_estimated + self._reserved_gems or
                    gold < self.state.gold_estimated + self._reserved_gold):
                raise BotError("Novo limite inferior ao gasto estimado ou reservado na execução.")
            if new_budget.refresh_cost != self.config.budget.refresh_cost:
                raise BotError("Custo por renovação só pode ser alterado com o bot parado.")
            if persist is not None:
                persist()
            self._live_budget = new_budget
        self.log(f"Orçamento atualizado: gemas até {gems}; ouro até {gold}.", "info")

    def set_item_enabled(self, item_id: str, enabled: bool):
        with self._live_lock:
            if item_id not in self._active_items:
                raise BotError(f"Item desconhecido: {item_id}")
            item = next(it for it in self.config.items if it.id == item_id)
            if enabled and self._driver is not None and hasattr(self._driver, "supports_item"):
                if not self._driver.supports_item(item):
                    raise BotError(f"Templates de {item_id} não foram carregados. "
                                   "Corrija os PNGs e reinicie a execução.")
            self._active_items[item_id] = bool(enabled)
        self.log(f"Busca por {item_id}: {'ativada' if enabled else 'desativada'}. ")
        self.notify(self.state.status)

    def active_items(self):
        with self._live_lock:
            return [it for it in self.config.items if self._active_items.get(it.id, False)]

    def limits(self):
        with self._live_lock:
            b = self._live_budget
            return (b.gems_limit or b.gems_available, b.gold_limit or b.gold_available)

    def set_ui_paused(self, paused: bool):
        # Solicita uma pausa cooperativa; não anuncia pausa até o motor chegar
        # a um ponto seguro, pois abrir a UI durante um clique criaria incerteza.
        if paused:
            self._ui_pause_event.set()
        else:
            self._ui_pause_event.clear()

    def pause_acknowledged(self) -> bool:
        return self._pause_ack.is_set()

    def _wait_ui_resume(self):
        if self._ui_pause_event.is_set():
            self._pause_ack.set()
            self.notify("pausado_configuracao")
        while self._ui_pause_event.is_set():
            self.check_stop()
            self.stop_event.wait(0.15)
        if self._pause_ack.is_set():
            self._pause_ack.clear()
            self.notify("executando")

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

    def log(self, message: str, level: str = "info", *, activity: str | None = None):
        """Registra detalhes técnicos e envia à interface apenas avisos selecionados."""
        log_diagnostic(message, level)
        if activity is not None:
            self.on_log(activity, level)

    def notify(self, status: str):
        self.state.status = status
        self.on_status(self.state.to_dict())

    def _await_focus(self, driver):
        self.notify("pausado_por_foco")
        self.log("Jogo perdeu foco ou há outra janela sobre ele. Nenhum clique será enviado.", "warn",
                 activity="Bot pausado. Deixe a loja visível e volte ao jogo para continuar.")
        waited = 0.0
        limit = self.config.calibration.focus_timeout
        while waited < limit:
            self.check_stop()
            if self._ui_pause_event.is_set():
                self._wait_ui_resume()
                waited = 0.0
                self.notify("pausado_por_foco")
            try:
                driver.ensure_focus()
                self.log("Foco recuperado; reiniciando varredura da loja.",
                         activity="Bot retomado.")
                self.notify("executando")
                return
            except FocusLost:
                self.pause(0.1)
                waited += 0.1
        raise BotError(f"Foco não retornou em {limit:.0f}s; operação encerrada.")

    def _try_purchase(self, driver, item):
        with self._live_lock:
            if not self._active_items[item.id] or not can_purchase(
                    item.price_gold, self.state, self.limits()[1]):
                return False
            self._reserved_gold = item.price_gold

        purchased = False
        try:
            purchased = driver.try_purchase(item)
            return purchased
        finally:
            with self._live_lock:
                if purchased:
                    self.state.purchased_in_rotation.add(item.id)
                    self.state.gold_estimated += item.price_gold
                    self.state.purchases_verified += 1
                    self.state.purchases_by_item[item.name] = (
                        self.state.purchases_by_item.get(item.name, 0) + 1)
                self._reserved_gold = 0

    def _scan_shop(self, driver):
        for scroll in range(self.config.calibration.max_scrolls + 1):
            self.check_stop()
            self._wait_ui_resume()
            for item in self.active_items():
                self.check_stop()
                self._wait_ui_resume()
                if item.id in self.state.purchased_in_rotation:
                    continue
                if self._try_purchase(driver, item):
                    cost = f"{item.price_gold:,}".replace(",", ".")
                    self.log(f"[{item.name}] Compra verificada na interface; custo estimado {cost} ouro.", "ok",
                             activity=f"Compra confirmada: {item.name} · {cost} de ouro estimados.")
                    self.notify("executando")
            if not any(it.id not in self.state.purchased_in_rotation for it in self.active_items()):
                break
            if scroll < self.config.calibration.max_scrolls:
                self._wait_ui_resume()
                driver.scroll_down()
                self.pause(0.05, 0.15)

    def _try_refresh(self, driver):
        cost = self.config.budget.refresh_cost
        with self._live_lock:
            if not any(self._active_items.values()) or not can_refresh(
                    cost, self.state, self.limits()[0]):
                return False
            self._reserved_gems = cost

        refreshed = False
        try:
            self.log("Solicitando renovação da loja…")
            driver.refresh()
            refreshed = True
            return True
        finally:
            with self._live_lock:
                if refreshed:
                    self.state.gems_estimated += cost
                    self.state.refreshes += 1
                    self.state.purchased_in_rotation.clear()
                self._reserved_gems = 0

    def _loop(self, driver):
        while True:
            self.check_stop()
            self._wait_ui_resume()
            # Todos desativados: permanece aguardando sem clicar nem renovar.
            if not self.active_items():
                self.notify("pausado_sem_itens")
                self.pause(0.15)
                continue
            try:
                driver.ensure_focus()
                if not any(can_purchase(item.price_gold, self.state, self.limits()[1])
                           for item in self.active_items()):
                    self.state.reason = "O saldo ou limite de ouro não cobre o custo de nenhum item ativo."
                    return
                self.log("Procurando itens na loja atual…")
                driver.click_safe()
                self.pause(self.config.calibration.pause_min, self.config.calibration.pause_max)
                self._scan_shop(driver)
                self.check_stop()
                if not self.active_items():
                    continue
                if not any(can_purchase(item.price_gold, self.state, self.limits()[1])
                           for item in self.active_items()):
                    self.state.reason = "O saldo ou limite de ouro não permite novas compras."
                    return
                if not can_refresh(self.config.budget.refresh_cost, self.state, self.limits()[0]):
                    self.state.reason = "As gemas restantes no orçamento não cobrem outra renovação."
                    return
                self._wait_ui_resume()
                if not self._try_refresh(driver):
                    continue
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
        with self._live_lock:
            self.state = RunState()
        try:
            validate_config(self.config)
            self.notify("preparando")
            self.log("Conferindo templates e janela…")
            if self._driver_factory is None:
                from app.platform.desktop import DesktopIO
                factory = DesktopIO
            else:
                factory = self._driver_factory
            driver = factory(self.config, self.templates_dir, self.check_stop, self.pause, self.log)
            driver.prepare()
            self._driver = driver
            self.log("Automação inicializa em 3 segundos. Mantenha a loja visível.",
                     activity="O bot começa em 3 segundos. Deixe a loja visível.")
            self.pause(3.0)
            self.notify("executando")
            self._loop(driver)
            self.state.status = "concluido"
        except StopRequested:
            self.state.status = "cancelado"
            self.state.reason = "cancelado pelo usuário"
        except UncertainAction as exc:
            self.state.uncertain_actions.append(str(exc))
            self.state.reason = "transação/renovação com resultado incerto; conferir saldos no jogo"
            self.state.status = "resultado_incerto"
            self.log(f"AÇÃO INCERTA: {exc}", "error",
                     activity="A ação não pôde ser confirmada. Confira os itens e saldos no jogo antes de reiniciar.")
        except (WindowInvalid, BotError) as exc:
            self.state.reason = str(exc)
            self.state.status = "erro"
            self.log(f"Execução interrompida: {exc}", "error",
                     activity=f"O bot foi interrompido. {exc}")
        except Exception as exc:
            self.state.reason = f"falha inesperada: {type(exc).__name__}: {exc}"
            self.state.status = "erro"
            self.log(self.state.reason, "error",
                     activity="O bot parou por um erro inesperado. Consulte o log de diagnóstico.")
        finally:
            self.state.finished_at = datetime.now().isoformat(timespec="seconds")
            self.notify(self.state.status)
            final = self.state.to_dict()
            self.on_finished(final)
            with self._lock:
                self._running = False
        return final

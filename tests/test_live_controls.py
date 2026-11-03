"""Estados concorrentes, limites e ativação em execução (sem Qt/Windows)."""
import threading
import time
from pathlib import Path

import pytest

from app.engine.runner import BotRunner
from app.models import AppConfig, BotError, BudgetConfig


def no_pause(a, b=None):
    pass


def runner_with_fake(cfg=None):
    class Driver:
        def __init__(self, *args):
            self.purchases = []
            self.refreshes = 0
            self.calls = 0
        def prepare(self): pass
        def ensure_focus(self): pass
        def click_safe(self): pass
        def scroll_top(self): pass
        def scroll_down(self): pass
        def supports_item(self, item):
            return item.id != "item2"
        def try_purchase(self, item):
            self.purchases.append(item.id)
            return False
        def refresh(self):
            self.refreshes += 1
    created = []
    def factory(*args):
        driver = Driver(*args)
        created.append(driver)
        return driver
    runner = BotRunner(cfg or AppConfig(), Path("unused"), driver_factory=factory)
    runner.pause = lambda a,b=None: runner.check_stop()
    return runner, created


def test_can_change_budget_without_mutating_original_config():
    cfg = AppConfig()
    runner, _ = runner_with_fake(cfg)
    new_budget = BudgetConfig(gems_available=100, gold_available=3_000_000,
                              gems_limit=60, gold_limit=2_000_000, refresh_cost=3)
    runner.update_budget(new_budget)
    assert runner.limits() == (60, 2_000_000)
    assert cfg.budget.gems_limit == 30
    assert runner.config.budget.gems_limit == 30


def test_cannot_decrease_budget_below_estimated_spend():
    runner, _ = runner_with_fake()
    runner.state.gold_estimated = 700_000
    with pytest.raises(BotError, match="inferior"):
        runner.update_budget(BudgetConfig(gems_available=60, gold_available=1_000_000,
                                          gems_limit=30, gold_limit=500_000))
    assert runner.limits()[1] == 1_000_000


def test_cannot_change_refresh_cost_during_run():
    runner, _ = runner_with_fake()
    with pytest.raises(BotError, match="Custo"):
        runner.update_budget(BudgetConfig(refresh_cost=5))


def test_live_item_toggle_does_not_change_saved_config():
    runner, _ = runner_with_fake()
    runner.set_item_enabled("item1", False)
    assert [it.id for it in runner.active_items()] == ["item2"]
    assert runner.config.items[0].enabled is True
    runner.set_item_enabled("item1", True)
    assert [it.id for it in runner.active_items()] == ["item1", "item2"]


def test_runtime_enable_rejects_unloaded_template():
    runner, created = runner_with_fake()
    class OnlyItem1:
        def supports_item(self, item): return item.id == "item1"
    runner._driver = OnlyItem1()
    runner.set_item_enabled("item2", False)
    with pytest.raises(BotError, match="não foram carregados"):
        runner.set_item_enabled("item2", True)


def test_all_items_off_waits_without_refresh_then_stop():
    runner, created = runner_with_fake()
    runner.set_item_enabled("item1", False)
    runner.set_item_enabled("item2", False)
    # Stop cooperativo após a primeira iteração, sem clique/refresh.
    runner.pause = lambda *args: runner.stop()
    result = runner.run()
    assert result["status"] == "cancelado"
    assert created[0].purchases == []
    assert created[0].refreshes == 0


def test_pause_only_acknowledges_at_safe_boundary():
    runner, _ = runner_with_fake()
    runner.set_ui_paused(True)
    assert not runner.pause_acknowledged()
    done = threading.Event()
    def wait():
        runner._wait_ui_resume()
        done.set()
    thread = threading.Thread(target=wait)
    thread.start()
    for _ in range(100):
        if runner.pause_acknowledged():
            break
        time.sleep(.005)
    assert runner.pause_acknowledged()
    assert not done.is_set()
    runner.set_ui_paused(False)
    thread.join(timeout=2)
    assert done.is_set()
    assert not runner.pause_acknowledged()

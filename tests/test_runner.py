from pathlib import Path
from app.engine.runner import BotRunner
from app.models import AppConfig, FocusLost, UncertainAction


class FakeDesktop:
    def __init__(self, cfg, templates, check_stop, pause, log):
        self.cfg = cfg
        self.check_stop = check_stop
        self.refreshes = 0
        self.buys = 0
        self.scrolls = 0
        self.lost_focus_once = False
        self.fail_buy = False
        self.on_refresh = lambda: None
    def prepare(self): pass
    def ensure_focus(self):
        if self.lost_focus_once:
            self.lost_focus_once = False
            raise FocusLost("simulado")
    def click_safe(self): pass
    def scroll_down(self): self.scrolls += 1
    def try_purchase(self, item):
        if self.fail_buy:
            raise UncertainAction("modal faltante")
        self.buys += 1
        return self.buys == 1
    def refresh(self):
        self.refreshes += 1
        self.on_refresh()


def create_runner(cfg=None):
    factory_records = []
    def create(*args):
        driver = FakeDesktop(*args)
        factory_records.append(driver)
        return driver
    runner = BotRunner(cfg or AppConfig(), Path("unused"), driver_factory=create)
    runner.pause = lambda a, b=None: runner.check_stop()  # acelera apenas testes
    return runner, factory_records


def test_runner_purchase_and_stop_on_gems():
    cfg = AppConfig()
    cfg.budget.gems_available = 0
    cfg.budget.gems_limit = 0
    runner, records = create_runner(cfg)
    data = runner.run()
    assert data["status"] == "concluido"
    assert data["refreshes"] == 0
    assert data["purchases_verified"] == 1
    assert data["gold_estimated"] == 184_000
    assert records[0].refreshes == 0


def test_uncertain_action_stops_without_counting_purchase():
    runner, records = create_runner()
    def change_factory(*args):
        x = FakeDesktop(*args)
        x.fail_buy = True
        records.append(x)
        return x
    runner._driver_factory = change_factory
    data = runner.run()
    assert data["status"] == "resultado_incerto"
    assert data["purchases_verified"] == 0
    assert data["gold_estimated"] == 0
    assert len(data["uncertain_actions"]) == 1
    assert records[0].refreshes == 0


def test_focus_loss_resumes_before_any_action():
    cfg = AppConfig()
    cfg.budget.gems_available = 0
    cfg.budget.gems_limit = 0
    runner, records = create_runner(cfg)
    def factory(*args):
        x = FakeDesktop(*args)
        x.lost_focus_once = True
        records.append(x)
        return x
    runner._driver_factory = factory
    data = runner.run()
    assert data["status"] == "concluido"
    assert data["purchases_verified"] == 1


def test_cancel_does_not_lose_completed_refresh():
    runner, records = create_runner()
    def factory(*args):
        x = FakeDesktop(*args)
        x.on_refresh = runner.stop
        records.append(x)
        return x
    runner._driver_factory = factory
    result = runner.run()
    assert result["status"] == "cancelado"
    assert result["refreshes"] == 1
    assert result["gems_estimated"] == 3


def test_budget_stops_without_scanning_when_all_prices_unaffordable():
    cfg = AppConfig()
    cfg.budget.gold_available = 100_000
    cfg.budget.gold_limit = 100_000
    runner, records = create_runner(cfg)
    data = runner.run()
    assert data["status"] == "concluido"
    assert records[0].buys == 0
    assert records[0].refreshes == 0

import types
import sys
import pytest
from pathlib import Path
from app.core.geometry import buy_button_action_region
from app.core.vision import Match
from app.models import AppConfig, BotError, FocusLost, StopRequested, UncertainAction
from app.platform.desktop import DesktopIO


class StubTarget:
    def __init__(self):
        self.calls = 0
    def ensure(self, *args):
        self.calls += 1
        if self.calls >= 2:
            raise FocusLost("simulated focus lost after move")


def driver():
    return DesktopIO(AppConfig(), Path("."),
                     stop_check=lambda: None, pause=lambda a, b: None,
                     log=lambda *args: None)


def test_click_prevents_mouse_down_after_focus_loss(monkeypatch):
    moves, downs, ups = [], [], []
    api = types.SimpleNamespace(FAILSAFE=False,
        FailSafeException=RuntimeError,
        moveTo=lambda *args, **kw: moves.append(args),
        mouseDown=lambda: downs.append(1),
        mouseUp=lambda: ups.append(1))
    monkeypatch.setitem(sys.modules, "pyautogui", api)
    d = driver()
    d.target = StubTarget()
    with pytest.raises(FocusLost):
        d._click_absolute(15, 25)
    assert moves == [(15, 25)]
    assert downs == []
    assert ups == []
    assert api.FAILSAFE is True


def test_bought_item_needs_price_modal():
    d = driver()
    icon = types.SimpleNamespace(y=20, height=24, confidence=.96)
    buy = Match(50, 20, 35, 22, .96)
    d.capture = lambda: object()
    d.match = lambda frame, name: icon if name == "item1_icone.png" else None
    d.same_row = lambda frame, name, icon: buy
    d.click_match = lambda *args: None
    d.wait_match = lambda *args, **kwargs: None
    with pytest.raises(UncertainAction):
        d.try_purchase(d.config.items[0])


def test_wait_match_logs_best_confidence_when_modal_is_missing(monkeypatch):
    d = driver()
    name = d.config.items[0].price_template
    d.templates[name] = object()
    scores = iter([.72, .82, .64])
    elapsed = 0.0
    messages = []

    def pause(*_):
        nonlocal elapsed
        elapsed += 0.125

    d.capture = lambda: Match(20, 15, 50, 30, next(scores))
    d.pause = pause
    d.log = lambda message, level: messages.append((message, level))
    monkeypatch.setattr("app.platform.desktop.time.monotonic", lambda: elapsed)
    monkeypatch.setattr("app.platform.desktop.best_match", lambda frame, _template: frame)
    assert d.wait_match(name, .25) is None
    assert len(messages) == 1
    message, level = messages[0]
    assert level == "warn"
    assert name in message and "melhor confiança 0.820, limiar 0.830" in message


def test_refresh_must_observe_confirmation_modal():
    d = driver()
    d.wait_match = lambda name, timeout, present=True: object() if name == "renovar.png" else None
    d.click_match = lambda *args: None
    with pytest.raises(UncertainAction) as exc:
        d.refresh()
    assert exc.value.operation == "a renovação"


@pytest.mark.parametrize("error", [FocusLost, BotError])
def test_refresh_blocked_before_click_preserves_guard_error(error):
    d = driver()
    d.wait_match = lambda *_: object()
    d.click_match = lambda *_: (_ for _ in ()).throw(error("alvo bloqueado"))
    with pytest.raises(error, match="bloqueado") as exc:
        d.refresh()
    assert type(exc.value) is error


def test_sent_click_logs_coordinates_after_button_release(monkeypatch):
    events = []
    api = types.SimpleNamespace(
        FAILSAFE=False, FailSafeException=RuntimeError,
        moveTo=lambda *args, **kwargs: None,
        mouseDown=lambda: events.append("down"),
        mouseUp=lambda: events.append("up"),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", api)
    d = driver()
    d.target = types.SimpleNamespace(ensure=lambda *args: None)
    d.log = lambda message, level: events.append(message)
    d._click_absolute(15, 25)
    assert events[:2] == ["down", "up"]
    assert "(15, 25)" in events[2]


@pytest.mark.parametrize("transaction", [False, True])
def test_cancel_mid_click_releases_mouse_button(monkeypatch, transaction):
    state = {"down": False, "up": False}
    class FakeTarget:
        def ensure(self, *args): pass
    def pause(a, b):
        if state["down"]:
            raise StopRequested()
    api = types.SimpleNamespace(FAILSAFE=False,
        FailSafeException=RuntimeError, moveTo=lambda *a, **kw: None,
        mouseDown=lambda: state.__setitem__("down", True),
        mouseUp=lambda: state.__setitem__("up", True))
    monkeypatch.setitem(sys.modules, "pyautogui", api)
    d = DesktopIO(AppConfig(), Path("."), lambda: None, pause, lambda *args: None)
    d.target = FakeTarget()
    with pytest.raises(UncertainAction if transaction else StopRequested):
        d._click_absolute(30, 40, transaction=transaction)
    assert state == {"down": True, "up": True}


def test_purchase_returns_immediately_after_final_click():
    d = driver()
    icon = Match(5, 20, 24, 24, .96)
    button = Match(50, 20, 35, 22, .96)
    price = Match(60, 40, 40, 28, .97)
    action_region = buy_button_action_region(button)
    item = d.config.items[0]
    snapshots = iter([object()])
    clicks = []

    def wait(name, timeout):
        assert name == item.price_template
        assert clicks == [(action_region, False)]
        return price

    d.capture = lambda: next(snapshots)
    d.match = lambda frame, name: icon if name == item.icon_template else None
    d.same_row = lambda *_: button
    d.click_match = lambda match, lower_half=False: clicks.append((match, lower_half))
    d.wait_match = wait
    assert d.try_purchase(item) is True
    assert clicks == [(action_region, False), (price, False)]


def test_cached_scale_must_recognize_renew_before_any_input():
    d = driver()
    d._check_cached_scale = True
    d.wait_match = lambda *_: None
    with pytest.raises(BotError, match="escala salva"):
        d.click_safe()
    assert d._check_cached_scale


def test_focus_loss_after_action_is_uncertain():
    d = driver()
    icon = types.SimpleNamespace(y=20, height=24, confidence=.96)
    d.capture = lambda: object()
    d.match = lambda frame, name: icon if name == "item1_icone.png" else None
    d.same_row = lambda *args: Match(50, 20, 35, 22, .96)
    d.click_match = lambda *args: None
    d.wait_match = lambda *args: (_ for _ in ()).throw(FocusLost("alt-tab"))
    with pytest.raises(UncertainAction):
        d.try_purchase(d.config.items[0])

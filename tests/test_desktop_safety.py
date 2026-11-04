import types
import sys
import pytest
from pathlib import Path
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
    buy = object()
    d.capture = lambda: object()
    d.match = lambda frame, name: icon if name == "item1_icone.png" else None
    d.same_row = lambda frame, name, icon: buy
    d.click_match = lambda *args: None
    d.wait_match = lambda *args, **kwargs: None
    with pytest.raises(UncertainAction):
        d.try_purchase(d.config.items[0])


def test_refresh_must_observe_confirmation_modal():
    d = driver()
    d.wait_match = lambda name, timeout, present=True: object() if name == "renovar.png" else None
    d.click_match = lambda *args: None
    with pytest.raises(UncertainAction):
        d.refresh()


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


def test_cancel_mid_click_releases_mouse_button(monkeypatch):
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
    with pytest.raises(StopRequested):
        d._click_absolute(30, 40)
    assert state == {"down": True, "up": True}


def test_purchase_requires_stable_post_transaction_evidence():
    d = driver()
    icon = types.SimpleNamespace(y=20, height=24, confidence=.96)
    price = object()
    counts = {"captures": 0, "clicks": 0, "buy_lookups": 0}
    def capture():
        counts["captures"] += 1
        return object()
    def match(frame, name):
        return icon if name == "item1_icone.png" else None
    def aligned(frame, name, item_icon):
        counts["buy_lookups"] += 1
        return object() if counts["buy_lookups"] == 1 else None
    def wait(name, *args, **kwargs):
        return price if name == "item1_comprar_preco.png" else None
    d.capture = capture
    d.match = match
    d.same_row = aligned
    d.click_match = lambda *args: counts.__setitem__("clicks", counts["clicks"] + 1)
    d.wait_match = wait
    assert d.try_purchase(d.config.items[0]) is True
    assert counts["clicks"] == 2
    assert counts["captures"] >= 3


@pytest.mark.parametrize("dialog", ["absent", "closes", "stuck"])
def test_purchase_polls_for_optional_dialog_and_result_together(monkeypatch, dialog):
    d = driver()
    item = d.config.items[0]
    icon = types.SimpleNamespace(y=20, height=24, confidence=.96)
    buy, price, generic = object(), object(), object()
    clicks, waits = [], []
    elapsed = 0.0

    def pause(a, b):
        nonlocal elapsed
        waits.append((a, b))
        elapsed += (a + b) / 2

    def match(frame, name):
        if name == item.icon_template:
            return icon
        if name == item.price_template and clicks == [buy]:
            return price
        if name == "confirmar.png" and (clicks == [buy, price] or
                                       (clicks == [buy, price, generic] and dialog == "stuck")):
            return generic if dialog != "absent" else None
        return None

    monkeypatch.setattr("app.platform.desktop.time.monotonic", lambda: elapsed)
    d.pause = pause
    d.capture = object
    d.match = match
    d.same_row = lambda *_: None if clicks else buy
    d.click_match = lambda match, *_: clicks.append(match)
    if dialog == "stuck":
        with pytest.raises(UncertainAction):
            d.try_purchase(item)
    else:
        assert d.try_purchase(item)
        # Duas capturas estáveis separadas por uma pausa de polling.
        assert waits == [(0.12, 0.15)]
    assert clicks == ([buy, price] if dialog == "absent" else [buy, price, generic])


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
    d.same_row = lambda *args: object()
    d.click_match = lambda *args: (_ for _ in ()).throw(FocusLost("alt-tab"))
    with pytest.raises(UncertainAction):
        d.try_purchase(d.config.items[0])

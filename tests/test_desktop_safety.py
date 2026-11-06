import types
import sys
import pytest
import cv2
import numpy as np
from pathlib import Path
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


def test_purchase_requires_stable_post_transaction_evidence():
    d = driver()
    icon = Match(5, 20, 24, 24, .96)
    button = Match(50, 20, 35, 22, .96)
    price = Match(60, 40, 40, 28, .97)
    counts = {"captures": 0, "clicks": 0, "buy_lookups": 0}
    def capture():
        counts["captures"] += 1
        return object()
    def match(frame, name, roi=None):
        return icon if name == "item1_icone.png" else None
    def aligned(frame, name, item_icon):
        counts["buy_lookups"] += 1
        return button if counts["buy_lookups"] == 1 else None
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
    icon = Match(5, 20, 24, 24, .96)
    buy = Match(50, 20, 35, 22, .96)
    price = Match(60, 40, 40, 28, .97)
    generic = object()
    clicks, waits = [], []
    elapsed = 0.0

    def pause(a, b):
        nonlocal elapsed
        waits.append((a, b))
        elapsed += (a + b) / 2

    def match(frame, name, roi=None):
        if name == item.icon_template:
            return icon
        if name == "confirmar.png" and (clicks == [buy, price] or
                                       (clicks == [buy, price, generic] and dialog == "stuck")):
            return generic if dialog != "absent" else None
        return None

    monkeypatch.setattr("app.platform.desktop.time.monotonic", lambda: elapsed)
    monkeypatch.setattr("app.platform.desktop.best_match", lambda *_: price if clicks == [buy] else None)
    d.templates[item.price_template] = object()
    d.pause = pause
    d.capture = object
    d.match = match
    d.same_row = lambda *_: None if clicks else buy
    d.click_match = lambda match, *_: clicks.append(match)
    if dialog == "stuck":
        with pytest.raises(UncertainAction) as exc:
            d.try_purchase(item)
        assert exc.value.operation == "a compra de Item 1"
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
    d.same_row = lambda *args: Match(50, 20, 35, 22, .96)
    d.click_match = lambda *args: None
    d.wait_match = lambda *args: (_ for _ in ()).throw(FocusLost("alt-tab"))
    with pytest.raises(UncertainAction):
        d.try_purchase(d.config.items[0])


def test_post_purchase_uses_original_row_and_recognizes_disabled_button():
    d = driver()
    item = d.config.items[0]
    templates = Path(__file__).resolve().parents[1] / "templates"
    for name in (item.icon_template, item.buy_template):
        d.templates[name] = cv2.imread(str(templates / name))
    rng = np.random.default_rng(41)
    before = rng.integers(0, 25, (560, 850, 3), dtype=np.uint8)
    for name, (x, y) in ((item.icon_template, (40, 45)), (item.buy_template, (510, 50))):
        template = d.templates[name]
        h, w = template.shape[:2]
        before[y:y+h, x:x+w] = template
    icon = d.match(before, item.icon_template)
    buy = d.same_row(before, item.buy_template, icon)
    assert icon is not None and buy is not None
    assert not d._purchase_visible(before, before, item, icon, buy, False)

    after = before.copy()
    other_y = 310
    after[other_y:other_y+icon.height, icon.x:icon.x+icon.width] = d.templates[item.icon_template]
    after[icon.y, icon.x] = (255, 255, 255)
    button = after[buy.y:buy.y+buy.height, buy.x:buy.x+buy.width]
    gray = cv2.cvtColor(button[buy.height // 2:], cv2.COLOR_BGR2GRAY)
    button[buy.height // 2:] = gray[:, :, None]
    assert d.match(after, item.icon_template).y == other_y
    assert d._nearby_match(after, item.buy_template, buy) is not None
    assert d._purchase_visible(before, after, item, icon, buy, False)

    # O botão cinza sozinho é insuficiente se a loja inteira tiver escurecido.
    original_row_icon = after[icon.y:icon.y+icon.height, icon.x:icon.x+icon.width]
    original_row_icon[:] = (original_row_icon * 0.5).astype(np.uint8)
    assert d._nearby_match(after, item.icon_template, icon) is not None
    assert not d._purchase_visible(before, after, item, icon, buy, False)

    after[icon.y:icon.y+icon.height, icon.x:icon.x+icon.width] = 0
    assert not d._purchase_visible(before, after, item, icon, buy, False)

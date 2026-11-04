"""Exercise the QML entry point and its connections without clicking the game."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
pytest.importorskip("PySide6.QtQuick")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import add_history, load_config, read_history
from app.core.geometry import Rect
from app.ui.quick_window import QuickWindow


def visual_item(parent, name):
    if parent.objectName() == name:
        return parent
    for child in parent.childItems():
        found = visual_item(child, name)
        if found is not None:
            return found
    return None


def click(window, name):
    item = visual_item(window.contentItem(), name)
    assert item is not None and item.isVisible() and item.isEnabled()
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)


@pytest.fixture
def quick(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    windows_font = Path("C:/Windows/Fonts/segoeui.ttf")
    if windows_font.is_file():
        QFontDatabase.addApplicationFont(str(windows_font))
    window = QuickWindow()
    try:
        window.show()
        app.processEvents()
        yield window
    finally:
        window.dispose()


def test_budget_input_saves_and_updates_the_bot_view(quick):
    window = quick.quick_window
    click(window, "tab2")
    assert quick.page == 2
    editor = visual_item(window.contentItem(), "gems_limitField")
    assert editor.property("text") == "30"
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_4)
    QTest.keyClick(window, Qt.Key.Key_1)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert load_config().budget.gems_limit == 41
    assert quick.info["gemText"] == "Gemas estimadas: 0 / 41"


def test_calibration_panels_stay_side_by_side_and_drag_updates_fields(quick):
    window = quick.quick_window
    window.resize(780, 560)
    QTest.qWait(20)
    click(window, "tab3")
    QTest.qWait(30)
    root = window.contentItem()
    detection = visual_item(root, "detectionCard")
    safe = visual_item(root, "safeAreaCard")
    first = detection.mapToScene(QPointF())
    second = safe.mapToScene(QPointF())
    assert first.y() == second.y()
    assert first.x() + detection.width() < second.x()
    assert second.x() + safe.width() <= window.width()
    outline = visual_item(root, "safeAreaOutline")
    point = outline.mapToScene(QPointF(outline.width() / 2, outline.height() / 2)).toPoint()
    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    QTest.mouseMove(window, point + QPoint(13, -10))
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       point + QPoint(13, -10))
    assert quick.calibration["safeArea"][0] > 0.72
    assert quick.area_fields["y0"].value() < 0.20
    quick.recordKey(int(Qt.Key.Key_E), Qt.KeyboardModifier.ControlModifier.value |
                    Qt.KeyboardModifier.AltModifier.value)
    assert quick.calibration["hotkey"] == "Ctrl+Alt+E"


def test_compact_overlay_returns_after_safe_pause(quick, monkeypatch):
    quick.tray.hide()
    quick.setCompact(True)
    pauses, protected = [], []
    runner = SimpleNamespace(pause_acknowledged=lambda: True)
    fake = SimpleNamespace(running=False, runner=runner, set_ui_paused=pauses.append)
    fake.start = lambda *_: setattr(fake, "running", True)
    quick.controller = fake
    monkeypatch.setattr(quick, "_register_hotkey", lambda: None)
    monkeypatch.setattr("app.platform.windows.Win32", lambda: SimpleNamespace(
        find=lambda _title: 1, rect=lambda _hwnd: Rect(0, 0, 1600, 900)))
    monkeypatch.setattr("app.platform.passive_overlay.enable_action_overlay",
                        lambda hwnd: protected.append(hwnd) or True)
    click(quick.quick_window, "startBot")
    assert quick.info["running"]
    assert quick.isMinimized()
    quick.update_metrics({"status": "executando", "refreshes": 3})
    assert protected and quick.overlay.isVisible()
    click(quick.overlay.window, "returnToApp")
    assert pauses == [True]
    assert quick.isVisible() and not quick.isMinimized()
    assert not quick.overlay.isVisible()


def test_qml_item_and_history_actions_reuse_saved_data(quick, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    add_history({"started_at": "primeira", "reason": "exemplo"})
    add_history({"started_at": "segunda", "reason": "exemplo"})
    quick._update_history()
    assert len(quick.history) == 2
    quick.deleteHistory([0])
    assert [record["started_at"] for record in read_history()] == ["primeira"]
    quick.toggleItem(0, False)
    assert not quick.items[0]["enabled"]
    quick.action("addItem")
    assert len(quick.items) == 3
    quick.editItem(2, "name", "Novo item")
    assert quick.items[2]["name"] == "Novo item"
    quick.removeItem(2)
    assert len(quick.items) == 2


def test_item_cards_are_compact_and_show_gold_next_to_price(quick):
    window = quick.quick_window
    click(window, "tab1")
    root = window.contentItem()
    first = visual_item(root, "itemCard0")
    second = visual_item(root, "itemCard1")
    assert first.width() <= 460 and second.width() <= 460
    assert first.mapToScene(QPointF()).y() == second.mapToScene(QPointF()).y()
    assert visual_item(first, "goldFieldIcon").property("source").toString() == "image://shop/gold"
    window.resize(780, 560)
    QTest.qWait(30)
    assert first.width() <= 460
    assert first.mapToScene(QPointF()).y() < second.mapToScene(QPointF()).y()


def test_activity_feed_keeps_message_level_and_can_be_copied(quick):
    feed = visual_item(quick.quick_window.contentItem(), "activityLog")
    initial = feed.property("count")
    assert initial == 0
    for number in range(18):
        quick.append_log(f"Evento {number}", "warn")
    QTest.qWait(30)
    assert feed.property("count") == initial + 18
    assert feed.property("atYEnd")
    model = quick.activity
    entry = model.item(model.rowCount() - 1)
    assert entry.data(model.MESSAGE) == "Evento 17"
    assert entry.data(model.LEVEL) == "warn"
    quick.copyActivity()
    assert "[WARN]  Evento 17" in QApplication.clipboard().text()

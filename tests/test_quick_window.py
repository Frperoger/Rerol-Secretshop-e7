"""Exercise the QML entry point and its connections without clicking the game."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
pytest.importorskip("PySide6.QtQuick")

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import add_history, load_config, load_interface_language, read_history
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


def test_language_selector_translates_live_without_changing_session_data(quick):
    window = quick.quick_window
    selector = visual_item(window.contentItem(), "languageSelector")
    assert visual_item(window.contentItem(), "startBot").property("contentItem").property("text") == "Iniciar"
    quick.editItem(0, "name", "Parar / Minha gema")
    state = {"status": "executando", "purchases_sent": 1003,
             "purchases_by_item": {"Parar / Minha gema": 1003}}
    quick.update_metrics(state)
    quick.append_log("O bot começa em 3 segundos. Deixe a loja visível.")
    quick._set_running(True)
    before = quick.budget.copy()
    click(window, "languageSelector")
    QTest.keyClick(window, Qt.Key.Key_End)
    QTest.keyClick(window, Qt.Key.Key_Return)
    QTest.qWait(30)
    assert quick.language.code == "en" and load_interface_language() == "en"
    assert selector.property("currentIndex") == 1
    assert visual_item(window.contentItem(), "tab1").property("text") == "Items"
    assert quick.info["status"] == "●  RUNNING"
    assert quick.info["gemText"] == "Estimated gems: 0 / 30"
    assert quick.info["metrics"]["purchases_sent"] == "1,003"
    assert quick.items[0]["name"] == "Parar / Minha gema"
    assert quick.budget == before and quick._metric_state == state
    assert quick.info["running"]
    assert quick.activity.data(quick.activity.index(0, 0), quick.activity.MESSAGE).startswith("The bot starts")
    quick.copyActivity()
    assert "The bot starts" in QApplication.clipboard().text()
    click(window, "tab2")
    QTest.qWait(20)
    gold = visual_item(window.contentItem(), "gold_limitField")
    assert gold.property("text") == "1,000,000"
    gold.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    for character in "750,000":
        QTest.keyClick(window, Qt.Key(ord(character)))
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert load_config().budget.gold_limit == 750000
    before["gold_limit"] = 750000
    quick.language.setLanguage("pt")
    QTest.qWait(20)
    assert gold.property("text") == "750.000"
    assert quick.info["status"] == "●  EM EXECUÇÃO"
    assert visual_item(window.contentItem(), "tab1").property("contentItem").property("text") == "Itens"
    assert quick.budget == before and quick._metric_state == state


def test_saved_language_is_loaded_and_validation_messages_are_translated(quick):
    quick.language.setLanguage("en")
    reopened = QuickWindow()
    try:
        assert reopened.language.code == "en"
        assert reopened.info["status"] == "●  STOPPED"
        assert "No run" in reopened.info["report"]
        reopened.editBudget("gems_limit", 61)
        assert reopened.info["budgetNotice"] == "✗ Previous budget still in use. The spending limit cannot exceed the available balance."
        assert load_config().budget.gems_limit == 30
    finally:
        reopened.dispose()


def test_english_dialogs_translate_prompts_and_preserve_history(quick, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    quick.language.setLanguage("en")
    add_history({"started_at": "example", "reason": "cancelado pelo usuário", "purchases_sent": 3})
    quick._update_history()
    prompts = []
    def refuse(parent, title, text, *args):
        prompts.append((title, text))
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "question", refuse)
    quick.deleteHistory([0])
    assert prompts[0] == ("Confirm deletion", "Delete 1 selected session(s) from history?\nThis cannot be undone.")
    assert len(read_history()) == 1
    assert quick.history[0][5] == "cancelled by the user"
    captions = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda parent, caption, directory, filter: captions.append((caption, filter)) or ("", ""))
    quick.pick_capture()
    assert captions == [("Shop PNG capture", "PNG images (*.png)")]


def test_donates_has_square_cards_and_pix_logo_copies_payment_code(quick):
    window = quick.quick_window
    click(window, "tab5")
    assert quick.page == 5
    page = visual_item(window.contentItem(), "donatesPage")
    assert page.isVisible()
    assert page.property("koFiUrl") == "https://ko-fi.com/frperoger"
    assert not visual_item(page, "PayPalLogo").isEnabled()
    for name in ("Ko-fi", "PayPal", "Pix · Brasil"):
        card = visual_item(page, name + "Card")
        assert card.width() == card.height()
    click(window, "Pix · BrasilLogo")
    assert QApplication.clipboard().text() == page.property("pixCode")
    assert "Código Pix copiado" in page.property("feedback")


def test_donation_buttons_fit_the_square_cards_at_minimum_width(quick):
    window = quick.quick_window
    window.resize(window.minimumWidth(), window.minimumHeight())
    QTest.qWait(20)
    click(window, "tab5")
    QTest.qWait(30)
    page = visual_item(window.contentItem(), "donatesPage")
    for name in ("Ko-fi", "PayPal", "Pix · Brasil"):
        card = visual_item(page, name + "Card")
        button = visual_item(card, name + "Action")
        top_left = button.mapToItem(card, QPointF())
        bottom_right = button.mapToItem(card, QPointF(button.width(), button.height()))
        assert 0 < top_left.x() < bottom_right.x() < card.width()
        assert 0 < top_left.y() < bottom_right.y() < card.height()
        label = button.property("contentItem")
        assert label.property("paintedWidth") <= label.width()
        assert label.property("paintedHeight") <= label.height()

    click(window, "Pix · BrasilAction")
    assert QApplication.clipboard().text() == page.property("pixCode")


@pytest.mark.parametrize("size", [(1110, 760), (780, 560)])
@pytest.mark.parametrize("language", ["pt", "en"])
def test_pix_qr_can_be_scanned_on_screen_and_matches_the_copied_code(quick, size, language):
    import cv2
    import numpy as np

    window = quick.quick_window
    quick.language.setLanguage(language)
    window.resize(*size)
    QTest.qWait(20)
    click(window, "tab5")
    QTest.qWait(20)
    click(window, "Pix · BrasilQr")
    QTest.qWait(40)
    dialog = window.findChild(QObject, "pixQrDialog")
    assert dialog.property("visible")
    assert 0 <= dialog.property("x")
    assert 0 <= dialog.property("y")
    assert dialog.property("x") + dialog.property("width") <= window.width()
    assert dialog.property("y") + dialog.property("height") <= window.height()

    # Decode the rendered image so scaling or clipping cannot silently break Pix.
    qr = visual_item(window.contentItem(), "pixQrFrame")
    point = qr.mapToScene(QPointF())
    capture = window.grabWindow()
    ratio = capture.width() / window.width()
    pixels = capture.copy(QRect(round(point.x() * ratio), round(point.y() * ratio),
                                round(qr.width() * ratio), round(qr.height() * ratio)))
    pixels = pixels.convertToFormat(QImage.Format.Format_RGB888)
    rows = np.frombuffer(pixels.bits(), dtype=np.uint8).reshape(pixels.height(), pixels.bytesPerLine())
    rgb = rows[:, :pixels.width() * 3].reshape(pixels.height(), pixels.width(), 3)
    code, _, _ = cv2.QRCodeDetector().detectAndDecode(rgb)
    page = visual_item(window.contentItem(), "donatesPage")
    assert code and code == page.property("pixCode")
    click(window, "copyPixFromQr")
    assert QApplication.clipboard().text() == code
    click(window, "closePixQr")
    assert not dialog.property("visible")


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


def test_purchase_counters_update_together_and_reset_for_a_new_run(quick):
    bot = visual_item(quick.quick_window.contentItem(), "botPurchases")
    compact = visual_item(quick.overlay.window.contentItem(), "compactPurchases")
    first, second = [item["name"].strip() for item in quick.items]
    quick.update_metrics({"purchases_sent": 1003,
                          "purchases_by_item": {first: 1000, second: 3}})
    QTest.qWait(20)

    for panel in (bot, compact):
        assert visual_item(panel, "purchasedTotal").property("text") == "1.003"
        for index, quantity in enumerate(("× 1.000", "× 3")):
            chip = visual_item(panel, f"purchasedItem{index}")
            assert visual_item(chip, "purchasedQuantity").property("text") == quantity

    # Turning off a target must not hide the purchases already made for it.
    quick.toggleItem(0, False)
    QTest.qWait(20)
    for panel in (bot, compact):
        chip = visual_item(panel, "purchasedItem0")
        assert visual_item(chip, "purchasedQuantity").property("text") == "× 1.000"

    quick.update_metrics({"status": "preparando", "purchases_sent": 0,
                          "purchases_by_item": {}})
    QTest.qWait(20)
    for panel in (bot, compact):
        assert visual_item(panel, "purchasedTotal").property("text") == "0"
        chip = visual_item(panel, "purchasedItem0")
        assert visual_item(chip, "purchasedQuantity").property("text") == "× 0"
        assert visual_item(panel, "purchasedItem1") is None


@pytest.mark.parametrize("size", [(397, 158), (300, 108), (220, 90)])
def test_compact_counters_stay_inside_the_calibrated_area(quick, size):
    popup = quick.overlay.window
    quick.update_metrics({"purchases_sent": 7, "purchases_by_item": {
        item["name"]: 7 for item in quick.items[:1]}})
    popup.resize(*size)
    popup.show()
    QTest.qWait(30)
    content = visual_item(popup.contentItem(), "compactContent")
    top_left = content.mapToScene(QPointF())
    bottom_right = content.mapToScene(QPointF(content.width(), content.height()))
    assert 0 < top_left.x() < bottom_right.x() < popup.width()
    assert 0 < top_left.y() < bottom_right.y() < popup.height()
    panel = visual_item(content, "compactPurchases")
    assert panel.isVisible()
    assert visual_item(panel, "purchasedTotal").property("text") == "7"


def test_qml_item_and_history_actions_reuse_saved_data(quick, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    add_history({"started_at": "primeira", "reason": "exemplo", "purchases_verified": 2})
    add_history({"started_at": "segunda", "reason": "exemplo", "purchases_sent": 3})
    quick._update_history()
    assert len(quick.history) == 2
    assert [record[2] for record in quick.history] == ["3", "2"]
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

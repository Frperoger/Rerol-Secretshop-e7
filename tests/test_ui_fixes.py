"""Regressões de interface: executar no Windows ou em Qt offscreen."""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox
from app.config import load_config
from app.ui.main_window import MainWindow


def test_incomplete_hotkey_does_not_block_other_saves(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(("info", args)))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(("warning", args)))
    win = MainWindow()
    try:
        win.cal_fields["hotkey"].setKeySequence(QKeySequence("Ctrl+Z"))
        # A calibração pode estar incompleta: isso não bloqueia o orçamento.
        assert win.save_budget() is True
        assert not any(kind == "warning" for kind, _ in messages)
        assert load_config().calibration.hotkey == "ctrl+alt+q"
        # Salvar calibração retém o atalho anterior e notifica sem erro.
        assert win.save_settings(notify=False) is True
        assert load_config().calibration.hotkey == "ctrl+alt+q"
        assert "atalho anterior" in win.settings_save_status.text().lower()
        assert not any(kind == "warning" for kind, _ in messages)
    finally:
        win.close()


def test_safe_area_preview_updates_coordinates(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        new_area = (0.4, 0.2, 0.6, 0.8)
        win._update_area_fields(new_area)
        assert tuple(win.area_fields[key].value()
                     for key in ("x0", "y0", "x1", "y1")) == new_area
        assert win.btn_delete_history is not None
        assert win.btn_clear_history is not None
        assert win._calibration_top_layout is not None
    finally:
        win.close()


def test_calibration_panels_share_a_row_at_small_and_large_widths(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        win.tabs.setCurrentIndex(3)
        win.show()
        for width in (win.minimumWidth(), 1110, 1400):
            win.resize(width, 760)
            app.processEvents()
            detection = win._calibration_detection_panel.geometry()
            safe_area = win._calibration_area_panel.geometry()
            assert detection.top() == safe_area.top()
            assert detection.right() < safe_area.left()
    finally:
        win.close()


def test_delete_history_selection_and_all(monkeypatch, tmp_path):
    from app.config import add_history, read_history
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    win = MainWindow()
    try:
        add_history({"started_at": "primeiro", "reason": "ok"})
        add_history({"started_at": "segundo", "reason": "ok"})
        win._update_history()
        win.history_table.selectRow(0)
        win.delete_selected_history()
        assert len(read_history()) == 1
        assert read_history()[0]["started_at"] == "primeiro"
        win.delete_all_history()
        assert read_history() == []
    finally:
        win.close()

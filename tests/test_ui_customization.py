"""Rodado no Windows CI ou em ambiente Linux com PySide6 offscreen."""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow


def test_dynamic_items_and_captured_hotkey(monkeypatch, tmp_path):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        win.item_table.item(0, 2).setText('Medalhas Místicas')
        assert win.live_item_checks['item1'].text() == 'Medalhas Místicas'
        assert win.btn_record_hotkey.text() == 'Gravar teclas'
        win.cal_fields['hotkey'].setKeySequence(QKeySequence('Ctrl+Shift+F8'))
        win._hotkey_preview()
        assert 'Ctrl+Shift+F8' in win.hotkey_label.text()
        win.overlay_enabled.setChecked(True)
        cfg = win._collect_config()
        assert cfg.calibration.hotkey == 'ctrl+shift+f8'
        assert cfg.calibration.auto_overlay is True
        assert win.save_settings(notify=False)
        assert 'salvas' in win.settings_save_status.text()
    finally:
        win.overlay.hide()
        win.close()

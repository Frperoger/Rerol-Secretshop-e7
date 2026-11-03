"""Teste básico da nova GUI; executa no Windows CI com Qt offscreen."""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow, NoWheelDoubleSpinBox, NoWheelSpinBox


def test_window_has_new_live_controls_and_thumbnails(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        assert win.tabs.count() == 5
        assert "Editar" in win.btn_edit_gems.text()
        assert "Editar" in win.btn_edit_gold.text()
        assert win.live_item_checks
        assert win.item_table.horizontalHeaderItem(4).text() == "Miniatura"
        assert win.item_table.cellWidget(0, 4) is not None
        assert win.btn_area_image is not None
        assert win.btn_area_live is not None
        assert win.btn_reset_calibration is not None
        assert isinstance(win.area_fields["x0"], NoWheelDoubleSpinBox)
        assert isinstance(win.cal_fields["max_scrolls"], NoWheelSpinBox)
    finally:
        win.close()

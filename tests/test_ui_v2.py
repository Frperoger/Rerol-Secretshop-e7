"""Teste básico da nova GUI; executa no Windows CI com Qt offscreen."""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel
from app.config import load_config, load_template_scale
from app.core.template_scale import decode_png, load_templates, resize_template, scale_key, template_filenames
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
        assert "same_row_factor" not in win.cal_fields
        for index, gold_count, gems_count in ((0, 2, 2), (2, 2, 3)):
            tab = win.tabs.widget(index)
            for currency, count in (("gold", gold_count), ("gems", gems_count)):
                icons = tab.findChildren(QLabel, f"Currency_{currency}")
                assert len(icons) == count
                assert all(not icon.pixmap().isNull() for icon in icons)
                for icon in icons:
                    image = icon.pixmap().toImage()
                    assert image.pixelColor(0, 0).alpha() == 0
                    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() == 255
    finally:
        win.close()


def test_budget_fields_apply_without_starting_or_clicking_save(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        assert win.gem_bar.maximum() == 30
        win.budget_fields["gems_limit"].setValue(45)
        assert win.gem_label.text() == "Gemas estimadas: 0 / 45"
        assert win.gem_bar.maximum() == 45
        assert load_config().budget.gems_limit == 45

        win.budget_fields["gems_available"].setValue(40)
        assert win.gem_bar.maximum() == 45
        assert load_config().budget.gems_available == 60
        assert "anterior em uso" in win.budget_save_status.text()

        win.budget_fields["gems_limit"].setValue(0)
        assert win.gem_bar.maximum() == 40
        assert load_config().budget.gems_available == 40
    finally:
        win.close()


def test_calibration_button_saves_recognized_scale(monkeypatch, tmp_path):
    import cv2
    import numpy as np

    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        anchor = decode_png((win.templates_dir / "renovar.png").read_bytes())
        scaled = resize_template(anchor, 1.25)
        height, width = scaled.shape[:2]
        screenshot = np.zeros((540, 960, 3), dtype=np.uint8)
        screenshot[20:20 + height, 30:30 + width] = scaled
        path = tmp_path / "loja.png"
        ok, encoded = cv2.imencode(".png", screenshot)
        assert ok
        path.write_bytes(encoded.tobytes())
        win.screenshot_path = str(path)
        win.btn_diagnose.click()
        assert "Escala salva" in win.diagnostic_label.text()
        required, optional = template_filenames(win.cfg.items)
        _, fingerprint = load_templates(win.templates_dir, required | optional)
        assert load_template_scale(scale_key(960, 540, fingerprint)) == 1.25
    finally:
        win.close()


@pytest.mark.parametrize("compact", [False, True])
def test_start_minimizes_only_for_compact_panel(monkeypatch, tmp_path, compact):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    monkeypatch.setattr(win, "_register_hotkey", lambda: None)
    starts = []
    monkeypatch.setattr(win.controller, "start", lambda cfg, path: starts.append(cfg))
    win.tray.hide()
    try:
        win.show()
        win.overlay_enabled.setChecked(compact)
        win.start_bot()
        assert len(starts) == 1
        assert win.isMinimized() == compact
        assert win.isVisible()
    finally:
        win.close()

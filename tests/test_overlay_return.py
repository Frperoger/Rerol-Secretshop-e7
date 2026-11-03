"""Regressões: botão de retorno, janela não ativável e estilo Win32."""
from app.platform.passive_overlay import (
    WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT,
    action_overlay_style,
)


def test_overlay_style_accepts_click_but_does_not_take_focus():
    old = WS_EX_TRANSPARENT | 0x00080000  # mantém outras opções do Qt
    new = action_overlay_style(old)
    assert new & WS_EX_NOACTIVATE
    assert new & WS_EX_TOOLWINDOW
    assert not (new & WS_EX_TRANSPARENT)
    assert new & 0x00080000


def test_overlay_style_is_idempotent():
    value = WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    assert action_overlay_style(action_overlay_style(value)) == value


def test_overlay_return_button_emits_request_and_resets(monkeypatch, tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import pytest
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.ui.overlay import StatusOverlay

    app = QApplication.instance() or QApplication([])
    overlay = StatusOverlay()
    received = []
    overlay.return_requested.connect(lambda: received.append(True))
    try:
        assert not (overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        overlay.show()
        QTest.mouseClick(overlay.return_button, Qt.MouseButton.LeftButton)
        assert received == [True]
        assert not overlay.return_button.isEnabled()
        assert overlay.return_button.text() == "Aguarde…"
        overlay.reset_return_button()
        assert overlay.return_button.isEnabled()
        assert overlay.return_button.text() == "Voltar ao app"
    finally:
        overlay.close()


def test_overlay_return_uses_safe_pause_then_opens_main(monkeypatch, tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import pytest
    pytest.importorskip("PySide6")
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import MainWindow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    pauses = []
    runner = SimpleNamespace(pause_acknowledged=lambda: True)
    fake_controller = SimpleNamespace(running=True, runner=runner,
                                      set_ui_paused=lambda paused: pauses.append(paused))
    actual_controller = window.controller
    try:
        window.controller = fake_controller
        window.overlay.show()
        window.overlay.return_button.click()
        assert pauses == [True]
        assert window.isVisible()
        assert not window.overlay.isVisible()
        assert window.overlay.return_button.isEnabled()
    finally:
        window.controller = actual_controller
        window.overlay.hide()
        window.close()

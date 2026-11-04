"""Ponto de entrada do aplicativo Windows; inicialização de DPI antes do Qt."""
import sys
from app.platform.windows import enable_dpi_awareness


def main():
    enable_dpi_awareness()
    try:
        from app.logging_setup import setup_logging
        setup_logging()
    except OSError:
        pass  # log visual continua disponível mesmo se AppData não permitir escrita
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QFont, QIcon
    from app.config import bundled_root
    from app.ui.quick_window import QuickWindow
    app = QApplication(sys.argv)
    app.setApplicationName("Epic7 Shop Bot")
    app.setFont(QFont("Segoe UI", 10))
    icon = bundled_root() / "assets" / "app_icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    app.setQuitOnLastWindowClosed(False)
    try:
        window = QuickWindow()
    except RuntimeError as exc:
        QMessageBox.critical(None, "Falha ao abrir Epic7 Shop Bot", str(exc))
        return 1
    window.show()
    try:
        return app.exec()
    finally:
        window.dispose()


if __name__ == "__main__":
    sys.exit(main())

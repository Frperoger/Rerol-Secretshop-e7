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
    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import MainWindow
    from app.ui.style import QSS
    app = QApplication(sys.argv)
    app.setApplicationName("Epic7 Shop Bot")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

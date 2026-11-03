"""Ponte entre motor Python e thread principal do Qt via signals enfileirados."""
import threading
from PySide6.QtCore import QObject, Signal
from app.engine.runner import BotRunner


class BotController(QObject):
    log_message = Signal(str, str)
    updated = Signal(dict)
    finished = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = None
        self.thread = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, cfg, templates_dir):
        if self.running:
            raise RuntimeError("Bot já está em execução.")
        self.runner = BotRunner(cfg, templates_dir,
                                on_log=self.log_message.emit,
                                on_status=self.updated.emit,
                                on_finished=self.finished.emit)
        self.thread = threading.Thread(target=self.runner.run,
                                       name="Epic7ShopBot", daemon=True)
        self.thread.start()

    def stop(self):
        if self.runner:
            self.runner.stop()

"""Logs estruturados e rotativos em AppData; úteis para diagnóstico Windows."""
import logging
from logging.handlers import RotatingFileHandler
from app.config import data_directory


def setup_logging():
    log = logging.getLogger("epic7shop")
    log.setLevel(logging.INFO)
    if log.handlers:
        return
    folder = data_directory() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / "sessao.log", maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.propagate = False

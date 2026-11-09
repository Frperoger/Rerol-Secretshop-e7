"""Translate dialog presentation while preserving the existing validation flows."""
from PySide6.QtWidgets import QFileDialog as _QFileDialog, QMessageBox as _QMessageBox

from app.ui.language import tr


class QMessageBox(_QMessageBox):
    @staticmethod
    def information(parent, title, text, *args, **kwargs):
        return _QMessageBox.information(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        return _QMessageBox.warning(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def critical(parent, title, text, *args, **kwargs):
        return _QMessageBox.critical(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def question(parent, title, text, *args, **kwargs):
        return _QMessageBox.question(parent, tr(title), tr(text), *args, **kwargs)


class QFileDialog(_QFileDialog):
    @staticmethod
    def getOpenFileName(parent=None, caption="", directory="", filter="", *args, **kwargs):
        return _QFileDialog.getOpenFileName(parent, tr(caption), directory, tr(filter), *args, **kwargs)

    @staticmethod
    def getExistingDirectory(parent=None, caption="", directory="", *args, **kwargs):
        return _QFileDialog.getExistingDirectory(parent, tr(caption), directory, *args, **kwargs)

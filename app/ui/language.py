"""Application translations and a UI preference independent of the bot settings."""
from PySide6.QtCore import (Property, QCoreApplication, QLibraryInfo, QLocale,
                            QObject, QTranslator, Signal, Slot)

from app.config import load_interface_language, save_interface_language
from app.ui.translations import translate_text


def tr(text: str) -> str:
    return QCoreApplication.translate("ShopBot", str(text))


class Catalog(QTranslator):
    def __init__(self, language):
        super().__init__(language)
        self._language = language

    def isEmpty(self):
        return False

    def translate(self, context, source, disambiguation=None, n=-1):
        translated = self._language.text(source)
        if translated == source and self._language.code == "pt":
            native = self._language._native.translate(context, source, disambiguation, n)
            return native or source
        return translated


class Language(QObject):
    changed = Signal()
    saveFailed = Signal(str)

    def __init__(self):
        super().__init__()
        self._code = load_interface_language()
        self._previous_locale = QLocale()
        self._native = QTranslator(self)
        self._catalog = Catalog(self)
        self._set_locale()
        QCoreApplication.installTranslator(self._catalog)

    @Property(str, notify=changed)
    def code(self):
        return self._code

    @Property(str, notify=changed)
    def localeName(self):
        return "en_US" if self._code == "en" else "pt_BR"

    def _set_locale(self):
        QLocale.setDefault(QLocale(self.localeName))
        QCoreApplication.removeTranslator(self._native)
        if self._code == "pt":
            folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if self._native.load("qtbase_pt_BR", folder):
                QCoreApplication.installTranslator(self._native)

    def text(self, text):
        return translate_text(str(text), self._code)

    def number(self, number):
        return QLocale(self.localeName).toString(int(number))

    @Slot(str, result=bool)
    def setLanguage(self, code):
        if code not in ("pt", "en"):
            return False
        if code == self._code:
            return True
        self._code = code
        self._set_locale()
        self.changed.emit()
        try:
            save_interface_language(code)
        except OSError:
            self.saveFailed.emit(self.text("Não foi possível salvar o idioma. A escolha vale apenas para esta sessão."))
        return True

    def dispose(self):
        QCoreApplication.removeTranslator(self._catalog)
        QCoreApplication.removeTranslator(self._native)
        QLocale.setDefault(self._previous_locale)

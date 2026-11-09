"""Connects the QML views to the existing desktop workflows."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import (Property, QCoreApplication, QEvent, QItemSelectionModel, QObject,
                            QKeyCombination, QSize, Qt, QTimer, QUrl, Signal, Slot)
from PySide6.QtGui import QKeySequence, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider, QQuickWindow
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from app.config import bundled_root
from app.core.drag_geometry import drag_area
from app.ui.main_window import MainWindow, currency_pixmap
from app.ui.overlay import StatusOverlay


class ActivityModel(QStandardItemModel):
    TIME, LEVEL, MESSAGE = range(Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 4)

    def __init__(self):
        super().__init__()
        self.setItemRoleNames({self.TIME: b"eventTime", self.LEVEL: b"eventLevel",
                               self.MESSAGE: b"eventMessage"})

    def append_entry(self, message, level):
        entry = QStandardItem()
        entry.setData(datetime.now().strftime("%H:%M:%S"), self.TIME)
        entry.setData(level, self.LEVEL)
        entry.setData(message, self.MESSAGE)
        self.appendRow(entry)
        if self.rowCount() > 1500:
            self.removeRow(0)

    def plain_text(self):
        lines = []
        for row in range(self.rowCount()):
            entry = self.item(row)
            lines.append(f"{entry.data(self.TIME)}  [{entry.data(self.LEVEL).upper()}]  "
                         f"{entry.data(self.MESSAGE)}")
        return "\n".join(lines)


class PreviewImages(QQuickImageProvider):
    def __init__(self, view):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self.view = view
        self.currencies = {name: currency_pixmap(name) for name in ("gold", "gems")}

    def requestPixmap(self, identifier, size, requested_size):
        name = identifier.split("/", 1)[0]
        if name == "capture":
            pixmap = self.view.preview.background_image
        elif name == "diagnostic":
            pixmap = QPixmap()
            if self.view.image_bytes:
                pixmap.loadFromData(self.view.image_bytes)
        else:
            pixmap = self.currencies.get(name, QPixmap())
        if pixmap.isNull():
            pixmap = QPixmap(QSize(1, 1))
            pixmap.fill(Qt.GlobalColor.transparent)
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


class QuickOverlay:
    def __init__(self, window, on_return):
        self.window = window
        self.window.returnRequested.connect(on_return)

    def __getattr__(self, name):
        return getattr(self.window, name)

    def reset_return_button(self):
        self.window.setProperty("waiting", False)

    def update_state(self, state):
        self.window.setProperty("metrics", state)

    def position_over_game(self, game_rect, area):
        StatusOverlay.position_over_game(self.window, game_rect, area)


class QuickWindow(MainWindow):
    # The existing forms remain hidden. They own validation, settings,
    # hotkeys, the Windows tray, and the bot lifecycle during this migration.
    infoChanged = Signal()
    budgetChanged = Signal()
    calibrationChanged = Signal()
    itemsChanged = Signal()
    historyChanged = Signal()
    pageChanged = Signal()
    budgetFocusRequested = Signal()

    def __init__(self):
        self._activity = ActivityModel()
        super().__init__()
        self.tabs.addTab(QWidget(), "Donates")
        self._activity.setParent(self)
        self.quick_window = None
        self._capture_version = 0
        self._diagnostic_version = 0
        self.engine = QQmlApplicationEngine(self)
        self.engine.addImageProvider("shop", PreviewImages(self))
        self.engine.setInitialProperties({"backend": self})
        self.engine.load(QUrl.fromLocalFile(str(bundled_root() / "qml" / "Main.qml")))
        if not self.engine.rootObjects():
            raise RuntimeError("Não foi possível carregar a interface QML.")
        self.quick_window = self.engine.rootObjects()[0]
        overlay_window = self.quick_window.findChild(QQuickWindow, "compactWindow")
        if overlay_window is None:
            raise RuntimeError("Não foi possível carregar o painel compacto QML.")
        self.overlay.deleteLater()
        self.overlay = QuickOverlay(overlay_window, self.show_panel)
        self.tabs.currentChanged.connect(lambda _index: self.pageChanged.emit())

    def dispose(self):
        # Destroy QML while its Python properties and image provider are still valid.
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(self.engine, QEvent.Type.DeferredDelete)

    def show(self):
        self.quick_window.show()

    def hide(self):
        self.quick_window.hide()

    def showNormal(self):
        self.quick_window.showNormal()

    def showMinimized(self):
        self.quick_window.showMinimized()

    def isVisible(self):
        window = getattr(self, "quick_window", None)
        return window.isVisible() if window is not None else False

    def isMinimized(self):
        return self.quick_window.visibility() == self.quick_window.Visibility.Minimized

    def raise_(self):
        self.quick_window.raise_()

    def activateWindow(self):
        self.quick_window.requestActivate()

    @Property("QVariantMap", notify=infoChanged)
    def info(self):
        return {
            "running": self.btn_stop.isEnabled(),
            "status": self.status.text(),
            "statusCode": self._metric_state.get("status", ""),
            "hotkey": self.hotkey_label.text(),
            "gemText": self.gem_label.text(),
            "goldText": self.gold_label.text(),
            "gemProgress": max(0, self.gem_bar.value()) / max(1, self.gem_bar.maximum()),
            "goldProgress": max(0, self.gold_bar.value()) / max(1, self.gold_bar.maximum()),
            "metrics": {key: label.text() for key, label in self.metric_labels.items()},
            "purchases": {
                "total": self._metric_state.get("purchases_sent", 0),
                "byItem": self._metric_state.get("purchases_by_item", {}),
            },
            "budgetNotice": self.budget_save_status.text(),
            "itemNotice": self.items_save_status.text(),
            "calibrationNotice": self.settings_save_status.text(),
            "hotkeyHint": self.hotkey_hint.text(),
            "areaWarning": self.area_warning.text(),
            "templates": str(self.templates_dir),
            "capturePath": self.screenshot_path,
            "captureImage": (f"image://shop/capture/{self._capture_version}"
                             if self.screenshot_path else ""),
            "diagnosticImage": (f"image://shop/diagnostic/{self._diagnostic_version}"
                                if self.image_bytes else ""),
            "diagnostic": self.diagnostic_label.text(),
            "report": self.report_label.text(),
            "historyNotice": self.history_status.text(),
        }

    @Property(QObject, constant=True)
    def activity(self):
        return self._activity

    @Slot()
    def copyActivity(self):
        QApplication.clipboard().setText(self._activity.plain_text())

    @Property(int, notify=pageChanged)
    def page(self):
        return self.tabs.currentIndex()

    @Property("QVariantMap", notify=budgetChanged)
    def budget(self):
        return {name: field.value() for name, field in self.budget_fields.items()}

    @Property("QVariantMap", notify=calibrationChanged)
    def calibration(self):
        fields = {}
        for name, field in self.cal_fields.items():
            if name == "hotkey":
                fields[name] = field.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            else:
                fields[name] = field.text() if isinstance(field, QLineEdit) else field.value()
        fields["compact"] = self.overlay_enabled.isChecked()
        fields["safeArea"] = list(self.preview.area)
        fields["overlayArea"] = list(self.preview.overlay_area)
        return fields

    @Property("QVariantList", notify=itemsChanged)
    def items(self):
        table = self.item_table
        items = []
        for row in range(table.rowCount()):
            values = {key: table.item(row, col).text() for key, col in (
                ("id", 1), ("name", 2), ("price", 3), ("icon", 5),
                ("buy", 6), ("confirm", 7), ("sold", 8))}
            path = self.templates_dir / values["icon"].strip()
            values["preview"] = QUrl.fromLocalFile(str(path)).toString() if path.is_file() else ""
            check = self.live_item_checks.get(values["id"].strip()) if self.btn_stop.isEnabled() else None
            values["enabled"] = (check.isChecked() if check is not None else
                                 table.item(row, 0).checkState() == Qt.CheckState.Checked)
            items.append(values)
        return items

    @Property("QVariantList", notify=historyChanged)
    def history(self):
        table = self.history_table
        return [[table.item(row, col).text() for col in range(table.columnCount())]
                for row in range(table.rowCount())]

    @Slot(int)
    def selectPage(self, index):
        if 0 <= index < self.tabs.count() and self.tabs.isTabEnabled(index):
            if self.tabs.currentIndex() == 1 and index != 1:
                self.itemsChanged.emit()
            self.tabs.setCurrentIndex(index)

    @Slot(str, int)
    def editBudget(self, name, value):
        if name in self.budget_fields and (name != "refresh_cost" or not self.btn_stop.isEnabled()):
            self.budget_fields[name].setValue(value)
            self.budgetChanged.emit()
            self.infoChanged.emit()

    @Slot(str, str)
    def editCalibration(self, name, value):
        field = self.cal_fields.get(name)
        if self.btn_stop.isEnabled() or field is None or name == "hotkey":
            return
        if isinstance(field, QLineEdit):
            field.setText(value)
        else:
            field.setValue(float(value) if name != "max_scrolls" else int(value))
        self.calibrationChanged.emit()

    @Slot(int, int)
    def recordKey(self, key, modifiers):
        if self.btn_stop.isEnabled():
            return
        sequence = QKeySequence(QKeyCombination(Qt.KeyboardModifier(modifiers), Qt.Key(key)))
        self.cal_fields["hotkey"].setKeySequence(sequence)
        self.calibrationChanged.emit()
        self.infoChanged.emit()

    @Slot(bool)
    def setCompact(self, enabled):
        if not self.btn_stop.isEnabled():
            self.overlay_enabled.setChecked(enabled)
            self.calibrationChanged.emit()
            self.infoChanged.emit()

    @Slot(bool, int, float)
    def editCoordinate(self, overlay, index, value):
        if self.btn_stop.isEnabled() or not 0 <= index < 4:
            return
        fields = self.overlay_fields if overlay else self.area_fields
        fields[("x0", "y0", "x1", "y1")[index]].setValue(value)
        self.calibrationChanged.emit()
        self.infoChanged.emit()

    @Slot(bool, "QVariantList", float, float, bool)
    def dragRectangle(self, overlay, initial, dx, dy, resize):
        if self.btn_stop.isEnabled() or len(initial) != 4:
            return
        minimum = (0.12, 0.09) if overlay else (0.025, 0.03)
        area = drag_area(tuple(initial), dx, dy, "resize" if resize else "move",
                         min_width=minimum[0], min_height=minimum[1])
        if overlay:
            self.preview.set_overlay_area(area)
            self._update_overlay_fields(area)
        else:
            self.preview.set_area(area)
            self._update_area_fields(area)
        self.calibrationChanged.emit()
        self.infoChanged.emit()

    @Slot(int, str, str)
    def editItem(self, row, name, text):
        columns = {"id": 1, "name": 2, "price": 3, "icon": 5, "buy": 6, "confirm": 7, "sold": 8}
        if not self.btn_stop.isEnabled() and name in columns and 0 <= row < self.item_table.rowCount():
            self.item_table.item(row, columns[name]).setText(text)
            if name == "icon":
                self.itemsChanged.emit()

    @Slot(int, bool)
    def toggleItem(self, row, enabled):
        if 0 <= row < self.item_table.rowCount():
            if self.btn_stop.isEnabled():
                ident = self.item_table.item(row, 1).text().strip()
                check = self.live_item_checks.get(ident)
                if check is not None:
                    check.setChecked(enabled)
            else:
                self.item_table.item(row, 0).setCheckState(
                    Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            self.itemsChanged.emit()

    @Slot(int)
    def removeItem(self, row):
        if not self.btn_stop.isEnabled() and 0 <= row < self.item_table.rowCount():
            self.item_table.setCurrentCell(row, 0)
            self.remove_item()
            self.itemsChanged.emit()

    @Slot("QVariantList")
    def deleteHistory(self, rows):
        selection = self.history_table.selectionModel()
        selection.clearSelection()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row in rows:
            if 0 <= row < self.history_table.rowCount():
                selection.select(self.history_table.model().index(row, 0), flags)
        self.delete_selected_history()
        self.historyChanged.emit()
        self.infoChanged.emit()

    @Slot(str)
    def action(self, name):
        actions = {
            "start": self.start_bot, "stop": self.stop_bot, "resume": self.resume_game,
            "budget": self.open_budget, "saveBudget": self.save_budget,
            "addItem": self.add_item, "saveItems": self.save_items, "templates": self.pick_templates,
            "image": self.pick_area_image, "png": self.pick_capture, "capture": self.capture_game_window,
            "diagnostic": self.run_diagnostic,
            "diagnosticPurchase": lambda: self.run_diagnostic(purchase=True),
            "resetSpeed": self.reset_speed,
            "resetCalibration": self.reset_calibration, "saveCalibration": self.save_settings,
            "clearHistory": self.delete_all_history,
        }
        if name not in actions:
            return
        if self.btn_stop.isEnabled() and name not in ("stop", "resume", "budget", "saveBudget", "clearHistory"):
            return
        actions[name]()
        if name in ("templates", "saveItems", "addItem", "start"):
            self.itemsChanged.emit()
        if name in ("image", "png"):
            self._capture_version += 1
        if name in ("diagnostic", "diagnosticPurchase"):
            self._diagnostic_version += 1
        if name in ("resetSpeed", "resetCalibration", "saveCalibration", "start"):
            self.calibrationChanged.emit()
        if name == "clearHistory":
            self.historyChanged.emit()
        if name == "budget":
            self.budgetFocusRequested.emit()
        self.infoChanged.emit()

    @Slot(result=bool)
    def closeWindow(self):
        if self.controller.running:
            self.close()
            return False
        QTimer.singleShot(0, self.exit_app)
        return True

    def _finish_game_capture(self):
        super()._finish_game_capture()
        self._capture_version += 1
        self.infoChanged.emit()

    def _set_running(self, running):
        super()._set_running(running)
        self.infoChanged.emit()

    def append_log(self, text, level="info"):
        self._activity.append_entry(text, level)

    def update_metrics(self, state):
        super().update_metrics(state)
        self.infoChanged.emit()

    def execution_finished(self, result):
        super().execution_finished(result)
        self.itemsChanged.emit()
        self.historyChanged.emit()
        self.infoChanged.emit()

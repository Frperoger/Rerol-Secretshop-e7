"""Interface Qt Widgets criada do zero a partir das funções do protótipo visual.

A UI não executa visão computacional nem manipula mouse. Apenas configura,
exibe métricas e envia comandos para a thread do BotRunner.
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QSignalBlocker, QRect, QRectF, QPoint
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QCheckBox,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon, QTabWidget, QKeySequenceEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QSizePolicy,
)

from app.config import (add_history, clear_history, data_directory, load_config,
                        prepare_templates, read_history, remove_history_rows,
                        save_config, save_template_scale, user_templates)
from app.core.budget import validate_config
from app.logging_setup import log_diagnostic
from app.models import AppConfig, BudgetConfig, CalibrationConfig, ItemConfig, BotError
from app.ui.controller import BotController
from app.ui.diagnostics import analyze_image, validate_item_templates
from app.core.hotkeys import (normalize_hotkey, display_hotkey,
                              select_hotkey_for_save, DEFAULT_HOTKEY)
from app.core.overlay_geometry import validate_overlay_area, rectangles_overlap
from app.core.drag_geometry import drag_area
from app.config import bundled_root
from app.ui.overlay import StatusOverlay


def fmt(number):
    return f"{number:,}".replace(",", ".")


def panel(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)
    heading = QLabel(title.upper())
    heading.setObjectName("Muted")
    heading.setWordWrap(False)
    heading.setFixedHeight(22)
    heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    font = heading.font()
    font.setBold(True)
    font.setPointSize(9)
    heading.setFont(font)
    layout.addWidget(heading)
    return frame, layout


def make_button(text: str, object_name: str = "") -> QPushButton:
    button = QPushButton(text)
    if object_name:
        button.setObjectName(object_name)
    button.setMinimumHeight(34)
    return button


def currency_pixmap(currency: str) -> QPixmap:
    source = QPixmap(str(bundled_root() / "assets" / f"currency_{currency}.png"))
    if source.isNull():
        return source

    # Contornos em pixels dos recortes do jogo em assets/.
    outline = QPainterPath()
    if currency == "gold":
        outline.addEllipse(QRectF(7, 6.5, 33, 33))
    else:
        outline.moveTo(22, 7)
        outline.cubicTo(26, 10, 31, 15, 32.5, 21)
        outline.cubicTo(35, 32, 31.5, 39, 22, 47)
        outline.cubicTo(14.5, 41, 11, 35, 11, 29)
        outline.cubicTo(11, 21, 16.5, 12, 22, 7)
        outline.closeSubpath()

    bounds = outline.boundingRect().toAlignedRect()
    cropped = QPixmap(bounds.size())
    cropped.fill(Qt.GlobalColor.transparent)
    painter = QPainter(cropped)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(-bounds.x(), -bounds.y())
    painter.fillPath(outline, Qt.GlobalColor.white)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.drawPixmap(0, 0, source)
    painter.end()
    return cropped


def currency_row(label: QLabel, currency: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    pixmap = currency_pixmap(currency)
    if not pixmap.isNull():
        icon = QLabel()
        icon.setObjectName(f"Currency_{currency}")
        icon.setStyleSheet("background: transparent;")
        icon.setFixedSize(20, 20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(pixmap.scaled(icon.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
        row.addWidget(icon)
    label.setWordWrap(True)
    row.addWidget(label, 1)
    return row


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


def spin(value: int, max_value: int = 2_147_483_647) -> QSpinBox:
    control = NoWheelSpinBox()
    control.setRange(0, max_value)
    control.setValue(value)
    control.setMinimumHeight(32)
    control.setGroupSeparatorShown(True)
    return control


def decimal(value: float, minimum: float, maximum: float, step=0.01, digits=2):
    control = NoWheelDoubleSpinBox()
    control.setDecimals(digits)
    control.setRange(minimum, maximum)
    control.setSingleStep(step)
    control.setValue(value)
    control.setMinimumHeight(32)
    return control


def scroll_wrap(content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return scroll


class SafeAreaPreview(QWidget):
    """Área verde segura e painel azul: ambos móveis e redimensionáveis.

    Os movimentos são aplicados apenas à prévia. O motor utiliza as coordenadas
    aprovadas e salvas; não há deslocamento da janela do jogo.
    """
    area_changed = Signal(tuple)
    overlay_changed = Signal(tuple)

    def __init__(self, area, overlay_area, overlay_enabled=False):
        super().__init__()
        self.area = tuple(area)
        self.overlay_area = tuple(overlay_area)
        self.overlay_enabled = bool(overlay_enabled)
        self.background_image = QPixmap()
        self.setMinimumHeight(230)
        self.setMouseTracking(True)
        self._drag_target = None
        self._drag_mode = None
        self._drag_initial = None

    def set_area(self, area):
        self.area = tuple(area)
        self.update()

    def set_overlay_area(self, area):
        self.overlay_area = tuple(area)
        self.update()

    def set_overlay_enabled(self, enabled):
        self.overlay_enabled = bool(enabled)
        self.update()

    def set_background(self, pixmap: QPixmap):
        self.background_image = QPixmap(pixmap)
        self.update()

    def _bounds(self):
        container = self.rect().adjusted(3, 3, -3, -3)
        if self.background_image.isNull():
            return container
        fitted = self.background_image.scaled(
            container.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        return QRect(container.x() + (container.width()-fitted.width())//2,
                     container.y() + (container.height()-fitted.height())//2,
                     fitted.width(), fitted.height())

    def _rectangle(self, area):
        bounds = self._bounds()
        x0, y0, x1, y1 = area
        return QRect(bounds.x() + round(x0 * bounds.width()),
                     bounds.y() + round(y0 * bounds.height()),
                     round((x1-x0)*bounds.width()),
                     round((y1-y0)*bounds.height()))

    @staticmethod
    def _handle_rect(rect):
        return QRect(rect.right() - 16, rect.bottom() - 16, 21, 21)

    def _hit_test(self, point):
        # As alças têm prioridade, para evitar arrastar uma área sobreposta.
        targets = [("safe", self.area)]
        if self.overlay_enabled:
            targets.append(("overlay", self.overlay_area))
        for name, area in reversed(targets):
            if self._handle_rect(self._rectangle(area)).contains(point):
                return name, "resize"
        for name, area in reversed(targets):
            if self._rectangle(area).contains(point):
                return name, "move"
        return None, None

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self._bounds()
        p.fillRect(self.rect(), QColor("#171717"))
        if self.background_image.isNull():
            p.setPen(QColor("#858585"))
            p.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "Carregue uma imagem da loja")
        else:
            p.drawPixmap(bounds.topLeft(), self.background_image.scaled(
                bounds.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        safe_rect = self._rectangle(self.area)
        overlap = self.overlay_enabled and rectangles_overlap(self.area, self.overlay_area)
        green = QColor("#ffad36") if overlap else QColor("#49aa19")
        p.setPen(QPen(green, 2, Qt.PenStyle.DashLine))
        p.setBrush(QColor(60, 180, 70, 40))
        p.drawRect(safe_rect)
        p.fillRect(QRect(safe_rect.right()-9, safe_rect.bottom()-9, 9, 9), green)
        if self.overlay_enabled:
            blue_rect = self._rectangle(self.overlay_area)
            p.setPen(QPen(QColor("#328dff"), 2))
            p.setBrush(QColor(25, 124, 255, 65))
            p.drawRect(blue_rect)
            p.setPen(QColor("#f0f6ff"))
            p.drawText(blue_rect.adjusted(5, 5, -5, -5),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                       "POP-UP")
            p.fillRect(QRect(blue_rect.right()-9, blue_rect.bottom()-9, 9, 9),
                       QColor("#328dff"))
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        point = event.position().toPoint()
        self._drag_target, self._drag_mode = self._hit_test(point)
        if self._drag_target is None:
            return super().mousePressEvent(event)
        original_area = self.area if self._drag_target == "safe" else self.overlay_area
        self._drag_initial = (point, tuple(original_area))
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_target is None or self._drag_initial is None:
            _, mode = self._hit_test(event.position().toPoint())
            self.setCursor(Qt.CursorShape.SizeFDiagCursor if mode == "resize"
                           else Qt.CursorShape.SizeAllCursor if mode == "move"
                           else Qt.CursorShape.ArrowCursor)
            return super().mouseMoveEvent(event)
        origin, original_area = self._drag_initial
        bounds = self._bounds()
        if bounds.width() <= 0 or bounds.height() <= 0:
            event.accept()
            return
        delta = event.position().toPoint() - origin
        min_width, min_height = ((0.025, 0.03) if self._drag_target == "safe"
                                 else (0.12, 0.09))
        new_area = drag_area(original_area, delta.x()/bounds.width(),
                             delta.y()/bounds.height(), self._drag_mode,
                             min_width=min_width, min_height=min_height)
        if self._drag_target == "safe":
            self.area = new_area
            self.area_changed.emit(new_area)
        else:
            self.overlay_area = new_area
            self.overlay_changed.emit(new_area)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_target = None
        self._drag_mode = None
        self._drag_initial = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epic7 Shop Bot — Desktop")
        self.resize(1110, 760)
        self.setMinimumSize(780, 560)
        self.controller = BotController(self)
        self.controller.log_message.connect(self.append_log)
        self.controller.updated.connect(self.update_metrics)
        self.controller.finished.connect(self.execution_finished)
        self.hotkey_handle = None
        self.hotkey_module = None
        self.image_bytes = None
        self.screenshot_path = ""
        self.last_result = None
        self._metric_state = {}
        self._startup_error = ""
        self._overlay_blocked = False
        self._overlay_warning_given = False
        self.overlay = StatusOverlay()
        self.overlay.return_requested.connect(self.show_panel)
        try:
            self.cfg = load_config()
        except BotError as exc:
            self._startup_error = str(exc)
            self.cfg = AppConfig()
        self.templates_dir = user_templates(self.cfg)
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(18, 14, 18, 16)
        main.setSpacing(11)
        heading = QHBoxLayout()
        brand = QLabel("Epic7  ·  Shop Bot")
        brand.setObjectName("Brand")
        heading.addWidget(brand)
        heading.addStretch()
        self.status = QLabel("●  PARADO")
        self.status.setStyleSheet("color:#a6a6a6;font-weight:600;")
        heading.addWidget(self.status)
        main.addLayout(heading)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self._build_bot_tab()
        self._build_items_tab()
        self._build_budget_tab()
        self._build_calibration_tab()
        self._build_reports_tab()
        self._make_tray()
        if self._startup_error:
            log_diagnostic(self._startup_error, "error")
            QMessageBox.warning(self, "Configuração anterior inválida", self._startup_error)
        try:
            prepare_templates(self.cfg)
        except OSError as exc:
            log_diagnostic(f"Falha ao preparar templates: {exc}", "warn")
            self.append_log("Não foi possível preparar as imagens da loja. Confira a pasta de templates na aba Itens.", "warn")
        self._refresh_template_labels()
        self._refresh_item_thumbnails()
        self._update_budget_metrics()

    def _build_bot_tab(self):
        content = QWidget()
        line = QHBoxLayout(content)
        line.setContentsMargins(0, 14, 0, 0)
        line.setSpacing(15)
        frame, col = panel("Controle")
        buttons = QHBoxLayout()
        self.btn_start = make_button("▶  Iniciar", "Primary")
        self.btn_stop = make_button("■  Parar", "Danger")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self.start_bot)
        self.btn_stop.clicked.connect(self.stop_bot)
        buttons.addWidget(self.btn_start)
        buttons.addWidget(self.btn_stop)
        col.addLayout(buttons)
        self.hotkey_label = QLabel("Emergência: Ctrl+Alt+Q · ou botão Parar na bandeja")
        self.hotkey_label.setObjectName("Muted")
        self.hotkey_label.setWordWrap(True)
        col.addWidget(self.hotkey_label)
        col.addSpacing(10)
        self.gem_label = QLabel("Gemas estimadas: 0 / 0")
        self.gold_label = QLabel("Ouro estimado: 0 / 0")
        self.gem_bar = QProgressBar()
        self.gold_bar = QProgressBar()
        self.gem_bar.setTextVisible(False)
        self.gold_bar.setTextVisible(False)
        self.gold_bar.setStyleSheet("QProgressBar::chunk {background:#d9a32a;}")
        gem_row = currency_row(self.gem_label, "gems")
        self.btn_edit_gems = make_button("Editar")
        self.btn_edit_gems.clicked.connect(self.open_budget)
        gem_row.addWidget(self.btn_edit_gems)
        col.addLayout(gem_row)
        col.addWidget(self.gem_bar)
        gold_row = currency_row(self.gold_label, "gold")
        self.btn_edit_gold = make_button("Editar")
        self.btn_edit_gold.clicked.connect(self.open_budget)
        gold_row.addWidget(self.btn_edit_gold)
        col.addLayout(gold_row)
        col.addWidget(self.gold_bar)
        active_label = QLabel("ITENS PROCURADOS — ALTERÁVEIS DURANTE A EXECUÇÃO")
        active_label.setObjectName("Muted")
        active_label.setWordWrap(True)
        col.addWidget(active_label)
        self.active_items_box = QWidget()
        self.active_items_layout = QVBoxLayout(self.active_items_box)
        self.active_items_layout.setContentsMargins(0, 0, 0, 0)
        self.active_items_layout.setSpacing(4)
        self.live_item_checks = {}
        col.addWidget(self.active_items_box)
        self.btn_resume_game = make_button("Voltar ao jogo e retomar", "Primary")
        self.btn_resume_game.clicked.connect(self.resume_game)
        self.btn_resume_game.setVisible(False)
        col.addWidget(self.btn_resume_game)
        col.addSpacing(8)
        self.metric_labels = {}
        stats = QGridLayout()
        metrics = [("refreshes", "Renovações", None),
                   ("purchases_verified", "Compras verificadas", None),
                   ("gems_estimated", "Gemas estimadas", "gems"),
                   ("gold_estimated", "Ouro estimado", "gold")]
        for idx, (key, title, currency) in enumerate(metrics):
            cell = QFrame()
            cell.setStyleSheet("QFrame {background:#292929; border-radius:5px;}")
            cellbox = QVBoxLayout(cell)
            cellbox.setSpacing(4)
            name = QLabel(title)
            name.setObjectName("Muted")
            value = QLabel("0")
            value.setObjectName("Metric")
            if currency:
                cellbox.addLayout(currency_row(name, currency))
            else:
                cellbox.addWidget(name)
            cellbox.addWidget(value)
            stats.addWidget(cell, idx//2, idx%2)
            self.metric_labels[key] = value
        col.addLayout(stats)
        col.addStretch()
        controls = scroll_wrap(frame)
        controls.setMinimumWidth(310)
        controls.setMaximumWidth(365)
        line.addWidget(controls)
        frame2, right = panel("Registro de atividade")
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.document().setMaximumBlockCount(1500)
        right.addWidget(self.console, 1)
        line.addWidget(frame2, 1)
        self.tabs.addTab(content, "Bot")

    def _build_items_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 14, 0, 0)
        frame, inner = panel("Itens a comprar")
        self.item_table = QTableWidget(0, 9)
        self.item_table.setHorizontalHeaderLabels([
            "Ativo", "ID", "Item", "Preço (ouro)", "Miniatura",
            "Ícone", "Botão comprar", "Confirmação", "Vendido (opcional)"])
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(True)
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for item in self.cfg.items:
            self._add_item_row(item)
        self.item_table.itemChanged.connect(self._sync_item_labels)
        inner.addWidget(self.item_table)
        row = QHBoxLayout()
        self.btn_add = make_button("+ Adicionar item")
        self.btn_remove = make_button("Remover selecionado")
        self.btn_save_items = make_button("Salvar itens", "Primary")
        self.btn_add.clicked.connect(self.add_item)
        self.btn_remove.clicked.connect(self.remove_item)
        self.btn_save_items.clicked.connect(self.save_items)
        for button in (self.btn_add, self.btn_remove, self.btn_save_items):
            row.addWidget(button)
        row.addStretch()
        inner.addLayout(row)
        folder_row = QHBoxLayout()
        self.btn_templates_items = make_button("Escolher pasta de templates")
        self.btn_templates_items.clicked.connect(self.pick_templates)
        folder_row.addWidget(self.btn_templates_items)
        self.items_folder_label = QLabel(str(self.templates_dir))
        self.items_folder_label.setWordWrap(True)
        self.items_folder_label.setObjectName("Muted")
        folder_row.addWidget(self.items_folder_label, 1)
        inner.addLayout(folder_row)
        self.items_save_status = QLabel("")
        self.items_save_status.setObjectName("Muted")
        self.items_save_status.setWordWrap(True)
        inner.addWidget(self.items_save_status)
        tip = QLabel("Os templates são arquivos PNG. IDs e nomes de arquivos devem corresponder aos recortes em templates/.")
        tip.setWordWrap(True)
        tip.setObjectName("Muted")
        inner.addWidget(tip)
        layout.addWidget(frame)
        self.tabs.addTab(content, "Itens")

    def _add_item_row(self, item: ItemConfig):
        row = self.item_table.rowCount()
        self.item_table.insertRow(row)
        values = ["", item.id, item.name, str(item.price_gold), "", item.icon_template,
                  item.buy_template, item.price_template, item.sold_template]
        for col, val in enumerate(values):
            cell = QTableWidgetItem(val)
            if col == 0:
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                cell.setCheckState(Qt.CheckState.Checked if item.enabled else Qt.CheckState.Unchecked)
            if col == 4:
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.item_table.setItem(row, col, cell)
        self._show_item_thumbnail(row, item.icon_template)
        self.item_table.setRowHeight(row, 54)

    def add_item(self):
        n = 1
        taken = {self.item_table.item(i, 1).text() for i in range(self.item_table.rowCount())}
        while f"item{n}" in taken:
            n += 1
        with QSignalBlocker(self.item_table):
            self._add_item_row(ItemConfig.standard(f"item{n}", f"Item {n}", 100000))
        self._rebuild_live_item_controls()

    def remove_item(self):
        row = self.item_table.currentRow()
        if row >= 0:
            self.item_table.removeRow(row)
            self._rebuild_live_item_controls()

    def _build_budget_tab(self):
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 14, 0, 0)
        frame, inner = panel("Orçamento da execução")
        grid = QGridLayout()
        b = self.cfg.budget
        self.budget_fields = {}
        fields = [
            ("gems_available", "Gemas disponíveis", b.gems_available, "gems"),
            ("gold_available", "Ouro disponível", b.gold_available, "gold"),
            ("gems_limit", "Quanto gastar de gemas (0 = todo o saldo)", b.gems_limit, "gems"),
            ("gold_limit", "Quanto gastar de ouro (0 = todo o saldo)", b.gold_limit, "gold"),
            ("refresh_cost", "Custo de cada renovação (gemas)", b.refresh_cost, "gems"),
        ]
        for idx, (key, text, value, currency) in enumerate(fields):
            group = QWidget()
            col = QVBoxLayout(group)
            col.setContentsMargins(5, 4, 5, 6)
            col.addLayout(currency_row(QLabel(text), currency))
            control = spin(value)
            control.setKeyboardTracking(False)
            control.valueChanged.connect(self.save_budget)
            self.budget_fields[key] = control
            col.addWidget(control)
            grid.addWidget(group, idx//2, idx%2)
        inner.addLayout(grid)
        hint = QLabel("Os valores são aplicados ao confirmar o campo. "
                      "O limite não pode superar o saldo. Os gastos exibidos são estimativas.")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        inner.addWidget(hint)
        self.budget_save_status = QLabel("")
        self.budget_save_status.setWordWrap(True)
        inner.addWidget(self.budget_save_status)
        self.btn_save_budget = make_button("Salvar orçamento", "Primary")
        self.btn_save_budget.clicked.connect(self.save_budget)
        inner.addWidget(self.btn_save_budget, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(frame)
        outer.addStretch()
        self.tabs.addTab(content, "Orçamento")

    def _build_calibration_tab(self):
        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(0, 14, 0, 0)
        top = QGridLayout()
        top.setSpacing(14)
        f1, left = panel("Janela e detecção")
        f2, right = panel("Área de clique seguro")
        c = self.cfg.calibration
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.cal_fields = {}
        self.cal_fields["window_title"] = QLineEdit(c.window_title)
        self.cal_fields["hotkey"] = QKeySequenceEdit(QKeySequence(display_hotkey(c.hotkey)))
        if hasattr(self.cal_fields["hotkey"], "setMaximumSequenceLength"):
            self.cal_fields["hotkey"].setMaximumSequenceLength(1)
        self.cal_fields["hotkey"].keySequenceChanged.connect(self._hotkey_preview)
        hotkey_capture_row = QWidget()
        capture_layout = QHBoxLayout(hotkey_capture_row)
        capture_layout.setContentsMargins(0, 0, 0, 0)
        capture_layout.addWidget(self.cal_fields["hotkey"], 1)
        self.btn_record_hotkey = make_button("Gravar teclas")
        self.btn_record_hotkey.clicked.connect(self.record_hotkey)
        capture_layout.addWidget(self.btn_record_hotkey)

        self.cal_fields["threshold"] = decimal(c.threshold, .60, .99)
        self.cal_fields["max_scrolls"] = spin(c.max_scrolls, 8)
        self.cal_fields["pause_min"] = decimal(c.pause_min, 0, 10, .05)
        self.cal_fields["pause_max"] = decimal(c.pause_max, 0, 10, .05)
        self.cal_fields["focus_timeout"] = decimal(c.focus_timeout, 1, 300, 1, 1)
        self.cal_fields["modal_timeout"] = decimal(c.modal_timeout, .5, 10, .5, 1)
        labels = {"window_title": "Título da janela", "hotkey": "Atalho de emergência",
                  "threshold": "Limiar de match", "max_scrolls": "Scrolls máximos",
                  "pause_min": "Pausa mínima (s)",
                  "pause_max": "Pausa máxima (s)", "focus_timeout": "Espera por foco (s)",
                  "modal_timeout": "Timeout de confirmação (s)"}
        for key, control in self.cal_fields.items():
            form.addRow(labels[key], hotkey_capture_row if key == "hotkey" else control)
        self.hotkey_hint = QLabel("Clique em Gravar teclas e pressione dois modificadores + uma tecla. "
                                  "Ctrl+Alt+Q permanece como emergência fixa.")
        self.hotkey_hint.setObjectName("Muted")
        self.hotkey_hint.setWordWrap(True)
        left.addLayout(form)
        left.addWidget(self.hotkey_hint)
        self.btn_reset_speed = make_button("Restaurar velocidade do script original")
        self.btn_reset_speed.clicked.connect(self.reset_speed)
        left.addWidget(self.btn_reset_speed)
        left.addStretch()
        self._calibration_detection_panel = f1
        top.addWidget(f1, 0, 0)
        self.preview = SafeAreaPreview(c.safe_area, c.overlay_area, c.auto_overlay)
        self.preview.area_changed.connect(self._update_area_fields)
        self.preview.overlay_changed.connect(self._update_overlay_fields)
        right.addWidget(self.preview)
        preview_actions = QHBoxLayout()
        self.btn_area_image = make_button("Abrir imagem")
        self.btn_area_image.clicked.connect(self.pick_area_image)
        self.btn_area_live = make_button("Capturar janela")
        self.btn_area_live.clicked.connect(self.capture_game_window)
        preview_actions.addWidget(self.btn_area_image)
        preview_actions.addWidget(self.btn_area_live)
        right.addLayout(preview_actions)
        coords = QGridLayout()
        self.area_fields = {}
        for idx, (key, val) in enumerate(zip(("x0", "y0", "x1", "y1"), c.safe_area)):
            control = decimal(val, 0, 1)
            control.valueChanged.connect(self._update_area_preview)
            self.area_fields[key] = control
            coords.addWidget(QLabel(key), idx // 2, (idx % 2) * 2)
            coords.addWidget(control, idx // 2, (idx % 2) * 2 + 1)
        right.addLayout(coords)
        green_hint = QLabel("Arraste a área verde para mover; arraste o canto inferior direito "
                            "para redimensionar. As coordenadas são atualizadas automaticamente.")
        green_hint.setObjectName("Muted")
        green_hint.setWordWrap(True)
        right.addWidget(green_hint)
        self.overlay_enabled = QCheckBox("Mostrar painel compacto sobre a loja")
        self.overlay_enabled.setChecked(c.auto_overlay)
        self.overlay_enabled.toggled.connect(self.preview.set_overlay_enabled)
        right.addWidget(self.overlay_enabled)
        overlay_hint = QLabel("Arraste a área azul para mover; arraste seu canto inferior direito "
                              "para redimensionar. Não cubra itens, botões nem a área verde.")
        overlay_hint.setObjectName("Muted")
        overlay_hint.setWordWrap(True)
        right.addWidget(overlay_hint)
        overlay_grid = QGridLayout()
        self.overlay_fields = {}
        for idx, (key, val) in enumerate(zip(("x0", "y0", "x1", "y1"), c.overlay_area)):
            control = decimal(val, 0, 1, .01, 3)
            control.valueChanged.connect(self._update_overlay_preview)
            self.overlay_fields[key] = control
            overlay_grid.addWidget(QLabel("Azul " + key), idx//2, (idx%2)*2)
            overlay_grid.addWidget(control, idx//2, (idx%2)*2+1)
        right.addLayout(overlay_grid)
        hint = QLabel("A área verde é relativa à janela do jogo; mantenha-a longe de botões e pop-ups.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        right.addWidget(hint)
        self.area_warning = QLabel("")
        self.area_warning.setObjectName("Muted")
        self.area_warning.setWordWrap(True)
        right.addWidget(self.area_warning)
        self.overlay_enabled.toggled.connect(self._update_area_warning)
        self.btn_reset_calibration = make_button("Restaurar calibração de fábrica")
        self.btn_reset_calibration.clicked.connect(self.reset_calibration)
        right.addWidget(self.btn_reset_calibration)
        self.btn_templates = make_button("Escolher pasta de templates")
        self.btn_templates.clicked.connect(self.pick_templates)
        right.addWidget(self.btn_templates)
        self.template_folder_label = QLabel(str(self.templates_dir))
        self.template_folder_label.setWordWrap(True)
        self.template_folder_label.setObjectName("Muted")
        right.addWidget(self.template_folder_label)
        self._calibration_area_panel = f2
        self._calibration_top_layout = top
        top.addWidget(f2, 0, 1)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)
        main.addLayout(top)
        self._update_area_warning()
        diag, dl = panel("Diagnóstico visual — sem clicar no jogo")
        instruction = QLabel("Capture a janela inteira do jogo com a loja aberta e sem diálogos, "
                             "ou abra um PNG nessa mesma resolução. O teste ajusta a escala dos "
                             "templates e salva o resultado quando reconhece Renovar. "
                             "A calibração não move o mouse.")
        instruction.setWordWrap(True)
        instruction.setObjectName("Muted")
        dl.addWidget(instruction)
        browse = QHBoxLayout()
        self.capture_label = QLineEdit()
        self.capture_label.setReadOnly(True)
        self.btn_capture = make_button("Abrir PNG")
        self.btn_capture.clicked.connect(self.pick_capture)
        btn_capture_window = make_button("Capturar janela")
        btn_capture_window.clicked.connect(self.capture_game_window)
        self.btn_diagnose = make_button("Calibrar e salvar escala")
        self.btn_diagnose.clicked.connect(self.run_diagnostic)
        browse.addWidget(self.capture_label, 1)
        browse.addWidget(self.btn_capture)
        browse.addWidget(btn_capture_window)
        browse.addWidget(self.btn_diagnose)
        dl.addLayout(browse)
        self.diagnostic_label = QLabel("Nenhuma captura analisada.")
        self.diagnostic_label.setWordWrap(True)
        dl.addWidget(self.diagnostic_label)
        self.diagnostic_image = QLabel()
        self.diagnostic_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diagnostic_image.setMinimumHeight(200)
        dl.addWidget(self.diagnostic_image)
        main.addWidget(diag)
        self.btn_save_calibration = make_button("Salvar calibração", "Primary")
        self.btn_save_calibration.clicked.connect(lambda: self.save_settings(notify=True))
        main.addWidget(self.btn_save_calibration, alignment=Qt.AlignmentFlag.AlignLeft)
        self.settings_save_status = QLabel("")
        self.settings_save_status.setObjectName("Muted")
        main.addWidget(self.settings_save_status)
        main.addStretch()
        self.tabs.addTab(scroll_wrap(content), "Calibração")

    def _build_reports_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 14, 0, 0)
        frame, inside = panel("Relatório da última execução")
        self.report_label = QLabel("Nenhuma execução nesta sessão.")
        self.report_label.setWordWrap(True)
        inside.addWidget(self.report_label)
        layout.addWidget(frame)
        history, inner = panel("Histórico de execuções")
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels([
            "Início", "Renovações", "Compras verificadas", "Gemas estimadas",
            "Ouro estimado", "Motivo de parada"])
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        inner.addWidget(self.history_table)
        actions = QHBoxLayout()
        self.btn_delete_history = make_button("Apagar selecionados", "Danger")
        self.btn_delete_history.clicked.connect(self.delete_selected_history)
        actions.addWidget(self.btn_delete_history)
        self.btn_clear_history = make_button("Apagar todo o histórico", "Danger")
        self.btn_clear_history.clicked.connect(self.delete_all_history)
        actions.addWidget(self.btn_clear_history)
        actions.addStretch()
        inner.addLayout(actions)
        self.history_status = QLabel("")
        self.history_status.setObjectName("Muted")
        inner.addWidget(self.history_status)
        layout.addWidget(history, 1)
        self._update_history()
        self.tabs.addTab(content, "Relatório")

    def _rebuild_live_item_controls(self):
        for check in self.live_item_checks.values():
            self.active_items_layout.removeWidget(check)
            check.setParent(None)
            check.deleteLater()
        self.live_item_checks.clear()
        for row in range(self.item_table.rowCount()):
            ident = self.item_table.item(row, 1).text().strip()
            if not ident:
                continue
            name = self.item_table.item(row, 2).text().strip() or ident
            filename = self.item_table.item(row, 5).text().strip()
            active = self.item_table.item(row, 0).checkState() == Qt.CheckState.Checked
            pixmap = QPixmap(str(self.templates_dir / filename)) if filename else QPixmap()
            control = QCheckBox(name if pixmap.isNull() else "")
            if not pixmap.isNull():
                control.setIcon(QIcon(pixmap))
                control.setIconSize(QSize(30, 30))
            control.setToolTip(name)
            control.setAccessibleName(name)
            control.setChecked(active)
            control.toggled.connect(lambda value, item_id=ident: self.change_live_item(item_id, value))
            self.active_items_layout.addWidget(control)
            self.live_item_checks[ident] = control

    def _sync_item_labels(self, cell):
        """Atualiza a aba Bot ao editar os itens."""
        if cell.column() == 5:
            self._show_item_thumbnail(cell.row(), cell.text().strip())
        if cell.column() in (1, 2, 5):
            self._rebuild_live_item_controls()
        elif cell.column() == 0:
            ident_cell = self.item_table.item(cell.row(), 1)
            if ident_cell is not None and ident_cell.text() in self.live_item_checks:
                check = self.live_item_checks[ident_cell.text()]
                blocker = QSignalBlocker(check)
                check.setChecked(cell.checkState() == Qt.CheckState.Checked)
                del blocker

    def change_live_item(self, ident: str, enabled: bool):
        if self.controller.running:
            try:
                self.controller.set_item_enabled(ident, enabled)
            except (ValueError, BotError) as exc:
                check = self.live_item_checks[ident]
                with QSignalBlocker(check):
                    check.setChecked(not enabled)
                QMessageBox.warning(self, "Item não alterado", str(exc))
                return
        else:
            for row in range(self.item_table.rowCount()):
                if self.item_table.item(row, 1).text() == ident:
                    self.item_table.item(row, 0).setCheckState(
                        Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
                    break

    def open_budget(self):
        self.tabs.setCurrentIndex(2)
        self.show_panel()
        self.budget_fields["gems_available"].setFocus()

    def _show_item_thumbnail(self, row, filename):
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setToolTip(filename)
        image_path = self.templates_dir / filename
        pix = QPixmap(str(image_path)) if image_path.is_file() else QPixmap()
        if not pix.isNull():
            label.setPixmap(pix.scaled(75, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        else:
            label.setText("Sem PNG")
        self.item_table.setCellWidget(row, 4, label)

    def _refresh_item_thumbnails(self):
        for row in range(self.item_table.rowCount()):
            self._show_item_thumbnail(row, self.item_table.item(row, 5).text().strip())
        self._rebuild_live_item_controls()

    def _collect_items(self) -> list[ItemConfig]:
        items = []
        for row in range(self.item_table.rowCount()):
            def value(col):
                cell = self.item_table.item(row, col)
                return cell.text().strip() if cell else ""
            text_price = value(3).replace(".", "").replace(" ", "")
            if not re.fullmatch(r"[0-9]+", text_price):
                raise ValueError(f"Preço inválido na linha {row+1}.")
            items.append(ItemConfig(
                id=value(1), name=value(2), price_gold=int(text_price),
                enabled=self.item_table.item(row, 0).checkState() == Qt.CheckState.Checked,
                lower_half=next((it.lower_half for it in self.cfg.items
                                 if it.id == value(1)), True),
                icon_template=value(5), buy_template=value(6),
                price_template=value(7), sold_template=value(8)))
        return items

    def _hotkey_for_config(self) -> tuple[str, bool]:
        """Retém o último atalho válido enquanto a captura estiver incompleta.

        O Ctrl+Alt+Q de emergência permanece ativo independentemente da edição.
        """
        raw = self.cal_fields["hotkey"].keySequence().toString(
            QKeySequence.SequenceFormat.PortableText)
        return select_hotkey_for_save(raw, self.cfg.calibration.hotkey or DEFAULT_HOTKEY)

    def save_items(self):
        if self.controller.running:
            QMessageBox.information(self, "Bot em execução", "Altere apenas os botões de busca na aba Bot durante a execução.")
            return
        try:
            # Salvar Itens NÃO deve aplicar alterações ainda incompletas
            # de atalho, orçamento ou áreas de calibração.
            cfg = AppConfig.from_dict(self.cfg.to_dict())
            cfg.items = self._collect_items()
            cfg.templates_dir = (str(self.templates_dir)
                                 if self.templates_dir != data_directory() / "templates" else "")
            validate_config(cfg)
            checked = validate_item_templates(cfg.items, self.templates_dir)
            save_config(cfg)
            self.cfg = cfg
            self.templates_dir = user_templates(cfg)
            self.items_save_status.setText(f"✓ {len(cfg.items)} item(ns) salvo(s); {len(checked)} PNGs encontrados e validados.")
            self._refresh_item_thumbnails()
            QMessageBox.information(self, "Itens salvos",
                f"Configuração salva com sucesso.\n"
                f"{len(cfg.items)} itens cadastrados e {len(checked)} imagens verificadas.")
        except (ValueError, BotError, OSError) as exc:
            self.items_save_status.setText("✗ Não foi possível salvar: " + str(exc))
            QMessageBox.warning(self, "Itens/templates inválidos", str(exc))

    def save_budget(self):
        try:
            budget = BudgetConfig(**{name: control.value() for name, control in self.budget_fields.items()})
            # O orçamento é independente da edição da calibração/atalho.
            cfg = AppConfig.from_dict(self.cfg.to_dict())
            cfg.budget = budget
            if self.controller.running:
                self.controller.update_budget(budget, persist=lambda: save_config(cfg))
            else:
                save_config(cfg)
            self.cfg = cfg
            self._update_budget_metrics()
            self.budget_save_status.setText("✓ Orçamento aplicado e salvo.")
            return True
        except (ValueError, OSError, RuntimeError) as exc:
            self.budget_save_status.setText(f"✗ Orçamento anterior em uso. {exc}")
            return False

    def pick_area_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Imagem da loja", str(Path.home()),
                                               "Imagens (*.png *.jpg *.jpeg *.bmp)")
        if path:
            pix = QPixmap(path)
            if pix.isNull():
                QMessageBox.warning(self, "Imagem inválida", "Não foi possível abrir esta imagem.")
                return
            self.preview.set_background(pix)
            self.screenshot_path = path
            self.capture_label.setText(path)

    def capture_game_window(self):
        if self.controller.running:
            QMessageBox.information(self, "Bot em execução", "Pare o bot para capturar uma nova imagem de calibração.")
            return
        self.hide()
        QTimer.singleShot(900, self._finish_game_capture)

    def _finish_game_capture(self):
        try:
            import mss
            import numpy as np
            import cv2
            from app.platform.windows import TargetWindow, Win32
            api = Win32()
            target = TargetWindow.locate(api, self.cal_fields["window_title"].text().strip())
            import time
            time.sleep(0.25)  # o Windows precisa apresentar a janela antes da captura
            rect = target.ensure()
            with mss.mss() as sct:
                image = np.asarray(sct.grab({"left": rect.left, "top": rect.top,
                                                "width": rect.width, "height": rect.height}))
            target.ensure()
            rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            file_path = data_directory() / "captura_calibracao.png"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            ok, encoded = cv2.imencode(".png", rgb)
            if not ok:
                raise ValueError("Não foi possível gerar o PNG.")
            file_path.write_bytes(encoded.tobytes())
            self.screenshot_path = str(file_path)
            self.capture_label.setText(str(file_path))
            self.preview.set_background(QPixmap(str(file_path)))
        except Exception as exc:
            QMessageBox.warning(self, "Captura indisponível", str(exc))
        finally:
            self.show_panel()

    def reset_speed(self):
        defaults = CalibrationConfig()
        for key in ("pause_min", "pause_max", "max_scrolls"):
            self.cal_fields[key].setValue(getattr(defaults, key))
        self.settings_save_status.setText("Velocidade do script original carregada. Salve para aplicar.")

    def reset_calibration(self):
        if self.controller.running:
            QMessageBox.warning(self, "Bot ativo", "Altere a calibração somente com o bot parado.")
            return
        if QMessageBox.question(self, "Restaurar padrões",
                "Restaurar os valores de calibração de fábrica? Salve para persistir.") != QMessageBox.StandardButton.Yes:
            return
        defaults = CalibrationConfig()
        for key, field in self.cal_fields.items():
            value = getattr(defaults, key)
            if isinstance(field, QKeySequenceEdit):
                field.setKeySequence(QKeySequence(display_hotkey(value)))
            elif isinstance(field, QLineEdit):
                field.setText(str(value))
            else:
                field.setValue(value)
        for key, value in zip(("x0", "y0", "x1", "y1"), defaults.safe_area):
            self.area_fields[key].setValue(value)
        for key, value in zip(("x0", "y0", "x1", "y1"), defaults.overlay_area):
            self.overlay_fields[key].setValue(value)
        self.overlay_enabled.setChecked(defaults.auto_overlay)
        self._update_area_preview()
        self._update_overlay_preview()
        self._hotkey_preview()
        self.settings_save_status.setText("Padrões restaurados. Salve a calibração para aplicar.")

    def _make_tray(self):
        pix = QPixmap(str(bundled_root() / "assets" / "app_icon.png"))
        if pix.isNull():
            pix = QPixmap(str(bundled_root() / "assets" / "app_icon.ico"))
        if pix.isNull():
            pix = QPixmap(48, 48)
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#177ddc"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 47, 47, 9, 9)
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
            painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "E7")
            painter.end()
        self.setWindowIcon(QIcon(pix))
        self.tray = QSystemTrayIcon(QIcon(pix), self)
        menu = QMenu()
        show_action = menu.addAction("Abrir painel")
        show_action.triggered.connect(self.show_panel)
        self.tray_stop_action = menu.addAction("Parar bot agora")
        self.tray_stop_action.setEnabled(False)
        self.tray_stop_action.triggered.connect(self.stop_bot)
        menu.addSeparator()
        exit_action = menu.addAction("Sair")
        exit_action.triggered.connect(self.exit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_panel()
                            if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _display_panel(self):
        self.overlay.hide()
        self.overlay.reset_return_button()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_panel(self):
        if self.controller.running and self.controller.runner is not None:
            self.controller.set_ui_paused(True)
            self._await_safe_panel()
        else:
            self._display_panel()

    def _await_safe_panel(self):
        runner = self.controller.runner
        if not self.controller.running or runner is None or runner.pause_acknowledged():
            self._display_panel()
        else:
            QTimer.singleShot(120, self._await_safe_panel)

    def resume_game(self):
        if self.controller.running:
            if self.cfg.calibration.auto_overlay:
                self.hide() if self.tray.isVisible() else self.showMinimized()
            self.controller.set_ui_paused(False)
            QTimer.singleShot(500, self._maybe_show_overlay)
            self.append_log("Retorne o foco à janela do jogo.")

    def _update_area_preview(self, _value=None):
        self.preview.set_area(tuple(self.area_fields[k].value()
                                    for k in ("x0", "y0", "x1", "y1")))
        self._update_area_warning()

    def _update_area_fields(self, area: tuple):
        for key, value in zip(("x0", "y0", "x1", "y1"), area):
            field = self.area_fields[key]
            blocker = QSignalBlocker(field)
            field.setValue(value)
            del blocker
        self._update_area_warning()

    def _update_area_warning(self, _value=None):
        if not hasattr(self, "area_warning"):
            return
        if self.overlay_enabled.isChecked() and rectangles_overlap(
                self.preview.area, self.preview.overlay_area):
            self.area_warning.setText(
                "⚠ A área verde está sobreposta à azul. Separe as regiões antes de salvar.")
        else:
            self.area_warning.setText("")

    def _update_overlay_preview(self, _value=None):
        self.preview.set_overlay_area(tuple(self.overlay_fields[k].value()
                                            for k in ("x0", "y0", "x1", "y1")))
        self._update_area_warning()

    def _update_overlay_fields(self, area: tuple):
        for key, value in zip(("x0", "y0", "x1", "y1"), area):
            field = self.overlay_fields[key]
            blocker = QSignalBlocker(field)
            field.setValue(value)
            del blocker
        self._update_area_warning()

    def record_hotkey(self):
        editor = self.cal_fields["hotkey"]
        editor.clear()
        editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self.hotkey_hint.setText("Pressione uma combinação: por exemplo Ctrl + Alt + E. "
                                "Depois clique em Salvar calibração.")

    def _hotkey_preview(self, _sequence=None):
        raw = self.cal_fields["hotkey"].keySequence().toString(
            QKeySequence.SequenceFormat.PortableText)
        try:
            chosen = display_hotkey(raw)
            text = f"Emergência: {display_hotkey(DEFAULT_HOTKEY)} (fixo)"
            if normalize_hotkey(raw) != DEFAULT_HOTKEY:
                text += f" + {chosen} (salvar para aplicar)"
            self.hotkey_label.setText(text + " · ou Parar na bandeja")
        except BotError:
            previous = self.cfg.calibration.hotkey or DEFAULT_HOTKEY
            label = f"Emergência: {display_hotkey(DEFAULT_HOTKEY)} (fixo)"
            if previous != DEFAULT_HOTKEY:
                label += f" + {display_hotkey(previous)} (ativo)"
            self.hotkey_label.setText(label + " · gravação incompleta, mantendo anterior")


    def _refresh_template_labels(self):
        self.template_folder_label.setText(str(self.templates_dir))
        self.items_folder_label.setText(str(self.templates_dir))
        self._hotkey_preview()

    def pick_templates(self):
        path = QFileDialog.getExistingDirectory(self, "Pasta com PNGs da loja", str(self.templates_dir))
        if path:
            self.templates_dir = Path(path)
            self._refresh_template_labels()
            self._refresh_item_thumbnails()

    def pick_capture(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Captura PNG da loja", str(Path.home()),
                                                   "Imagens PNG (*.png)")
        if filename:
            self.screenshot_path = filename
            self.capture_label.setText(filename)
            self.preview.set_background(QPixmap(filename))

    def run_diagnostic(self):
        if not self.screenshot_path:
            QMessageBox.information(self, "Captura ausente", "Capture a janela do jogo ou abra um PNG.")
            return
        try:
            cfg = self._collect_config()
            validate_config(cfg)
            png_data, lines, profile = analyze_image(Path(self.screenshot_path), cfg, self.templates_dir)
            pix = QPixmap()
            if not pix.loadFromData(png_data):
                raise ValueError("Não foi possível exibir o resultado do teste.")
            self.image_bytes = png_data
            self.diagnostic_image.setPixmap(pix.scaled(QSize(680, 290), Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation))
            if profile is not None:
                save_template_scale(*profile)
                lines.append("Escala salva para essa resolução e conjunto de templates.")
            else:
                lines.append("Sem escala validada para salvar.")
            self.diagnostic_label.setText("\n".join(lines))
        except Exception as exc:
            QMessageBox.warning(self, "Falha no diagnóstico", str(exc))

    def _collect_config(self) -> AppConfig:
        budget = BudgetConfig(**{name: control.value()
                                 for name, control in self.budget_fields.items()})
        calibration_values = {}
        for key, control in self.cal_fields.items():
            if key == "hotkey":
                calibration_values[key], _ = self._hotkey_for_config()
            elif isinstance(control, QLineEdit):
                calibration_values[key] = control.text().strip()
            else:
                calibration_values[key] = control.value()
        calibration = CalibrationConfig(
            **calibration_values,
            safe_area=tuple(self.area_fields[k].value() for k in ("x0", "y0", "x1", "y1")),
            auto_overlay=self.overlay_enabled.isChecked(),
            overlay_area=tuple(self.overlay_fields[k].value()
                               for k in ("x0", "y0", "x1", "y1")))
        saved_dir = (str(self.templates_dir)
                     if self.templates_dir != data_directory() / "templates" else "")
        return AppConfig(budget=budget, calibration=calibration,
                         items=self._collect_items(), templates_dir=saved_dir)

    def save_settings(self, notify=True):
        if self.controller.running:
            QMessageBox.warning(self, "Bot ativo", "Use o botão de orçamento para alterações durante a execução.")
            return False
        try:
            cfg = self._collect_config()
            _, hotkey_kept = self._hotkey_for_config()
            validate_config(cfg)
            save_config(cfg)
            self.cfg = cfg
            self.templates_dir = user_templates(cfg)
            self._refresh_template_labels()
            self._refresh_item_thumbnails()
            self._update_budget_metrics()
            notice = (" Atalho incompleto: o atalho anterior foi mantido."
                      if hotkey_kept else "")
            self.settings_save_status.setText("✓ Configurações salvas no AppData." + notice)
            if hotkey_kept:
                # Restaurar o campo ao valor efetivamente persistido evita
                # avisos recorrentes ao navegar entre abas.
                self.cal_fields["hotkey"].setKeySequence(
                    QKeySequence(display_hotkey(cfg.calibration.hotkey)))
                self.hotkey_hint.setText(
                    "O atalho incompleto não foi aplicado; o anterior foi preservado. "
                    "Para alterá-lo, clique em Gravar teclas e finalize a combinação.")
            if notify:
                QMessageBox.information(self, "Calibração salva",
                                        "Configurações salvas e validadas com sucesso." + notice)
            return True
        except (ValueError, BotError, OSError) as exc:
            QMessageBox.warning(self, "Configuração inválida", str(exc))
            return False

    def _register_hotkey(self):
        self._unregister_hotkey()
        self.hotkey_handles = []
        try:
            import keyboard
            self.hotkey_module = keyboard
            # Parada independente da configuração editável.
            fixed = keyboard.add_hotkey(DEFAULT_HOTKEY, self.controller.stop)
            self.hotkey_handles.append(fixed)
            custom = normalize_hotkey(self.cfg.calibration.hotkey)
            if custom != DEFAULT_HOTKEY:
                try:
                    self.hotkey_handles.append(keyboard.add_hotkey(custom, self.controller.stop))
                except Exception as exc:
                    log_diagnostic(f"Falha no atalho personalizado: {exc}", "warn")
                    self.append_log("O atalho personalizado está indisponível. Use Ctrl+Alt+Q para parar.", "warn")
            log_diagnostic("Atalhos de parada registrados: " + DEFAULT_HOTKEY +
                           (" e " + custom if custom != DEFAULT_HOTKEY else ""))
        except Exception as exc:
            self.hotkey_handles = []
            self.hotkey_module = None
            log_diagnostic(f"Atalho global indisponível: {exc}", "warn")
            self.append_log("Atalho de emergência indisponível. Use o botão Parar no app ou na bandeja.", "warn")

    def _unregister_hotkey(self):
        if self.hotkey_module is not None:
            for handle in getattr(self, "hotkey_handles", []):
                try:
                    self.hotkey_module.remove_hotkey(handle)
                except Exception:
                    pass
        self.hotkey_handles = []
        self.hotkey_module = None

    def _maybe_show_overlay(self):
        if (not self.controller.running or not self.cfg.calibration.auto_overlay or
                self._overlay_blocked or (self.isVisible() and not self.isMinimized()) or
                self.overlay.isVisible()):
            return
        try:
            from app.platform.windows import Win32
            from app.platform.passive_overlay import enable_action_overlay
            api = Win32()
            hwnd = api.find(self.cfg.calibration.window_title)
            game_rect = api.rect(hwnd)
            self.overlay.position_over_game(
                (game_rect.left, game_rect.top, game_rect.width, game_rect.height),
                self.cfg.calibration.overlay_area)
            self.overlay.show()
            # Não recebe foco, mas permite clicar no botão Voltar ao app.
            # Continua obrigatoriamente excluído das capturas MSS.
            if not enable_action_overlay(int(self.overlay.winId())):
                self.overlay.hide()
                self._overlay_blocked = True
                if self.tray.isVisible():
                    self.tray.showMessage("Pop-up desativado",
                        "Não foi possível excluir o painel da captura do jogo. "
                        "Acompanhe pela bandeja.",
                        QSystemTrayIcon.MessageIcon.Warning, 4000)
                log_diagnostic("O Windows não conseguiu excluir o painel compacto das capturas.", "warn")
                self.append_log("Painel compacto desativado. Acompanhe o bot pelo app ou pela bandeja.", "warn")
        except Exception as exc:
            self.overlay.hide()
            self._overlay_blocked = True
            log_diagnostic(f"Falha ao abrir o painel compacto: {exc}", "warn")
            self.append_log("Painel compacto indisponível. Acompanhe o bot pelo app ou pela bandeja.", "warn")

    def _set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.tray_stop_action.setEnabled(running)
        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, not running or i in (0, 2, 4))
        self.budget_fields["refresh_cost"].setEnabled(not running)
        self.btn_edit_gems.setEnabled(True)
        self.btn_edit_gold.setEnabled(True)
        self.btn_resume_game.setVisible(running)

    def start_bot(self):
        if self.controller.running:
            return
        if not self.save_settings(notify=False):
            return
        try:
            path = prepare_templates(self.cfg)
            self._register_hotkey()
            self._overlay_blocked = False
            self._set_running(True)
            self.status.setText("●  PREPARANDO")
            self.status.setStyleSheet("color:#52a8ff;font-weight:600;")
            if self.cfg.calibration.auto_overlay:
                self.hide() if self.tray.isVisible() else self.showMinimized()
            self.controller.start(self.cfg, path)
        except Exception as exc:
            self._set_running(False)
            self._unregister_hotkey()
            self.show_panel()
            QMessageBox.critical(self, "Não foi possível iniciar", str(exc))

    def stop_bot(self):
        if self.controller.running:
            self.controller.stop()
            self.append_log("Parada solicitada. Aguarde o término da ação em andamento.", "warn")

    def append_log(self, text: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.appendPlainText(f"{timestamp}  [{level.upper()}]  {text}")
        scroll = self.console.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def _update_budget_metrics(self):
        budget = self.cfg.budget
        limit_gems = budget.gems_limit or budget.gems_available
        limit_gold = budget.gold_limit or budget.gold_available
        gems = self._metric_state.get("gems_estimated", 0)
        gold = self._metric_state.get("gold_estimated", 0)
        self.gem_label.setText(f"Gemas estimadas: {fmt(gems)} / {fmt(limit_gems)}")
        self.gold_label.setText(f"Ouro estimado: {fmt(gold)} / {fmt(limit_gold)}")
        self.gem_bar.setRange(0, max(1, limit_gems))
        self.gold_bar.setRange(0, max(1, limit_gold))
        self.gem_bar.setValue(min(gems, limit_gems))
        self.gold_bar.setValue(min(gold, limit_gold))

    def update_metrics(self, state: dict):
        self._metric_state = state
        self._update_budget_metrics()
        self.overlay.update_state(state)
        if state.get("status") in ("executando", "pausado_sem_itens", "pausado_por_foco"):
            self._maybe_show_overlay()
        for key, widget in self.metric_labels.items():
            widget.setText(fmt(state.get(key, 0)))
        status = state.get("status", "")
        title = {"executando": "EM EXECUÇÃO", "preparando": "PREPARANDO",
                 "pausado_por_foco": "PAUSADO — FOCO",
                 "pausado_configuracao": "PAUSADO — CONFIGURAÇÃO",
                 "pausado_sem_itens": "PAUSADO — SEM ITENS",
                 "resultado_incerto": "RESULTADO INCERTO", "erro": "ERRO",
                 "concluido": "FINALIZADO", "cancelado": "CANCELADO"}.get(status, status.upper())
        color = "#49aa19" if status == "executando" else (
            "#f5b44b" if status in ("preparando", "pausado_por_foco", "pausado_sem_itens", "pausado_configuracao") else "#ff7875"
            if status in ("erro", "resultado_incerto") else "#a6a6a6")
        self.status.setText("●  " + title)
        self.status.setStyleSheet(f"color:{color};font-weight:600;")

    def execution_finished(self, result: dict):
        self.overlay.hide()
        self._unregister_hotkey()
        self.last_result = result
        self._set_running(False)
        try:
            add_history(result)
        except OSError as exc:
            log_diagnostic(f"Falha ao salvar histórico: {exc}", "warn")
            self.append_log("O relatório desta execução não pôde ser salvo no histórico.", "warn")
        self.report_label.setText(
            f"Status: {result['status']}\n"
            f"Renovações: {fmt(result['refreshes'])} · Gemas estimadas: {fmt(result['gems_estimated'])}\n"
            f"Compras verificadas: {result['purchases_verified']} · Ouro estimado: {fmt(result['gold_estimated'])}\n"
            f"Por item: {result['purchases_by_item']}\n"
            f"Motivo: {result['reason']}\n"
            "A contabilidade estima gastos pela ação e NÃO confere os saldos reais do jogo."
        )
        self._update_history()
        self.tabs.setCurrentIndex(4)
        self._display_panel()
        if result["status"] == "concluido":
            self.append_log(f"Execução concluída. {result['reason']}")
        elif result["status"] == "cancelado":
            self.append_log("Execução cancelada.")
        elif result["status"] == "resultado_incerto":
            QMessageBox.warning(self, "Resultado incerto",
                                "Uma ação foi enviada, mas não pôde ser verificada. "
                                "Confira os saldos/itens do jogo antes de iniciar outra execução.")

    def delete_selected_history(self):
        selected = sorted({cell.row() for cell in self.history_table.selectedIndexes()})
        if not selected:
            QMessageBox.information(self, "Histórico", "Selecione uma ou mais linhas do relatório.")
            return
        count = len(selected)
        question = (f"Apagar {count} execução(ões) selecionada(s) do histórico?\n"
                    "Esta operação não pode ser desfeita.")
        if QMessageBox.question(self, "Confirmar exclusão", question,
                                QMessageBox.StandardButton.Yes |
                                QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = remove_history_rows(set(selected))
            self._update_history()
            self.history_status.setText(f"✓ {deleted} registro(s) removido(s) do histórico.")
        except OSError as exc:
            QMessageBox.warning(self, "Falha ao excluir histórico", str(exc))

    def delete_all_history(self):
        if QMessageBox.question(self, "Apagar todo o histórico",
                "Apagar permanentemente TODAS as execuções salvas?\n"
                "Esta operação não pode ser desfeita.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = clear_history()
            self._update_history()
            self.history_status.setText(f"✓ Histórico limpo ({deleted} registro(s)).")
        except OSError as exc:
            QMessageBox.warning(self, "Falha ao limpar histórico", str(exc))

    def _update_history(self):
        history = read_history()
        self.history_table.setRowCount(len(history))
        for row, result in enumerate(history):
            values = (result.get("started_at", ""), str(result.get("refreshes", 0)),
                      str(result.get("purchases_verified", 0)),
                      fmt(result.get("gems_estimated", 0)),
                      fmt(result.get("gold_estimated", 0)), result.get("reason", ""))
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.history_table.setItem(row, col, item)

    def exit_app(self):
        if self.controller.running:
            self.stop_bot()
            self.show_panel()
            QMessageBox.information(self, "Execução em andamento",
                                    "Foi solicitada a parada. Feche novamente após o encerramento.")
            return
        self._unregister_hotkey()
        self.tray.hide()
        self.overlay.close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.controller.running:
            if self.tray.isVisible():
                self.hide()
                self.controller.set_ui_paused(False)
                self.tray.showMessage("Epic7 Shop Bot", "Bot ativo; use Parar na bandeja ou o atalho.",
                                      QSystemTrayIcon.MessageIcon.Information, 2500)
            else:
                self.showMinimized()  # sem bandeja, preserva acesso ao botão Parar
                self.controller.set_ui_paused(False)
            event.ignore()
            return
        self._unregister_hotkey()
        self.tray.hide()
        self.overlay.close()
        event.accept()
        QApplication.instance().quit()

"""Interface Qt Widgets criada do zero a partir das funções do protótipo visual.

A UI não executa visão computacional nem manipula mouse. Apenas configura,
exibe métricas e envia comandos para a thread do BotRunner.
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.config import (add_history, data_directory, load_config,
                        prepare_templates, read_history, save_config, user_templates)
from app.core.budget import validate_config
from app.models import AppConfig, BudgetConfig, CalibrationConfig, ItemConfig, BotError
from app.ui.controller import BotController
from app.ui.diagnostics import analyze_image


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


def spin(value: int, max_value: int = 2_147_483_647) -> QSpinBox:
    control = QSpinBox()
    control.setRange(0, max_value)
    control.setValue(value)
    control.setMinimumHeight(32)
    control.setGroupSeparatorShown(True)
    return control


def decimal(value: float, minimum: float, maximum: float, step=0.01, digits=2):
    control = QDoubleSpinBox()
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
    def __init__(self, area):
        super().__init__()
        self.area = area
        self.setMinimumHeight(205)

    def set_area(self, area):
        self.area = area
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bounds = self.rect().adjusted(2, 2, -2, -2)
        p.fillRect(bounds, QColor("#211a13"))
        p.setPen(QPen(QColor("#453b32"), 1))
        for y in (0.16, 0.36, 0.56, 0.76):
            r = bounds.adjusted(int(bounds.width() * .60), int(bounds.height() * y),
                                -int(bounds.width() * .06), -int(bounds.height() * (1-y-.12)))
            p.drawRoundedRect(r, 3, 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#267c18"))
        p.drawRoundedRect(int(bounds.width()*.27), int(bounds.height()*.87),
                          int(bounds.width()*.22), int(bounds.height()*.08), 4, 4)
        x0, y0, x1, y1 = self.area
        x, y = int(x0*bounds.width()), int(y0*bounds.height())
        w, h = int((x1-x0)*bounds.width()), int((y1-y0)*bounds.height())
        p.setBrush(QColor(60, 180, 70, 48))
        p.setPen(QPen(QColor("#49aa19"), 2, Qt.PenStyle.DashLine))
        p.drawRect(x, y, w, h)
        p.end()


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
        self._startup_error = ""
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
        self.append_log("Aplicação pronta. Verifique o orçamento e a calibração antes de iniciar.", "info")
        if self._startup_error:
            self.append_log(self._startup_error, "error")
            QMessageBox.warning(self, "Configuração anterior inválida", self._startup_error)
        try:
            prepare_templates(self.cfg)
        except OSError as exc:
            self.append_log(f"Templates: {exc}", "warn")
        self._refresh_template_labels()

    def _build_bot_tab(self):
        content = QWidget()
        line = QHBoxLayout(content)
        line.setContentsMargins(0, 14, 0, 0)
        line.setSpacing(15)
        frame, col = panel("Controle")
        frame.setMinimumWidth(310)
        frame.setMaximumWidth(365)
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
        col.addWidget(self.gem_label)
        col.addWidget(self.gem_bar)
        col.addWidget(self.gold_label)
        col.addWidget(self.gold_bar)
        col.addSpacing(10)
        self.metric_labels = {}
        stats = QGridLayout()
        metrics = [("refreshes", "Renovações"), ("purchases_verified", "Compras verificadas"),
                   ("gems_estimated", "Gemas estimadas"), ("gold_estimated", "Ouro estimado")]
        for idx, (key, title) in enumerate(metrics):
            cell = QFrame()
            cell.setStyleSheet("QFrame {background:#292929; border-radius:5px;}")
            cellbox = QVBoxLayout(cell)
            cellbox.setSpacing(4)
            name = QLabel(title)
            name.setObjectName("Muted")
            value = QLabel("0")
            value.setObjectName("Metric")
            cellbox.addWidget(name)
            cellbox.addWidget(value)
            stats.addWidget(cell, idx//2, idx%2)
            self.metric_labels[key] = value
        col.addLayout(stats)
        col.addStretch()
        line.addWidget(frame)
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
            "Ativo", "ID", "Item", "Preço (ouro)", "Metade inferior",
            "Ícone", "Botão comprar", "Confirmação", "Vendido (opcional)"])
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(True)
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for item in self.cfg.items:
            self._add_item_row(item)
        inner.addWidget(self.item_table)
        row = QHBoxLayout()
        self.btn_add = make_button("+ Adicionar item")
        self.btn_remove = make_button("Remover selecionado")
        self.btn_save_items = make_button("Salvar itens", "Primary")
        self.btn_add.clicked.connect(self.add_item)
        self.btn_remove.clicked.connect(self.remove_item)
        self.btn_save_items.clicked.connect(self.save_settings)
        for button in (self.btn_add, self.btn_remove, self.btn_save_items):
            row.addWidget(button)
        row.addStretch()
        inner.addLayout(row)
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
            if col in (0, 4):
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                cell.setCheckState(Qt.CheckState.Checked if (item.enabled if col == 0 else item.lower_half) else Qt.CheckState.Unchecked)
            self.item_table.setItem(row, col, cell)
        self.item_table.setRowHeight(row, 39)

    def add_item(self):
        n = 1
        taken = {self.item_table.item(i, 1).text() for i in range(self.item_table.rowCount())}
        while f"item{n}" in taken:
            n += 1
        self._add_item_row(ItemConfig.standard(f"item{n}", f"Item {n}", 100000))

    def remove_item(self):
        row = self.item_table.currentRow()
        if row >= 0:
            self.item_table.removeRow(row)

    def _build_budget_tab(self):
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 14, 0, 0)
        frame, inner = panel("Orçamento da execução")
        grid = QGridLayout()
        b = self.cfg.budget
        self.budget_fields = {}
        fields = [
            ("gems_available", "Gemas disponíveis", b.gems_available),
            ("gold_available", "Ouro disponível", b.gold_available),
            ("gems_limit", "Quanto gastar de gemas (0 = todo o saldo)", b.gems_limit),
            ("gold_limit", "Quanto gastar de ouro (0 = todo o saldo)", b.gold_limit),
            ("refresh_cost", "Custo de cada renovação (gemas)", b.refresh_cost),
        ]
        for idx, (key, text, value) in enumerate(fields):
            group = QWidget()
            col = QVBoxLayout(group)
            col.setContentsMargins(5, 4, 5, 6)
            col.addWidget(QLabel(text))
            control = spin(value)
            self.budget_fields[key] = control
            col.addWidget(control)
            grid.addWidget(group, idx//2, idx%2)
        inner.addLayout(grid)
        hint = QLabel("Limite nunca superior ao saldo. Valores exibidos como gastos são estimativas — o bot não lê o saldo do jogo.")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        inner.addWidget(hint)
        self.btn_save_budget = make_button("Validar e salvar orçamento", "Primary")
        self.btn_save_budget.clicked.connect(self.save_settings)
        inner.addWidget(self.btn_save_budget, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(frame)
        outer.addStretch()
        self.tabs.addTab(content, "Orçamento")

    def _build_calibration_tab(self):
        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(0, 14, 0, 0)
        top = QHBoxLayout()
        f1, left = panel("Janela e detecção")
        f2, right = panel("Área de clique seguro")
        c = self.cfg.calibration
        form = QFormLayout()
        self.cal_fields = {}
        self.cal_fields["window_title"] = QLineEdit(c.window_title)
        self.cal_fields["hotkey"] = QLineEdit(c.hotkey)
        self.cal_fields["threshold"] = decimal(c.threshold, .60, .99)
        self.cal_fields["max_scrolls"] = spin(c.max_scrolls, 8)
        self.cal_fields["same_row_factor"] = decimal(c.same_row_factor, 1, 3, .1, 1)
        self.cal_fields["pause_min"] = decimal(c.pause_min, 0, 10, .05)
        self.cal_fields["pause_max"] = decimal(c.pause_max, 0, 10, .05)
        self.cal_fields["focus_timeout"] = decimal(c.focus_timeout, 1, 300, 1, 1)
        self.cal_fields["modal_timeout"] = decimal(c.modal_timeout, .5, 10, .5, 1)
        labels = {"window_title": "Título da janela", "hotkey": "Atalho de emergência",
                  "threshold": "Limiar de match", "max_scrolls": "Scrolls máximos",
                  "same_row_factor": "Faixa da mesma linha", "pause_min": "Pausa mínima (s)",
                  "pause_max": "Pausa máxima (s)", "focus_timeout": "Espera por foco (s)",
                  "modal_timeout": "Timeout de confirmação (s)"}
        for key, control in self.cal_fields.items():
            form.addRow(labels[key], control)
        left.addLayout(form)
        top.addWidget(f1, 1)
        self.preview = SafeAreaPreview(c.safe_area)
        right.addWidget(self.preview)
        coords = QGridLayout()
        self.area_fields = {}
        for idx, (key, val) in enumerate(zip(("x0", "y0", "x1", "y1"), c.safe_area)):
            control = decimal(val, 0, 1)
            control.valueChanged.connect(self._update_area_preview)
            self.area_fields[key] = control
            coords.addWidget(QLabel(key), idx // 2, (idx % 2) * 2)
            coords.addWidget(control, idx // 2, (idx % 2) * 2 + 1)
        right.addLayout(coords)
        hint = QLabel("A área verde é relativa à janela do jogo; mantenha-a longe de botões e pop-ups.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        right.addWidget(hint)
        self.btn_templates = make_button("Escolher pasta de templates")
        self.btn_templates.clicked.connect(self.pick_templates)
        right.addWidget(self.btn_templates)
        self.template_folder_label = QLabel(str(self.templates_dir))
        self.template_folder_label.setWordWrap(True)
        self.template_folder_label.setObjectName("Muted")
        right.addWidget(self.template_folder_label)
        top.addWidget(f2, 1)
        main.addLayout(top)
        diag, dl = panel("Diagnóstico visual — sem clicar no jogo")
        instruction = QLabel("Selecione uma captura PNG da loja e verifique as caixas de detecção. Este teste nunca move o mouse.")
        instruction.setWordWrap(True)
        instruction.setObjectName("Muted")
        dl.addWidget(instruction)
        browse = QHBoxLayout()
        self.capture_label = QLineEdit()
        self.capture_label.setReadOnly(True)
        self.btn_capture = make_button("Abrir PNG")
        self.btn_capture.clicked.connect(self.pick_capture)
        self.btn_diagnose = make_button("Testar reconhecimento")
        self.btn_diagnose.clicked.connect(self.run_diagnostic)
        browse.addWidget(self.capture_label, 1)
        browse.addWidget(self.btn_capture)
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
        self.btn_save_calibration.clicked.connect(self.save_settings)
        main.addWidget(self.btn_save_calibration, alignment=Qt.AlignmentFlag.AlignLeft)
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
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        inner.addWidget(self.history_table)
        layout.addWidget(history, 1)
        self._update_history()
        self.tabs.addTab(content, "Relatório")

    def _make_tray(self):
        pix = QPixmap(48, 48)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#177ddc"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 47, 47, 9, 9)
        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 17, QFont.Weight.Bold)
        painter.setFont(font)
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

    def show_panel(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _update_area_preview(self, _value=None):
        self.preview.set_area(tuple(self.area_fields[k].value() for k in ("x0", "y0", "x1", "y1")))

    def _refresh_template_labels(self):
        self.template_folder_label.setText(str(self.templates_dir))
        self.hotkey_label.setText(f"Emergência: {self.cfg.calibration.hotkey} · ou botão Parar na bandeja")

    def pick_templates(self):
        path = QFileDialog.getExistingDirectory(self, "Pasta com PNGs da loja", str(self.templates_dir))
        if path:
            self.templates_dir = Path(path)
            self._refresh_template_labels()

    def pick_capture(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Captura PNG da loja", str(Path.home()),
                                                   "Imagens PNG (*.png)")
        if filename:
            self.screenshot_path = filename
            self.capture_label.setText(filename)

    def run_diagnostic(self):
        if not self.screenshot_path:
            QMessageBox.information(self, "Captura ausente", "Escolha um arquivo PNG antes do teste.")
            return
        try:
            cfg = self._collect_config()
            validate_config(cfg)
            png_data, lines = analyze_image(Path(self.screenshot_path), cfg, self.templates_dir)
            pix = QPixmap()
            if not pix.loadFromData(png_data):
                raise ValueError("Não foi possível exibir o resultado do teste.")
            self.image_bytes = png_data
            self.diagnostic_image.setPixmap(pix.scaled(QSize(900, 290), Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation))
            self.diagnostic_label.setText("  |  ".join(lines) or "Nenhum item ativo.")
            self.append_log("Diagnóstico offline executado sem cliques.", "ok")
        except Exception as exc:
            QMessageBox.warning(self, "Falha no diagnóstico", str(exc))

    def _collect_config(self) -> AppConfig:
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
                lower_half=self.item_table.item(row, 4).checkState() == Qt.CheckState.Checked,
                icon_template=value(5), buy_template=value(6),
                price_template=value(7), sold_template=value(8)))
        budget = BudgetConfig(**{name: control.value() for name, control in self.budget_fields.items()})
        calibration = CalibrationConfig(
            **{key: control.text().strip() if isinstance(control, QLineEdit) else control.value()
               for key, control in self.cal_fields.items()},
            safe_area=tuple(self.area_fields[k].value() for k in ("x0", "y0", "x1", "y1")))
        saved_dir = str(self.templates_dir) if self.templates_dir != data_directory() / "templates" else ""
        return AppConfig(budget=budget, calibration=calibration, items=items,
                         templates_dir=saved_dir)

    def save_settings(self):
        try:
            cfg = self._collect_config()
            validate_config(cfg)
            save_config(cfg)
            self.cfg = cfg
            self.templates_dir = user_templates(cfg)
            self._refresh_template_labels()
            self.append_log("Configurações validadas e salvas no AppData.", "ok")
            return True
        except (ValueError, BotError, OSError) as exc:
            QMessageBox.warning(self, "Configuração inválida", str(exc))
            return False

    def _register_hotkey(self):
        self._unregister_hotkey()
        try:
            import keyboard
            self.hotkey_module = keyboard
            self.hotkey_handle = keyboard.add_hotkey(self.cfg.calibration.hotkey,
                                                       self.controller.stop)
            self.append_log("Atalho global disponível: " + self.cfg.calibration.hotkey)
        except Exception as exc:
            self.hotkey_handle = None
            self.append_log(f"Atalho global indisponível: {exc}. Use Parar na bandeja.", "warn")

    def _unregister_hotkey(self):
        if self.hotkey_module is not None and self.hotkey_handle is not None:
            try:
                self.hotkey_module.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass
        self.hotkey_handle = None
        self.hotkey_module = None

    def _set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.tray_stop_action.setEnabled(running)
        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, not running or i in (0, 4))

    def start_bot(self):
        if self.controller.running:
            return
        if not self.save_settings():
            return
        try:
            path = prepare_templates(self.cfg)
            self._register_hotkey()
            self._set_running(True)
            self.status.setText("●  PREPARANDO")
            self.status.setStyleSheet("color:#52a8ff;font-weight:600;")
            if self.tray.isVisible():
                self.hide()  # oculta o painel antes da ativação do jogo
            else:
                self.showMinimized()
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

    def update_metrics(self, state: dict):
        for key, widget in self.metric_labels.items():
            widget.setText(fmt(state.get(key, 0)))
        limit_gems = self.cfg.budget.gems_limit or self.cfg.budget.gems_available
        limit_gold = self.cfg.budget.gold_limit or self.cfg.budget.gold_available
        gems, gold = state.get("gems_estimated", 0), state.get("gold_estimated", 0)
        self.gem_label.setText(f"Gemas estimadas: {fmt(gems)} / {fmt(limit_gems)}")
        self.gold_label.setText(f"Ouro estimado: {fmt(gold)} / {fmt(limit_gold)}")
        self.gem_bar.setRange(0, max(1, limit_gems))
        self.gold_bar.setRange(0, max(1, limit_gold))
        self.gem_bar.setValue(min(gems, limit_gems))
        self.gold_bar.setValue(min(gold, limit_gold))
        status = state.get("status", "")
        title = {"executando": "EM EXECUÇÃO", "preparando": "PREPARANDO",
                 "pausado_por_foco": "PAUSADO — FOCO",
                 "resultado_incerto": "RESULTADO INCERTO", "erro": "ERRO",
                 "concluido": "FINALIZADO", "cancelado": "CANCELADO"}.get(status, status.upper())
        color = "#49aa19" if status == "executando" else (
            "#f5b44b" if status in ("preparando", "pausado_por_foco") else "#ff7875"
            if status in ("erro", "resultado_incerto") else "#a6a6a6")
        self.status.setText("●  " + title)
        self.status.setStyleSheet(f"color:{color};font-weight:600;")

    def execution_finished(self, result: dict):
        self._unregister_hotkey()
        self.last_result = result
        self._set_running(False)
        try:
            add_history(result)
        except OSError as exc:
            self.append_log(f"Falha ao salvar histórico: {exc}", "warn")
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
        self.show_panel()
        self.append_log("Execução encerrada: " + result.get("reason", result.get("status", "")), "info")
        if result["status"] == "resultado_incerto":
            QMessageBox.warning(self, "Resultado incerto",
                                "Uma ação foi enviada, mas não pôde ser verificada. "
                                "Confira os saldos/itens do jogo antes de iniciar outra execução.")

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
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.controller.running:
            if self.tray.isVisible():
                self.hide()
                self.tray.showMessage("Epic7 Shop Bot", "Bot ativo; use Parar na bandeja ou o atalho.",
                                      QSystemTrayIcon.MessageIcon.Information, 2500)
            else:
                self.showMinimized()  # sem bandeja, preserva acesso ao botão Parar
            event.ignore()
            return
        self._unregister_hotkey()
        self.tray.hide()
        event.accept()
        QApplication.instance().quit()

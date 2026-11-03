"""Painel compacto sem ativação de janela, com botão de retorno ao aplicativo.

A região azul não pode sobrepor a região verde de cliques seguros. O botão
solicita uma pausa cooperativa do motor antes de abrir a janela principal.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from app.core.overlay_geometry import overlay_rect


class StatusOverlay(QWidget):
    return_requested = Signal()

    def __init__(self):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("StatusOverlay")
        self.setStyleSheet("""
            QWidget#StatusOverlay {background-color: #0a1420;
                border:2px solid #328dff; border-radius:9px;}
            QLabel {background:transparent; color:#f4f7fc; font: 9pt 'Segoe UI';}
            QPushButton#ReturnToApp {background:#1d67a9; color:#ffffff;
                border:1px solid #5eb5ff; border-radius:5px;
                padding:3px 7px; font: 600 8pt 'Segoe UI';}
            QPushButton#ReturnToApp:hover {background:#287fcc;}
            QPushButton#ReturnToApp:disabled {background:#425367; color:#c5ccda;}
        """)
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(3)
        header = QHBoxLayout()
        header.setSpacing(5)
        self.title_label = QLabel("E7 SHOP BOT")
        self.title_label.setToolTip("Monitoramento do Epic7 Shop Bot")
        self.title_label.setMinimumWidth(0)
        header.addWidget(self.title_label, 1)
        self.return_button = QPushButton("Voltar ao app")
        self.return_button.setObjectName("ReturnToApp")
        self.return_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.return_button.setMinimumHeight(24)
        self.return_button.setToolTip("Pausa em um ponto seguro e abre a janela principal")
        self.return_button.clicked.connect(self.request_return)
        header.addWidget(self.return_button)
        box.addLayout(header)
        self.status_label = QLabel("Preparando…")
        self.cost_label = QLabel("Gemas: 0  |  Ouro: 0")
        self.counter_label = QLabel("Renovações: 0  |  Compras: 0")
        for label in (self.status_label, self.cost_label, self.counter_label):
            box.addWidget(label)

    def request_return(self):
        # Não ativamos a janela aqui: a MainWindow primeiro solicita uma pausa
        # cooperativa e aguarda o motor alcançar um ponto seguro.
        self.return_button.setEnabled(False)
        self.return_button.setText("Aguarde…")
        self.return_requested.emit()

    def reset_return_button(self):
        self.return_button.setText("Voltar ao app")
        self.return_button.setEnabled(True)

    def update_state(self, state: dict):
        fmt = lambda n: f"{int(n):,}".replace(",", ".")
        self.status_label.setText("Status: " + state.get("status", "preparando"))
        self.cost_label.setText(
            f"Gemas: {fmt(state.get('gems_estimated', 0))}  |  "
            f"Ouro: {fmt(state.get('gold_estimated', 0))}")
        self.counter_label.setText(
            f"Renovações: {fmt(state.get('refreshes', 0))}  |  "
            f"Compras: {fmt(state.get('purchases_verified', 0))}")

    def position_over_game(self, game_rect: tuple, area: tuple):
        # QRect Win32 usa pixels físicos; Qt Widgets utiliza coordenadas lógicas.
        # Resolução primária: suficiente para o cenário de um monitor.
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 1.0
        x, y, w, h = overlay_rect(game_rect, area)
        # Múltiplos monitores com DPI misto exigem conversão por monitor;
        # a UI avisa para desabilitar o modo em tal configuração.
        self.setGeometry(round(x / dpr), round(y / dpr),
                         max(1, round(w / dpr)), max(1, round(h / dpr)))

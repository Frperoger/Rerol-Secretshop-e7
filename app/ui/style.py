"""Qt Style Sheets; interface própria inspirada no protótipo, sem reutilizar HTML."""
QSS = """
QWidget {background:#141414; color:#e8e8e8; font: 10pt 'Segoe UI';}
QMainWindow {background:#141414;}
QLabel#Brand {font-size:19pt; font-weight:700; color:#f1f1f1;}
QLabel#Muted {color:#969696;}
QLabel#Metric {font-size:21pt; font-weight:700; color:#eaf4ff;}
QFrame#Panel {background:#1f1f1f; border:1px solid #333333; border-radius:8px;}
QFrame#Panel QLabel,QFrame#Panel QTableWidget {background:transparent;}
QTabWidget::pane {border:0; background:#141414;}
QTabBar::tab {background:#141414; color:#8e8e8e; padding:12px 19px; border-bottom:2px solid transparent;}
QTabBar::tab:selected {color:#52a8ff; border-bottom:2px solid #177ddc;}
QTabBar::tab:hover {color:#fff;}
QPushButton {background:#303030; border:1px solid #414141; border-radius:5px; padding:8px 16px;}
QPushButton:hover {border-color:#52a8ff;}
QPushButton:disabled {color:#696969; background:#262626;}
QPushButton#Primary {background:#177ddc; border-color:#177ddc; font-weight:600;}
QPushButton#Danger {background:#a61d24; border-color:#a61d24; font-weight:600;}
QLineEdit,QSpinBox,QDoubleSpinBox {border:1px solid #404040; background:#292929; padding:6px 8px; border-radius:4px; selection-background-color:#177ddc;}
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus {border-color:#52a8ff;}
QPlainTextEdit {background:#0d0d0d; border:1px solid #363636; border-radius:5px; font: 9pt Consolas;}
QTableWidget {background:#1b1b1b; alternate-background-color:#252525; gridline-color:#383838; border:1px solid #383838;}
QHeaderView::section {background:#2b2b2b; color:#c2c2c2; border:0; border-bottom:1px solid #3b3b3b; padding:8px;}
QProgressBar {background:#2b2b2b; border:0; border-radius:4px; height:9px; text-align:center; color:transparent;}
QProgressBar::chunk {background:#369bff; border-radius:4px;}
QScrollBar:vertical {width:10px; background:#1b1b1b;}
QScrollBar::handle:vertical {background:#424242; border-radius:5px;}
QCheckBox {spacing:7px;}
"""

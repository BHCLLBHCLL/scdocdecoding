"""Shared Fusion light theme (cabdecoding / hmdecoding chrome)."""
from __future__ import annotations

from PyQt5.QtGui import QColor, QFont, QPalette

APP_QSS = """
QMainWindow { background: #e8e8e8; }
QMenuBar {
    background: #f0f0f0; border-bottom: 1px solid #c0c0c0; padding: 1px;
}
QMenuBar::item { padding: 3px 10px; }
QMenuBar::item:selected { background: #cde4f7; }
QMenu { background: #f7f7f7; border: 1px solid #a0a0a0; }
QMenu::item { padding: 4px 24px 4px 12px; }
QMenu::item:selected { background: #cde4f7; color: #000; }
QSplitter::handle { background: #d0d0d0; }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:vertical { height: 4px; }
QSplitter::handle:hover { background: #90caf9; }
QStatusBar {
    background: #ececec; border-top: 1px solid #b8b8b8;
    min-height: 24px; color: #333; font-size: 12px;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { padding: 0 6px; }
QToolBar#QuickAccess {
    background: #ececec; border: none; border-bottom: 1px solid #c0c0c0;
    spacing: 2px; padding: 2px 6px; min-height: 30px;
}
QToolBar#QuickAccess QToolButton {
    padding: 2px 6px 1px 6px; margin: 1px;
    border: 1px solid transparent; border-radius: 3px;
}
QToolBar#QuickAccess QToolButton:hover {
    background: #d6ebf8; border: 1px solid #7eb6d9;
}
QToolBar#QuickAccess QToolButton:pressed { background: #b8d8ef; }
QToolBar#QuickAccess QToolButton:checked {
    background: #b8d8ef; border: 1px solid #5a9ac6;
}
QTabBar#DocTabs { background: #e8e8e8; }
QTabBar#DocTabs::tab {
    height: 24px; padding: 4px 14px; background: #ececec;
    border: 1px solid #c8c8c8; border-bottom: none; color: #333; font-size: 12px;
    margin-right: 1px;
}
QTabBar#DocTabs::tab:selected {
    background: #ffffff; color: #111; font-weight: bold;
}
QWidget#LeftPanel { background: #f5f5f5; border-right: 1px solid #9a9a9a; }
QLabel#PaneTitle {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #5b9bd5, stop:1 #2e75b6);
    color: white; font-weight: bold; font-size: 11px;
    padding: 4px 8px;
}
QGroupBox {
    font-size: 12px; color: #333; border: 1px solid #9a9a9a;
    border-radius: 0px; margin-top: 10px; padding: 10px 8px 8px 8px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 8px; padding: 0 5px;
    color: #333; font-size: 11px; font-weight: bold;
}
QTreeWidget, QListWidget, QTableWidget {
    background: #ffffff; border: none; font-size: 12px; color: #2A2A2A;
    outline: none; alternate-background-color: #f7f8fa;
}
QTreeWidget::item, QListWidget::item { height: 22px; padding: 2px 4px; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #e8f3fb; }
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
    background: #cde4f7; color: #111;
}
QHeaderView::section {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #f6f6f6, stop:1 #e0e0e0);
    color: #333; padding: 4px 8px;
    border: 1px solid #c0c0c0; font-size: 11px; font-weight: bold;
}
QTabWidget::pane { border: 1px solid #9a9a9a; background: #ffffff; }
QTabBar::tab {
    height: 24px; padding: 4px 12px; background: #d8d8d8;
    border: 1px solid #9a9a9a; color: #444; font-size: 11px;
    margin-right: 1px;
}
QTabBar::tab:selected { background: #ffffff; color: #111; font-weight: bold; }
QCheckBox, QRadioButton { font-size: 12px; spacing: 6px; color: #333; }
QScrollBar:vertical { width: 10px; background: #f5f5f5; }
QScrollBar::handle:vertical { background: #bdbdbd; min-height: 24px; border-radius: 4px; }
QScrollBar:horizontal { height: 10px; background: #f5f5f5; }
QScrollBar::handle:horizontal { background: #bdbdbd; min-width: 24px; border-radius: 4px; }
QToolButton { border: 1px solid transparent; border-radius: 3px; }
QToolButton:hover { background: #d6ebf8; border-color: #7eb6d9; }
QToolButton:checked { background: #b8d8ef; border-color: #5a9ac6; }
"""


def apply_palette(app):
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(232, 232, 232))
    pal.setColor(QPalette.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.AlternateBase, QColor(247, 248, 250))
    pal.setColor(QPalette.Text, QColor(42, 42, 42))
    pal.setColor(QPalette.WindowText, QColor(42, 42, 42))
    pal.setColor(QPalette.Button, QColor(245, 245, 245))
    pal.setColor(QPalette.ButtonText, QColor(42, 42, 42))
    pal.setColor(QPalette.Highlight, QColor(46, 117, 182))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipText, QColor(32, 32, 32))
    pal.setColor(QPalette.Mid, QColor(200, 200, 200))
    app.setPalette(pal)


def ui_font() -> QFont:
    for family in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Noto Sans CJK SC"):
        font = QFont(family)
        font.setStyleHint(QFont.SansSerif)
        if font.exactMatch() or family == "Segoe UI":
            font.setPointSize(9)
            font.setHintingPreference(QFont.PreferFullHinting)
            return font
    font = QFont()
    font.setPointSize(9)
    return font

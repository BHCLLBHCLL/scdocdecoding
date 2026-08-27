"""Shared Fusion light theme (SpaceClaim-like chrome, original assets)."""
from __future__ import annotations

from PyQt5.QtGui import QColor, QFont, QPalette

APP_QSS = """
QMainWindow { background: #F0F0F0; }
QSplitter::handle { background: #E2E2E2; }
QSplitter::handle:horizontal { width: 5px; }
QSplitter::handle:vertical { height: 5px; }
QSplitter::handle:hover { background: #C5C5C5; }
QStatusBar {
    background: #F4F4F4; border-top: 1px solid #D6D6D6;
    min-height: 26px; color: #333; font-size: 12px;
}
QStatusBar::item { border: none; }
QToolBar#QuickAccess {
    background: #ECECEC; border: none; border-bottom: 1px solid #D6D6D6;
    spacing: 4px; padding: 3px 8px; min-height: 28px;
}
QTabBar#DocTabs { background: #EFEFEF; }
QTabBar#DocTabs::tab {
    height: 24px; padding: 4px 14px; background: #E8E8E8;
    border: 1px solid #D4D4D4; border-bottom: none; color: #333; font-size: 12px;
}
QTabBar#DocTabs::tab:selected { background: #FFFFFF; color: #111; }
QWidget#LeftPanel { background: #FAFAFA; border-right: 1px solid #D6D6D6; }
QGroupBox {
    font-size: 12px; color: #555; border: 1px solid #E0E0E0;
    border-radius: 2px; margin-top: 10px; padding: 8px 6px 6px 6px;
    background: #FFFFFF;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 8px; padding: 0 4px;
    color: #666; font-size: 11px;
}
QTreeWidget, QListWidget, QTableWidget {
    background: #FFFFFF; border: none; font-size: 12px; color: #2A2A2A;
    outline: none; alternate-background-color: #F7F8FA;
}
QTreeWidget::item, QListWidget::item { height: 22px; padding: 1px 4px; }
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
    background: #CDE4F7; color: #111;
}
QHeaderView::section {
    background: #F5F5F5; color: #555; padding: 5px 8px; border: none;
    border-bottom: 1px solid #E2E2E2; font-size: 11px;
}
QTabWidget::pane { border: 1px solid #E0E0E0; background: #FFFFFF; }
QTabBar::tab {
    height: 22px; padding: 3px 10px; background: #F0F0F0;
    border: 1px solid #E0E0E0; color: #444; font-size: 11px;
}
QTabBar::tab:selected { background: #FFFFFF; color: #111; }
QCheckBox, QRadioButton { font-size: 12px; spacing: 6px; color: #333; }
QScrollBar:vertical { width: 10px; background: #F5F5F5; }
QScrollBar::handle:vertical { background: #C8C8C8; min-height: 24px; border-radius: 4px; }
QScrollBar:horizontal { height: 10px; background: #F5F5F5; }
QScrollBar::handle:horizontal { background: #C8C8C8; min-width: 24px; border-radius: 4px; }
"""


def apply_palette(app):
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(240, 240, 240))
    pal.setColor(QPalette.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.AlternateBase, QColor(247, 248, 250))
    pal.setColor(QPalette.Text, QColor(42, 42, 42))
    pal.setColor(QPalette.WindowText, QColor(42, 42, 42))
    pal.setColor(QPalette.Button, QColor(240, 240, 240))
    pal.setColor(QPalette.ButtonText, QColor(42, 42, 42))
    pal.setColor(QPalette.Highlight, QColor(0, 120, 215))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipText, QColor(32, 32, 32))
    pal.setColor(QPalette.Mid, QColor(214, 214, 214))
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

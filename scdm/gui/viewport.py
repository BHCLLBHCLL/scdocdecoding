"""Viewport host: VTK fill + HUD overlay + mini toolbar + document tabs."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QLabel, QToolButton, QWidget, QHBoxLayout,
)

from scdm.gui.icons import make_icon

HUD_QSS = """
QLabel#ViewPrompt {
    color: #3A3A3A;
    background: #FAFAFA;
    padding: 3px 14px;
    font-size: 12px;
    border: none;
    border-bottom: 1px solid #E2E2E2;
}
"""

MINI_QSS = """
QWidget#MiniBar {
    background: rgba(252, 252, 252, 235);
    border: 1px solid #C8C8C8;
    border-radius: 3px;
}
QToolButton { padding: 3px; border: 1px solid transparent; border-radius: 2px; }
QToolButton:hover { background: #E5F1FB; border-color: #C0D4EA; }
"""


class MiniBar(QWidget):
    command = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MiniBar")
        self.setStyleSheet(MINI_QSS)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(3)
        for cid, key, name in (
            ("tool.pull", "pull", "拉动"),
            ("tool.move", "move", "移动"),
            ("tool.fill", "fill", "填充"),
            ("tool.combine", "combine", "合并"),
        ):
            b = QToolButton()
            b.setIcon(make_icon(key, 24))
            b.setIconSize(QSize(24, 24))
            b.setFixedSize(32, 32)
            b.setToolTip(name)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, i=cid: self.command.emit(i))
            lay.addWidget(b)
        self.adjustSize()


class ViewportHost(QWidget):
    def __init__(self, vtk_widget, parent=None):
        super().__init__(parent)
        self.vtk_widget = vtk_widget
        vtk_widget.setParent(self)
        self.hud = QLabel(self)
        self.hud.setObjectName("ViewPrompt")
        self.hud.setStyleSheet(HUD_QSS)
        self.hud.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hud.setText("单击选择对象；双击选环边；三击选实体")
        self.mini = MiniBar(self)
        self.mini.hide()

    def set_hud(self, text: str):
        self.hud.setText(text)

    def show_mini(self, on: bool):
        self.mini.setVisible(on)
        if on:
            self._place_mini()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        bar_h = 26
        self.hud.setGeometry(0, 0, self.width(), bar_h)
        self.vtk_widget.setGeometry(0, bar_h, self.width(), max(1, self.height() - bar_h))
        self._place_mini()

    def _place_mini(self):
        self.mini.move(max(14, self.width() - self.mini.width() - 18), 34)

    def sizeHint(self):
        return QSize(800, 600)

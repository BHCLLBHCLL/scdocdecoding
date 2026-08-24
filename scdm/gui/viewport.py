"""Viewport host: VTK fill + HUD overlay + mini toolbar + document tabs."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QLabel, QTabBar, QToolButton, QVBoxLayout, QWidget, QHBoxLayout,
)

from scdm.gui.icons import make_icon

HUD_QSS = "color: #333333; background: rgba(255,255,255,180); padding: 4px 8px; font-size: 12px;"


class MiniBar(QWidget):
    command = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QWidget { background: #F7F7F7; border: 1px solid #B0B0B0; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        for cid, key, name in (
            ("tool.pull", "pull", "拉动"),
            ("tool.move", "move", "移动"),
            ("tool.fill", "fill", "填充"),
            ("tool.combine", "combine", "合并"),
        ):
            b = QToolButton()
            b.setIcon(make_icon(key, 16))
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
        self.hud.setStyleSheet(HUD_QSS)
        self.hud.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hud.setText("单击选择对象；双击选环边；三击选实体")
        self.hud.adjustSize()
        self.mini = MiniBar(self)
        self.mini.hide()

    def set_hud(self, text: str):
        self.hud.setText(text)
        self.hud.adjustSize()

    def show_mini(self, on: bool):
        self.mini.setVisible(on)
        if on:
            self._place_mini()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.vtk_widget.setGeometry(0, 0, self.width(), self.height())
        self.hud.move(12, 10)
        self._place_mini()

    def _place_mini(self):
        self.mini.move(max(12, self.width() - self.mini.width() - 16), 48)

    def sizeHint(self):
        return QSize(800, 600)

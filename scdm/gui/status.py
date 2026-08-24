"""Status bar: prompt + selection filters + unit."""
from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel, QSizePolicy, QToolButton, QWidget, QHBoxLayout

FILTERS = (
    ("vertex", "点"),
    ("edge", "边"),
    ("face", "面"),
    ("body", "体"),
    ("component", "组件"),
)


class FilterBar(QWidget):
    filter_changed = pyqtSignal(str, bool)
    view_cmd = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.buttons = {}
        for key, label in FILTERS:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.setChecked(True)
            b.setAutoRaise(True)
            b.toggled.connect(lambda on, k=key: self.filter_changed.emit(k, on))
            lay.addWidget(b)
            self.buttons[key] = b
        lay.addSpacing(8)
        self.unit = QLabel("mm")
        self.unit.setStyleSheet("padding: 0 8px; color: #333;")
        lay.addWidget(self.unit)
        for cid, text in (("view.spin", "旋转"), ("view.pan", "平移"), ("view.fit", "适合")):
            b = QToolButton()
            b.setText(text)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, i=cid: self.view_cmd.emit(i))
            lay.addWidget(b)


class StatusPrompt(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("单击选择对象；双击选环边；三击选实体")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

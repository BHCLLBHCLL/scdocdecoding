"""File backstage (Office-style) covering the workspace."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from scdm.catalog import BACKSTAGE
from scdm.gui.icons import make_icon


class Backstage(QWidget):
    command = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QWidget#Backstage { background: #F3F3F3; }")
        self.setObjectName("Backstage")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = QFrame()
        nav.setFixedWidth(220)
        nav.setStyleSheet("QFrame { background: #2B579A; } QPushButton { color: white; text-align: left; "
                          "padding: 10px 16px; border: none; font-size: 13px; }"
                          "QPushButton:hover { background: #3A6DB2; }")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(0, 12, 0, 12)
        for cmd in BACKSTAGE:
            b = QPushButton(make_icon(cmd.icon, 16), f"  {cmd.name}")
            b.clicked.connect(lambda _=False, i=cmd.id: self.command.emit(i))
            nl.addWidget(b)
        nl.addStretch(1)
        root.addWidget(nav)

        self.recent = QListWidget()
        self.recent.itemDoubleClicked.connect(self._open_recent)
        right = QVBoxLayout()
        lab = QLabel("最近文件")
        lab.setStyleSheet("font-size: 18px; padding: 16px 8px 8px 8px;")
        right.addWidget(lab)
        right.addWidget(self.recent, 1)
        hint = QLabel("双击打开。保存 / 另存为 / 导出几何在 M2 接入内核后生效。")
        hint.setStyleSheet("color: #666; padding: 8px;")
        hint.setWordWrap(True)
        right.addWidget(hint)
        wrap = QWidget()
        wrap.setLayout(right)
        root.addWidget(wrap, 1)

    def _open_recent(self, item):
        path = item.data(Qt.UserRole)
        if path:
            self.command.emit("file.open:" + path)

    def set_recent(self, paths):
        self.recent.clear()
        for p in paths:
            self.recent.addItem(p)
            self.recent.item(self.recent.count() - 1).setData(Qt.UserRole, p)

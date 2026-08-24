"""Office-style ribbon: tab bar + grouped command body."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QTabBar, QToolButton, QVBoxLayout, QWidget,
)

from scdm.catalog import TABS, Command, Group
from scdm.gui.icons import make_icon

RIBBON_QSS = """
QWidget#RibbonBar { background: #F0F0F0; }
QTabBar#RibbonTabs { background: #E6E6E6; }
QTabBar#RibbonTabs::tab {
    height: 28px; padding: 4px 14px; background: #E6E6E6;
    border: none; color: #222; font-size: 12px;
}
QTabBar#RibbonTabs::tab:selected {
    background: #FFFFFF; border-bottom: 2px solid #0078D7; color: #000;
}
QWidget#RibbonBody { background: #FFFFFF; border-bottom: 1px solid #D0D0D0; }
QLabel#GroupTitle { color: #666; font-size: 11px; }
QFrame#GroupSep { color: #D0D0D0; }
QToolButton {
    border: 1px solid transparent; border-radius: 3px; padding: 2px;
    background: transparent; font-size: 11px;
}
QToolButton:hover { background: #E5F1FB; border-color: #C0D4EA; }
QToolButton:checked { background: #CDE4F7; border-color: #0078D7; }
QToolButton:pressed { background: #B7D7F0; }
"""


class RibbonButton(QToolButton):
    triggered_id = pyqtSignal(str)

    def __init__(self, cmd: Command, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.setObjectName(cmd.id)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if cmd.large else Qt.ToolButtonTextBesideIcon)
        sz = 32 if cmd.large else 16
        self.setIcon(make_icon(cmd.icon, sz))
        self.setIconSize(QSize(sz, sz))
        self.setText(cmd.name)
        self.setCheckable(cmd.checkable)
        self.setAutoRaise(True)
        tip = f"{cmd.name} ({cmd.en})"
        if cmd.note:
            tip += f"\n{cmd.note}"
        tip += f"\n{cmd.wave}"
        self.setToolTip(tip)
        if cmd.large:
            self.setMinimumSize(56, 64)
        else:
            self.setMinimumHeight(22)
        self.clicked.connect(lambda: self.triggered_id.emit(cmd.id))


class RibbonGroup(QWidget):
    def __init__(self, group: Group, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 2)
        root.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(2)
        self.buttons = []
        large = [c for c in group.commands if c.large]
        small = [c for c in group.commands if not c.large]
        for c in large:
            b = RibbonButton(c)
            row.addWidget(b)
            self.buttons.append(b)
        if small:
            grid = QVBoxLayout()
            grid.setSpacing(1)
            # pack small buttons two-up
            i = 0
            while i < len(small):
                line = QHBoxLayout()
                line.setSpacing(2)
                for _ in range(2):
                    if i >= len(small):
                        break
                    b = RibbonButton(small[i])
                    line.addWidget(b)
                    self.buttons.append(b)
                    i += 1
                line.addStretch(1)
                grid.addLayout(line)
            row.addLayout(grid)
        row.addStretch(0)
        root.addLayout(row, 1)
        title = QLabel(group.name)
        title.setObjectName("GroupTitle")
        title.setAlignment(Qt.AlignHCenter)
        root.addWidget(title)


class RibbonBar(QWidget):
    command = pyqtSignal(str)
    tab_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RibbonBar")
        self.setStyleSheet(RIBBON_QSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QTabBar()
        self.tabs.setObjectName("RibbonTabs")
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self._tab_ids = []
        for tab in TABS:
            self.tabs.addTab(tab.name)
            self._tab_ids.append(tab.id)
        lay.addWidget(self.tabs)

        self.body = QWidget()
        self.body.setObjectName("RibbonBody")
        self.body.setFixedHeight(92)
        body_l = QHBoxLayout(self.body)
        body_l.setContentsMargins(4, 0, 4, 0)
        body_l.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll = scroll
        scroll.setWidget(self.body)
        lay.addWidget(scroll)

        self._pages = {}
        self._buttons = {}
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._style_group = QButtonGroup(self)
        self._style_group.setExclusive(True)

        from scdm.catalog import TABS as _T
        for tab in _T:
            host = QWidget()
            hl = QHBoxLayout(host)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(0)
            for gi, g in enumerate(tab.groups):
                rg = RibbonGroup(g)
                for b in rg.buttons:
                    b.triggered_id.connect(self.command.emit)
                    self._buttons[b.cmd.id] = b
                    if b.cmd.id.startswith("mode."):
                        self._mode_group.addButton(b)
                    if b.cmd.checkable and (
                        b.cmd.id.startswith("tool.") or b.cmd.id == "measure.dist"
                    ):
                        self._tool_group.addButton(b)
                    if b.cmd.id.startswith("style."):
                        self._style_group.addButton(b)
                hl.addWidget(rg)
                if gi < len(tab.groups) - 1:
                    sep = QFrame()
                    sep.setObjectName("GroupSep")
                    sep.setFrameShape(QFrame.VLine)
                    sep.setStyleSheet("color:#D0D0D0;")
                    hl.addWidget(sep)
            hl.addStretch(1)
            self._pages[tab.id] = host

        self._current_host = None
        self.tabs.currentChanged.connect(self._on_tab)
        # default Design
        design_idx = self._tab_ids.index("design")
        self.tabs.setCurrentIndex(design_idx)
        self._show_tab("design")

    def _on_tab(self, index: int):
        tid = self._tab_ids[index]
        self.tab_changed.emit(tid)
        if tid == "file":
            return
        self._show_tab(tid)

    def _show_tab(self, tid: str):
        lay = self.body.layout()
        if self._current_host is not None:
            lay.removeWidget(self._current_host)
            self._current_host.hide()
        host = self._pages.get(tid)
        if host is None:
            return
        lay.insertWidget(0, host)
        host.show()
        self._current_host = host

    def select_tab(self, tid: str):
        if tid in self._tab_ids:
            self.tabs.setCurrentIndex(self._tab_ids.index(tid))

    def set_body_visible(self, on: bool):
        self._scroll.setVisible(on)

    def restore_design(self):
        self.select_tab("design")

    def set_checked(self, cmd_id: str, on: bool):
        b = self._buttons.get(cmd_id)
        if b and b.isCheckable():
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)

    def button(self, cmd_id: str):
        return self._buttons.get(cmd_id)

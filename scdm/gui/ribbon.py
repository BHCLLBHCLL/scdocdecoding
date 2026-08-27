"""Office-style ribbon: tab bar + grouped command body."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QTabBar, QToolButton, QVBoxLayout, QWidget,
)

from scdm.catalog import TABS, Command, Group
from scdm.gui.icons import make_icon

LARGE_ICON = 32
SMALL_ICON = 24
RIBBON_BODY_H = 118

RIBBON_QSS = """
QWidget#RibbonBar { background: #F0F0F0; }
QTabBar#RibbonTabs { background: #E8E8E8; }
QTabBar#RibbonTabs::tab {
    height: 28px; padding: 5px 16px; background: #E8E8E8;
    border: none; color: #333; font-size: 12px;
}
QTabBar#RibbonTabs::tab:selected {
    background: #FFFFFF; border-bottom: 2px solid #0078D7; color: #111;
}
QWidget#RibbonBody { background: #FFFFFF; border-bottom: 1px solid #D4D4D4; }
QLabel#GroupTitle { color: #6A6A6A; font-size: 11px; padding: 2px 6px 3px 6px; }
QFrame#GroupSep { background: #E4E4E4; max-width: 1px; margin: 10px 5px 16px 5px; }
QToolButton {
    border: 1px solid transparent; border-radius: 3px;
    background: transparent; font-size: 11px; color: #333;
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
        self.setAutoRaise(True)
        self.setCheckable(cmd.checkable)
        self.setCursor(Qt.PointingHandCursor)
        tip = f"{cmd.name} ({cmd.en})"
        if cmd.note:
            tip += f"\n{cmd.note}"
        tip += f"\n{cmd.wave}"
        self.setToolTip(tip)
        if cmd.large:
            self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            self.setIcon(make_icon(cmd.icon, LARGE_ICON))
            self.setIconSize(QSize(LARGE_ICON, LARGE_ICON))
            self.setText(cmd.name)
            width = 58 if len(cmd.name) <= 3 else 74
            self.setFixedSize(width, 80)
        else:
            self.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.setIcon(make_icon(cmd.icon, SMALL_ICON))
            self.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            self.setText(cmd.name)
            self.setFixedSize(36, 36)
        self.clicked.connect(lambda: self.triggered_id.emit(cmd.id))


class RibbonGroup(QWidget):
    def __init__(self, group: Group, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 4)
        root.setSpacing(1)
        row = QHBoxLayout()
        row.setSpacing(4)
        row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.buttons = []
        large = [c for c in group.commands if c.large]
        small = [c for c in group.commands if not c.large]
        for c in large:
            b = RibbonButton(c)
            row.addWidget(b, 0, Qt.AlignTop)
            self.buttons.append(b)
        if small:
            nrows = 3 if (not large and len(small) <= 3) else 2
            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setContentsMargins(0, 4, 0, 0)
            grid.setHorizontalSpacing(3)
            grid.setVerticalSpacing(3)
            for i, c in enumerate(small):
                b = RibbonButton(c)
                grid.addWidget(b, i % nrows, i // nrows)
                self.buttons.append(b)
            row.addWidget(grid_host, 0, Qt.AlignVCenter)
        root.addLayout(row, 1)
        title = QLabel(group.name)
        title.setObjectName("GroupTitle")
        title.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
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
        self.body.setFixedHeight(RIBBON_BODY_H)
        body_l = QHBoxLayout(self.body)
        body_l.setContentsMargins(6, 0, 6, 0)
        body_l.setSpacing(0)
        body_l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

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
            hl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
                    sep.setFixedWidth(1)
                    hl.addWidget(sep)
            hl.addStretch(1)
            self._pages[tab.id] = host

        self._current_host = None
        self.tabs.currentChanged.connect(self._on_tab)
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

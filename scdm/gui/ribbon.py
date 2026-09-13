"""Office-style ribbon: tab bar + grouped command body."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QTabBar, QToolButton, QVBoxLayout, QWidget,
)

from scdm.catalog import TABS, Command, Group
from scdm.gui.icons import make_icon

# Match cabdecoding toolbar density (22) and Office large-command scale (~32).
LARGE_ICON = 32
SMALL_ICON = 22
RIBBON_BODY_H = 110

RIBBON_QSS = """
QWidget#RibbonBar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #f2f2f2, stop:1 #e6e6e6);
}
QTabBar#RibbonTabs {
    background: transparent;
}
QTabBar#RibbonTabs::tab {
    height: 28px; padding: 5px 16px;
    background: transparent;
    border: none; color: #333; font-size: 12px;
    margin-right: 1px;
}
QTabBar#RibbonTabs::tab:selected {
    background: #ffffff; color: #111; font-weight: bold;
    border-bottom: 2px solid #2e75b6;
}
QTabBar#RibbonTabs::tab:hover:!selected { background: #f3f6f9; }
QWidget#RibbonBody {
    background: #ffffff;
    border-bottom: 1px solid #c0c0c0;
}
QLabel#GroupTitle {
    color: #6a6a6a; font-size: 11px;
    padding: 1px 6px 3px 6px;
}
QFrame#GroupSep {
    background: #d0d0d0; max-width: 1px;
    margin: 10px 8px 16px 8px;
}
QToolButton {
    border: 1px solid transparent; border-radius: 3px;
    background: transparent; font-size: 11px; color: #333;
    padding: 2px 6px 1px 6px;
}
QToolButton:hover { background: #e3f2fd; border-color: #90caf9; }
QToolButton:checked {
    background: #bbdefb; border-color: #5a9ac6;
}
QToolButton:pressed { background: #90caf9; }
QToolButton:disabled { color: #9a9a9a; }
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
            n = len(cmd.name)
            width = 58 if n <= 2 else (66 if n <= 3 else 80)
            self.setFixedSize(width, 86)
        else:
            # Office/SpaceClaim small cmds: icon + label, readable at a glance.
            self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.setIcon(make_icon(cmd.icon, SMALL_ICON))
            self.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            self.setText(cmd.name)
            n = len(cmd.name)
            width = 72 if n <= 2 else (84 if n <= 3 else 98)
            self.setFixedSize(width, 28)
        self.clicked.connect(lambda: self.triggered_id.emit(cmd.id))


class RibbonGroup(QWidget):
    def __init__(self, group: Group, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 2)
        root.setSpacing(0)
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
            nrows = 3
            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setContentsMargins(2, 2, 2, 0)
            grid.setHorizontalSpacing(3)
            grid.setVerticalSpacing(2)
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

    def _on_tab(self, idx: int):
        if 0 <= idx < len(self._tab_ids):
            tid = self._tab_ids[idx]
            self._show_tab(tid)
            self.tab_changed.emit(tid)

    def _show_tab(self, tab_id: str):
        host = self._pages.get(tab_id)
        if host is None:
            return
        lay = self.body.layout()
        if self._current_host is not None:
            lay.removeWidget(self._current_host)
            self._current_host.hide()
            self._current_host.setParent(None)
        self._current_host = host
        lay.insertWidget(0, host)
        host.show()

    def select_tab(self, tid: str):
        if tid in self._tab_ids:
            self.tabs.setCurrentIndex(self._tab_ids.index(tid))

    def set_body_visible(self, on: bool):
        self._scroll.setVisible(on)

    def restore_design(self):
        self.select_tab("design")

    def set_checked(self, cmd_id: str, on: bool = True):
        b = self._buttons.get(cmd_id)
        if b and b.isCheckable():
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)

    def button(self, cmd_id: str):
        return self._buttons.get(cmd_id)

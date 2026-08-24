"""Left navigation: structure / layers / selection / groups / views + options + properties."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QGroupBox, QHeaderView, QLabel,
    QListWidget, QRadioButton, QScrollArea, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QFrame,
)

from scdm.document import Session


def _section(title: str, widget: QWidget) -> QWidget:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(6, 8, 6, 6)
    lay.addWidget(widget)
    return box


class LeftPanel(QWidget):
    tree_clicked = pyqtSignal(object)  # QTreeWidgetItem
    tree_checked = pyqtSignal(object, int)
    layer_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)
        split = QSplitter(Qt.Vertical, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(split)

        self.nav = QTabWidget()
        self.nav.setTabPosition(QTabWidget.South)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemClicked.connect(self.tree_clicked.emit)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.nav.addTab(self.tree, "结构")

        self.layer_list = QTreeWidget()
        self.layer_list.setHeaderLabels(["图层", "色"])
        self.layer_list.header().setStretchLastSection(False)
        self.layer_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.nav.addTab(self.layer_list, "图层")

        self.sel_list = QListWidget()
        self.nav.addTab(self.sel_list, "选择")

        self.group_list = QListWidget()
        self.group_list.addItem("（尚无群组）")
        self.nav.addTab(self.group_list, "群组")

        self.view_list = QListWidget()
        self.view_list.addItem("主视图")
        self.view_list.addItem("等轴测")
        self.nav.addTab(self.view_list, "视图")
        split.addWidget(self.nav)

        self.opt_stack = QStackedWidget()
        self._opt_pages = {}
        self._build_option_pages()
        opt_scroll = QScrollArea()
        opt_scroll.setWidgetResizable(True)
        opt_scroll.setFrameShape(QFrame.NoFrame)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self.opt_stack)
        opt_scroll.setWidget(wrap)
        split.addWidget(_section("选项", opt_scroll))

        self.props = QTableWidget(0, 2)
        self.props.setHorizontalHeaderLabels(["属性", "值"])
        self.props.verticalHeader().setVisible(False)
        self.props.horizontalHeader().setStretchLastSection(True)
        self.props.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.props.setSelectionMode(QAbstractItemView.SingleSelection)
        split.addWidget(_section("属性", self.props))
        split.setSizes([280, 140, 180])

        self._block_tree = False

    def _on_item_changed(self, item, col):
        if self._block_tree:
            return
        self.tree_checked.emit(item, col)

    def _build_option_pages(self):
        def checks(cmd, pairs):
            w = QWidget()
            f = QVBoxLayout(w)
            f.setContentsMargins(2, 2, 2, 2)
            boxes = []
            for label, default in pairs:
                cb = QCheckBox(label)
                cb.setChecked(default)
                f.addWidget(cb)
                boxes.append(cb)
            f.addStretch(1)
            self._opt_pages[cmd] = (w, boxes)
            self.opt_stack.addWidget(w)

        def radios(cmd, labels):
            w = QWidget()
            f = QVBoxLayout(w)
            f.setContentsMargins(2, 2, 2, 2)
            buttons = []
            for i, label in enumerate(labels):
                rb = QRadioButton(label)
                rb.setChecked(i == 0)
                f.addWidget(rb)
                buttons.append(rb)
            f.addStretch(1)
            self._opt_pages[cmd] = (w, buttons)
            self.opt_stack.addWidget(w)

        none = QLabel("无选项")
        none.setAlignment(Qt.AlignCenter)
        self._opt_pages["none"] = (none, [])
        self.opt_stack.addWidget(none)

        checks("tool.select", [("捕捉到栅格", False), ("端点", True), ("中点", True), ("重合", False)])
        checks("tool.pull", [("对称", False), ("两侧", False), ("复制", False), ("到面", False)])
        checks("tool.move", [("复制", False), ("沿轴", True), ("到点", False), ("到面", False)])
        checks("tool.fill", [("保留边", False), ("相切连续", True)])
        checks("tool.replace", [("延伸目标面", True)])
        radios("tool.combine", ["合并", "减去", "相交"])
        checks("tool.split_body", [("保留两侧", True), ("仅切割面", False)])
        checks("mode.sketch", [("草图网格", True), ("捕捉栅格", True)])
        checks("mode.section", [("剖面显示", True), ("截面可拉", True)])
        checks("measure.dist", [("自动标注", True)])
        checks("insert.cyl", [("创建后进入拉动", True)])
        checks("insert.sphere", [("创建后进入拉动", True)])

    def combine_mode(self) -> str:
        page = self._opt_pages.get("tool.combine")
        if not page:
            return "fuse"
        _w, buttons = page
        labels = ["fuse", "cut", "common"]
        for i, b in enumerate(buttons):
            if b.isChecked():
                return labels[i]
        return "fuse"

    def is_checked(self, cmd: str, index: int) -> bool:
        page = self._opt_pages.get(cmd)
        if not page:
            return False
        _w, boxes = page
        if 0 <= index < len(boxes):
            return bool(boxes[index].isChecked())
        return False

    def show_options(self, cmd: str) -> None:
        """Show the option page for the active tool/command (defaults to 'none')."""
        page = self._opt_pages.get(cmd) or self._opt_pages.get("none")
        self.opt_stack.setCurrentWidget(page[0])

    def set_props(self, rows):
        self.props.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.props.setItem(i, 0, QTableWidgetItem(str(k)))
            self.props.setItem(i, 1, QTableWidgetItem(str(v)))

    def set_selection_list(self, labels):
        self.sel_list.clear()
        for lab in labels:
            self.sel_list.addItem(lab)
        if not labels:
            self.sel_list.addItem("（无选择）")

    def populate_tree(self, session: Session):
        self._block_tree = True
        self.tree.clear()
        root_name = session.root_caption() if session.data else session.name
        root = QTreeWidgetItem([root_name])
        root.setData(0, Qt.UserRole, ("root", session.name))
        root.setCheckState(0, Qt.Checked)
        self.tree.addTopLevelItem(root)

        origin = QTreeWidgetItem(["原点"])
        origin.setData(0, Qt.UserRole, ("origin", "origin"))
        origin.setCheckState(0, Qt.Checked if session.show_axes else Qt.Unchecked)
        root.addChild(origin)
        for pid, label in (("xy", "平面 XY"), ("zx", "平面 ZX"), ("yz", "平面 YZ")):
            it = QTreeWidgetItem([label])
            it.setData(0, Qt.UserRole, ("plane", pid))
            it.setCheckState(0, Qt.Checked if session.show_planes else Qt.Unchecked)
            root.addChild(it)

        doc = session.design_doc
        if session.kdoc is not None and session.kdoc.bodies:
            for body in session.kdoc.bodies:
                it = QTreeWidgetItem([body.name])
                it.setData(0, Qt.UserRole, ("body", body.id))
                it.setCheckState(0, Qt.Checked if body.visible else Qt.Unchecked)
                root.addChild(it)
            for sk in session.kdoc.sketches:
                it = QTreeWidgetItem([sk.name])
                it.setData(0, Qt.UserRole, ("sketch", sk.id))
                it.setCheckState(0, Qt.Checked)
                root.addChild(it)
        elif doc is not None:
            for i, body in enumerate(doc.bodies):
                caption = session.body_caption(body)
                it = QTreeWidgetItem([caption])
                it.setData(0, Qt.UserRole, ("body", body.id))
                it.setCheckState(0, Qt.Checked)
                it.setToolTip(0, body.id)
                root.addChild(it)
            if doc.sketch_curves:
                sk = QTreeWidgetItem([f"草图 ({len(doc.sketch_curves)})"])
                sk.setData(0, Qt.UserRole, ("sketch", "all"))
                sk.setCheckState(0, Qt.Checked)
                root.addChild(sk)
        root.setExpanded(True)
        self._block_tree = False

        self.layer_list.clear()
        layers = session.layers()
        if not layers:
            it = QTreeWidgetItem(["默认", ""])
            it.setCheckState(0, Qt.Checked)
            self.layer_list.addTopLevelItem(it)
        else:
            for ly in layers:
                it = QTreeWidgetItem([ly.name or ly.id, ly.color or ""])
                it.setData(0, Qt.UserRole, ly.id)
                it.setCheckState(0, Qt.Checked if ly.visible else Qt.Unchecked)
                self.layer_list.addTopLevelItem(it)

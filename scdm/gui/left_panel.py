"""Left navigation: structure / layers / selection / groups / views + options + properties."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDoubleSpinBox, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QListWidget, QListWidgetItem, QMenu, QInputDialog,
    QRadioButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QFrame,
)

from scdm.document import Session


def _section(title: str, widget: QWidget) -> QWidget:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(8, 12, 8, 8)
    lay.setSpacing(4)
    lay.addWidget(widget)
    return box


class LeftPanel(QWidget):
    tree_clicked = pyqtSignal(object)  # QTreeWidgetItem
    tree_checked = pyqtSignal(object, int)
    layer_toggled = pyqtSignal(str, bool)
    layer_assign = pyqtSignal(str)   # create layer from current selection
    layer_remove = pyqtSignal(str)
    group_save = pyqtSignal()
    group_clicked = pyqtSignal(str)
    view_save = pyqtSignal()
    view_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftPanel")
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)
        split = QSplitter(Qt.Vertical, self)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(5)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(split)

        self.nav = QTabWidget()
        self.nav.setTabPosition(QTabWidget.South)
        self.nav.setDocumentMode(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.itemClicked.connect(self.tree_clicked.emit)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.nav.addTab(self.tree, "结构")

        self.layer_list = QTreeWidget()
        self.layer_list.setHeaderLabels(["图层", "色"])
        self.layer_list.header().setStretchLastSection(False)
        self.layer_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.layer_list.itemChanged.connect(self._on_layer_item)
        self.layer_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.layer_list.customContextMenuRequested.connect(self._layer_menu)
        self.nav.addTab(self.layer_list, "图层")

        self.sel_list = QListWidget()
        self.nav.addTab(self.sel_list, "选择")

        self.group_box = QWidget()
        gv = QVBoxLayout(self.group_box)
        gv.setContentsMargins(2, 2, 2, 2)
        gv.setSpacing(2)
        self.group_save_btn = QToolButton()
        self.group_save_btn.setText("＋ 保存当前选择为群组")
        self.group_save_btn.clicked.connect(self.group_save.emit)
        gv.addWidget(self.group_save_btn)
        self.group_list = QListWidget()
        self.group_list.itemClicked.connect(
            lambda it: self.group_clicked.emit(it.text()))
        gv.addWidget(self.group_list)
        self.nav.addTab(self.group_box, "群组")

        self.view_box = QWidget()
        vv = QVBoxLayout(self.view_box)
        vv.setContentsMargins(2, 2, 2, 2)
        vv.setSpacing(2)
        self.view_save_btn = QToolButton()
        self.view_save_btn.setText("＋ 保存当前视图")
        self.view_save_btn.clicked.connect(self.view_save.emit)
        vv.addWidget(self.view_save_btn)
        self.view_list = QListWidget()
        self.view_list.itemClicked.connect(
            lambda it: self.view_clicked.emit(it.text()))
        vv.addWidget(self.view_list)
        self.nav.addTab(self.view_box, "视图")
        self._populate_views(None)
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
        self.props.verticalHeader().setDefaultSectionSize(24)
        self.props.horizontalHeader().setStretchLastSection(True)
        self.props.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.props.setSelectionMode(QAbstractItemView.SingleSelection)
        self.props.setAlternatingRowColors(True)
        self.props.setShowGrid(False)
        self.props.setWordWrap(False)
        split.addWidget(_section("属性", self.props))
        split.setSizes([300, 150, 200])

        self._block_tree = False

    def _on_item_changed(self, item, col):
        if self._block_tree:
            return
        self.tree_checked.emit(item, col)

    def _build_option_pages(self):
        def checks(cmd, pairs):
            w = QWidget()
            f = QVBoxLayout(w)
            f.setContentsMargins(4, 4, 4, 4)
            f.setSpacing(6)
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
            f.setContentsMargins(4, 4, 4, 4)
            f.setSpacing(6)
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

        def check_spin(cmd, pairs, spins):
            """Option page with checkboxes + numeric (mm) spinboxes."""
            w = QWidget()
            f = QVBoxLayout(w)
            f.setContentsMargins(4, 4, 4, 4)
            f.setSpacing(6)
            boxes = []
            for label, default in pairs:
                cb = QCheckBox(label)
                cb.setChecked(default)
                f.addWidget(cb)
                boxes.append(cb)
            sp = []
            for label, default in spins:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                sb = QDoubleSpinBox()
                sb.setRange(0.001, 100000.0)
                sb.setValue(float(default))
                sb.setSuffix(" mm")
                row.addWidget(sb)
                f.addLayout(row)
                sp.append(sb)
            f.addStretch(1)
            self._opt_pages[cmd] = (w, boxes, sp)
            self.opt_stack.addWidget(w)

        checks("tool.select", [("捕捉到栅格", False), ("端点", True), ("中点", True), ("重合", False)])
        check_spin("tool.pull", [("对称", False), ("复制", False), ("到面", False)],
                   [("距离", 5.0)])
        check_spin("tool.move", [("复制", False), ("到点", False), ("到面", False)],
                   [("距离", 10.0)])
        radios("tool.combine", ["合并", "减去", "相交"])
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
        _w, boxes = page[0], page[1]
        if 0 <= index < len(boxes):
            return bool(boxes[index].isChecked())
        return False

    def spin_value(self, cmd: str, index: int):
        """Value of a mm spinbox on the option page, or None when absent."""
        page = self._opt_pages.get(cmd)
        if page and len(page) > 2 and 0 <= index < len(page[2]):
            return float(page[2][index].value())
        return None

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
            if session.kdoc.components:
                for comp in session.kdoc.components:
                    label = comp.name + ("（锚定）" if comp.anchored else "")
                    it = QTreeWidgetItem([label])
                    it.setData(0, Qt.UserRole, ("component", comp.id))
                    it.setCheckState(0, Qt.Checked if comp.visible else Qt.Unchecked)
                    root.addChild(it)
                    for bid in comp.body_ids:
                        body = session.kdoc.body_by_id(bid)
                        if body is not None:
                            sub = QTreeWidgetItem([body.name])
                            sub.setData(0, Qt.UserRole, ("body", bid))
                            sub.setCheckState(0, Qt.Checked if body.visible else Qt.Unchecked)
                            it.addChild(sub)
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
            for ns in getattr(session.kdoc, "named", []):
                it = QTreeWidgetItem([f"命名选择: {ns['name']}"])
                it.setData(0, Qt.UserRole, ("named", ns["name"]))
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
        self._block_layer = True
        if session.kdoc is not None and session.kdoc.bodies:
            buckets = {}
            for b in session.kdoc.bodies:
                buckets.setdefault(getattr(b, "layer", "默认") or "默认", []).append(b)
            for name in sorted(buckets):
                bodies = buckets[name]
                it = QTreeWidgetItem([f"{name}（{len(bodies)}）", ""])
                it.setData(0, Qt.UserRole, ("layer", name))
                it.setCheckState(0, Qt.Checked if all(b.visible for b in bodies)
                                 else Qt.Unchecked)
                self.layer_list.addTopLevelItem(it)
        else:
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
        self._block_layer = False

        self.group_list.clear()
        for g in getattr(session.kdoc, "groups", []) if session.kdoc else []:
            self.group_list.addItem(f"{g['name']}（{len(g['items'])}）")
        if not self.group_list.count():
            self.group_list.addItem("（尚无群组）")
        self._populate_views(session)

    def _populate_views(self, session):
        self.view_list.clear()
        for label in ("主视图", "等轴测"):
            self.view_list.addItem(QListWidgetItem(label))
        for sv in getattr(session, "saved_views", []) or []:
            self.view_list.addItem(QListWidgetItem(sv["name"]))

    def _on_layer_item(self, item, col):
        if getattr(self, "_block_layer", False):
            return
        data = item.data(0, Qt.UserRole)
        if data and isinstance(data, tuple) and data[0] == "layer":
            self.layer_toggled.emit(data[1], item.checkState(0) == Qt.Checked)

    def _layer_menu(self, pos):
        menu = QMenu(self)
        act_new = menu.addAction("新建图层（移入选中实体）")
        act_del = None
        item = self.layer_list.itemAt(pos)
        data = item.data(0, Qt.UserRole) if item else None
        if data and isinstance(data, tuple) and data[0] == "layer" and data[1] != "默认":
            act_del = menu.addAction("删除图层（实体回到默认）")
        chosen = menu.exec_(self.layer_list.viewport().mapToGlobal(pos))
        if chosen is act_new:
            name, ok = QInputDialog.getText(self, "新建图层", "图层名：")
            if ok and name.strip():
                self.layer_assign.emit(name.strip())
        elif act_del is not None and chosen is act_del:
            self.layer_remove.emit(data[1])

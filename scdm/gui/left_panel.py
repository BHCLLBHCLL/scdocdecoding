"""Left navigation: structure / layers / selection / groups / views + options + properties."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDoubleSpinBox, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QListWidget, QListWidgetItem, QMenu, QInputDialog,
    QRadioButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QFrame,
)

from scdm.document import Session
from scdm.gui.icons import make_icon


def _section(title: str, widget: QWidget) -> QWidget:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(6, 10, 6, 6)
    lay.setSpacing(4)
    lay.addWidget(widget)
    return box


class LeftPanel(QWidget):
    tree_clicked = pyqtSignal(object)  # QTreeWidgetItem
    tree_double_clicked = pyqtSignal(object)   # R103/A-4: edit a feature parameter
    tree_checked = pyqtSignal(object, int)
    layer_toggled = pyqtSignal(str, bool)
    group_toggled = pyqtSignal(str, bool)   # R26/P151: official/part group shown or hidden
    group_isolate = pyqtSignal(str)         # R27/P157: show only this part
    group_show_all = pyqtSignal()           # R27/P157: show every part again
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
        self.tree.setIconSize(QSize(18, 18))
        self.tree.itemClicked.connect(self.tree_clicked.emit)
        self.tree.itemDoubleClicked.connect(
            lambda item, _col: self.tree_double_clicked.emit(item))
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
        self._block_group = False
        self.group_list.itemChanged.connect(self._on_group_item)
        # R27/P157: right-click -> isolate / show all (menu built on demand)
        self.group_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(
            self._on_group_menu)
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

        def checks_nyi(cmd, labels, note):
            """Greyed-out option page: the option exists in SpaceClaim but is
            not wired here - declared instead of silently accepted (P2)."""
            w = QWidget()
            f = QVBoxLayout(w)
            f.setContentsMargins(4, 4, 4, 4)
            f.setSpacing(6)
            boxes = []
            for label in labels:
                cb = QCheckBox(label)
                cb.setChecked(False)
                cb.setEnabled(False)
                cb.setToolTip("未接线：" + note)
                f.addWidget(cb)
                boxes.append(cb)
            hint = QLabel("未接线：" + note)
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#8a8a8a; font-size:11px;")
            f.addWidget(hint)
            f.addStretch(1)
            self._opt_pages[cmd] = (w, boxes)
            self.opt_stack.addWidget(w)

        checks("tool.select", [("捕捉到栅格", False), ("端点", True), ("中点", True), ("重合", False)])
        check_spin("tool.pull", [("对称", False), ("复制", False), ("到面", False)],
                   [("距离", 5.0)])
        check_spin("tool.move", [("复制", False), ("到点", False), ("到面", False)],
                   [("距离", 10.0)])
        radios("tool.combine", ["合并", "减去", "相交"])
        checks("mode.sketch", [("草图网格", True), ("捕捉栅格", True)])
        checks("mode.section", [("剖面显示", True), ("截面可拉", True)])
        checks("tool.split_body", [("保留两侧", True)])
        checks_nyi("tool.fill", ["保留边", "相切连续"],
                   "填充走 OCCT Defeaturing，无保留边/相切参数")
        checks_nyi("tool.replace", ["延伸目标面"],
                   "替换为平面移动+愈合，无延伸语义")
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

    def set_checked(self, cmd: str, index: int, on: bool) -> None:
        page = self._opt_pages.get(cmd)
        if not page:
            return
        boxes = page[1]
        if 0 <= index < len(boxes):
            boxes[index].setChecked(bool(on))

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

        def add_features(node, body_id):
            """P16/R103: a body's feature history, with editable parameters.

            A body whose recorded history no longer reproduces its shape gets a
            tooltip with the measured reason and **no** editable rows - the tree
            never offers an edit that the replay would refuse.
            """
            stack = getattr(session.kdoc, "features", {}).get(body_id)
            if stack is None or not len(stack):
                return
            ok, why = ((False, "内核不可用") if not hasattr(session.kdoc, "can_replay")
                       else session.kdoc.can_replay(body_id, session.scale))
            for fi, feat in enumerate(stack.features):
                fnode = QTreeWidgetItem([feat.label()])
                fnode.setData(0, Qt.UserRole, ("feature", body_id, fi))
                fnode.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if not ok:
                    fnode.setToolTip(0, "不可重放：%s" % why)
                node.addChild(fnode)
                if not ok:
                    continue
                for row in stack.editable():
                    if row["index"] != fi:
                        continue
                    unit = (" " + row["unit"]) if row["unit"] else ""
                    pnode = QTreeWidgetItem(["%s = %g%s" % (row["label"],
                                                            row["value"], unit)])
                    pnode.setData(0, Qt.UserRole,
                                  ("feature_param", body_id, fi, row["param"]))
                    pnode.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    pnode.setToolTip(0, "双击修改 %s（重放特征历史）" % row["label"])
                    fnode.addChild(pnode)

        doc = session.design_doc
        # P27: read-only view of the loaded official document structure
        if session.data and doc is not None:
            info = QTreeWidgetItem(["文档结构（只读）"])
            info.setData(0, Qt.UserRole, ("docinfo", ""))
            info.setFlags(Qt.ItemIsEnabled)
            root.addChild(info)
            parts = list(getattr(doc, "parts", []) or [])
            pit = QTreeWidgetItem(["零件 PartDef：%d 个" % len(parts)])
            pit.setData(0, Qt.UserRole, ("docparts", len(parts)))
            info.addChild(pit)
            layers = list(getattr(doc, "layers", []) or [])
            lit = QTreeWidgetItem(["图层：%d 个" % len(layers)])
            lit.setData(0, Qt.UserRole, ("doclayers", len(layers)))
            info.addChild(lit)
            for lay in layers[:12]:
                sub = QTreeWidgetItem([getattr(lay, "name", "") or "图层"])
                sub.setData(0, Qt.UserRole, ("doclayer", getattr(lay, "id", "")))
                sub.setFlags(Qt.ItemIsEnabled)
                lit.addChild(sub)
            caps = list(getattr(doc, "captions", []) or [])
            info.addChild(QTreeWidgetItem(["标题 Caption：%d 个" % len(caps)]))
            named = list(getattr(doc, "named_selections", []) or [])
            info.addChild(QTreeWidgetItem(["命名选择：%d 个" % len(named)]))
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
                            add_features(sub, bid)
            for body in session.kdoc.bodies:
                it = QTreeWidgetItem([body.name])
                it.setData(0, Qt.UserRole, ("body", body.id))
                it.setCheckState(0, Qt.Checked if body.visible else Qt.Unchecked)
                root.addChild(it)
                add_features(it, body.id)
            for sk in session.kdoc.sketches:
                it = QTreeWidgetItem([sk.name])
                it.setData(0, Qt.UserRole, ("sketch", sk.id))
                it.setCheckState(0, Qt.Checked)
                it.setToolTip(0, "双击进入该草图编辑")
                root.addChild(it)
                # R107/A-3: the drivable dimensions, so a sketch can be changed
                # by its numbers instead of by redrawing
                try:
                    from scdm import sketchmode as _SKM
                    dims = _SKM.dimensions(session.kdoc, sk.id, session.scale)
                except Exception:
                    dims = []
                for d in dims:
                    # R111/A-1: the index is shown because another dimension
                    # references this one by name ("dim5"), so it has to be
                    # discoverable without reading the file
                    dn = QTreeWidgetItem(["#%d %s（双击修改）"
                                          % (d["index"], d["label"])])
                    dn.setData(0, Qt.UserRole,
                               ("sketch_dim", sk.id, d["index"]))
                    dn.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    dn.setToolTip(0, "驱动尺寸：改值后重新求解草图并重建实体；"
                                    "别的尺寸可用 dim%d 引用它" % d["index"])
                    it.addChild(dn)
            doc_feats = getattr(getattr(session.kdoc, "document_features",
                                        None), "features", [])
            if doc_feats:
                fh = QTreeWidgetItem(["特征历史"])
                fh.setData(0, Qt.UserRole, ("feature_history", ""))
                fh.setFlags(Qt.ItemIsEnabled)
                root.addChild(fh)
                for fi, feat in enumerate(doc_feats):
                    sub = QTreeWidgetItem(["%d. %s" % (fi + 1, feat.label())])
                    sub.setData(0, Qt.UserRole, ("doc_feature", fi))
                    fh.addChild(sub)
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
        self._block_group = True
        report = dict(getattr(session.kdoc, "import_report", None) or {})
        hint = ""
        # R72/P358: countable ref split (referencing / unbuilt / no-boundary)
        # comes from import_sab so the tree, the status line and the tests
        # cannot drift apart.
        from scdm.import_sab import ref_family_hint, watertight_hint
        hint += ref_family_hint(report)
        # R77/P380: same Qt-free wording source as the status line
        hint += watertight_hint(report)
        if report.get("unbuilt_faces"):
            hint += " · 未重建 %d" % report["unbuilt_faces"]
        for g in getattr(session.kdoc, "groups", []) if session.kdoc else []:
            suffix = hint if g.get("imported") else ""
            it = QListWidgetItem(f"{g['name']}（{len(g['items'])}）{suffix}")
            it.setData(Qt.UserRole, ("group", g["name"]))
            # R26/P151: official part groups carry a checkbox; the layer pattern
            # is reused (block the signal while repopulating)
            if g.get("imported"):
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked)
            self.group_list.addItem(it)
        self._block_group = False
        if not self.group_list.count():
            self.group_list.addItem("（尚无群组）")
        self._populate_views(session)

    def _populate_views(self, session):
        self.view_list.clear()
        for label in ("主视图", "等轴测"):
            self.view_list.addItem(QListWidgetItem(label))
        for sv in getattr(session, "saved_views", []) or []:
            self.view_list.addItem(QListWidgetItem(sv["name"]))

    def _on_group_menu(self, pos):
        """R27/P157: isolate / show-all for an official part group."""
        item = self.group_list.itemAt(pos)
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if not (data and isinstance(data, tuple) and data[0] == "group"):
            return
        try:
            menu = QMenu(self.group_list)
            act_iso = menu.addAction("隔离显示")
            act_all = menu.addAction("全部显示")
            chosen = menu.exec_(self.group_list.mapToGlobal(pos))
        except Exception:
            return
        if chosen is act_iso:
            self.group_isolate.emit(data[1])
        elif chosen is act_all:
            self.group_show_all.emit()

    def _on_group_item(self, item):
        """R26/P151: a part-group checkbox toggled -> tell the viewer."""
        if getattr(self, "_block_group", False):
            return
        data = item.data(Qt.UserRole)
        if data and isinstance(data, tuple) and data[0] == "group":
            self.group_toggled.emit(data[1],
                                    item.checkState() == Qt.Checked)

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

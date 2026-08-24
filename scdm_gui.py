"""SpaceClaim-style shell: viewer + direct-modeler UI (DEV_PLAN M1–M5).

M1 live: open/new/close, ribbon chrome, structure tree, picking, display, measure.
M2–M5 commands are present; activating them shows options and a wave status line
until the OCCT kernel lands.
"""
from __future__ import annotations

import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from PyQt5.QtCore import Qt, QSettings, QSize
    from PyQt5.QtGui import QColor, QPalette
    from PyQt5.QtWidgets import (
        QAction, QApplication, QCheckBox, QDialog, QDialogButtonBox,
        QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
        QMenu, QMessageBox, QSplitter, QStackedWidget, QStatusBar,
        QTabBar, QToolBar, QToolButton, QVBoxLayout, QWidget,
    )
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    try:
        import vtkmodules.vtkInteractionStyle  # noqa: F401
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    except Exception:
        pass
    _HAS_DEPS = True
except Exception:
    _HAS_DEPS = False
    QMainWindow = object


from scdm.catalog import BACKSTAGE, M1_LIVE, QAT, command_by_id
from scdm.document import Session, new_session, session_from_scdoc
from scdm.history import History
from scdm.selection import SelectionModel
from scdm.tools.base import ToolManager


def apply_light_theme(app):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(240, 240, 240))
    pal.setColor(QPalette.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    pal.setColor(QPalette.Text, QColor(32, 32, 32))
    pal.setColor(QPalette.WindowText, QColor(32, 32, 32))
    pal.setColor(QPalette.Button, QColor(240, 240, 240))
    pal.setColor(QPalette.ButtonText, QColor(32, 32, 32))
    pal.setColor(QPalette.Highlight, QColor(0, 120, 215))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)


if not _HAS_DEPS:
    class ScdmViewer:
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt5 / vtk not installed; GUI unavailable")

    def main(argv=None):
        sys.stderr.write("PyQt5 / vtk not installed; GUI unavailable\n")
        return 1
else:
    from scdm.gui.backstage import Backstage
    from scdm.gui.icons import make_icon
    from scdm.gui.left_panel import LeftPanel
    from scdm.gui.ribbon import RibbonBar
    from scdm.gui.scene import Scene
    from scdm.gui.status import FilterBar, StatusPrompt
    from scdm.gui.viewport import ViewportHost

    class OptionsDialog(QDialog):
        def __init__(self, sel: SelectionModel, parent=None):
            super().__init__(parent)
            self.setWindowTitle("选项")
            form = QFormLayout(self)
            self.snap_grid = QCheckBox("捕捉到栅格")
            self.snap_grid.setChecked(sel.snap_grid)
            self.snap_end = QCheckBox("端点")
            self.snap_end.setChecked(sel.snap_end)
            self.snap_mid = QCheckBox("中点")
            self.snap_mid.setChecked(sel.snap_mid)
            form.addRow("捕捉", self.snap_grid)
            form.addRow("", self.snap_end)
            form.addRow("", self.snap_mid)
            hint = QLabel("内核精度与撤销步数在 M2 接入 OCCT 后生效。")
            hint.setWordWrap(True)
            form.addRow(hint)
            box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            box.accepted.connect(self.accept)
            box.rejected.connect(self.reject)
            form.addRow(box)

        def apply_to(self, sel: SelectionModel):
            sel.snap_grid = self.snap_grid.isChecked()
            sel.snap_end = self.snap_end.isChecked()
            sel.snap_mid = self.snap_mid.isChecked()

    class ScdmViewer(QMainWindow):
        def __init__(self, path: str = None):
            super().__init__()
            self.resize(1400, 900)
            self.sessions = []
            self.cur = -1
            self.sel = SelectionModel()
            self.history = History()
            self._measure_pts = []
            self._click_n = 0
            self._click_actor = None
            self._click_t = 0.0
            self._cam_prev = None
            self._nav_mode = None  # spin|pan|zoom or None
            self.settings = QSettings("scdocdecoding", "scdm")

            self._build_chrome()
            self.tools = ToolManager(self._set_status)
            self._new_session(activate=True)
            self._wire_defaults()
            if path:
                self.open_path(path)

        # -- chrome ----------------------------------------------------------
        def _build_chrome(self):
            central = QWidget(self)
            self.setCentralWidget(central)
            root = QVBoxLayout(central)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            qat = QToolBar()
            qat.setMovable(False)
            qat.setIconSize(QSize(16, 16))
            qat.setStyleSheet("QToolBar { background: #E8E8E8; border: none; spacing: 2px; }")
            for cmd in QAT:
                act = QAction(make_icon(cmd.icon, 16), cmd.name, self)
                act.setToolTip(f"{cmd.name} ({cmd.en})  {cmd.wave}")
                act.triggered.connect(lambda _=False, i=cmd.id: self.on_command(i))
                qat.addAction(act)
            root.addWidget(qat)

            self.ribbon = RibbonBar()
            self.ribbon.command.connect(self.on_command)
            self.ribbon.tab_changed.connect(self._on_ribbon_tab)
            root.addWidget(self.ribbon)

            self.stack = QStackedWidget()
            root.addWidget(self.stack, 1)

            self.left = LeftPanel()
            self.left.tree_clicked.connect(self._on_tree_click)
            self.left.tree_checked.connect(self._on_tree_checked)
            self.left.tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.left.tree.customContextMenuRequested.connect(self._tree_menu)

            self._enable_3d = QApplication.instance() is not None and (
                QApplication.platformName() != "offscreen"
            )
            work = QWidget()
            work_l = QHBoxLayout(work)
            work_l.setContentsMargins(0, 0, 0, 0)
            work_l.setSpacing(0)
            split = QSplitter(Qt.Horizontal)
            split.addWidget(self.left)
            right = QWidget()
            rl = QVBoxLayout(right)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(0)
            if self._enable_3d:
                self.vtk_widget = QVTKRenderWindowInteractor(right)
                self.vp = ViewportHost(self.vtk_widget)
                self.vp.mini.command.connect(self.on_command)
                self.scene = Scene(self.vtk_widget)
                self.scene.style.click_cb = self._on_vtk_click
                self.scene.style.right_cb = self._on_vtk_right
                iren = self.vtk_widget.GetRenderWindow().GetInteractor()
                iren.AddObserver("KeyPressEvent", self._on_vtk_key)
                rl.addWidget(self.vp, 1)
            else:
                self.vtk_widget = None
                self.scene = None
                self.vp = None
                lab = QLabel("3D 视图已禁用（headless 模式）")
                lab.setAlignment(Qt.AlignCenter)
                rl.addWidget(lab, 1)
            self.doc_tabs = QTabBar()
            self.doc_tabs.setExpanding(False)
            self.doc_tabs.setTabsClosable(True)
            self.doc_tabs.currentChanged.connect(self._on_doc_tab)
            self.doc_tabs.tabCloseRequested.connect(self._close_tab)
            rl.addWidget(self.doc_tabs)
            split.addWidget(right)
            split.setStretchFactor(0, 0)
            split.setStretchFactor(1, 1)
            split.setSizes([300, 1100])
            work_l.addWidget(split)
            self.stack.addWidget(work)

            self.backstage = Backstage()
            self.backstage.command.connect(self.on_command)
            self.stack.addWidget(self.backstage)

            sb = QStatusBar()
            self.setStatusBar(sb)
            self._prompt = StatusPrompt()
            sb.addWidget(self._prompt, 1)
            self._filters = FilterBar()
            self._filters.filter_changed.connect(self._on_filter)
            self._filters.view_cmd.connect(self.on_command)
            sb.addPermanentWidget(self._filters)
            self.menuBar().hide()

        def _wire_defaults(self):
            self.ribbon.set_checked("mode.3d", True)
            self.ribbon.set_checked("tool.select", True)
            self.ribbon.set_checked("style.shaded_edges", True)
            for cid in ("show.faces", "show.edges", "show.vertices", "show.axes"):
                self.ribbon.set_checked(cid, True)
            self.left.show_options("tool.select")
            self._refresh_recent()

        def session(self) -> Session:
            return self.sessions[self.cur]

        def _set_status(self, text: str):
            self._prompt.setText(text)
            if self.vp:
                self.vp.set_hud(text)

        def _refresh_title(self):
            if self.cur < 0:
                self.setWindowTitle("SpaceClaim")
                return
            ses = self.session()
            self.setWindowTitle(ses.title())
            if 0 <= self.cur < self.doc_tabs.count():
                mark = "*" if ses.dirty else ""
                self.doc_tabs.setTabText(self.cur, mark + ses.name)

        def _refresh_recent(self):
            recent = self.settings.value("recent", [], type=list)
            self.backstage.set_recent(recent)

        def _push_recent(self, path: str):
            recent = self.settings.value("recent", [], type=list)
            path = os.path.abspath(path)
            recent = [p for p in recent if p != path]
            recent.insert(0, path)
            self.settings.setValue("recent", recent[:12])
            self._refresh_recent()

        # -- sessions --------------------------------------------------------
        def _new_session(self, activate=True):
            n = len(self.sessions) + 1
            ses = new_session(n)
            self.sessions.append(ses)
            self.doc_tabs.blockSignals(True)
            idx = self.doc_tabs.addTab(ses.name)
            self.doc_tabs.blockSignals(False)
            if activate:
                self.doc_tabs.setCurrentIndex(idx)
                self.cur = idx
                self._activate_session()

        def _activate_session(self):
            if self.cur < 0:
                return
            ses = self.session()
            self.left.populate_tree(ses)
            self.left.set_props([
                ("文档", ses.name),
                ("路径", ses.path or "（未保存）"),
                ("单位", ses.units_symbol()),
            ])
            self.left.set_selection_list([])
            self._filters.unit.setText(ses.units_symbol())
            if self.scene:
                if ses.data:
                    self.scene.build(ses)
                else:
                    self.scene.clear_bodies()
                    self.scene.apply_visibility(ses)
                    self.scene.fit()
            self._refresh_title()
            self._set_status("单击选择对象；双击选环边；三击选实体")

        def _on_doc_tab(self, index: int):
            if index < 0 or index >= len(self.sessions):
                return
            self.cur = index
            self._activate_session()

        def _close_tab(self, index: int):
            if index < 0 or index >= len(self.sessions):
                return
            self.sessions.pop(index)
            self.doc_tabs.blockSignals(True)
            self.doc_tabs.removeTab(index)
            self.doc_tabs.blockSignals(False)
            if not self.sessions:
                self.cur = -1
                self._new_session(True)
                return
            self.cur = min(index, len(self.sessions) - 1)
            self.doc_tabs.setCurrentIndex(self.cur)
            self._activate_session()

        def open_path(self, path: str):
            try:
                ses = session_from_scdoc(path)
            except Exception as exc:
                QMessageBox.critical(self, "打开", f"无法解析:\n{path}\n{exc}")
                return
            if self.cur >= 0 and self.session().data is None and not self.session().dirty:
                self.sessions[self.cur] = ses
                self.doc_tabs.setTabText(self.cur, ses.name)
            else:
                self.sessions.append(ses)
                idx = self.doc_tabs.addTab(ses.name)
                self.doc_tabs.setCurrentIndex(idx)
                self.cur = idx
            self._push_recent(path)
            self.ribbon.restore_design()
            self.stack.setCurrentIndex(0)
            self.ribbon.set_body_visible(True)
            self._activate_session()

        # -- ribbon / commands ----------------------------------------------
        def _on_ribbon_tab(self, tid: str):
            if tid == "file":
                self.ribbon.set_body_visible(False)
                self.stack.setCurrentIndex(1)
            else:
                self.ribbon.set_body_visible(True)
                self.stack.setCurrentIndex(0)

        def on_command(self, cmd_id: str):
            if cmd_id.startswith("file.open:"):
                self.open_path(cmd_id.split(":", 1)[1])
                return
            cmd = command_by_id(cmd_id)
            live = cmd_id in M1_LIVE
            if cmd_id.startswith("tool.") or cmd_id in (
                "measure.dist", "mode.sketch", "mode.section", "mode.3d",
            ):
                hud = {
                    "tool.select": "单击选择对象；双击选环边；三击选实体",
                    "measure.dist": "依次点选两个对象测量距离",
                    "mode.3d": "三维模式",
                }.get(cmd_id, cmd.name if cmd else cmd_id)
                if cmd_id.startswith("mode."):
                    self.tools.set_mode(cmd_id, cmd.wave if cmd else "M?", live)
                    self.ribbon.set_checked(cmd_id, True)
                else:
                    self.tools.activate(cmd_id, cmd.name if cmd else cmd_id,
                                        cmd.wave if cmd else "M?", live, hud)
                    self.ribbon.set_checked(cmd_id, True)
                self.left.show_options(cmd_id if cmd_id in (
                    "tool.select", "tool.pull", "tool.move", "tool.fill",
                    "tool.replace", "tool.combine", "tool.split_body",
                    "mode.sketch", "mode.section", "measure.dist",
                    "insert.cyl", "insert.sphere",
                ) else "none")
                if cmd_id == "tool.select":
                    self._set_status(hud)
                if live and cmd_id in ("mode.3d", "tool.select", "measure.dist"):
                    if cmd_id == "measure.dist":
                        self._measure_pts = []
                        self._set_status(hud)
                    return
                if not live:
                    return

            if cmd_id.startswith("show."):
                self._toggle_show(cmd_id)
                return
            if cmd_id.startswith("style."):
                self._set_style(cmd_id)
                return

            fn = getattr(self, "_do_" + cmd_id.replace(".", "_"), None)
            if fn:
                fn()
                return
            if cmd:
                self._set_status(
                    f"{cmd.wave} 未实现：{cmd.name}（{cmd.en}）— 界面已就位"
                )
            else:
                self._set_status(f"未知命令 {cmd_id}")

        def _do_file_new(self):
            self._new_session(True)
            self.stack.setCurrentIndex(0)
            self.ribbon.restore_design()
            self.ribbon.set_body_visible(True)

        def _do_file_open(self):
            fn, _ = QFileDialog.getOpenFileName(
                self, "打开", "",
                "SpaceClaim (*.scdoc);;STEP (*.step *.stp);;All (*)",
            )
            if fn:
                if fn.lower().endswith((".step", ".stp")):
                    self._set_status("M1：STEP 走 OCCT I/O，内核接入后打开；请先打开 .scdoc")
                    return
                self.open_path(fn)

        def _do_file_recent(self):
            self.ribbon.select_tab("file")
            self._on_ribbon_tab("file")

        def _do_file_close(self):
            if self.cur >= 0:
                self._close_tab(self.cur)

        def _do_file_image(self):
            if not self.scene:
                return
            fn, _ = QFileDialog.getSaveFileName(self, "导出图像", "", "PNG (*.png)")
            if fn:
                self.scene.export_png(fn)
                self._set_status(f"已导出 {fn}")

        def _do_file_options(self):
            dlg = OptionsDialog(self.sel, self)
            if dlg.exec_():
                dlg.apply_to(self.sel)
                self._set_status("已更新捕捉选项")

        def _do_file_exit(self):
            self.close()

        def _do_file_save(self):
            self._set_status("M2 未实现：保存（会话包 + STEP）")

        def _do_file_save_as(self):
            self._set_status("M2 未实现：另存为")

        def _do_edit_undo(self):
            self._set_status("M2 未实现：撤销（命令栈）")

        def _do_edit_redo(self):
            self._set_status("M2 未实现：重做")

        def _do_view_fit(self):
            if self.scene:
                self.scene.fit()
            self._set_status("缩放至适合")

        def _do_view_spin(self):
            self._nav_mode = "spin"
            self._set_status("中键拖动旋转（SpaceClaim 惯例）")

        def _do_view_pan(self):
            self._nav_mode = "pan"
            self._set_status("Shift+中键平移")

        def _do_view_zoom(self):
            self._set_status("滚轮朝光标缩放")

        def _do_view_prev(self):
            if self.scene and self._cam_prev:
                cur = self.scene.store_camera()
                self.scene.restore_camera(self._cam_prev)
                self._cam_prev = cur
                self._set_status("上一视图")

        def _do_view_home(self):
            self._remember_cam()
            if self.scene:
                self.scene.iso_view(self.session().scale)
            self._set_status("主视图")

        def _do_view_iso(self):
            self._remember_cam()
            if self.scene:
                self.scene.iso_view(self.session().scale)

        def _do_view_pos_x(self):
            self._remember_cam()
            if self.scene:
                self.scene.plane_view("x", self.session().scale)

        def _do_view_pos_y(self):
            self._remember_cam()
            if self.scene:
                self.scene.plane_view("y", self.session().scale)

        def _do_view_pos_z(self):
            self._remember_cam()
            if self.scene:
                self.scene.plane_view("z", self.session().scale)

        def _remember_cam(self):
            if self.scene:
                self._cam_prev = self.scene.store_camera()

        def _toggle_show(self, cmd_id: str):
            ses = self.session()
            btn = self.ribbon.button(cmd_id)
            on = btn.isChecked() if btn else True
            attr = {
                "show.faces": "show_faces",
                "show.edges": "show_edges",
                "show.vertices": "show_vertices",
                "show.planes": "show_planes",
                "show.axes": "show_axes",
            }[cmd_id]
            setattr(ses, attr, on)
            if self.scene:
                self.scene.apply_visibility(ses)
            self._set_status(f"{cmd_id} {'显示' if on else '隐藏'}")

        def _set_style(self, cmd_id: str):
            ses = self.session()
            ses.style = cmd_id.split(".", 1)[1]
            self.ribbon.set_checked(cmd_id, True)
            if self.scene:
                self.scene.apply_style(ses.style)
                self.scene.apply_visibility(ses)
            self._set_status(f"显示样式：{ses.style}")

        def _on_filter(self, key: str, on: bool):
            setattr(self.sel, "allow_" + key, on)

        # -- picking / tree -------------------------------------------------
        def _on_vtk_click(self):
            if not self.scene:
                return
            iren = self.vtk_widget.GetRenderWindow().GetInteractor()
            actor, world = self.scene.pick_actor()
            tool = self.tools.active
            if tool == "measure.dist" and world:
                self._measure_pts.append(world)
                if len(self._measure_pts) == 1:
                    self._set_status("已点选第一点，请选择第二点")
                elif len(self._measure_pts) >= 2:
                    a, b = self._measure_pts[:2]
                    d = math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))
                    mm = d * self.session().scale
                    self._set_status(f"距离 {mm:.3f} {self.session().units_symbol()}")
                    self._measure_pts = []
                return
            if tool != "tool.select":
                cmd = command_by_id(tool)
                wave = cmd.wave if cmd else "M2"
                name = cmd.name if cmd else tool
                self._set_status(f"{wave} 未实现：{name} — 当前单击不修改几何")
                return
            now = time.monotonic()
            if actor is not None and actor is self._click_actor and (now - self._click_t) < 0.45:
                self._click_n += 1
            else:
                self._click_n = 1
                self._click_actor = actor
            self._click_t = now
            add = bool(iren.GetControlKey())
            if actor is None:
                if not add:
                    self.sel.clear()
                    self.scene.highlight_actors([])
                    self.vp.show_mini(False)
                    self.left.set_selection_list([])
                return
            node = getattr(actor, "_node_id", None)
            if self._click_n >= 3 and self.sel.allows("body"):
                self._select_body_from_face(node, add)
            elif self._click_n == 2 and self.sel.allows("face"):
                self._select_body_from_face(node, add)
            elif self.sel.allows("face") and node is not None:
                self._select_face_node(node, add)

        def _on_vtk_right(self):
            self._set_status("右键菜单：隐藏 / 缩放到（树中亦可右键）")

        def _on_vtk_key(self, obj, ev):
            try:
                key = (obj.GetKeySym() or "").lower()
            except Exception:
                return
            if key == "f":
                self._do_view_fit()
            elif key == "x":
                self._do_view_pos_x()
            elif key == "y":
                self._do_view_pos_y()
            elif key == "z":
                self._do_view_pos_z()
            elif key == "escape":
                self.on_command("tool.select")
            elif key == "space":
                prev = self.tools.repeat_previous()
                if prev:
                    self.on_command(prev)

        def _body_face_nodes(self, body_id: str):
            ses = self.session()
            doc = ses.design_doc
            if doc is None:
                return list(self.scene._face_actors.keys()) if self.scene else []
            body = doc.body_by_doc_id(body_id)
            if body is None:
                return list(self.scene._face_actors.keys())
            nodes = []
            for f in body.faces:
                try:
                    nodes.append(int(f.id.split(":")[1]))
                except Exception:
                    pass
            return nodes

        def _select_face_node(self, node: int, add: bool):
            did = f"0:{node}"
            if add:
                self.sel.toggle("face", did)
            else:
                self.sel.set_one("face", did)
            nodes = [int(i.split(":")[1]) for k, i in self.sel.items if k == "face"]
            if self.scene:
                self.scene.highlight_nodes(nodes)
            if self.vp:
                self.vp.show_mini(True)
            self.left.set_selection_list([f"面 {i}" for i in nodes])
            self.left.set_props(self._face_props(did, node))
            self._set_status(f"已选择面 {did}")

        def _select_body_from_face(self, node, add: bool):
            ses = self.session()
            doc = ses.design_doc
            body_id = None
            if doc is not None and node is not None:
                for b in doc.bodies:
                    for f in b.faces:
                        if f.id.endswith(":" + str(node)) or f.id == f"0:{node}":
                            body_id = b.id
                            break
            if body_id is None and doc is not None and doc.bodies:
                body_id = doc.bodies[0].id
            if body_id is None:
                if self.scene:
                    self.scene.highlight_all_faces()
                return
            self._select_body(body_id, add)

        def _select_body(self, body_id: str, add: bool = False):
            if add:
                self.sel.toggle("body", body_id)
            else:
                self.sel.set_one("body", body_id)
            nodes = []
            for kind, sid in self.sel.items:
                if kind == "body":
                    nodes.extend(self._body_face_nodes(sid))
            if self.scene:
                self.scene.highlight_nodes(nodes)
            if self.vp:
                self.vp.show_mini(True)
            ses = self.session()
            doc = ses.design_doc
            body = doc.body_by_doc_id(body_id) if doc else None
            name = ses.body_caption(body) if body else body_id
            self.left.set_selection_list([name])
            rows = [("名称", name), ("Id", body_id)]
            if body:
                rows += [("面数", len(body.faces)), ("边数", len(body.edges))]
                if body.color:
                    rows.append(("颜色", body.color))
            self.left.set_props(rows)
            self._set_status(f"已选择实体 {name}")

        def _face_props(self, did: str, node: int):
            ses = self.session()
            rows = [("名称", f"面 {did}"), ("Facet", node)]
            data = ses.data or {}
            model = data.get("model")
            if model is None:
                return rows
            face = None
            for f in model.of_kind("face"):
                if model.doc_id_of(f) == did:
                    face = f
                    break
            if face:
                fm = model.face_metrics(face)
                if fm:
                    rows.append(("面积", round(fm["area"] * ses.scale ** 2, 3)))
                    d = model.describe_plane(fm["normal"], fm["offset"], ses.scale)
                    if d:
                        rows.append(("平面", d))
            return rows

        def _on_tree_click(self, item):
            data = item.data(0, Qt.UserRole)
            if not data:
                return
            kind, sid = data
            if kind == "body":
                self._select_body(sid)
            elif kind == "origin":
                self.left.set_props([("名称", "原点"), ("类型", "基准")])
            elif kind == "plane":
                self.left.set_props([("名称", f"平面 {sid.upper()}"), ("类型", "基准面")])
            elif kind == "root":
                ses = self.session()
                self.left.set_props([
                    ("文档", ses.name),
                    ("路径", ses.path or "（未保存）"),
                    ("单位", ses.units_symbol()),
                ])

        def _on_tree_checked(self, item, col):
            data = item.data(0, Qt.UserRole)
            if not data or not self.scene:
                return
            kind, sid = data
            on = item.checkState(0) == Qt.Checked
            ses = self.session()
            if kind == "origin":
                ses.show_axes = on
            elif kind == "plane":
                ses.show_planes = on
                self.ribbon.set_checked("show.planes", on)
            elif kind == "body":
                for n in self._body_face_nodes(sid):
                    act = self.scene._face_actors.get(n)
                    if act:
                        act.SetVisibility(1 if on else 0)
                self.scene.render()
                return
            self.scene.apply_visibility(ses)

        def _tree_menu(self, pos):
            item = self.left.tree.itemAt(pos)
            menu = QMenu(self)
            act_fit = menu.addAction("缩放到")
            act_hide = menu.addAction("隐藏")
            chosen = menu.exec_(self.left.tree.viewport().mapToGlobal(pos))
            if chosen is act_fit:
                self._do_view_fit()
            elif chosen is act_hide and item:
                item.setCheckState(0, Qt.Unchecked)

        def closeEvent(self, ev):
            if self.vtk_widget is not None:
                try:
                    self.vtk_widget.Finalize()
                except Exception:
                    pass
            super().closeEvent(ev)


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if not _HAS_DEPS:
        sys.stderr.write("PyQt5 / vtk not installed; GUI unavailable\n")
        return 1
    app = QApplication.instance() or QApplication(argv)
    apply_light_theme(app)
    path = argv[1] if len(argv) > 1 else None
    win = ScdmViewer(path)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)

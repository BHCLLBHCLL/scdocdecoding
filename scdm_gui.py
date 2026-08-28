"""SpaceClaim-style shell: viewer + direct-modeler UI (DEV_PLAN M1–M5).

M1 live: open/new/close, ribbon chrome, structure tree, picking, display, measure.
M2–M5 commands are present; activating them shows options and a wave status line
until the OCCT kernel lands.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from PyQt5.QtCore import Qt, QSettings, QSize, QPoint
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


from scdm.catalog import BACKSTAGE, M1_LIVE, QAT, command_by_id, live_commands
from scdm.document import Session, new_session, session_from_scdoc
from scdm import kernel as K
from scdm.kdoc import KernelDoc
from scdm.history import History
from scdm.selection import SelectionModel
from scdm.tools.base import ToolManager


def apply_light_theme(app):
    from scdm.gui.theme import APP_QSS, apply_palette, ui_font
    app.setStyle("Fusion")
    apply_palette(app)
    app.setFont(ui_font())
    app.setStyleSheet(APP_QSS)


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
            self.setWindowIcon(make_icon("select", 32))
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
            from scdm.scripting import Recorder
            self.recorder = Recorder()

            self._build_chrome()
            self._apply_customize(self.settings.value("ribbon/hidden", []) or [])
            self.tools = ToolManager(self._set_status)
            self._new_session(activate=True)
            self._wire_defaults()
            from PyQt5.QtCore import QTimer
            self._autosave_timer = QTimer(self)
            self._autosave_timer.timeout.connect(self._autosave_all)
            self._autosave_timer.start(60 * 1000)
            if path:
                self.open_path(path)
            self._recover_prompt()

        # -- chrome ----------------------------------------------------------
        def _build_chrome(self):
            central = QWidget(self)
            self.setCentralWidget(central)
            root = QVBoxLayout(central)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            qat = QToolBar()
            qat.setObjectName("QuickAccess")
            qat.setMovable(False)
            qat.setIconSize(QSize(18, 18))
            qat.setToolButtonStyle(Qt.ToolButtonIconOnly)
            for cmd in QAT:
                act = QAction(make_icon(cmd.icon, 18), cmd.name, self)
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
            split.setChildrenCollapsible(False)
            split.setHandleWidth(5)
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
            self.doc_tabs.setObjectName("DocTabs")
            self.doc_tabs.setExpanding(False)
            self.doc_tabs.setTabsClosable(True)
            self.doc_tabs.setDocumentMode(True)
            self.doc_tabs.currentChanged.connect(self._on_doc_tab)
            self.doc_tabs.tabCloseRequested.connect(self._close_tab)
            rl.addWidget(self.doc_tabs)
            split.addWidget(right)
            split.setStretchFactor(0, 0)
            split.setStretchFactor(1, 1)
            split.setSizes([280, 1120])
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
            self._set_drag_hooks("tool.select")
            self._refresh_recent()

        def session(self) -> Session:
            return self.sessions[self.cur]

        def _set_status(self, text: str):
            self._prompt.setText(text)
            if self.vp:
                self.vp.set_hud(text)

        def _record(self, cmd_id: str, **opts):
            """Note a successful geometry step when the recorder is enabled."""
            self.recorder.note(cmd_id, **opts)

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
            low = path.lower()
            try:
                if low.endswith((".step", ".stp", ".brep", ".scdm")):
                    ses = self._session_from_cad(path)
                else:
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

        def _session_from_cad(self, path: str) -> Session:
            if not K.available():
                raise RuntimeError("打开 STEP/SCDM 需要 pythonocc-core")
            stem = os.path.splitext(os.path.basename(path))[0]
            ses = new_session(1)
            ses.name = stem
            ses.path = path
            ses.kdoc = KernelDoc()
            low = path.lower()
            if low.endswith(".scdm"):
                from scdm.io_project import load_scdm
                ses.kdoc = load_scdm(path)
            elif low.endswith(".brep"):
                ses.kdoc.add_body(K.read_brep(path), name=stem)
            else:
                ses.kdoc.add_body(K.read_step(path), name=stem)
            ses.history.clear()
            ses.history.push(ses.kdoc.snapshot())
            return ses

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
            live = cmd_id in live_commands()
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
                self._set_drag_hooks(cmd_id)
                if cmd_id == "tool.select":
                    self._set_status(hud)
                if live and cmd_id in ("mode.3d", "tool.select", "measure.dist"):
                    if cmd_id == "measure.dist":
                        self._measure_pts = []
                        self._set_status(hud)
                    elif cmd_id == "mode.3d":
                        self._set_sketch_grid(False)
                    return
                if cmd_id in ("tool.pull", "tool.move", "tool.fill", "tool.replace",
                              "tool.combine", "tool.split_body", "tool.split_faces",
                              "mode.sketch", "mode.section"):
                    if live:
                        self._set_status(hud if live else "")
                        if cmd_id == "tool.pull":
                            self._set_status("拉动：选择面后再次单击，沿法向挤出 5mm")
                        elif cmd_id == "tool.move":
                            self._set_status("移动：选择实体后单击，沿 X 平移 10mm；选项可复制")
                        elif cmd_id == "tool.combine":
                            self._set_status("合并：先选目标体，再选刀具体")
                        elif cmd_id == "tool.fill":
                            self._set_status("填充：选择要移除并愈合的面后单击")
                        elif cmd_id == "mode.sketch":
                            self._begin_sketch()
                        elif cmd_id == "mode.section":
                            self._toggle_section()
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
                "CAD (*.scdoc *.step *.stp *.scdm *.brep);;All (*)",
            )
            if fn:
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

        def _do_file_print(self):
            if not self.scene:
                self._set_status("3D 视图不可用")
                return
            try:
                from PyQt5.QtGui import QPainter
                from PyQt5.QtPrintSupport import QPrintPreviewDialog, QPrinter
            except Exception:
                self._set_status("打印组件不可用（QtPrintSupport）")
                return
            img = self.scene.render_image()
            if img is None or img.isNull():
                self._set_status("无法获取视口图像")
                return
            printer = QPrinter(QPrinter.HighResolution)
            preview = QPrintPreviewDialog(printer, self)

            def _paint():
                p = QPainter(printer)
                target = p.viewport()
                scaled = img.scaled(target.size(), Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
                p.drawImage((target.width() - scaled.width()) // 2,
                            (target.height() - scaled.height()) // 2, scaled)
                p.end()

            preview.paintRequested.connect(_paint)
            self._set_status("打印预览：当前视口")
            preview.exec_()

        def _do_file_options(self):
            dlg = OptionsDialog(self.sel, self)
            if dlg.exec_():
                dlg.apply_to(self.sel)
                self._set_status("已更新捕捉选项")

        def _do_file_exit(self):
            self.close()

        # -- crash recovery (G2-01) ------------------------------------------
        def _autosave_path(self, ses):
            safe = "".join(c for c in ses.name if c.isalnum() or c in "-_") or "design"
            return os.path.join(tempfile.gettempdir(), "scdm_autosave", safe + ".scdm")

        def _autosave_all(self):
            """Periodically write dirty sessions so a crash is recoverable."""
            if not K.available():
                return
            try:
                os.makedirs(os.path.dirname(self._autosave_path(self.session())),
                            exist_ok=True)
            except Exception:
                return
            from scdm.io_project import save_scdm
            for ses in self.sessions:
                if not ses.dirty or not ses.kdoc or not ses.kdoc.bodies:
                    continue
                try:
                    save_scdm(self._autosave_path(ses), ses.kdoc)
                except Exception:
                    pass

        def _recover_prompt(self):
            adir = os.path.join(tempfile.gettempdir(), "scdm_autosave")
            try:
                files = [os.path.join(adir, f) for f in os.listdir(adir)
                         if f.endswith(".scdm")]
            except Exception:
                return
            if not files:
                return
            names = "\n".join(os.path.basename(f) for f in files)
            if QMessageBox.question(
                    self, "恢复",
                    f"发现未正常关闭的会话恢复文件：\n{names}\n\n是否恢复？"
            ) != QMessageBox.Yes:
                for f in files:
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                return
            for f in files:
                try:
                    self.open_path(f)
                    os.remove(f)
                except Exception as exc:
                    self._set_status(f"恢复失败: {exc}")

        def _do_file_recover(self):
            self._recover_prompt()

        def _do_file_save(self):
            ses = self.session()
            path = ses.path
            if not path or path.lower().endswith(".scdoc"):
                path, _ = QFileDialog.getSaveFileName(
                    self, "保存", ses.name + ".step",
                    "STEP (*.step *.stp);;SCDM (*.scdm);;STL (*.stl)")
                if not path:
                    return
            self._save_to(path)

        def _do_file_save_as(self):
            ses = self.session()
            path, _ = QFileDialog.getSaveFileName(
                self, "另存为", (ses.name or "Design") + ".step",
                "STEP (*.step *.stp);;SCDM (*.scdm);;STL (*.stl)")
            if path:
                self._save_to(path)

        def _do_file_export(self):
            self._do_file_save_as()

        def _save_to(self, path: str):
            ses = self.session()
            if not K.available() or ses.kdoc is None or not ses.kdoc.bodies:
                self._set_status("没有可保存的内核几何")
                return
            try:
                low = path.lower()
                shape = ses.kdoc.compound()
                if low.endswith(".stl"):
                    K.write_stl(shape, path)
                elif low.endswith(".scdm"):
                    from scdm.io_project import save_scdm
                    save_scdm(path, ses.kdoc)
                elif low.endswith(".scdoc"):
                    from scdm.scdoc_write import write_scdoc
                    write_scdoc(path, ses.kdoc, name=ses.name)
                else:
                    if not low.endswith((".step", ".stp")):
                        path += ".step"
                    K.write_step(shape, path)
                ses.path = path
                ses.name = os.path.splitext(os.path.basename(path))[0]
                ses.dirty = False
                self._refresh_title()
                self._set_status(f"已保存 {path}")
            except Exception as exc:
                self._set_status(f"保存失败: {exc}")

        def _do_edit_undo(self):
            ses = self.session()
            snap = ses.history.undo()
            if snap is None:
                self._set_status("无法撤销")
                return
            ses.kdoc.restore(snap)
            ses.dirty = True
            self._rebuild("已撤销")

        def _do_edit_redo(self):
            ses = self.session()
            snap = ses.history.redo()
            if snap is None:
                self._set_status("无法重做")
                return
            ses.kdoc.restore(snap)
            self._rebuild("已重做")

        def _do_edit_copy(self):
            self._clipboard_copy(cut=False)

        def _do_edit_cut(self):
            self._clipboard_copy(cut=True)

        def _do_edit_paste(self):
            ses = self.session()
            if not ses.clipboard:
                self._set_status("剪贴板为空")
                return
            sh = K.loads_brep(ses.clipboard)
            sh = K.translate(sh, (10 / ses.scale, 0, 0))
            ses.kdoc.add_body(sh, name="粘贴")
            self._commit("已粘贴")

        def _do_insert_cyl(self):
            self.tools.activate("insert.cyl", "圆柱", "M2", True, "单击视口放置圆柱（Ø10×10 mm）")
            self.left.show_options("insert.cyl")

        def _do_insert_sphere(self):
            self.tools.activate("insert.sphere", "球", "M2", True, "单击视口放置球（Ø10 mm）")
            self.left.show_options("insert.sphere")

        def _do_insert_plane(self):
            self.session().show_planes = True
            if self.scene:
                self.scene.apply_visibility(self.session())
            self.ribbon.set_checked("show.planes", True)
            self._set_status("已显示基准平面")

        def _do_insert_origin(self):
            self.session().show_axes = True
            if self.scene:
                self.scene.apply_visibility(self.session())
            self._set_status("已显示原点")

        def _do_insert_axis(self):
            self._do_insert_origin()

        def _do_insert_component(self):
            ses = self.session()
            if not self._need_kernel():
                return
            fn, _ = QFileDialog.getOpenFileName(
                self, "插入组件", "",
                "CAD (*.scdm *.step *.stp *.brep *.scdoc);;All (*)")
            if not fn:
                return
            stem = os.path.splitext(os.path.basename(fn))[0]
            low = fn.lower()
            try:
                if low.endswith(".scdm"):
                    from scdm.io_project import load_scdm
                    kdoc2 = load_scdm(fn)
                elif low.endswith(".scdoc"):
                    from scdm.document import load_scdoc
                    from scdm.import_sab import import_scdoc_bundle
                    kdoc2 = import_scdoc_bundle(load_scdoc(fn))
                elif low.endswith(".brep"):
                    kdoc2 = KernelDoc()
                    kdoc2.add_body(K.read_brep(fn), name=stem)
                else:
                    kdoc2 = KernelDoc()
                    kdoc2.add_body(K.read_step(fn), name=stem)
            except Exception as exc:
                self._set_status(f"插入组件失败: {exc}")
                return
            ids = []
            for b in kdoc2.bodies:
                nb = ses.kdoc.add_body(b.shape, name=b.name, color=b.color)
                ids.append(nb.id)
            if not ids:
                self._set_status("文件中没有实体")
                return
            comp = ses.kdoc.add_component(body_ids=ids, name=stem)
            self._commit(f"已插入组件 {comp.name}（{len(ids)} 实体）")

        def _do_insert_helix(self):
            ses = self.session()
            if not self._need_kernel():
                return
            try:
                sh = K.helix_solid(3 / ses.scale, 2 / ses.scale, 20 / ses.scale,
                                   0.4 / ses.scale)
                ses.kdoc.add_body(sh, name="螺旋")
                self._commit("已插入螺旋体")
            except Exception as exc:
                self._set_status(f"螺旋插入失败: {exc}")

        def _do_create_offset(self):
            self.on_command("tool.pull")

        def _do_create_blend(self):
            self._fillet_or_chamfer(fillet=True)

        def _do_create_chamfer(self):
            self._fillet_or_chamfer(fillet=False)

        def _do_create_mirror(self):
            body = self._selected_kbody()
            if body is None:
                return
            ses = self.session()
            mir = K.mirror(body.shape, (0, 0, 0), (1, 0, 0))
            ses.kdoc.add_body(mir, name=body.name + " 镜像")
            self._record("create.mirror")
            self._commit("已镜像")

        def _do_create_pattern(self):
            body = self._selected_kbody()
            if body is None:
                return
            ses = self.session()
            step = 15 / ses.scale
            shapes = K.pattern_linear(body.shape, (step, 0, 0), 3)
            for i, sh in enumerate(shapes[1:], 2):
                ses.kdoc.add_body(sh, name=f"{body.name} 阵列{i}")
            self._record("create.pattern", step=15.0, count=3)
            self._commit("线性阵列 ×3")

        def _do_create_shell(self):
            body = self._selected_kbody()
            if body is None:
                return
            faces = K.explore(body.shape, "face")
            if not faces:
                return
            try:
                body.shape = K.shell_solid(body.shape, 1 / self.session().scale, [faces[0]])
                self._record("create.shell", thickness=1.0)
                self._commit("已抽壳")
            except Exception as exc:
                self._set_status(f"抽壳失败: {exc}")

        def _do_create_draft(self):
            body = self._selected_kbody()
            if body is None:
                return
            faces = K.explore(body.shape, "face")
            if not faces:
                return
            ang = math.radians(5.0)
            try:
                # draft the first face about +Z as the neutral direction
                body.shape = K.draft_face(body.shape, faces[0], ang, (0, 0, 1))
                self._commit("拔模 5°")
            except Exception as exc:
                self._set_status(f"拔模失败: {exc}")

        def _do_measure_mass(self):
            body = self._selected_kbody()
            if body is None:
                kdoc = self.session().kdoc
                if not kdoc or not kdoc.bodies:
                    self._set_status("无实体")
                    return
                body = kdoc.bodies[0]
            ses = self.session()
            s = ses.scale
            v = K.volume(body.shape) * s ** 3
            a = K.area(body.shape) * s ** 2
            c = K.cog(body.shape)
            self.left.set_props([
                ("体积 mm³", round(v, 4)),
                ("面积 mm²", round(a, 4)),
                ("重心", [round(x * s, 3) for x in c]),
            ])
            self._set_status(f"体积 {v:.3f} mm³")

        def _do_measure_interfere(self):
            ses = self.session()
            bodies = [ses.kdoc.body_by_id(i) for k, i in self.sel.items if k == "body"]
            bodies = [b for b in bodies if b]
            if len(bodies) < 2 and ses.kdoc and len(ses.kdoc.bodies) >= 2:
                bodies = ses.kdoc.bodies[:2]
            if len(bodies) < 2:
                self._set_status("干涉需要两个实体")
                return
            vol = K.interference_volume(bodies[0].shape, bodies[1].shape) * ses.scale ** 3
            self._set_status(f"干涉体积 {vol:.4f} mm³")

        def _do_repair_stitch(self):
            ses = self.session()
            if not ses.kdoc or not ses.kdoc.bodies:
                return
            faces = []
            for b in ses.kdoc.bodies:
                faces.extend(K.explore(b.shape, "face"))
            try:
                solid = K.sew_faces(faces)
                ses.kdoc.bodies = []
                ses.kdoc.add_body(solid, name="缝合体")
                self._commit("已缝合")
            except Exception as exc:
                self._set_status(f"缝合失败: {exc}")

        def _do_repair_solidify(self):
            self._do_repair_stitch()

        def _do_repair_gaps(self):
            """Close gaps: sew all faces with a larger tolerance (order of magnitude)."""
            ses = self.session()
            if not ses.kdoc or not ses.kdoc.bodies:
                return
            faces = []
            for b in ses.kdoc.bodies:
                faces.extend(K.explore(b.shape, "face"))
            try:
                solid = K.sew_faces(faces, tol=1e-4)
                ses.kdoc.bodies = []
                ses.kdoc.add_body(solid, name="补隙体")
                self._commit("已补隙缝合")
            except Exception as exc:
                self._set_status(f"补隙失败: {exc}")

        def _do_repair_missing(self):
            self._do_repair_gaps()

        def _do_repair_extra(self):
            """Remove the smallest faces (defeaturing) to clean up extra/thin faces."""
            body = self._selected_kbody()
            if body is None:
                return
            faces = K.explore(body.shape, "face")
            if len(faces) < 2:
                self._set_status("没有可移除的多余面")
                return
            try:
                smallest = min(faces, key=lambda f: K.area(f))
                body.shape = K.fill_faces(body.shape, [smallest])
                self._commit("已移除多余小面")
            except Exception as exc:
                self._set_status(f"移除失败: {exc}")

        def _do_repair_small(self):
            self._do_repair_extra()

        def _selected_component(self):
            ses = self.session()
            for kind, sid in reversed(self.sel.items):
                if kind == "body":
                    for c in ses.kdoc.components:
                        if sid in c.body_ids:
                            return c
            return ses.kdoc.components[0] if ses.kdoc.components else None

        def _do_asm_create(self):
            ses = self.session()
            if not ses.kdoc or not ses.kdoc.bodies:
                return
            ids = [sid for k, sid in self.sel.items if k == "body"] or [ses.kdoc.bodies[0].id]
            comp = ses.kdoc.add_component(body_ids=ids)
            self._rebuild(f"已创建组件 {comp.name}")

        def _do_asm_insert(self):
            self._do_asm_create()

        def _do_asm_move(self):
            comp = self._selected_component()
            if comp is None:
                self._set_status("请先创建/选择组件")
                return
            ses = self.session()
            vec = (10 / ses.scale, 0, 0)
            n = 0
            for b in ses.kdoc.bodies_of_component(comp.id):
                if comp.anchored:
                    continue
                b.shape = K.translate(b.shape, vec)
                n += 1
            self._commit(f"移动组件 ×{n} (10mm X)")

        def _do_asm_anchor(self):
            comp = self._selected_component()
            if comp is None:
                self._set_status("请先创建/选择组件")
                return
            comp.anchored = not comp.anchored
            self._rebuild(f"组件{'已锚定' if comp.anchored else '已解除锚定'}")

        def _do_asm_mate(self):
            ses = self.session()
            faces = [sid for k, sid in self.sel.items if k == "face"]
            if len(faces) < 2:
                self._set_status("配合需要两个面")
                return
            bid1, fi1 = faces[0].split(":", 1)
            bid2, fi2 = faces[1].split(":", 1)
            b1 = ses.kdoc.body_by_id(bid1)
            b2 = ses.kdoc.body_by_id(bid2)
            if b1 is None or b2 is None or b1 is b2:
                self._set_status("配合需要不同实体上的两个面")
                return
            try:
                f1 = K.explore(b1.shape, "face")
                f2 = K.explore(b2.shape, "face")
                b1.shape = K.align_faces(b1.shape, f1[int(fi1)], f2[int(fi2)])
                self._commit("已配合（面重合）")
            except Exception as exc:
                self._set_status(f"配合失败: {exc}")

        def _do_asm_explode(self):
            ses = self.session()
            if not ses.kdoc.components:
                return
            for i, comp in enumerate(ses.kdoc.components, 1):
                vec = (0.02 * i, 0, 0)
                for b in ses.kdoc.bodies_of_component(comp.id):
                    if comp.anchored:
                        continue
                    b.shape = K.translate(b.shape, vec)
            self._commit("已爆炸组件")

        def _do_asm_light(self):
            comp = self._selected_component()
            ses = self.session()
            if comp is not None:
                comp.lightweight = not comp.lightweight
                self._rebuild(f"组件{'已轻量化' if comp.lightweight else '已恢复完整显示'}")
            else:
                # no component: toggle a global lightweight session flag
                ses.lightweight = not getattr(ses, "lightweight", False)
                for c in ses.kdoc.components:
                    c.lightweight = ses.lightweight
                self._rebuild("已切换全局轻量化")

        def _do_wb_params(self):
            from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox,
                                        QFormLayout, QLabel, QVBoxLayout)
            ses = self.session()
            if not ses.kdoc or not ses.kdoc.parametrics:
                from scdm.params import param_box
                ses.kdoc.add_parametric(param_box(), ses.scale)
                self._commit("已创建参数盒（W/H/D）")
                self._set_status("参数盒已创建；再次点击「参数」编辑尺寸")
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("参数")
            lay = QVBoxLayout(dlg)
            spins = []
            for p in ses.kdoc.parametrics:
                lay.addWidget(QLabel(p.body_name))
                f = QFormLayout()
                for k, v in p.params.items():
                    sp = QDoubleSpinBox()
                    sp.setRange(0.1, 100000.0)
                    sp.setValue(float(v))
                    f.addRow(k, sp)
                    spins.append((p, k, sp))
                lay.addLayout(f)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            lay.addWidget(bb)
            if dlg.exec_() != QDialog.Accepted:
                return
            for p, k, sp in spins:
                p.set(**{k: sp.value()})
            for p in ses.kdoc.parametrics:
                ses.kdoc.rebuild_parametric(p, ses.scale)
            self._commit("参数已更新并重建")

        def _do_wb_publish(self):
            import json
            ses = self.session()
            if ses.kdoc and ses.kdoc.parametrics:
                fn, _ = QFileDialog.getSaveFileName(
                    self, "发布参数", ses.name + "_params.json", "JSON (*.json)")
                if not fn:
                    return
                if not fn.lower().endswith(".json"):
                    fn += ".json"
                payload = {
                    "format": "scdm-params", "version": 1,
                    "params": [
                        {"body_name": p.body_name,
                         "builder": getattr(p.builder, "__name__", "box_builder"),
                         "params": dict(p.params)}
                        for p in ses.kdoc.parametrics
                    ],
                }
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                self._set_status(f"参数已发布 → {fn}")
                return
            # nothing to publish: offer to read a published file back
            fn, _ = QFileDialog.getOpenFileName(
                self, "读回参数", "", "JSON (*.json)")
            if not fn:
                return
            try:
                from scdm.params import param_box, param_cylinder
                with open(fn, encoding="utf-8") as f:
                    payload = json.load(f)
                if not self._need_kernel():
                    return
                makers = {"box_builder": param_box, "cylinder_builder": param_cylinder}
                n = 0
                for entry in payload.get("params", []):
                    mk = makers.get(entry.get("builder", "box_builder"), param_box)
                    p = mk(body_name=entry.get("body_name", "参数体"))
                    for k, v in entry.get("params", {}).items():
                        p.set(**{k: float(v)})
                    ses.kdoc.add_parametric(p, ses.scale)
                    n += 1
                self._commit(f"已读回参数并重建 ×{n}")
            except Exception as exc:
                self._set_status(f"参数读回失败: {exc}")

        def _do_add_build(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm import additive as A
            vol = A.build_volume(body.shape, 1.0, self.session().scale)
            self.session().kdoc.add_body(vol, name="构建体")
            self._commit("已创建构建体")

        def _do_add_orient(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm import additive as A
            body.shape = A.orient_min_height(body.shape)
            self._commit("已取向（最短边朝 Z）")

        def _do_add_support(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm import additive as A
            ses = self.session()
            made = 0
            for s in A.support_blocks(body.shape, scale=ses.scale):
                ses.kdoc.add_body(s, name="支撑")
                made += 1
            if made:
                self._commit(f"已生成支撑 ×{made}")
            else:
                self._set_status("底面无悬空，无需支撑")

        def _do_add_lattice(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm import additive as A
            ses = self.session()
            vol = A.build_volume(body.shape, 0.5, ses.scale)
            made = 0
            for s in A.lattice(vol, 5.0, 0.5, ses.scale):
                ses.kdoc.add_body(s, name="点阵杆")
                made += 1
            if made:
                self._commit(f"已生成点阵 ×{made}")
            else:
                self._set_status("构建体太小，无法布点阵")

        def _do_prep_enclose(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm import additive as A
            ses = self.session()
            ses.kdoc.add_body(A.build_volume(body.shape, 1.0, ses.scale),
                              name="包围体")
            self._commit("已创建包围体（1mm 余量）")

        def _do_prep_named(self):
            from PyQt5.QtWidgets import QInputDialog
            ses = self.session()
            if not self._need_kernel():
                return
            if not self.sel.items:
                self._set_status("命名选择：先选中对象，再点击「命名选择」保存")
                return
            name, ok = QInputDialog.getText(self, "命名选择", "名称：")
            if not ok or not name.strip():
                return
            name = name.strip()
            others = [n for n in getattr(ses.kdoc, "named", []) if n["name"] != name]
            others.append({"name": name,
                           "items": [[k, s] for k, s in self.sel.items]})
            ses.kdoc.named = others
            self.left.populate_tree(ses)
            self._set_status(f"已保存命名选择 [{name}]（{len(self.sel.items)} 项）")

        def _do_det_bom(self):
            from PyQt5.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout
            ses = self.session()
            if not ses.kdoc or not ses.kdoc.bodies:
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("BOM")
            lay = QVBoxLayout(dlg)
            tab = QTableWidget(len(ses.kdoc.bodies), 4)
            tab.setHorizontalHeaderLabels(["名称", "体积 mm³", "面积 mm²", "重心 mm"])
            scale = ses.scale
            for i, b in enumerate(ses.kdoc.bodies):
                vol = K.volume(b.shape) * scale ** 3
                area = K.area(b.shape) * scale ** 2
                c = K.cog(b.shape)
                row = [b.name, f"{vol:.2f}", f"{area:.2f}",
                       f"{c[0]*scale:.2f}, {c[1]*scale:.2f}, {c[2]*scale:.2f}"]
                for j, txt in enumerate(row):
                    tab.setItem(i, j, QTableWidgetItem(txt))
            lay.addWidget(tab)
            dlg.resize(520, 320)
            dlg.exec_()

        def _do_det_dim(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm import additive as A
            lo, hi = A.shape_bbox(body.shape)
            scale = self.session().scale
            self._set_status(
                f"尺寸: {(hi[0]-lo[0])*scale:.2f} × {(hi[1]-lo[1])*scale:.2f} × "
                f"{(hi[2]-lo[2])*scale:.2f} mm")

        def _do_det_view(self):
            self._do_file_image()

        def _do_det_note(self):
            from PyQt5.QtWidgets import QInputDialog
            ses = self.session()
            if not self._need_kernel():
                return
            text, ok = QInputDialog.getText(self, "注释", "注释内容：")
            if not ok or not text.strip():
                return
            pos = self.scene.focal_point() if self.scene else (0.0, 0.0, 0.0)
            ses.kdoc.notes.append({"pos": [float(v) for v in pos],
                                   "text": text.strip()})
            self._commit("已添加注释")

        def _do_tools_record(self):
            if self.recorder.enabled:
                steps = self.recorder.stop()
                fn, _ = QFileDialog.getSaveFileName(
                    self, "保存脚本", "", "SCDM 脚本 (*.json)")
                if fn:
                    if not fn.lower().endswith(".json"):
                        fn += ".json"
                    self.recorder.save(fn)
                    self._set_status(f"脚本已保存：{len(steps)} 步 → {fn}")
                else:
                    self._set_status(f"录制已停止（{len(steps)} 步未保存）")
            else:
                self.recorder.start()
                self._set_status("录制已开始：接下来执行的几何操作将被记录")

        def _do_tools_script(self):
            fn, _ = QFileDialog.getOpenFileName(
                self, "运行脚本", "", "SCDM 脚本 (*.json)")
            if not fn:
                return
            try:
                from scdm.scripting import load_script, replay
                steps = load_script(fn)
                ses = self.session()
                if not ses.kdoc:
                    ses.kdoc = KernelDoc()
                msgs = replay(steps, ses.kdoc, ses.scale)
                self._commit(f"脚本回放完成：{len(msgs)} 步")
                for m in msgs:
                    self._set_status(m)
            except Exception as exc:
                self._set_status(f"脚本回放失败: {exc}")

        def _apply_customize(self, hidden):
            """Show/hide ribbon command buttons per a list of hidden cmd ids."""
            from scdm.catalog import TABS
            hidden = set(hidden or [])
            if isinstance(hidden, str):
                hidden = {hidden}
            for tab in TABS:
                for g in tab.groups:
                    for c in g.commands:
                        b = self.ribbon.button(c.id)
                        if b:
                            b.setVisible(c.id not in hidden)

        def _do_tools_customize(self):
            from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                                         QGridLayout, QLabel, QScrollArea,
                                         QTabWidget, QWidget)
            from scdm.catalog import TABS
            hidden = self.settings.value("ribbon/hidden", []) or []
            if isinstance(hidden, str):
                hidden = [hidden]
            dlg = QDialog(self)
            dlg.setWindowTitle("自定义功能区")
            tabs = QTabWidget(dlg)
            boxes = {}
            for tab in TABS:
                page = QWidget()
                grid = QGridLayout(page)
                r = 0
                for g in tab.groups:
                    lab = QLabel(f"{g.name}（{g.en}）")
                    lab.setStyleSheet("font-weight: bold;")
                    grid.addWidget(lab, r, 0, 1, 2)
                    r += 1
                    for c in g.commands:
                        cb = QCheckBox(f"{c.name}（{c.en}）")
                        cb.setChecked(c.id not in set(hidden))
                        grid.addWidget(cb, r, 0, 1, 2)
                        r += 1
                        boxes[c.id] = cb
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(page)
                tabs.addTab(scroll, tab.name)
            lay = QVBoxLayout(dlg)
            lay.addWidget(tabs)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            lay.addWidget(bb)
            dlg.resize(420, 520)
            if dlg.exec_() != QDialog.Accepted:
                return
            hidden = sorted(cid for cid, cb in boxes.items() if not cb.isChecked())
            self.settings.setValue("ribbon/hidden", hidden)
            self._apply_customize(hidden)
            self._set_status(f"功能区已自定义（隐藏 {len(hidden)} 个命令）")

        def _do_ks_render(self):
            """Own-renderer entry on the KeyShot tab: export the current view as PNG."""
            fn, _ = QFileDialog.getSaveFileName(
                self, "导出渲染图", "", "PNG (*.png);;JPG (*.jpg)")
            if not fn:
                return
            if not fn.lower().endswith((".png", ".jpg", ".jpeg")):
                fn += ".png"
            try:
                if self.scene is None:
                    self._set_status("3D 视图不可用")
                    return
                self.scene.export_png(fn)
                self._set_status(f"已导出当前视图 → {fn}")
            except Exception as exc:
                self._set_status(f"渲染导出失败: {exc}")

        def _do_facet_convert(self):
            """STL -> session facet body (sew triangles into a shell/solid)."""
            if not self._need_kernel():
                return
            fn, _ = QFileDialog.getOpenFileName(
                self, "导入 STL", "", "STL (*.stl);;All files (*)")
            if not fn:
                return
            try:
                import numpy as np
                from scdm import facets as F
                verts, tris = F.read_stl(fn)
                if tris.shape[0] == 0:
                    self._set_status("STL 无三角形")
                    return
                solid = F.mesh_to_shell(verts, tris)
                ses = self.session()
                ses.kdoc.add_body(solid, name="导入网格")
                self._commit(f"已导入 STL：{tris.shape[0]} 三角形")
            except Exception as exc:
                self._set_status(f"STL 导入失败: {exc}")

        def _do_facet_reverse(self):
            body = self._selected_kbody()
            if body is None:
                return
            try:
                from scdm import facets as F
                import numpy as np
                faces = K.explore(body.shape, "face")
                if not faces:
                    return
                # rebuild with reversed normals: copy + flip every face orientation
                body.shape = K.reverse_shape(body.shape)
                self._commit("已反转法向")
            except Exception as exc:
                self._set_status(f"反转法向失败: {exc}")

        def _facet_mesh(self, body, deflection_mm: float = 0.02):
            """Tessellate a body into a welded (verts, tris) triangle soup."""
            import numpy as np
            from scdm import facets as F
            from scdm.kernel import tessellate_faces
            faces = tessellate_faces(
                body.shape, deflection=max(1e-6, deflection_mm / self.session().scale))
            vs, ts, off = [], [], 0
            for fd in faces:
                pts = np.asarray(fd["vertices"], dtype=np.float64)
                tris = np.asarray(fd["triangles"], dtype=np.int64)
                if len(pts) == 0 or not len(tris):
                    continue
                vs.append(pts)
                ts.append(tris + off)
                off += len(pts)
            if not vs:
                return None, None
            return F.weld(np.vstack(vs), np.vstack(ts), tol=1e-6)

        def _do_facet_smooth(self):
            self._facet_op("smooth")

        def _do_facet_reduce(self):
            self._facet_op("reduce")

        def _do_facet_fill(self):
            self._facet_op("fill")

        def _facet_op(self, op: str):
            from scdm import facets as F
            body = self._selected_kbody()
            if body is None:
                return
            verts, tris = self._facet_mesh(body)
            if verts is None:
                self._set_status("分面：所选实体没有可用的网格")
                return
            ses = self.session()
            try:
                if op == "smooth":
                    verts = F.laplacian_smooth(verts, tris, iters=3, factor=0.5)
                    msg = "已光滑（Laplacian ×3）"
                elif op == "reduce":
                    cell = 2.0 / ses.scale
                    verts, tris = F.reduce_grid(verts, tris, cell)
                    msg = f"已简化至 {len(tris)} 三角形"
                else:
                    tris, n = F.fill_holes(verts, tris)
                    if not n:
                        self._set_status("分面填孔：没有开放边界需要填补")
                        return
                    msg = f"已填补 {n} 个孔"
                solid = F.mesh_to_shell(verts, tris)
                body.shape = solid
                self._commit(msg)
            except Exception as exc:
                self._set_status(f"分面操作失败: {exc}")

        def _do_sketch_line(self):
            self._sketch_add("line")

        def _do_sketch_rect(self):
            self._sketch_add("rect")

        def _do_sketch_circle(self):
            self._sketch_add("circle")

        def _do_sketch_point(self):
            self._sketch_add("point")

        def _do_sketch_grid(self):
            ses = self.session()
            self._set_sketch_grid(not ses.show_grid)
            self._set_status(f"草图网格已{'开启' if ses.show_grid else '关闭'}")

        def _do_create_project(self):
            """Project selected face boundary edges onto the active sketch plane."""
            ses = self.session()
            if not self._need_kernel():
                return
            if not ses.kdoc.sketches:
                self._begin_sketch()
            sk = ses.kdoc.sketches[-1]
            plane = sk.plane

            def w2uv(p):
                x, y, z = p[0], p[1], p[2]
                if plane == "zx":
                    return (x, z)
                if plane == "yz":
                    return (y, z)
                return (x, y)

            faces = []
            for kind, sid in self.sel.items:
                if kind == "face" and ":" in sid:
                    bid, fi = sid.split(":", 1)
                    b = ses.kdoc.body_by_id(bid)
                    if b is None:
                        continue
                    bfs = K.explore(b.shape, "face")
                    if int(fi) < len(bfs):
                        faces.append(bfs[int(fi)])
            if not faces:
                self._set_status("投影：请先选择一个面（边拾取在 G3-02 提供）")
                return
            n = 0
            for face in faces:
                for e in K.explore(face, "edge"):
                    pts3 = K.edge_polyline(e, deflection=0.05 / ses.scale)
                    if len(pts3) >= 2:
                        sk.curves.append(("poly", [w2uv(p) for p in pts3]))
                        n += 1
            self.left.populate_tree(ses)
            self._set_status(f"已投影 {n} 条边到草图 [{sk.name}]（平面 {plane.upper()}）")

        def _fillet_or_chamfer(self, fillet=True):
            body = self._selected_kbody()
            if body is None:
                return
            r = 1.0 / self.session().scale
            try:
                if fillet:
                    body.shape = K.fillet_edges(body.shape, r)
                    self._record("create.blend", radius=1.0)
                    self._commit("已倒圆 1mm")
                else:
                    body.shape = K.chamfer_edges(body.shape, r)
                    self._record("create.chamfer", distance=1.0)
                    self._commit("已倒角 1mm")
            except Exception as exc:
                self._set_status(str(exc))

        def _need_kernel(self) -> bool:
            if not K.available():
                self._set_status("需要 pythonocc-core：conda install -c conda-forge pythonocc-core")
                return False
            ses = self.session()
            if ses.kdoc is None:
                ses.kdoc = KernelDoc()
                ses.history.push(ses.kdoc.snapshot())
            return True

        def _rebuild(self, msg: str = ""):
            ses = self.session()
            if self.scene:
                self.scene.build(ses)
            self.left.populate_tree(ses)
            self._refresh_title()
            if msg:
                self._set_status(msg)

        def _commit(self, msg: str):
            ses = self.session()
            ses.dirty = True
            ses.history.push(ses.kdoc.snapshot())
            self._rebuild(msg)

        def _selected_kbody(self):
            if not self._need_kernel():
                return None
            ses = self.session()
            for kind, sid in reversed(self.sel.items):
                if kind == "body":
                    b = ses.kdoc.body_by_id(sid)
                    if b:
                        return b
            # face -> body
            for kind, sid in self.sel.items:
                if kind == "face" and ":" in sid:
                    b = ses.kdoc.body_by_id(sid.split(":")[0])
                    if b:
                        return b
            if ses.kdoc.bodies:
                return ses.kdoc.bodies[0]
            self._set_status("请先选择或创建一个实体")
            return None

        def _clipboard_copy(self, cut: bool):
            body = self._selected_kbody()
            if body is None:
                return
            ses = self.session()
            ses.clipboard = K.dumps_brep(body.shape)
            if cut:
                ses.kdoc.remove(body.id)
                self._commit("已剪切")
            else:
                self._set_status("已复制")

        def _set_sketch_grid(self, on: bool):
            ses = self.session()
            ses.show_grid = on
            if self.scene:
                self.scene.update_grid(ses)

        def _begin_sketch(self):
            if not self._need_kernel():
                return
            ses = self.session()
            ses.kdoc.add_sketch("xy")
            self._set_sketch_grid(True)
            self.left.populate_tree(ses)
            self._set_status("草图模式：直线/矩形/圆；完成后选草图再拉动")

        def _sketch_add(self, kind: str):
            if not self._need_kernel():
                return
            ses = self.session()
            if not ses.kdoc.sketches:
                self._begin_sketch()
            sk = ses.kdoc.sketches[-1]
            s = 10 / ses.scale
            if kind == "rect":
                sk.curves.append(("rect", (0, 0, 0), (s, s, 0)))
                self._set_status("已在 XY 添加 10mm 矩形")
            elif kind == "circle":
                sk.curves.append(("circle", (s / 2, s / 2, 0), s / 2))
                self._set_status("已添加 Ø10mm 圆")
            elif kind == "line":
                sk.curves.append(("line", (0, 0, 0), (s, 0, 0)))
                self._set_status("已添加直线")
            else:
                sk.curves.append(("point", (0, 0, 0)))
                self._set_status("已添加点")
            self.left.populate_tree(ses)

        def _toggle_section(self):
            if not self.scene:
                return
            ses = self.session()
            ses.show_planes = True
            self.scene.apply_visibility(ses)
            self._set_status("截面：已显示基准面；拉动仍在三维实体上进行")

        def _place_at(self, kind: str, world):
            if not self._need_kernel():
                return
            ses = self.session()
            if world is None:
                world = (0.0, 0.0, 0.0)
            if self.sel.snap_grid:
                world = tuple(round(v * ses.scale) / ses.scale for v in world)
            r = 5 / ses.scale
            h = 10 / ses.scale
            if kind == "cyl":
                sh = K.make_cylinder(r, h, origin=world)
                ses.kdoc.add_body(sh, name="圆柱")
                self._record("insert.cyl", r=5, h=10)
                self._commit("已插入圆柱")
                self.on_command("tool.pull")
            else:
                sh = K.make_sphere(r, origin=world)
                ses.kdoc.add_body(sh, name="球")
                self._record("insert.sphere", r=5)
                self._commit("已插入球")

        def _opts_for(self, cmd: str) -> dict:
            """Read the active option page checkboxes/spins into a plain dict."""
            def chk(idx):
                try:
                    return self.left.is_checked(cmd, idx)
                except Exception:
                    return False

            def spin(idx):
                try:
                    return self.left.spin_value(cmd, idx)
                except Exception:
                    return None

            opts = {}
            if cmd == "tool.pull":
                opts["symmetric"] = chk(0)
                opts["copy"] = chk(1)
                opts["to_face"] = chk(2)
                d = spin(0)
                if d:
                    opts["distance"] = float(d)
            elif cmd == "tool.move":
                opts["copy"] = chk(0)
                opts["to_point"] = chk(1)
                opts["to_face"] = chk(2)
                d = spin(0)
                if d:
                    opts["distance"] = float(d)
                # default move axis = X; replaced with a picked face normal when available
                opts["axis"] = (1.0, 0.0, 0.0)
            if cmd == "tool.combine":
                opts["mode"] = self.left.combine_mode()
            return opts

        def _pull_to_face_target(self, exclude_id):
            """Normal/centre of a previously selected face (pull 'to face' target)."""
            if not self.scene:
                return None
            for kind, sid in self.sel.items:
                if kind != "face" or sid == exclude_id:
                    continue
                act = self.scene._face_actors.get(sid)
                if act is not None and getattr(act, "_face_i", None) is not None:
                    return {"normal": tuple(act._normal), "center": tuple(act._center)}
            return None

        def _apply_pull(self, actor):
            if actor is None or not self._need_kernel():
                return
            body_id = getattr(actor, "_body_id", None)
            face_i = getattr(actor, "_face_i", None)
            node = f"{body_id}:{face_i}" if body_id is not None and face_i is not None else None
            from scdm.tools.direct import get_tool, ToolError
            opts = self._opts_for("tool.pull")
            ctx = {"body_id": body_id, "face_i": face_i}
            if opts.get("to_face"):
                ctx["to_face_target"] = self._pull_to_face_target(node)
                if ctx["to_face_target"] is None:
                    self._set_status("到面：先在选择工具里选中目标面，再拉动")
                    return
            try:
                msg = get_tool("tool.pull").apply(self.session(), ctx, opts)
                self._record("tool.pull", face_i=int(face_i or 0),
                             distance=float(opts.get("distance", 5.0)),
                             symmetric=bool(opts.get("symmetric")),
                             copy=bool(opts.get("copy")),
                             to_face=bool(opts.get("to_face")))
                self._commit(msg)
            except ToolError as exc:
                self._set_status(str(exc))
            except Exception as exc:
                self._set_status(f"拉动失败: {exc}")

        def _apply_move(self, actor=None, world=None):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm.tools.direct import get_tool, ToolError
            opts = self._opts_for("tool.move")
            # Use the picked face normal as the move axis when a face is selected.
            if self.sel.items and self.sel.items[-1][0] == "face":
                sid = self.sel.items[-1][1]
                if ":" in sid:
                    bid, fi = sid.split(":", 1)
                    b = self.session().kdoc.body_by_id(bid)
                    if b is not None:
                        faces = K.explore(b.shape, "face")
                        if int(fi) < len(faces):
                            n, _c = K.face_normal_center(faces[int(fi)])
                            opts["axis"] = n
            ctx = {"body_id": body.id}
            if opts.get("to_point") and world is not None:
                ctx["pick_point"] = tuple(float(v) for v in world)
            elif opts.get("to_face") and actor is not None \
                    and getattr(actor, "_face_i", None) is not None \
                    and getattr(actor, "_body_id", None) != body.id:
                ctx["pick_face"] = {"normal": tuple(actor._normal),
                                    "center": tuple(actor._center)}
            try:
                msg = get_tool("tool.move").apply(self.session(), ctx, opts)
                self._record("tool.move",
                             distance=float(opts.get("distance", 10.0)),
                             axis=list(opts.get("axis", (1.0, 0.0, 0.0))),
                             copy=bool(opts.get("copy", False)),
                             to_point=bool(opts.get("to_point")),
                             to_face=bool(opts.get("to_face")))
                self._commit(msg)
            except ToolError as exc:
                self._set_status(str(exc))
            except Exception as exc:
                self._set_status(f"移动失败: {exc}")

        def _apply_fill(self, actor):
            if actor is None or not self._need_kernel():
                return
            from scdm.tools.direct import get_tool, ToolError
            try:
                msg = get_tool("tool.fill").apply(
                    self.session(),
                    {"body_id": getattr(actor, "_body_id", None),
                     "face_i": getattr(actor, "_face_i", None)},
                    self._opts_for("tool.fill"),
                )
                self._record("tool.fill", face_i=int(getattr(actor, "_face_i", 0) or 0))
                self._commit(msg)
            except ToolError as exc:
                self._set_status(str(exc))
            except Exception as exc:
                self._set_status(f"填充失败: {exc}")

        def _apply_combine(self):
            ses = self.session()
            ids = [sid for k, sid in self.sel.items if k == "body"]
            from scdm.tools.direct import get_tool, ToolError
            try:
                msg = get_tool("tool.combine").apply(
                    ses,
                    {"sel_ids": ids},
                    self._opts_for("tool.combine"),
                )
                self._record("tool.combine", mode=self.left.combine_mode())
                self._commit(msg)
            except ToolError as exc:
                self._set_status(str(exc))
            except Exception as exc:
                self._set_status(f"合并失败: {exc}")

        def _apply_split(self):
            body = self._selected_kbody()
            if body is None:
                return
            from scdm.tools.direct import get_tool, ToolError
            ctx = {"body_id": body.id}
            # Use the picked face's plane as the splitter when available.
            for kind, sid in reversed(self.sel.items):
                if kind == "face" and ":" in sid:
                    bid, fi = sid.split(":", 1)
                    b = self.session().kdoc.body_by_id(bid)
                    if b is not None:
                        faces = K.explore(b.shape, "face")
                        if int(fi) < len(faces):
                            n, cc = K.face_normal_center(faces[int(fi)])
                            ctx["origin"] = cc
                            ctx["normal"] = n
                    break
            try:
                msg = get_tool("tool.split_body").apply(
                    self.session(), ctx, self._opts_for("tool.split_body"))
                self._record("tool.split_body")
                self._commit(msg)
            except ToolError as exc:
                self._set_status(str(exc))
            except Exception as exc:
                self._set_status(f"分割失败: {exc}")

        def _set_drag_hooks(self, tool_id: str):
            """Enable drag preview only for Pull/Move; other tools keep plain clicks."""
            if self.scene is None:
                return
            if tool_id in ("tool.pull", "tool.move"):
                self.scene.style.drag_start_cb = self._on_drag_start
                self.scene.style.drag_move_cb = self._on_drag_move
                self.scene.style.drag_end_cb = self._on_drag_end
            else:
                self.scene.style.drag_start_cb = None
                self.scene.style.drag_move_cb = None
                self.scene.style.drag_end_cb = None
            self.scene.clear_preview()

        def _on_drag_start(self):
            """Pick the face at drag start and stash the entry snapshot."""
            self._drag = None
            if not self.scene:
                return
            tool = self.tools.active
            if tool not in ("tool.pull", "tool.move"):
                return
            actor, _world = self.scene.pick_actor()
            if actor is None:
                return
            body_id = getattr(actor, "_body_id", None)
            face_i = getattr(actor, "_face_i", None)
            ses = self.session()
            body = ses.kdoc.body_by_id(body_id) if body_id else None
            if body is None or face_i is None:
                return
            faces = K.explore(body.shape, "face")
            if face_i >= len(faces):
                return
            n, _c = K.face_normal_center(faces[face_i])
            self._drag = {"tool": tool, "body": body, "face_i": face_i,
                          "orig": body.shape, "normal": n, "dist": 0.0}

        def _world_per_px(self):
            if not self.scene:
                return 1e-4
            cam = self.scene.renderer.GetActiveCamera()
            height = max(1, self.vtk_widget.height())
            return 2.0 * cam.GetParallelScale() / height

        def _on_drag_move(self, dx, dy):
            d = self._drag
            if d is None or not self.scene:
                return
            d["dist"] = -dy * self._world_per_px()
            faces = K.explore(d["orig"], "face")
            if d["tool"] == "tool.pull":
                preview = K.pull_face(d["orig"], faces[d["face_i"]], d["dist"])
            else:
                vec = tuple(d["normal"][k] * d["dist"] for k in range(3))
                preview = K.translate(d["orig"], vec)
            self.scene.show_preview(preview)

        def _on_drag_end(self, dx, dy):
            d = self._drag
            self._drag = None
            if self.scene:
                self.scene.clear_preview()
            # a tiny movement counts as a plain click (fixed 5mm behaviour)
            if d is None or max(abs(dx), abs(dy)) < 4:
                self._on_vtk_click()
                return
            if abs(d["dist"]) < 1e-7:
                return
            body = d["body"]
            mm = abs(d["dist"]) * self.session().scale
            if d["tool"] == "tool.pull":
                faces = K.explore(d["orig"], "face")
                body.shape = K.pull_face(d["orig"], faces[d["face_i"]], d["dist"])
                self._commit(f"拉动 {mm:.1f}mm")
            else:
                vec = tuple(d["normal"][k] * d["dist"] for k in range(3))
                body.shape = K.translate(d["orig"], vec)
                self._commit(f"移动 {mm:.1f}mm")

        def _apply_replace(self, actor):
            """SpaceClaim Replace: first click picks a source face, second the target face."""
            if actor is None or not self._need_kernel():
                return
            bid = getattr(actor, "_body_id", None)
            fi = getattr(actor, "_face_i", None)
            if bid is None or fi is None:
                return
            if getattr(self, "_replace_src", None) is None:
                self._replace_src = (bid, fi)
                self._set_status("替换：已选源面，请再选目标面")
                return
            src_bid, src_fi = self._replace_src
            self._replace_src = None
            if (src_bid, src_fi) == (bid, fi):
                self._set_status("替换：目标面与源面相同，请重选")
                return
            ses = self.session()
            a = ses.kdoc.body_by_id(src_bid)
            b = ses.kdoc.body_by_id(bid)
            if a is None or b is None:
                self._set_status("替换失败：实体不存在")
                return
            faces_a = K.explore(a.shape, "face")
            faces_b = K.explore(b.shape, "face")
            if src_fi >= len(faces_a) or fi >= len(faces_b):
                self._set_status("替换失败：面索引越界")
                return
            try:
                a.shape = K.replace_face(a.shape, faces_a[src_fi], faces_b[fi])
                self._commit("已替换面")
            except Exception as exc:
                self._set_status(f"替换失败: {exc}")

        def _pull_sketch(self):
            ses = self.session()
            if not ses.kdoc.sketches:
                self._set_status("没有草图")
                return
            sk = ses.kdoc.sketches[-1]
            h = 10 / ses.scale
            made = 0
            try:
                from scdm import sketch as S
                solid = S.extrude_sketch(sk.curves, h, sk.plane)
                ses.kdoc.add_body(solid, name="拉伸")
                made += 1
            except (ValueError, Exception) as exc:
                # fall back to circles -> cylinder
                for c in sk.curves:
                    if c[0] == "circle":
                        center, r = c[1], c[2]
                        ses.kdoc.add_body(K.make_cylinder(r, h, origin=center), name="拉伸圆")
                        made += 1
                if not made:
                    self._set_status(f"草图无闭环：{exc}")
                    return
            self._commit(f"草图拉动 ×{made}")

        def _apply_sketch_constraint(self, kind: str):
            """Resolve a constraint against the active sketch using scdm.sketch."""
            ses = self.session()
            if not ses.kdoc.sketches:
                self._begin_sketch()
            sk = ses.kdoc.sketches[-1]
            try:
                from scdm import sketch as S
                pts, segments = self._sketch_points(sk)
                if not pts:
                    self._set_status("草图无曲线可约束")
                    return
                segs = segments or []
                if kind == "dim":
                    d = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) if len(pts) > 1 else 10.0
                    consts = [(S.DIST, 0, 1, d)]
                elif kind == "h":
                    consts = [(S.HORIZONTAL, 0, 1, None)]
                elif kind == "v":
                    consts = [(S.VERTICAL, 0, 1, None)]
                elif kind == "coin":
                    consts = [(S.COINCIDENT, 0, 1, None)]
                elif kind == "perp":
                    if len(segs) < 2:
                        self._set_status("垂直约束需要两条线段")
                        return
                    consts = [(S.PERPENDICULAR, 0, 1, None)]
                elif kind == "eq":
                    if len(segs) < 2:
                        self._set_status("相等约束需要两条线段")
                        return
                    consts = [(S.EQUAL, 0, 1, None)]
                elif kind == "par":
                    if len(segs) < 2:
                        self._set_status("平行约束需要两条线段")
                        return
                    consts = [(S.PARALLEL, 0, 1, None)]
                elif kind == "mid":
                    if not segs or len(pts) < 3:
                        self._set_status("中点约束需要线段和一个点")
                        return
                    consts = [(S.MIDPOINT, len(pts) - 1, 0, None)]
                elif kind == "tan":
                    if not segs:
                        self._set_status("相切约束需要线段与圆")
                        return
                    # circle centre = last point, radius from the sketch's circle curve
                    r = 5 / ses.scale
                    for c in sk.curves:
                        if c[0] == "circle":
                            r = c[2]
                            break
                    consts = [(S.TANGENT, 0, len(pts) - 1, r)]
                elif kind == "fix":
                    if not pts:
                        return
                    x, y = pts[0][0], pts[0][1]
                    consts = [(S.FIXED, 0, x, y)]
                else:
                    self._set_status(f"约束 {kind} 预留")
                    return
                S.solve_constraints(pts, consts, segments=segs, iters=40)
                self._write_sketch_points(sk, pts)
                self.left.populate_tree(ses)
                self._set_status(f"已解算约束 [{kind}]")
                self._rebuild("约束已应用")
            except Exception as exc:
                self._set_status(f"约束失败: {exc}")

        def _do_con_dim(self):
            self._apply_sketch_constraint("dim")

        def _do_con_hv(self):
            self._apply_sketch_constraint("h")

        def _do_con_coin(self):
            self._apply_sketch_constraint("coin")

        def _do_con_perp(self):
            self._apply_sketch_constraint("perp")

        def _do_con_eq(self):
            self._apply_sketch_constraint("eq")

        def _do_con_par(self):
            self._apply_sketch_constraint("par")

        def _do_con_tan(self):
            self._apply_sketch_constraint("tan")

        def _do_con_mid(self):
            self._apply_sketch_constraint("mid")

        def _do_con_fix(self):
            self._apply_sketch_constraint("fix")

        def _sketch_points(self, sk):
            pts = []
            segments = []
            for c in sk.curves:
                if c[0] in ("line", "rect"):
                    base = len(pts)
                    for p in (c[1], c[2]):
                        pts.append([float(p[0]), float(p[1]), float(p[2])])
                    segments.append((base, base + 1))
                elif c[0] == "circle":
                    pts.append([float(c[1][0]), float(c[1][1]), float(c[1][2])])
                    pts.append([float(c[1][0] + c[2]), float(c[1][1]), float(c[1][2])])
            return pts, segments

        def _write_sketch_points(self, sk, pts):
            idx = 0
            for c in sk.curves:
                if c[0] in ("line", "rect"):
                    p1 = tuple(pts[idx]); p2 = tuple(pts[idx + 1]) if idx + 1 < len(pts) else c[2]
                    sk.curves[sk.curves.index(c)] = (c[0], p1, p2)
                    idx += 2
                elif c[0] == "circle":
                    sk.curves[sk.curves.index(c)] = (c[0], tuple(pts[idx])[:2] + (c[1][2],), c[2])
                    idx += 2

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

        def _do_gfx_silhouette(self):
            ses = self.session()
            ses.show_silhouette = not ses.show_silhouette
            self.ribbon.set_checked("gfx.silhouette", ses.show_silhouette)
            if self.scene:
                self.scene.apply_visibility(ses)
            self._set_status(f"轮廓边已{'开启' if ses.show_silhouette else '关闭'}")

        def _do_gfx_section(self):
            ses = self.session()
            order = [None, "x", "y", "z"]
            cur = getattr(ses, "section_axis", None)
            nxt = order[(order.index(cur) + 1) % len(order)]
            ses.section_axis = nxt
            self.ribbon.set_checked("gfx.section", nxt is not None)
            if self.scene:
                self.scene.set_section(nxt)
            label = {"x": "X 向", "y": "Y 向", "z": "Z 向", None: "关"}[nxt]
            self._set_status(f"剖面显示：{label}（再次点击切换方向/关闭）")

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
            if tool == "insert.cyl":
                self._place_at("cyl", world)
                return
            if tool == "insert.sphere":
                self._place_at("sphere", world)
                return
            if tool == "tool.pull":
                if actor is not None:
                    self._apply_pull(actor)
                else:
                    self._pull_sketch()
                return
            if tool == "tool.move":
                self._apply_move(actor, world)
                return
            if tool == "tool.fill":
                self._apply_fill(actor)
                return
            if tool == "tool.combine":
                if actor is not None:
                    node = getattr(actor, "_node_id", None)
                    self._select_body_from_face(node, add=True)
                self._apply_combine()
                return
            if tool in ("tool.split_body", "tool.split_faces"):
                self._apply_split()
                return
            if tool == "tool.replace":
                self._apply_replace(actor)
                return
            if tool != "tool.select":
                cmd = command_by_id(tool)
                wave = cmd.wave if cmd else "M2"
                name = cmd.name if cmd else tool
                self._set_status(f"{wave} 未实现：{name}")
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

        def _selected_body_ids(self):
            ids = []
            for kind, sid in self.sel.items:
                if kind == "body":
                    bid = sid
                elif kind == "face" and ":" in sid:
                    bid = sid.split(":", 1)[0]
                else:
                    bid = None
                if bid and bid not in ids:
                    ids.append(bid)
            return ids

        def _hide_bodies(self, bids, isolate=False):
            ses = self.session()
            if not ses.kdoc:
                return
            for b in ses.kdoc.bodies:
                if isolate:
                    b.visible = b.id in bids
                elif b.id in bids:
                    b.visible = False
            self._rebuild("已仅显示所选" if isolate else "已隐藏所选")

        def _recolor_bodies(self, bids):
            from PyQt5.QtWidgets import QColorDialog
            ses = self.session()
            if not ses.kdoc:
                return
            col = QColorDialog.getColor(parent=self, title="实体颜色")
            if not col.isValid():
                return
            rgb = (col.redF(), col.greenF(), col.blueF())
            n = 0
            for b in ses.kdoc.bodies:
                if b.id in bids:
                    b.color = rgb
                    n += 1
            if n:
                self._commit(f"已改色 ×{n}")

        def _on_vtk_right(self):
            bids = self._selected_body_ids()
            if not bids:
                self._set_status("右键：先选择对象（隐藏 / 仅显示 / 缩放到 / 改色）")
                return
            menu = QMenu(self)
            menu.addAction("隐藏", lambda: self._hide_bodies(bids))
            menu.addAction("仅显示", lambda: self._hide_bodies(bids, isolate=True))
            menu.addAction("缩放到", lambda: self.scene.fit_to_bodies(bids))
            menu.addAction("改色…", lambda: self._recolor_bodies(bids))
            x, y = 0, 0
            try:
                iren = self.vtk_widget.GetRenderWindow().GetInteractor()
                x, y = iren.GetEventPosition()
                y = max(0, self.vtk_widget.height() - y)
            except Exception:
                pass
            menu.exec_(self.vtk_widget.mapToGlobal(QPoint(x, y)))

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
            elif key in ("control_z", "z") and obj.GetControlKey():
                self._do_edit_undo()
            elif key in ("control_y", "y") and obj.GetControlKey():
                self._do_edit_redo()

        def _body_face_nodes(self, body_id: str):
            if self.scene is None:
                return []
            keyed = [k for k, a in self.scene._face_actors.items()
                     if getattr(a, "_body_id", None) == body_id]
            if keyed:
                return keyed
            ses = self.session()
            doc = ses.design_doc
            if doc is None:
                return list(self.scene._face_actors.keys())
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

        def _select_face_node(self, node, add: bool):
            key = str(node)
            if add:
                self.sel.toggle("face", key)
            else:
                self.sel.set_one("face", key)
            face_keys = [i for k, i in self.sel.items if k == "face"]
            if self.scene:
                acts = []
                for fk in face_keys:
                    acts.append(self.scene._face_actors.get(fk))
                    try:
                        acts.append(self.scene._face_actors.get(int(fk)))
                    except Exception:
                        pass
                self.scene.highlight_actors(acts)
            if self.vp:
                self.vp.show_mini(True)
            self.left.set_selection_list([f"面 {i}" for i in face_keys])
            actor = self.scene._face_actors.get(node) if self.scene else None
            rows = [("名称", f"面 {key}")]
            if actor is not None:
                rows.append(("体", getattr(actor, "_body_id", "")))
                if getattr(actor, "_normal", None):
                    rows.append(("法向", [round(x, 4) for x in actor._normal]))
            self.left.set_props(rows)
            self._set_status(f"已选择面 {key}")

        def _select_body_from_face(self, node, add: bool):
            if self.scene and node is not None:
                act = self.scene._face_actors.get(node)
                if act is not None and getattr(act, "_body_id", None):
                    self._select_body(act._body_id, add)
                    return
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
            name = body_id
            rows = [("Id", body_id)]
            if ses.kdoc is not None:
                kb = ses.kdoc.body_by_id(body_id)
                if kb:
                    name = kb.name
                    rows = [("名称", name), ("Id", body_id)]
                    try:
                        s = ses.scale
                        rows.append(("体积 mm³", round(K.volume(kb.shape) * s ** 3, 4)))
                    except Exception:
                        pass
            else:
                doc = ses.design_doc
                body = doc.body_by_doc_id(body_id) if doc else None
                name = ses.body_caption(body) if body else body_id
                rows = [("名称", name), ("Id", body_id)]
                if body:
                    rows += [("面数", len(body.faces)), ("边数", len(body.edges))]
            self.left.set_selection_list([name])
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

        def _restore_named(self, name):
            ses = self.session()
            ns = next((n for n in getattr(ses.kdoc, "named", [])
                       if n["name"] == name), None)
            if ns is None:
                return
            self.sel.clear()
            for kind, sid in ns["items"]:
                self.sel.items.append((kind, sid))
            if self.scene:
                nodes = []
                for kind, sid in ns["items"]:
                    if kind == "face":
                        nodes.append(sid)
                    elif kind == "body":
                        nodes.extend(self._body_face_nodes(sid))
                self.scene.highlight_nodes(
                    [n for n in nodes if n in self.scene._face_actors])
            self.left.set_selection_list([f"{k}:{s}" for k, s in ns["items"]])
            self._set_status(f"命名选择 [{name}]：{len(ns['items'])} 项")

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
            elif kind == "named":
                self._restore_named(sid)
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
            # clean exit: drop autosave files so the next start won't offer recovery
            for ses in self.sessions:
                try:
                    os.remove(self._autosave_path(ses))
                except Exception:
                    pass
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

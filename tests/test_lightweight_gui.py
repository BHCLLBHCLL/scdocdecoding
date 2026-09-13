"""Lightweight-mode GUI regressions (P0-3 follow-up).

The GUI must degrade into an explicit lightweight mode when pythonocc-core
is missing: kernel-only ribbon buttons disabled, a startup status hint, and
an honest "lightweight" reason on tool activation — NOT the misleading
"M2 未实现" (the M2 tools are implemented; that env just lacks OCC).
"""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

QT = __import__("importlib").util.find_spec("PyQt5") is not None


@unittest.skipUnless(QT, "PyQt5 not installed")
class LightweightModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        import scdm_gui
        cls.gui = scdm_gui
        from scdm.catalog import M2_LIVE, M3_LIVE, M4_LIVE, M5_LIVE
        cls.kernel_tool_ids = M2_LIVE | M3_LIVE | M4_LIVE | M5_LIVE

    def _status(self, v):
        return v._prompt.text()

    def _viewer_without_kernel(self, act=None):
        """Viewer (and optional follow-up action) with the kernel patched
        out — scdm.kernel.available is the single capability switch."""
        import scdm.kernel as K
        real = K.available
        K.available = lambda: False
        try:
            v = self.gui.ScdmViewer(path=None)
            if act is not None:
                act(v)
            return v
        finally:
            K.available = real

    def test_kernel_tools_disabled_and_hinted(self):
        v = self._viewer_without_kernel()
        pulled = [self.kernel_tool_ids & {"tool.pull"}]
        b = v.ribbon.button("tool.pull")
        self.assertIsNotNone(b)
        self.assertFalse(b.isEnabled(), "kernel tool must be greyed out")
        self.assertIn("轻量模式", self._status(v))

    def test_activation_reason_is_lightweight_not_m2(self):
        def act(v):
            v.on_command("tool.pull")
        v = self._viewer_without_kernel(act)
        msg = self._status(v)
        self.assertIn("轻量模式", msg)
        self.assertIn("run_scdm.bat", msg)
        self.assertNotIn("未实现", msg)
        self.assertEqual(v.tools.active, "tool.pull")

    def test_kernel_present_keeps_tools_enabled(self):
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        v = self.gui.ScdmViewer(path=None)
        b = v.ribbon.button("tool.pull")
        self.assertIsNotNone(b)
        self.assertTrue(b.isEnabled())
        v.on_command("tool.pull")
        self.assertEqual(v.tools.active, "tool.pull")
        self.assertNotIn("未实现", self._status(v))

    def test_import_report_reaches_the_status_bar(self):
        """P47: opening a partly-rebuilt file must say so, not look empty."""
        from types import SimpleNamespace

        v = self.gui.ScdmViewer(path=None)
        kdoc = SimpleNamespace(
            import_warnings=["1/25 个部件无法重建为 B-rep（未生成网格兜底）"],
            import_report={"parts": 25, "failed_parts": ["0:23"],
                           "unbuilt_faces": 2, "dropped_faces": 4,
                           "mesh_bodies": []})
        v._report_import(SimpleNamespace(kdoc=kdoc, import_error=None))
        msg = self._status(v)
        self.assertIn("1/25 个部件未重建", msg)
        self.assertIn("2 个面未重建", msg)
        self.assertIn("0:23", msg)

    def test_import_report_is_silent_when_clean(self):
        from types import SimpleNamespace

        v = self.gui.ScdmViewer(path=None)
        v._set_status("初始")
        clean = SimpleNamespace(import_warnings=[], import_report={})
        v._report_import(SimpleNamespace(kdoc=clean, import_error=None))
        self.assertEqual(self._status(v), "初始")
        # a hard failure still reports
        v._report_import(SimpleNamespace(kdoc=clean,
                                         import_error="KernelError: x"))
        self.assertIn("几何未导入", self._status(v))

    def test_p48_sheet_canvas_drags_dimension_handles(self):
        """P48: the sheet preview drags Dimension.offset, not the value."""
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from scdm import drawing as D
        from scdm import kernel as K
        from scdm.gui.sheet import SheetCanvas

        box = K.make_box(0.02, 0.02, 0.02)
        view = D.projected_view(box, (0.0, 0.0, -1.0), label='前视')
        dims = D.dimensions_for([view])
        canvas = SheetCanvas([view], dims)
        canvas.resize(600, 400)
        assert canvas.pick(-999, -999) == -1

        i = 0
        hp = canvas.handle_px(i)
        assert canvas.pick(hp.x(), hp.y()) == i, 'handle must be pickable'

        value = dims[i].value_mm
        before = dims[i].offset
        canvas.drag_handle(i, hp.x(), hp.y() - 25)      # 25 px up
        assert dims[i].offset != before
        assert dims[i].value_mm == value, 'dragging must not re-measure'
        # the handle follows the line it was dragged to
        moved = canvas.handle_px(i)
        assert abs(moved.y() - (hp.y() - 25)) < 1.5

    def test_p48_det_dim_opens_the_sheet(self):
        """det.dim gets a real handler (the sheet dialog), not a status stub."""
        from scdm import kernel as K
        from scdm.import_sab import import_scdoc_bundle  # noqa: F401
        from scdm.gui import sheet as S

        v = self.gui.ScdmViewer(path=None)
        assert hasattr(v, '_do_det_dim')
        # no selection -> it explains itself instead of raising
        v._do_det_dim()
        msg = self._status(v)
        assert '尺寸' in msg or '请先选择' in msg, msg
        assert S.SheetCanvas is not None and S.SheetDialog is not None

    def test_p145_official_parts_toggle_and_isolate(self):
        """R25/P145: the viewer binds part groups to visibility + isolate."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        v = self.gui.ScdmViewer(path=None)
        kdoc = KernelDoc()
        a = kdoc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        b = kdoc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
        kdoc.import_report = {"hierarchy": [{"name": "P1", "bodies": [a.id]},
                                            {"name": "P2", "bodies": [b.id]}],
                              "ref_faces": 3, "unbuilt_faces": 1}
        v.session().kdoc = kdoc

        assert [g["name"] for g in v._import_groups()] == ["P1", "P2"]
        assert v.set_import_group_visible("P1", False) == 1
        assert a.visible is False and b.visible is True
        assert v.isolate_import_group("P2") == 1
        assert a.visible is False and b.visible is True
        hints = v.show_import_group_hints()
        assert hints["ref_faces"] == 3 and hints["parts"] == 2

    def test_p151_tree_group_checkbox_emits_and_toggles(self):
        """R26/P151: the tree checkbox is wired to the part visibility."""
        from PyQt5.QtCore import Qt
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        v = self.gui.ScdmViewer(path=None)
        kdoc = KernelDoc()
        a = kdoc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        kdoc.import_report = {"hierarchy": [{"name": "P1", "bodies": [a.id]}]}
        v.session().kdoc = kdoc
        v._import_groups()
        v._populate_structure() if hasattr(v, "_populate_structure") else None
        gl = v.left.group_list
        gl.clear()
        from PyQt5.QtWidgets import QListWidgetItem
        it = QListWidgetItem("P1")
        it.setData(Qt.UserRole, ("group", "P1"))
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked)
        gl.addItem(it)
        # unchecking must reach the part body (geometry identity is proven in
        # test_p133; here we only drive the tree -> viewer -> body path)
        it.setCheckState(Qt.Unchecked)
        assert a.visible is False
        it.setCheckState(Qt.Checked)
        assert a.visible is True

    def test_p157_group_hints_and_show_all(self):
        """R27/P157: node hints carry the import counts; show-all undoes isolation."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        v = self.gui.ScdmViewer(path=None)
        kdoc = KernelDoc()
        a = kdoc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        b = kdoc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
        kdoc.import_report = {"hierarchy": [{"name": "P1", "bodies": [a.id]},
                                            {"name": "P2", "bodies": [b.id]}],
                              "ref_faces": 3, "unbuilt_faces": 1}
        v.session().kdoc = kdoc
        v._import_groups()
        hints = v.show_import_group_hints()
        assert hints["ref_faces"] == 3 and hints["unbuilt_faces"] == 1
        assert v.isolate_import_group("P1") == 1
        assert a.visible is True and b.visible is False
        assert v.show_all_import_groups() == 2
        assert a.visible is True and b.visible is True

    def test_p205_tapped_hole_command(self):
        """R35/P205: the command cuts the tap drill and rejects bad threads."""
        import math
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        v = self.gui.ScdmViewer(path=None)
        kdoc = KernelDoc()
        box = K.make_box(0.02, 0.02, 0.02)
        body = kdoc.add_body(box, name="B")
        v.session().kdoc = kdoc
        face = [f for f in K.explore(box, "face")
                if K.face_normal_center(f)[0][2] > 0.99][0]
        v._selected_face = lambda: (body, face)
        v._commit = lambda *a, **k: None

        v._ask_numbers = lambda *a, **k: [6.0, 1.0, 0.0]
        before = K.volume(body.shape)
        v._do_create_hole_tapped()
        removed = before - K.volume(body.shape)
        expected = math.pi * 0.0025 ** 2 * 0.02
        assert abs(removed - expected) < expected * 1e-3

        # illegal pitch (>= nominal): explained, geometry untouched
        keep = K.volume(body.shape)
        v._ask_numbers = lambda *a, **k: [6.0, 6.0, 0.0]
        v._do_create_hole_tapped()
        assert abs(K.volume(body.shape) - keep) < 1e-15
        assert "非法" in self._status(v) or "螺距" in self._status(v)

    def test_p211_thread_annotation_is_unpickable(self):
        """R37: the thread profile is annotation - unpickable, out of bounds."""
        import math
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        v = self.gui.ScdmViewer(path=None)
        if v.scene is None:
            self.skipTest("scene not built headless")
        box = K.make_box(0.02, 0.02, 0.02)
        face = [f for f in K.explore(box, "face")
                if K.face_normal_center(f)[0][2] > 0.99][0]
        holed = K.hole_tapped(box, face, 0.006, 0.001)
        before = K.volume(holed)
        act = v.scene.show_thread_annotation((0.01, 0.01, 0.0), (0.0, 0.0, 1.0),
                                             0.006, 0.001, 0.02)
        assert act is not None
        assert act.GetPickable() == 0, "annotation must not be pickable"
        # the annotation is symbolic: the body volume is untouched
        assert abs(K.volume(holed) - before) < 1e-18
        v.scene.clear_thread_annotation()

    def test_p217_tapped_command_mounts_and_retires_annotation(self):
        """R38/P217: the command mounts the symbolic profile, plain holes clear it."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_thread_annotation(self, *a):
                self.calls.append(("show", a))

            def clear_thread_annotation(self):
                self.calls.append(("clear", None))

        v = self.gui.ScdmViewer(path=None)
        scene = FakeScene()
        v.scene = scene
        kdoc = KernelDoc()
        box = K.make_box(0.02, 0.02, 0.02)
        body = kdoc.add_body(box, name="B")
        v.session().kdoc = kdoc
        face = [f for f in K.explore(box, "face")
                if K.face_normal_center(f)[0][2] > 0.99][0]
        v._selected_face = lambda: (body, face)
        v._commit = lambda *a, **k: None

        v._ask_numbers = lambda *a, **k: [6.0, 1.0, 0.0]
        v._do_create_hole_tapped()
        assert scene.calls and scene.calls[0][0] == "show"
        (nominal, pitch) = scene.calls[0][1][2], scene.calls[0][1][3]
        assert abs(nominal - 0.006) < 1e-12 and abs(pitch - 0.001) < 1e-12
        assert scene.calls[0][1][4] > 0, "through hole must get a measured depth"

        v._ask_numbers = lambda *a, **k: [5.0, 0.0]
        v._do_create_hole()
        assert scene.calls[-1][0] == "clear"

    def test_tool_manager_reason_plumbing(self):
        from scdm.tools.base import ToolManager
        msgs = []
        tm = ToolManager(msgs.append)
        tm.activate("tool.pull", "拉动", "M2", False, "hud",
                    reason="轻量模式：拉动需要内核")
        self.assertEqual(msgs[-1], "轻量模式：拉动需要内核")
        tm.activate("tool.move", "移动", "M2", False, "hud")
        self.assertIn("未实现", msgs[-1])  # legacy fallback text preserved

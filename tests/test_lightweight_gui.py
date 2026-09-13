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

    def test_p287_sheet_multi_select_group_drag_snaps_exactly(self):
        """R52/P287: Ctrl append + rubber band, group drag, exact snap."""
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from scdm import drawing as D
        from scdm import kernel as K
        from scdm.gui.sheet import SheetCanvas

        # two parallel horizontal dimensions over two horizontal edges; the
        # offsets are scalars along the normal, so the assertions are exact
        views = [('前视', [[(0.0, 0.0), (0.02, 0.0)],
                           [(0.0, 0.005), (0.02, 0.005)]])]
        dims = [D.Dimension('前视', 'h', 20.0, (0.0, 0.0), (0.02, 0.0), 0.01),
                D.Dimension('前视', 'h', 20.0, (0.0, 0.0), (0.02, 0.0), 0.02)]
        canvas = SheetCanvas(views, dims)
        canvas.resize(600, 400)
        values = [d.value_mm for d in dims]
        tol_m = canvas.snap_tol_px / canvas.scale

        canvas.select(0)
        assert canvas.selected == [0]
        canvas.select(1, append=True)          # Ctrl 追加
        assert canvas.selected == [0, 1]
        canvas.select(1, append=True)          # Ctrl 再点 = 取消
        assert canvas.selected == [0]
        assert sorted(canvas.box_select(0, 0, 600, 400)) == [0, 1]

        # aim 40% of the snap radius past the y=5 mm edge: the line must land
        # EXACTLY on that edge (offset 5 mm), not near it
        aim = canvas.to_px(0.01, 0.005 + 0.4 * tol_m)
        hp = canvas.handle_px(0)
        canvas.begin_drag(0, hp.x(), hp.y())
        canvas.drag_handle(0, aim.x(), aim.y())
        canvas.end_drag()
        assert canvas.last_snap == 'end'
        assert dims[0].offset == 0.005            # exact: the edge's own offset
        # the whole selection kept its spacing (same vector -> same delta here)
        assert dims[1].offset == 0.02 + (0.005 - 0.01)
        # the dimension line passes through a real target exactly
        (ax, ay) = dims[0].a
        (nx, ny) = dims[0].normal()
        assert any(abs((x - ax) * nx + (y - ay) * ny - dims[0].offset) < 1e-15
                   for (x, y, _k) in canvas.snap.targets)
        # dragging is still an offset edit: the measured values never change
        assert [d.value_mm for d in dims] == values

    def test_p287_sheet_undo_redo_round_trips(self):
        """R52/P287: three drags -> three undos -> three redos, offsets exact."""
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from scdm import drawing as D
        from scdm import kernel as K
        from scdm.gui.sheet import SheetCanvas

        box = K.make_box(0.02, 0.02, 0.02)
        view = D.projected_view(box, (0.0, 0.0, -1.0), label='前视')
        dims = D.dimensions_for([view])
        canvas = SheetCanvas([view], dims)
        canvas.resize(600, 400)
        canvas.snap_enabled = False            # this test is about undo, not snap

        start = canvas.offsets()
        states = []
        for dy in (20.0, 30.0, 40.0):
            hp = canvas.handle_px(0)
            canvas.begin_drag(0, hp.x(), hp.y())
            canvas.drag_handle(0, hp.x() + 5.0, hp.y() - dy)
            canvas.end_drag()
            states.append(canvas.offsets())
        assert states[0] != start and states[1] != states[0]

        assert canvas.undo_last() is True
        assert canvas.offsets() == states[1]
        assert canvas.undo_last() is True
        assert canvas.offsets() == states[0]
        assert canvas.undo_last() is True
        assert canvas.offsets() == start
        assert canvas.undo_last() is False     # nothing left to undo
        for _ in range(3):
            assert canvas.redo_last() is True
        assert canvas.offsets() == states[2]
        assert canvas.redo_last() is False

    def test_p287_sheet_snap_to_a_deleted_edge_is_refused(self):
        """R52/P287: after the edge is deleted its endpoint stops snapping."""
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from scdm import drawing as D
        from scdm.gui.sheet import SheetCanvas

        base_edge = [(0.0, 0.0), (0.02, 0.0)]
        extra = [(0.005, 0.005), (0.015, 0.005)]
        views = [('前视', [base_edge, extra])]
        dims = [D.Dimension('前视', 'h', 20.0, (0.0, 0.0), (0.02, 0.0), 0.01)]
        canvas = SheetCanvas(views, dims)
        canvas.resize(600, 400)
        tol_m = canvas.snap_tol_px / canvas.scale

        tol_m = canvas.snap_tol_px / canvas.scale
        aim = canvas.to_px(0.01, 0.005 + 0.4 * tol_m)
        hp = canvas.handle_px(0)
        canvas.begin_drag(0, hp.x(), hp.y())
        canvas.drag_handle(0, aim.x(), aim.y())
        canvas.end_drag()
        assert canvas.last_snap == 'end' and dims[0].offset == 0.005

        # the edge is deleted -> the same aim point must no longer snap, so the
        # line lands on the raw dragged offset instead of the old edge
        canvas.views = [('前视', [base_edge])]
        canvas.rebuild_targets()
        raw = dims[0].offset_for_point(canvas.to_view(aim.x(), aim.y()))
        hp = canvas.handle_px(0)
        canvas.begin_drag(0, hp.x(), hp.y())
        canvas.drag_handle(0, aim.x(), aim.y())
        canvas.end_drag()
        assert canvas.last_snap == ''
        assert abs(dims[0].offset - raw) < 1e-15
        assert abs(dims[0].offset - 0.005) > 1e-6

    def test_p291_polyline_beam_command_builds_members_from_edges(self):
        """R53/P291: selected edges -> one body per member + weldment + axes."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm import beams as BEAMS
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_beam_axes(self, *a):
                self.calls.append(("axes", a))

            def clear_beam_axis(self):
                self.calls.append(("clear", None))

        v = self.gui.ScdmViewer(path=None)
        scene = FakeScene()
        v.scene = scene
        kdoc = KernelDoc()
        box = K.make_box(0.02, 0.02, 0.02)
        body = kdoc.add_body(box, name="B")
        v.session().kdoc = kdoc
        v._commit = lambda *a, **k: None
        v.sel.items = [("edge", "edge:%s:0" % body.id)]
        v._ask_choice = lambda *a, **k: BEAMS.LABELS["i"]
        v._ask_numbers = lambda *a, **k: [100.0, 50.0, 5.0, 7.0]
        v._do_create_beam_polyline()

        assert scene.calls and scene.calls[0][0] == "axes"
        assert len(scene.calls[0][1][0]) == 1          # one member axis
        assert len(kdoc.weldments) == 1
        weld = kdoc.weldments[0]
        assert len(weld.members) == 1
        assert abs(weld.member_lengths()[0] - 0.02) < 1e-12   # a cube edge
        area = BEAMS.closed_form("i", h=0.1, b=0.05, tw=0.005, tf=0.007)["area"]
        want = area * 0.02
        assert abs(K.volume(kdoc.bodies[-1].shape) - want) / want < 1e-9
        feats = kdoc.feature_stack(kdoc.bodies[-1].id).as_dict()
        assert feats and feats[-1]["op"] == "beam_polyline"

    def test_p295_gusset_and_tab_commands_mark_and_clear(self):
        """R54/P295: both forming commands add material, record the feature and
        mount the rim marker; a plain hole clears it again."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_form_marker(self, *a):
                self.calls.append(("mark", a))

            def clear_form_marker(self):
                self.calls.append(("clear", None))

        v = self.gui.ScdmViewer(path=None)
        scene = FakeScene()
        v.scene = scene
        kdoc = KernelDoc()
        box = K.make_box(0.02, 0.02, 0.002)
        body = kdoc.add_body(box, name="B")
        v.session().kdoc = kdoc
        top = [f for f in K.explore(box, "face")
               if K.face_normal_center(f)[0][2] > 0.99][0]
        bottom = [f for f in K.explore(box, "face")
                  if K.face_normal_center(f)[0][2] < -0.99][0]
        v._selected_face = lambda: (body, top)
        v._commit = lambda *a, **k: None

        v0 = K.volume(body.shape)
        v._ask_numbers = lambda *a, **k: [5.0, 3.0, 1.0]
        v._do_create_gusset()
        assert scene.calls and scene.calls[0][0] == "mark"
        got = K.volume(body.shape) - v0
        assert abs(got - 0.005 * 0.003 / 2.0 * 0.001) / got < 1e-9
        feats = kdoc.feature_stack(body.id).as_dict()
        assert feats[-1]["op"] == "gusset"

        # the tab goes on the opposite face: two added-material features on the
        # SAME face would overlap, and their union is not the sum of volumes
        v._selected_face = lambda: (body, bottom)
        v0 = K.volume(body.shape)
        v._do_create_tab()
        got = K.volume(body.shape) - v0
        assert abs(got - 0.005 * 0.003 * 0.001) / got < 1e-9
        feats = kdoc.feature_stack(body.id).as_dict()
        assert feats[-1]["op"] == "tab"

        v._ask_numbers = lambda *a, **k: [5.0, 0.0]
        v._do_create_hole()
        assert scene.calls[-1][0] == "clear"

    def test_p299_annotation_drag_snaps_in_2d_and_undoes(self):
        """R55/P299: an annotation has both degrees of freedom, so its anchor
        snaps to the nearest target POINT (a dimension only snaps its offset)."""
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from scdm import drawing as D
        from scdm.annotation import Leader
        from scdm.gui.sheet import SheetCanvas

        views = [('前视', [[(0.0, 0.0), (0.02, 0.0), (0.02, 0.02), (0.0, 0.02),
                            (0.0, 0.0)]])]
        dims = [D.Dimension('前视', 'h', 20.0, (0.0, 0.0), (0.02, 0.0), 0.01)]
        lead = Leader(view='前视', anchor=(0.005, 0.005), text='注')
        canvas = SheetCanvas(views, dims, annotations=[lead])
        canvas.resize(600, 400)
        tol_m = canvas.snap_tol_px / canvas.scale

        assert canvas.pick_annotation(*[canvas.to_px(0.005, 0.005).x(),
                                        canvas.to_px(0.005, 0.005).y()]) == 0
        aim = canvas.to_px(0.02 + 0.4 * tol_m, 0.0 + 0.4 * tol_m)
        canvas.begin_annotation_drag(0, *[canvas.handle_px(0).x(),
                                          canvas.handle_px(0).y()])
        canvas.drag_annotation(0, aim.x(), aim.y())
        canvas.end_drag()
        assert canvas.last_snap == 'end'
        assert lead.anchor == (0.02, 0.0)          # exact corner
        # undo restores the anchor exactly (annotations ride in the snapshot)
        assert canvas.undo_last() is True
        assert canvas.notes[0].anchor == (0.005, 0.005)
        assert canvas.redo_last() is True
        assert canvas.notes[0].anchor == (0.02, 0.0)

    def test_p299_sheet_dialog_adds_a_leader_on_a_real_target(self):
        """R55/P299: the dialog button path mounts a leader whose anchor is a
        genuine snap target, and the export carries it."""
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import tempfile
        from scdm import drawing as D
        from scdm.gui.sheet import SheetDialog

        views = [('前视', [[(0.0, 0.0), (0.02, 0.0), (0.02, 0.02), (0.0, 0.02),
                            (0.0, 0.0)]])]
        dims = D.dimensions_for(views)
        dlg = SheetDialog(views, dims)
        dlg.canvas.resize(600, 400)
        note = dlg.add_leader('见明细')
        assert note is not None and len(dlg.canvas.notes) == 1
        anchor = note.anchor
        assert any(abs(anchor[0] - x) < 1e-15 and abs(anchor[1] - y) < 1e-15
                   for (x, y, _k) in dlg.canvas.snap.targets)
        with self.assertRaises(ValueError):
            dlg.add_leader('   ')
        tmp = tempfile.mkdtemp(prefix='p299gui_')
        try:
            fn = os.path.join(tmp, 'sheet.svg')
            D.svg_sheet(dlg.views, fn, dimensions=dlg.canvas.dims,
                        annotations=dlg.canvas.notes)
            body = open(fn, encoding='utf-8').read()
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        assert '见明细' in body and 'class="note"' in body

    def test_p303_junction_command_forms_and_marks(self):
        """R56/P303: the junction command cuts the triangular release, records
        the feature and mounts the rim marker."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_form_marker(self, *a):
                self.calls.append(("mark", a))

            def clear_form_marker(self):
                self.calls.append(("clear", None))

        v = self.gui.ScdmViewer(path=None)
        scene = FakeScene()
        v.scene = scene
        kdoc = KernelDoc()
        box = K.make_box(0.02, 0.02, 0.002)
        body = kdoc.add_body(box, name="B")
        v.session().kdoc = kdoc
        face = [f for f in K.explore(box, "face")
                if K.face_normal_center(f)[0][2] > 0.99][0]
        v._selected_face = lambda: (body, face)
        v._commit = lambda *a, **k: None
        v._ask_choice = lambda *a, **k: "释放（三角缺口）"
        v._ask_numbers = lambda *a, **k: [4.0]

        v0 = K.volume(body.shape)
        v._do_sheet_junction()
        assert scene.calls and scene.calls[0][0] == "mark"
        got = v0 - K.volume(body.shape)
        want = 0.004 ** 2 / 2.0 * 0.002
        assert abs(got - want) / want < 1e-9
        feats = kdoc.feature_stack(body.id).as_dict()
        assert feats[-1]["op"] == "junction"
        assert feats[-1]["params"]["mode"] == "release"

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

    def test_p235_dimple_command_marks_and_clears(self):
        """R42/P235: the forming command mounts a rim marker; holes clear it."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_form_marker(self, *a):
                self.calls.append(("mark", a))

            def clear_form_marker(self):
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

        v._ask_numbers = lambda *a, **k: [8.0, 2.0]
        v._do_create_dimple()
        assert scene.calls and scene.calls[0][0] == "mark"
        assert abs(scene.calls[0][1][2] - 0.008) < 1e-12

        v._ask_numbers = lambda *a, **k: [5.0, 0.0]
        v._do_create_hole()
        assert scene.calls[-1][0] == "clear"

    def test_p278_knockout_command_records_marks_and_clears(self):
        """R50/P278: the knockout command forms the ring cut, records the
        feature, mounts the rim marker and a plain hole clears it."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_form_marker(self, *a):
                self.calls.append(("mark", a))

            def clear_form_marker(self):
                self.calls.append(("clear", None))

        v = self.gui.ScdmViewer(path=None)
        scene = FakeScene()
        v.scene = scene
        kdoc = KernelDoc()
        box = K.make_box(0.02, 0.02, 0.002)
        body = kdoc.add_body(box, name="B")
        v.session().kdoc = kdoc
        face = [f for f in K.explore(box, "face")
                if K.face_normal_center(f)[0][2] > 0.99][0]
        v._selected_face = lambda: (body, face)
        v._commit = lambda *a, **k: None

        v._ask_numbers = lambda *a, **k: [10.0, 1.0, 4.0]
        v._do_create_knockout()
        assert scene.calls and scene.calls[0][0] == "mark"
        assert abs(scene.calls[0][1][2] - 0.010) < 1e-12
        assert len(K.explore(body.shape, "shell")) == 1   # rule 66
        feats = kdoc.feature_stack(body.id).as_dict()
        assert feats and feats[-1]["op"] == "knockout"
        assert feats[-1]["params"]["web_count"] == 4

        v._ask_numbers = lambda *a, **k: [5.0, 0.0]
        v._do_create_hole()
        assert scene.calls[-1][0] == "clear"

    def test_p283_beam_command_creates_the_solid_and_marks_the_axis(self):
        """R51/P283: the beam command builds the section, records the feature
        and mounts the axis annotation (unpickable, excluded from bounds)."""
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        from scdm import beams as BEAMS
        from scdm.kdoc import KernelDoc

        class FakeScene:
            def __init__(self):
                self.calls = []

            def show_beam_axis(self, *a):
                self.calls.append(("axis", a))

            def clear_beam_axis(self):
                self.calls.append(("clear", None))

        v = self.gui.ScdmViewer(path=None)
        scene = FakeScene()
        v.scene = scene
        kdoc = KernelDoc()
        v.session().kdoc = kdoc
        v._commit = lambda *a, **k: None
        v._ask_choice = lambda *a, **k: BEAMS.LABELS["i"]
        v._ask_numbers = lambda *a, **k: [100.0, 50.0, 5.0, 7.0, 200.0]
        v._do_create_beam()
        assert scene.calls and scene.calls[0][0] == "axis"
        assert abs(scene.calls[0][1][2] - 0.2) < 1e-12     # 200 mm axis line
        assert len(kdoc.bodies) == 1
        body = kdoc.bodies[0]
        cf = BEAMS.closed_form("i", h=0.1, b=0.05, tw=0.005, tf=0.007)
        want = cf["area"] * 0.2
        assert abs(K.volume(body.shape) - want) / want < 1e-9
        assert "工字钢" in body.name
        feats = kdoc.feature_stack(body.id).as_dict()
        assert feats and feats[-1]["op"] == "beam"
        assert feats[-1]["params"]["profile"] == "i"

    def test_tool_manager_reason_plumbing(self):
        from scdm.tools.base import ToolManager
        msgs = []
        tm = ToolManager(msgs.append)
        tm.activate("tool.pull", "拉动", "M2", False, "hud",
                    reason="轻量模式：拉动需要内核")
        self.assertEqual(msgs[-1], "轻量模式：拉动需要内核")
        tm.activate("tool.move", "移动", "M2", False, "hud")
        self.assertIn("未实现", msgs[-1])  # legacy fallback text preserved

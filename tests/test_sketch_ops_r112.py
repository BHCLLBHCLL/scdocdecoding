"""R112 A-1 + A-2 + A-6: sketch mirror / linear pattern, the weld tolerance as a
document setting (the viewport snap radius), and conflict localisation.

A-1: `sketch.mirror` / `sketch.pattern` are sketch-only commands: the curve
     count is countable, a mirrored sketch extrudes into twice the loops, and a
     curve kind the 2D map does not understand refuses the whole operation.
A-2: the weld tolerance is one number with the snap radius (default 0.1mm, the
     viewport writes its radius), so a 0.5mm tear welds at 5mm and is refused -
     naming the distance and the tolerance - at 0.1mm.  `min_vertex_gap` now
     reports the *open* tear even when the other corners are welded.
A-6: the solver names the constraints behind `redundant` / `conflicting`
     (indices into the constraint list), and the mode chip / structure tree use
     those same `#N` numbers.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketch_solver as SS  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _mm3(w, h, t):
    return w * h * t * 1e-9


def _rect(doc, u0=0.002, v0=0.0, u1=0.004, v1=0.003):
    """A free-standing rectangle (its own loop, away from the sketch axes)."""
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (u0, v0, 0.0), (u1, v1, 0.0)))
    return sk


def _torn_rect(doc):
    """A rectangle whose left edge is 0.5mm off (the other corners are exact)."""
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.010, 0.0, 0.0)))
    sk.curves.append(("line", (0.010, 0.0, 0.0), (0.010, 0.008, 0.0)))
    sk.curves.append(("line", (0.010, 0.008, 0.0), (0.0, 0.008, 0.0)))
    sk.curves.append(("line", (0.0, 0.008, 0.0), (0.0005, 0.0, 0.0)))
    return sk


def _vol(doc):
    return sum(K.volume(b.shape) for b in doc.bodies)


# --- A-1: sketch mirror / pattern -------------------------------------------

def test_mirroring_about_an_axis_doubles_the_loops():
    doc = KernelDoc()
    sk = _rect(doc)                       # u in [2,4]mm, v in [0,3]mm
    rep = S.mirror_curves(sk, "v")        # about the vertical axis
    assert rep["ok"] and rep["added"] == 1 and rep["kept"] is True
    assert len(sk.curves) == 2
    assert len(S.sketch_loops(sk.curves)) == 2
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    assert out["ok"] and len(out["bodies"]) == 2
    assert _vol(doc) == pytest.approx(_mm3(2 * 2, 3, 5), rel=1e-9)


def test_mirroring_about_a_line_places_the_copy():
    doc = KernelDoc()
    sk = _rect(doc, 0.002, 0.0, 0.004, 0.003)
    rep = S.mirror_curves(sk, ((0.005, 0.0), (0.005, 0.001)))   # u = 5mm
    assert rep["ok"] and rep["axis"] == "line"
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    xs = sorted(K.face_normal_center(f)[1][0]
                for b in doc.bodies for f in K.explore(b.shape, "face")
                if abs(abs(K.face_normal_center(f)[0][0]) - 1.0) < 1e-9)
    # u in [2,4]mm mirrored about u = 5mm lands on [6,8]mm
    assert xs == [pytest.approx(0.002, abs=1e-12), pytest.approx(0.004, abs=1e-12),
                  pytest.approx(0.006, abs=1e-12), pytest.approx(0.008, abs=1e-12)]
    assert _vol(doc) == pytest.approx(_mm3(2 * 2, 3, 5), rel=1e-9)


def test_mirror_can_replace_the_originals():
    doc = KernelDoc()
    sk = _rect(doc)
    rep = S.mirror_curves(sk, "u", keep=False)     # about the horizontal axis
    assert rep["ok"] and rep["kept"] is False and len(sk.curves) == 1
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    assert len(out["bodies"]) == 1
    lo, hi = K._vertex_bbox(out["bodies"][0].shape)
    assert hi[1] == pytest.approx(0.0, abs=1e-12)  # v in [-3, 0] now
    assert lo[1] == pytest.approx(-0.003, abs=1e-12)


def test_the_pattern_adds_linear_instances():
    doc = KernelDoc()
    sk = _rect(doc, 0.0, 0.0, 0.002, 0.003)
    rep = S.pattern_curves(sk, 3, 0.005, 0.0)      # 3 instances, 5mm apart
    assert rep["ok"] and rep["added"] == 2 and len(sk.curves) == 3
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    assert len(out["bodies"]) == 3
    assert _vol(doc) == pytest.approx(_mm3(3 * 2, 3, 5), rel=1e-9)


def test_the_pattern_refuses_a_degenerate_step():
    doc = KernelDoc()
    sk = _rect(doc)
    one = S.pattern_curves(sk, 1, 0.005, 0.0)
    assert one["ok"] is False and "数量" in one["reason"]
    zero = S.pattern_curves(sk, 4, 0.0, 0.0)
    assert zero["ok"] is False and "间距" in zero["reason"]
    assert len(sk.curves) == 1                     # nothing was added


def test_an_unmapped_curve_kind_refuses_the_whole_transform():
    doc = KernelDoc()
    sk = _rect(doc)
    sk.curves.append(("ellipse", (0.02, 0.0), 0.001))
    rep = S.mirror_curves(sk, "v")
    assert rep["ok"] is False and "ellipse" in rep["reason"]
    assert len(sk.curves) == 2                     # no half-mirrored sketch
    pat = S.pattern_curves(sk, 3, 0.005, 0.0)
    assert pat["ok"] is False and "ellipse" in pat["reason"]


def test_the_script_ops_mirror_and_pattern():
    doc = KernelDoc()
    sk = _rect(doc, 0.0, 0.0, 0.002, 0.003)
    _b, msg = SCR.OPS["sketch.pattern"](doc, {"count": 2, "dx_mm": 5.0}, 1000.0)
    assert "×2" in msg
    _b, msg2 = SCR.OPS["sketch.mirror"](doc, {"axis": "v"}, 1000.0)
    assert "镜像" in msg2
    assert len(S.sketch_loops(sk.curves)) == 4
    out = SKM.extrude_active(doc, 5.0, 1000.0)     # the ops edit curves only
    assert out["ok"] and len(out["bodies"]) == 4
    assert _vol(doc) == pytest.approx(_mm3(4 * 2, 3, 5), rel=1e-6)


# --- A-2: the weld tolerance is the snap radius -----------------------------

def test_a_tear_welds_once_the_tolerance_allows_it():
    tight = KernelDoc()
    _torn_rect(tight)                              # 0.5mm tear, tol 0.1mm
    rep = SKM.extrude_active(tight, 5.0, 1000.0)
    assert rep["ok"] is False
    assert "未重合" in rep["reason"] and "0.5mm" in rep["reason"]
    assert "容差" in rep["reason"] and "0.1mm" in rep["reason"]
    assert tight.bodies == []

    loose = KernelDoc()
    loose.weld_tol_mm = 5.0                        # the viewport snap radius
    _torn_rect(loose)
    rep2 = SKM.extrude_active(loose, 5.0, 1000.0)
    assert rep2["ok"], rep2["reason"]
    assert rep2["welded"] == 4 and rep2["welded_moved"] == 1
    assert _vol(loose) == pytest.approx(_mm3(10, 8, 5), rel=1e-9)


def test_min_vertex_gap_reports_the_open_tear():
    """The other three corners are exact; the gap must still be the open one."""
    doc = KernelDoc()
    sk = _torn_rect(doc)
    gap = S.min_vertex_gap(sk)
    assert gap == pytest.approx(0.0005, rel=1e-9)          # 0.5mm, exactly
    assert S.min_vertex_gap(sk) == gap             # and it stays a measurement


def test_the_tolerance_is_clamped_and_round_trips():
    from scdm.io_project import load_scdm, save_scdm
    import tempfile

    doc = KernelDoc()
    assert SKM.weld_tolerance_mm(doc) == pytest.approx(0.1)
    assert SKM.set_weld_tolerance_mm(doc, 5.0) == pytest.approx(5.0)
    assert SKM.set_weld_tolerance_mm(doc, 0.0) == pytest.approx(5.0)   # refused
    assert SKM.set_weld_tolerance_mm(doc, "x") == pytest.approx(5.0)
    path = os.path.join(tempfile.mkdtemp(), "tol.scdoc")
    save_scdm(path, doc)
    assert load_scdm(path).weld_tol_mm == pytest.approx(5.0)


def test_the_options_dialog_edits_both_tolerances_separately():
    """Snapping and welding are different questions, so they are different
    numbers: a 5mm *weld* tolerance merges profiles 2mm apart (measured in
    test_gui_mirror_and_pattern_drive_the_sketch), while a 5mm snap radius is a
    drawing aid.  The dialog edits both, the document keeps the weld one."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        v.sel.snap_radius_mm = 3.5
        v.on_command("mode.sketch")
        # entering the mode does not overload the snap radius as a weld tolerance
        assert v.session().kdoc.weld_tol_mm == pytest.approx(0.1)
        v.session().kdoc.weld_tol_mm = 0.25
        dlg = scdm_gui.OptionsDialog(
            v.sel, weld_mm=SKM.weld_tolerance_mm(v.session().kdoc))
        try:
            assert dlg.snap_radius.value() == pytest.approx(3.5)
            assert dlg.weld_tol.value() == pytest.approx(0.25)   # the document
            dlg.snap_radius.setValue(1.25)
            dlg.weld_tol.setValue(0.5)
            dlg.apply_to(v.sel)
        finally:
            dlg.close()
        assert v.sel.snap_radius_mm == pytest.approx(1.25)
        assert v.sel.weld_tol_mm == pytest.approx(0.5)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-6: conflict and redundancy localisation ------------------------------

_RECT_CONS = [(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
              (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
              (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008)]
_RECT_PTS = [(0.0, 0.0), (0.010, 0.0), (0.010, 0.008), (0.0, 0.008)]
_RECT_SEGS = [(0, 1), (1, 2), (2, 3), (3, 0)]


def _solve(cons):
    return SS.solve_report([list(p) for p in _RECT_PTS], cons,
                           segments=list(_RECT_SEGS))


def test_a_duplicate_row_is_named_as_redundant():
    rep = _solve(_RECT_CONS + [(S.DIST, 0, 1, 0.010)])
    assert rep.converged and rep.redundant == 1
    assert rep.redundant_cons == (7,) and rep.violated_cons == ()


def test_conflicting_dimensions_are_named():
    rep = _solve(_RECT_CONS + [(S.DIST, 0, 1, 0.012)])   # 10mm vs 12mm
    assert rep.conflicting and rep.violated_cons == (5, 7)
    assert rep.redundant_cons == (7,)


def test_the_localisation_agrees_with_the_count():
    """Whatever the analysis says, the named rows are the ones the count uses."""
    for extra in ([(S.DIST, 0, 1, 0.010)], [(S.DIST, 0, 1, 0.012)],
                  [(S.VERTICAL, 0, 1)], []):
        cons = _RECT_CONS + extra
        rep = _solve(cons)
        solver = SS.SketchSolver([list(p) for p in _RECT_PTS], _RECT_SEGS,
                                 None, cons)
        J = solver._jacobian(solver._gather(),
                             solver.residuals(solver._gather()))
        dep = SS.SketchSolver.dependent_rows(J)
        assert len(dep) == len(J) - SS.SketchSolver._rank(J)
        owners = solver.row_owners()
        assert len(owners) == len(J)
        named = sorted({owners[i] for i in dep})
        assert named == sorted(rep.redundant_cons)


def test_dof_report_and_marks_name_the_rows():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                               [0.010, 0.008], [0.0, 0.008]]))
    sk.constraints.extend(_RECT_CONS)
    sk.constraints.append((S.DIST, 0, 1, 0.012))          # index 7: conflicting
    info = SKM.dof_report(doc, sk.id, 1000.0)
    assert info["ok"] and info["conflicting"]
    assert info["conflict_cons"] == (5, 7)
    marks = SKM.dimension_marks(doc, sk.id, 1000.0)["marks"]
    assert marks[5] == "冲突" and marks[7] == "冲突"
    assert marks.get(6, "") == ""                          # 6 is fine


def test_the_chip_and_the_tree_show_the_same_numbers():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    panel = None
    try:
        doc = v.session().kdoc
        v.on_command("mode.sketch")
        sk = doc.sketches[-1]
        sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                                   [0.010, 0.008], [0.0, 0.008]]))
        sk.constraints.extend(_RECT_CONS)
        sk.constraints.append((S.DIST, 0, 1, 0.012))   # 7: 10mm vs 12mm
        doc.active_sketch = sk.id
        v._refresh_sketch_dof()
        chip = v._mode_chip.text()
        assert "冲突" in chip and "#5" in chip, chip

        panel = LeftPanel()
        rows = []
        panel.populate_tree(Session(kdoc=doc, name="R112"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "sketch_dim":
                rows.append((data[2], item.text(0)))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
        marked = {i: t for i, t in rows if t.startswith("冲突")}
        assert 5 in marked and 7 in marked, rows
    finally:
        for w in (panel, v):
            if w is None:
                continue
            try:
                w.hide()
            except RuntimeError:
                pass
        try:
            v.close()
        except RuntimeError:
            pass


# --- the GUI commands -------------------------------------------------------

def test_gui_mirror_and_pattern_drive_the_sketch():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        v.left.show_options("sketch.mirror")
        v.on_command("sketch.mirror")
        assert len(S.sketch_loops(sk.curves)) == 2
        assert "已镜像" in v._prompt.text(), v._prompt.text()

        v.left.show_options("sketch.pattern")
        # the option page carries the count and the spacing (mm)
        page = v.left._opt_pages["sketch.pattern"]
        page[3][0].setValue(3)
        page[2][0].setValue(10.0)         # keeps the copies disjoint
        v.on_command("sketch.pattern")
        assert len(S.sketch_loops(sk.curves)) == 2 + 2 * 2

        out = SKM.extrude_active(v.session().kdoc, 5.0, 1000.0)
        assert out["ok"] and len(out["bodies"]) == 6
        # only the sketch's own bodies: the session also shows the loaded box
        vol = sum(K.volume(b.shape) for b in out["bodies"])
        assert vol == pytest.approx(_mm3(6 * 2, 3, 5), rel=1e-6)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_gui_mirror_reports_loops_no_body_follows_yet():
    """The live link follows recorded loops; a mirrored loop is new geometry, so
    the status has to say that a pull is still needed (rule 91)."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        doc = v.session().kdoc
        before = len(doc.bodies)                       # box.scdoc is already open
        v.on_command("sketch.pull")                    # 1 new body, back to 3D
        assert len(doc.bodies) == before + 1 and v._mode() == SKM.MODE_SOLID

        v._edit_sketch(sk.id)                          # double-click the tree
        assert v._mode() == SKM.MODE_SKETCH
        v.left.show_options("sketch.mirror")
        v.on_command("sketch.mirror")
        text = v._prompt.text()
        assert "已镜像" in text and "未建体" in text, text
        assert len(doc.bodies) == before + 1           # the recorded loop only

        v.on_command("sketch.pull")                    # now both loops exist
        assert len(doc.bodies) == before + 2
        vol = sum(K.volume(b.shape) for b in doc.bodies[before:])
        # the Pull option page default is 5mm; both loops are now built
        assert vol == pytest.approx(_mm3(2 * 2, 3, 5), rel=1e-6)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_gui_mirror_refuses_to_drop_dimensioned_curves():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                                   [0.010, 0.008], [0.0, 0.008]]))
        sk.constraints.extend(_RECT_CONS)
        v.left.show_options("sketch.mirror")
        v.left.set_checked("sketch.mirror", 1, False)     # 不保留原曲线
        before = len(sk.curves)
        v.on_command("sketch.mirror")
        assert len(sk.curves) == before                   # refused, not applied
        assert "尺寸" in v._prompt.text(), v._prompt.text()
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

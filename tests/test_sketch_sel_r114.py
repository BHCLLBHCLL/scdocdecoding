"""R114 A-1 + A-2 + A-5: a sketch entity selection set, pattern along a curve,
and diagnosable dangling cross-sketch references.

A-1: `pick_entity()` resolves a sketch-plane click to an edge or a vertex, the
     viewport draws the selected entities as an overlay, and Mirror consumes the
     selection (one edge, or two vertices, is an axis).
A-2: `pattern_curves(mode="along")` walks a UV path by arc length and rotates
     each instance by the change of tangent.
A-5: a reference to a deleted sketch, or to a row that is not a dimension, says
     so - and the structure tree marks the row.
"""
from __future__ import annotations

import math
import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _mm3(w, h, t):
    return w * h * t * 1e-9


def _doc_rect(u0=0.002, v0=0.0, u1=0.004, v1=0.003):
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (u0, v0, 0.0), (u1, v1, 0.0)))
    return doc, sk


def _viewer():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui
    return scdm_gui.ScdmViewer(path=_BOX)


def _vol(bodies):
    return sum(K.volume(b.shape) for b in bodies)

# --- A-1: picking and the selection set -------------------------------------

def test_pick_entity_resolves_a_click():
    doc, sk = _doc_rect()
    sk.curves.append(("circle", (0.020, 0.004, 0.0), 0.003))
    mid = S.pick_entity(sk, (0.003, 0.0002), 0.001)
    assert mid[0] == "curve" and mid[1] == 0 and mid[3] == pytest.approx(0.0002)
    corner = S.pick_entity(sk, (0.0021, 0.0001), 0.001)
    assert corner[0] == "point" and corner[1] == 0
    rim = S.pick_entity(sk, (0.0232, 0.004), 0.001)
    assert rim[0] == "curve" and rim[1] == 1
    ctr = S.pick_entity(sk, (0.0201, 0.004), 0.001)
    assert ctr[0] == "point" and ctr[1] == 1 and ctr[2] == 0
    assert S.pick_entity(sk, (0.05, 0.05), 0.001) is None


def test_curve_points_and_segment_cover_every_kind():
    doc, sk = _doc_rect()
    assert len(S.curve_points(sk, 0)) == 5          # rect is a closed ring
    assert S.curve_segment(sk, 0, 0) == ((0.002, 0.0), (0.004, 0.0))
    assert S.curve_segment(sk, 0, 3) == ((0.002, 0.003), (0.002, 0.0))
    sk.curves.append(("line", (0.010, 0.0, 0.0), (0.010, 0.005, 0.0)))
    assert S.curve_points(sk, 1) == [(0.010, 0.0), (0.010, 0.005)]
    sk.curves.append(("point", (0.020, 0.0, 0.0)))
    assert S.curve_points(sk, 2) == [(0.020, 0.0)]
    assert S.curve_points(sk, 9) is None


def test_the_highlight_geometry_is_the_drawn_geometry():
    """One source for both (R114/A-1): the overlay is built from the same
    per-curve mapping the sketch display uses, so a highlighted edge is exactly
    a drawn edge - checked here without a 3D scene (headless has none)."""
    from scdm.gui.scene import Scene

    doc, sk = _doc_rect()
    sk.curves.append(("circle", (0.020, 0.004, 0.0), 0.003))
    sk.curves.append(("line", (0.030, 0.0, 0.0), (0.030, 0.005, 0.0)))
    sk.curves.append(("point", (0.040, 0.0, 0.0)))
    axes = S.sketch_axes("xy")
    segs, pts = Scene._curve_geometry(sk, axes, sk.curves[0])
    assert len(segs) == 4 and pts == []
    assert segs[0] == [[0.002, 0.0, 0.0], [0.004, 0.0, 0.0]]
    assert segs[3] == [[0.002, 0.003, 0.0], [0.002, 0.0, 0.0]]
    csegs, cpts = Scene._curve_geometry(sk, axes, sk.curves[1])
    assert len(csegs) == 32 and cpts == []
    lsegs, _lpts = Scene._curve_geometry(sk, axes, sk.curves[2])
    assert lsegs == [[[0.030, 0.0, 0.0], [0.030, 0.005, 0.0]]]
    _s, ppts = Scene._curve_geometry(sk, axes, sk.curves[3])
    assert ppts == [[0.040, 0.0, 0.0]]
    # and it agrees with the picking helpers the highlight is driven by
    seg = S.curve_segment(sk, 0, 0)
    assert seg == ((0.002, 0.0), (0.004, 0.0))


def test_the_selection_set_replaces_toggles_and_clears():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        first = v._select_sketch_entity([0.003, 0.0002])
        assert first == ("curve", 0, 0)
        assert v.sketch_selection == [first]

        second = v._select_sketch_entity([0.0021, 0.0001])
        assert second[0] == "point"
        assert v.sketch_selection == [second]           # replaces, not adds

        v._select_sketch_entity([0.003, 0.0002], add=True)
        assert len(v.sketch_selection) == 2             # Shift adds
        v._select_sketch_entity([0.003, 0.0002], add=True)
        assert v.sketch_selection == [second]           # and toggles off

        assert v._select_sketch_entity([0.03, 0.03]) is None
        assert v.sketch_selection == []
        assert "未选中" in v._prompt.text()
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_leaving_sketch_mode_drops_the_selection():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        v._select_sketch_entity([0.003, 0.0002])
        assert v.sketch_selection
        v.on_command("mode.3d")
        assert v._mode() == SKM.MODE_SOLID
        assert v.sketch_selection == []
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_gui_mirror_about_a_selected_edge():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        assert v._select_sketch_entity([0.0021, 0.0015]) == ("curve", 0, 3)
        v.left.show_options("sketch.mirror")
        v.on_command("sketch.mirror")
        text = v._prompt.text()
        assert "以选中的草图边为轴" in text, text
        xs = [float(p[0]) for c in sk.curves if c[0] == "poly" for p in c[1]]
        assert min(xs) == pytest.approx(0.000, abs=1e-9)
        assert len(S.sketch_loops(sk.curves)) == 2
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_gui_mirror_refuses_an_ambiguous_selection():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        v._select_sketch_entity([0.003, 0.0002])             # the bottom edge
        v._select_sketch_entity([0.0021, 0.0015], add=True)  # the left edge
        assert len(v.sketch_selection) == 2
        before = len(sk.curves)
        v.on_command("sketch.mirror")
        assert "请只选一条轴" in v._prompt.text(), v._prompt.text()
        assert len(sk.curves) == before
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_gui_mirror_about_two_selected_vertices():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
        v._select_sketch_entity([0.0021, 0.0001])            # bottom-left
        v._select_sketch_entity([0.0039, 0.0001], add=True)  # bottom-right
        assert [r[0] for r in v.sketch_selection] == ["point", "point"]
        v.left.show_options("sketch.mirror")
        v.on_command("sketch.mirror")
        assert "以两个选中端点为轴" in v._prompt.text(), v._prompt.text()
        vs = [float(p[1]) for c in sk.curves if c[0] == "poly" for p in c[1]]
        assert min(vs) == pytest.approx(-0.003, abs=1e-9)
        out = SKM.extrude_active(v.session().kdoc, 5.0, 1000.0)
        assert out["ok"] and len(out["bodies"]) == 2
        assert _vol(out["bodies"]) == pytest.approx(_mm3(2 * 2, 3, 5), rel=1e-9)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-2: pattern along a curve ---------------------------------------------

def test_a_pattern_along_a_straight_path_is_evenly_spaced():
    doc, sk = _doc_rect(0.0, 0.0, 0.002, 0.003)
    rep = S.pattern_curves(sk, 3, mode="along", path=[(0.0, 0.0), (0.020, 0.0)])
    assert rep["ok"] and rep["added"] == 2
    assert rep["path_length"] == pytest.approx(0.020, rel=1e-12)
    assert rep["step"] == pytest.approx(0.010, rel=1e-12)
    xs = sorted(float(c[1][0][0]) for c in sk.curves if c[0] == "poly")
    assert xs == [pytest.approx(0.010, abs=1e-12), pytest.approx(0.020, abs=1e-12)]
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    assert out["ok"] and len(out["bodies"]) == 3
    assert _vol(out["bodies"]) == pytest.approx(_mm3(3 * 2, 3, 5), rel=1e-9)


def test_a_pattern_along_an_arc_follows_the_tangent():
    path = [(0.010 * math.cos(math.radians(a)), 0.010 * math.sin(math.radians(a)))
            for a in range(0, 91, 5)]
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.010, 0.0, 0.0), (0.012, 0.002, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="along", path=path)
    assert rep["ok"] and rep["added"] == 2
    assert rep["path_length"] == pytest.approx(math.pi / 2 * 0.010, rel=1e-3)
    anchors = [(float(c[1][0][0]), float(c[1][0][1]))
               for c in sk.curves if c[0] == "poly"]
    for i, want in enumerate((45.0, 90.0)):
        p = anchors[i]
        assert math.hypot(*p) == pytest.approx(0.010, rel=1e-9)
        assert math.degrees(math.atan2(p[1], p[0])) == pytest.approx(want, abs=1e-6)
    # the copy is the original rotated by the tangent change: its first edge
    # (2mm along +u) turns towards +v.  The path is a *polyline*, so the tangent
    # is the chord of the step it lands on - the deviation must shrink with the
    # sampling, which is what "follows the tangent" means here.
    def tangent_error(step):
        pts = [(0.010 * math.cos(math.radians(a)),
                0.010 * math.sin(math.radians(a)))
               for a in range(0, 91, step)]
        d2 = KernelDoc()
        s2 = d2.add_sketch("xy")
        s2.curves.append(("rect", (0.010, 0.0, 0.0), (0.012, 0.002, 0.0)))
        assert S.pattern_curves(s2, 3, mode="along", path=pts)["ok"]
        c2 = s2.curves[2]                    # the instance at the far end
        ex = float(c2[1][1][0]) - float(c2[1][0][0])
        ey = float(c2[1][1][1]) - float(c2[1][0][1])
        return max(abs(ex), abs(ey - 0.002))

    assert tangent_error(5) < 2e-4
    assert tangent_error(1) < tangent_error(5) / 4.0


def test_the_along_mode_refuses_a_bad_path():
    doc, sk = _doc_rect()
    none = S.pattern_curves(sk, 3, mode="along")
    assert none["ok"] is False and "路径" in none["reason"]
    zero = S.pattern_curves(sk, 3, mode="along",
                            path=[(0.001, 0.001), (0.001, 0.001)])
    assert zero["ok"] is False and "长度为零" in zero["reason"]
    assert len(sk.curves) == 1


def test_the_op_and_gui_pattern_along_a_selected_curve():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
    sk.curves.append(("rect", (0.0, 0.002, 0.0), (0.002, 0.005, 0.0)))
    _b, msg = SCR.OPS["sketch.pattern"](doc, {"count": 3, "mode": "along",
                                              "path_index": 0}, 1000.0)
    assert "沿曲线" in msg and "×3" in msg, msg
    assert len(S.sketch_loops(sk.curves)) == 3
    with pytest.raises(ValueError) as err:
        SCR.OPS["sketch.pattern"](doc, {"count": 3, "mode": "along"}, 1000.0)
    assert "path_index" in str(err.value)

    v = _viewer()
    try:
        v.on_command("mode.sketch")
        vsk = v.session().kdoc.sketches[-1]
        vsk.curves.append(("line", (0.030, 0.0, 0.0), (0.050, 0.0, 0.0)))
        vsk.curves.append(("rect", (0.030, 0.002, 0.0), (0.032, 0.005, 0.0)))
        v.left.show_options("sketch.pattern")
        v.left.set_checked("sketch.pattern", 1, True)
        before = len(vsk.curves)
        v.on_command("sketch.pattern")
        assert "需要先选中一条曲线" in v._prompt.text(), v._prompt.text()
        assert len(vsk.curves) == before
        v._select_sketch_entity([0.040, 0.0002])
        page = v.left._opt_pages["sketch.pattern"]
        page[3][0].setValue(3)
        v.on_command("sketch.pattern")
        assert "沿曲线" in v._prompt.text(), v._prompt.text()
        assert len(S.sketch_loops(vsk.curves)) == 3        # the 3 instances
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-5: dangling cross-sketch references ----------------------------------

def test_a_reference_to_a_deleted_sketch_is_diagnosed():
    doc = KernelDoc()
    a = doc.add_sketch("xy")
    a.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0], [0.020, 0.008],
                              [0.0, 0.008]]))
    a.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, "S2_dim5"), (S.DIST, 1, 2, 0.008)])
    b = doc.add_sketch("xy")
    b.curves.append(("poly", [[0.040, 0.0], [0.050, 0.0],
                              [0.050, 0.008], [0.040, 0.008]]))
    b.constraints.extend([
        (S.FIXED, 0, 0.040, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008)])
    assert (a.id, b.id) == ("S1", "S2")
    assert SKM.dimensions(doc, a.id, 1000.0)[0]["value_mm"] == pytest.approx(10.0)

    doc.sketches = [s for s in doc.sketches if s.id != "S2"]
    row = SKM.dimensions(doc, a.id, 1000.0)[0]
    assert row["value_mm"] is None and "S2" in row["reason"], row
    assert "已不存在" in row["reason"], row["reason"]
    assert SKM.dimension_marks(doc, a.id, 1000.0)["marks"][5] == "悬空"
    rep = SKM.set_dimension(doc, a.id, 5, "S2_dim5", 1000.0)
    assert rep["ok"] is False and "被引用草图 S2 已不存在" in rep["reason"]


def test_a_reference_to_a_non_dimension_names_the_sketch():
    doc = KernelDoc()
    a = doc.add_sketch("xy")
    a.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0], [0.010, 0.008],
                              [0.0, 0.008]]))
    a.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008)])
    rep = SKM.set_dimension(doc, a.id, 5, "S1_dim3", 1000.0)
    assert rep["ok"] is False
    assert "被引用草图 S1 没有尺寸 #3" in rep["reason"], rep["reason"]


def test_the_tree_marks_a_dangling_dimension():
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc = KernelDoc()
    a = doc.add_sketch("xy")
    a.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0], [0.020, 0.008],
                              [0.0, 0.008]]))
    a.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, "S2_dim5"), (S.DIST, 1, 2, 0.008)])
    doc.active_sketch = a.id
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R114"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "sketch_dim":
                rows.append((data[2], item.text(0)))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    marked = {i: t for i, t in rows if t.startswith("悬空")}
    assert 5 in marked, rows
    assert "无法求值" in marked[5]


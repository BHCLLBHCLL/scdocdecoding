"""R113 A-1 + A-2 + A-5: a picked sketch edge as the mirror axis, circular
sketch patterns, and dimensions that reference another sketch.

A-1: `nearest_segment()` turns the last sketch click into an axis, so Mirror
     can use a drawn line - the interaction the sketch tools already use.
A-2: `pattern_curves(mode="circular")` rotates copies about a centre;
     `sweep_deg` is the angle from the first instance to the last.
A-5: `<sketch_id>_dimN` (e.g. `S2_dim5`) drives a dimension in another
     sketch; cycles are refused with both sides labelled by sketch.
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


def _rect_sk(doc, u0, v0, w, h, width=None, plane="xy"):
    """A fully constrained rectangle, optionally with an expression width."""
    sk = doc.add_sketch(plane)
    sk.curves.append(("poly", [[u0, v0], [u0 + w, v0], [u0 + w, v0 + h],
                               [u0, v0 + h]]))
    sk.constraints.extend([
        (S.FIXED, 0, u0, v0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, width if width is not None else 0.010),
        (S.DIST, 1, 2, 0.008)])
    return sk


def _session(sk):
    return SKM.SketchSession(sketch_id=sk.id, plane=sk.plane)


def _vol(bodies):
    return sum(K.volume(b.shape) for b in bodies)


# --- A-1: a picked sketch edge as the mirror axis ---------------------------

def test_nearest_segment_finds_the_picked_edge():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.010, 0.008, 0.0)))
    top = S.nearest_segment(sk, (0.005, 0.0085), 0.002)
    assert top is not None and top[2] == pytest.approx(0.0005)
    assert sorted([top[0], top[1]]) == [(0.0, 0.008), (0.010, 0.008)]
    left = S.nearest_segment(sk, (-0.0004, 0.004), 0.002)
    assert left is not None and left[2] == pytest.approx(0.0004)
    assert S.nearest_segment(sk, (0.005, 0.020), 0.002) is None

    # a drawn line is a candidate too, a circle is not (it has no axis)
    sk.curves.append(("line", (0.020, 0.0, 0.0), (0.020, 0.010, 0.0)))
    sk.curves.append(("circle", (0.040, 0.0, 0.0), 0.002))
    seg = S.nearest_segment(sk, (0.0201, 0.005), 0.001)
    assert seg is not None and seg[0] == (0.020, 0.0) and seg[1] == (0.020, 0.010)
    assert S.nearest_segment(sk, (0.0421, 0.0), 0.001) is None


def test_mirroring_about_a_picked_edge_places_the_copy():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
    seg = S.nearest_segment(sk, (0.0021, 0.0015), 0.0005)   # the left edge
    assert seg is not None
    rep = S.mirror_curves(sk, (seg[0], seg[1]))
    assert rep["ok"] and rep["axis"] == "line" and rep["added"] == 1
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    assert out["ok"] and len(out["bodies"]) == 2
    # u in [2,4]mm mirrored about u = 2mm lands on [0,2]mm
    xs = sorted(K.face_normal_center(f)[1][0]
                for b in out["bodies"] for f in K.explore(b.shape, "face")
                if abs(abs(K.face_normal_center(f)[0][0]) - 1.0) < 1e-9)
    # the copy spans [0,2]mm and the original [2,4]mm, sharing u = 2mm
    assert xs == [pytest.approx(0.000, abs=1e-12), pytest.approx(0.002, abs=1e-12),
                  pytest.approx(0.002, abs=1e-12), pytest.approx(0.004, abs=1e-12)]
    assert _vol(out["bodies"]) == pytest.approx(_mm3(2 * 2, 3, 5), rel=1e-9)


def test_the_op_takes_a_pick_or_an_explicit_line():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
    _b, msg = SCR.OPS["sketch.mirror"](doc, {"pick_mm": [2.1, 1.5],
                                             "pick_tol_mm": 0.5}, 1000.0)
    assert "以直线为轴" in msg, msg
    assert len(S.sketch_loops(sk.curves)) == 2

    doc2 = KernelDoc()
    sk2 = doc2.add_sketch("xy")
    sk2.curves.append(("rect", (0.002, 0.0, 0.0), (0.004, 0.003, 0.0)))
    _b2, msg2 = SCR.OPS["sketch.mirror"](
        doc2, {"axis_line_mm": [2.0, 0.0, 2.0, 3.0]}, 1000.0)
    assert "以直线为轴" in msg2
    assert len(S.sketch_loops(sk2.curves)) == 2

    with pytest.raises(ValueError) as err:
        SCR.OPS["sketch.mirror"](doc2, {"pick_mm": [50.0, 50.0]}, 1000.0)
    assert "没有可作为轴的直线" in str(err.value)


def test_the_gui_mirrors_about_the_last_pick():
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
        v._sketch_recent = [[0.0021, 0.0015]]          # the user clicked the edge
        v.left.show_options("sketch.mirror")
        v.on_command("sketch.mirror")
        text = v._prompt.text()
        assert "以拾取直线为轴" in text, text
        xs = [float(p[0]) for c in sk.curves if c[0] == "poly" for p in c[1]]
        assert min(xs) == pytest.approx(0.000, abs=1e-9)   # mirrored past u=2mm

        # switching the option off falls back to the sketch axis
        v.left.set_checked("sketch.mirror", 2, False)
        v._sketch_recent = [[0.0021, 0.0015]]
        v.on_command("sketch.mirror")
        assert "关于竖直轴" in v._prompt.text(), v._prompt.text()
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-2: circular sketch pattern ------------------------------------------

def test_a_circular_pattern_spaces_the_instances():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.008, 0.0, 0.0), (0.010, 0.003, 0.0)))
    rep = S.pattern_curves(sk, 4, mode="circular", center=(0.0, 0.0),
                           sweep_deg=360.0)
    assert rep["ok"] and rep["added"] == 3 and rep["step_deg"] == pytest.approx(120.0)
    assert len(S.sketch_loops(sk.curves)) == 4
    out = SKM.extrude_active(doc, 5.0, 1000.0)
    assert out["ok"] and len(out["bodies"]) == 4
    assert _vol(out["bodies"]) == pytest.approx(_mm3(4 * 2, 3, 5), rel=1e-9)
    # every instance sits on the 8..10mm radius band, a quarter turn apart
    # the three *copies* are polys (the original is still a rect)
    angs = sorted(round(math.degrees(math.atan2(float(c[1][0][1]),
                                                float(c[1][0][0]))), 6) % 360.0
                  for c in sk.curves if c[0] == "poly")
    assert angs == [pytest.approx(a, abs=1e-6) for a in (0.0, 120.0, 240.0)]


def test_a_partial_sweep_uses_the_total_angle():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.010, 0.0, 0.0), (0.020, 0.0, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="circular", center=(0.0, 0.0),
                           sweep_deg=90.0)
    assert rep["ok"] and rep["step_deg"] == pytest.approx(45.0)
    angs = sorted(round(math.degrees(math.atan2(c[1][1], c[1][0])), 6)
                  for c in sk.curves)
    assert angs == [0.0, 45.0, 90.0]
    for c in sk.curves:                             # the radius never drifts
        assert math.hypot(c[1][0], c[1][1]) == pytest.approx(0.010, rel=1e-12)


def test_circular_refusals_leave_the_sketch_alone():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.008, 0.0, 0.0), (0.010, 0.003, 0.0)))
    no_center = S.pattern_curves(sk, 3, mode="circular")
    assert no_center["ok"] is False and "圆心" in no_center["reason"]
    zero = S.pattern_curves(sk, 3, mode="circular", center=(0.0, 0.0),
                            sweep_deg=0.0)
    assert zero["ok"] is False and "总角度" in zero["reason"]
    unknown = S.pattern_curves(sk, 3, mode="helix")
    assert unknown["ok"] is False and "未知阵列方式" in unknown["reason"]
    assert len(sk.curves) == 1


def test_the_op_and_the_gui_pattern_circularly():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.008, 0.0, 0.0), (0.010, 0.003, 0.0)))
    _b, msg = SCR.OPS["sketch.pattern"](doc, {"count": 4, "mode": "circular",
                                              "cu_mm": 0.0, "cv_mm": 0.0,
                                              "sweep_deg": 360.0}, 1000.0)
    assert "圆周" in msg and "×4" in msg, msg
    assert len(S.sketch_loops(sk.curves)) == 4

    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        v.on_command("mode.sketch")
        vsk = v.session().kdoc.sketches[-1]
        vsk.curves.append(("rect", (0.008, 0.0, 0.0), (0.010, 0.003, 0.0)))
        v.left.show_options("sketch.pattern")
        page = v.left._opt_pages["sketch.pattern"]
        page[1][0].setChecked(True)                  # 圆周阵列
        page[3][0].setValue(4)                       # 数量
        page[2][4].setValue(360.0)                   # 总角度
        v.on_command("sketch.pattern")
        assert "圆周" in v._prompt.text(), v._prompt.text()
        assert len(S.sketch_loops(vsk.curves)) == 4
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-5: dimensions that reference another sketch --------------------------

def test_a_dimension_can_reference_another_sketch():
    doc = KernelDoc()
    a = _rect_sk(doc, 0.0, 0.0, 0.020, 0.008, width="S2_dim5")   # S1 <- S2
    b = _rect_sk(doc, 0.040, 0.0, 0.010, 0.008)                  # S2: 10mm
    assert (a.id, b.id) == ("S1", "S2")
    rep = SKM.extrude_active(doc, 5.0, 1000.0, _session(a))
    body = rep["bodies"][0]
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-9)

    assert SKM.redrive_expressions(doc, 1000.0)["ok"]
    SKM.sync_sketch_bodies(doc, a.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-6)
    rows = {d["index"]: d for d in SKM.dimensions(doc, a.id, 1000.0)}
    assert rows[5]["expr"] == "S2_dim5"

    drove = SKM.set_dimension(doc, b.id, 5, 20.0, 1000.0)
    assert drove["ok"], drove["reason"]
    SKM.redrive_expressions(doc, 1000.0)
    SKM.sync_sketch_bodies(doc, a.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)


def test_a_cross_sketch_cycle_is_refused_with_both_sides():
    doc = KernelDoc()
    _a = _rect_sk(doc, 0.0, 0.0, 0.020, 0.008, width="S2_dim5")
    b = _rect_sk(doc, 0.040, 0.0, 0.010, 0.008)
    rep = SKM.set_dimension(doc, b.id, 5, "S1_dim5", 1000.0)
    assert rep["ok"] is False and "循环" in rep["reason"], rep["reason"]
    assert "S1#5" in rep["reason"] and "#5" in rep["reason"], rep["reason"]
    assert b.constraints[5][3] == 0.010            # rolled back


def test_a_sketch_may_not_reference_itself_by_id():
    doc = KernelDoc()
    a = _rect_sk(doc, 0.0, 0.0, 0.020, 0.008)
    rep = SKM.set_dimension(doc, a.id, 5, "S1_dim5", 1000.0)
    assert rep["ok"] is False and "尺寸引用存在循环（#5 → #5）" in rep["reason"]
    assert a.constraints[5][3] == 0.010


def test_a_stale_sketch_id_names_the_ones_that_exist():
    doc = KernelDoc()
    _a = _rect_sk(doc, 0.0, 0.0, 0.020, 0.008)
    _b = _rect_sk(doc, 0.040, 0.0, 0.010, 0.008)
    rep = SKM.set_dimension(doc, "S1", 5, "S9_dim5", 1000.0)
    assert rep["ok"] is False
    assert "S9_dim5" in rep["reason"]
    assert "S2_dim5" in rep["reason"], rep["reason"]   # the fix is in the message


def test_a_cross_reference_survives_a_reload():
    from scdm.io_project import load_scdm, save_scdm
    import tempfile

    doc = KernelDoc()
    a = _rect_sk(doc, 0.0, 0.0, 0.020, 0.008, width="S2_dim5")
    b = _rect_sk(doc, 0.040, 0.0, 0.010, 0.008)
    path = os.path.join(tempfile.mkdtemp(), "x.scdoc")
    save_scdm(path, doc)
    back = load_scdm(path)
    assert back.sketches[0].constraints[5][3] == "S2_dim5"
    SKM.set_dimension(back, b.id, 5, 25.0, 1000.0)
    assert SKM.redrive_expressions(back, 1000.0)["ok"]
    rows = {d["index"]: d for d in SKM.dimensions(back, a.id, 1000.0)}
    assert rows[5]["value_mm"] == pytest.approx(25.0, rel=1e-9)


def test_the_tree_shows_how_to_reference_a_sketch():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc = KernelDoc()
    sk = _rect_sk(doc, 0.0, 0.0, 0.020, 0.008)
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R113"))

        def walk(item, parent_text=""):
            data = item.data(0, Qt.UserRole)
            rows.append((data, item.text(0), item.toolTip(0)))
            for i in range(item.childCount()):
                walk(item.child(i), item.text(0))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    sketch_tip = [tip for (d, t, tip) in rows if d and d[0] == "sketch" and tip]
    assert any("S1_dim3" in tip for tip in sketch_tip), sketch_tip
    dim_tips = [tip for (d, t, tip) in rows if d and d[0] == "sketch_dim"]
    assert any("S1_dim5" in tip for tip in dim_tips), dim_tips

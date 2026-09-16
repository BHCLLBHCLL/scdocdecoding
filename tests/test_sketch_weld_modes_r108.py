"""R108 A-1 + A-4: welded sketch vertices, and placed extrusions.

A-1: separately drawn lines only *touch* in coordinates; without COINCIDENT a
     solve pulls the corners apart and the outline tears open (R107 measured it).
     `weld_coincident()` states "these are the same point" before solving, and
     the dimension drive does it automatically.
A-4: an extrusion is placed one-sided, symmetric or reversed - same volume for
     the same thickness, different seat relative to the sketch plane.
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


def _four_lines(doc, w_mm=10.0, h_mm=8.0, constraints=True):
    """A rectangle drawn as four separate lines (the tearing scenario)."""
    sk = doc.add_sketch("xy")
    w, h = w_mm / 1000.0, h_mm / 1000.0
    corners = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        sk.curves.append(("line", (a[0], a[1], 0.0), (b[0], b[1], 0.0)))
    if constraints:
        sk.constraints.extend([
            (S.FIXED, 0, 0.0, 0.0),
            (S.HORIZONTAL, 0, 1), (S.VERTICAL, 2, 3),
            (S.HORIZONTAL, 4, 5), (S.VERTICAL, 6, 7),
            (S.DIST, 0, 1, w), (S.DIST, 2, 3, h),
        ])
    return sk


def _bbox_z(shape):
    lo, hi = K._vertex_bbox(shape)
    return lo[2], hi[2]


def _mm3(w, h, t):
    return w * h * t * 1e-9


# --- A-1: welding -----------------------------------------------------------

def test_welding_is_idempotent_and_does_not_move_geometry():
    doc = KernelDoc()
    sk = _four_lines(doc, constraints=False)
    pts_before = S.read_points(sk)[0]
    added = S.weld_coincident(sk)
    assert added == 4                     # four corners -> four coincidences
    assert S.weld_coincident(sk) == 0     # idempotent
    assert S.read_points(sk)[0] == pts_before
    assert len(S.sketch_loops(sk.curves)) == 1


def test_welding_only_touches_real_vertices():
    """A circle centre may sit on a line endpoint and must still not be welded."""
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("circle", (0.0, 0.0), 0.002))       # centre at (0,0)
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.010, 0.0, 0.0)))
    assert S.weld_coincident(sk) == 0


def test_solving_without_welding_tears_the_outline():
    """The honest 'before' half: this is what R107 measured.

    R109 makes welding automatic when a sketch is extruded or synced, so the tear
    is reproduced at the solver level - exactly the path that used to be taken.
    """
    doc = KernelDoc()
    sk = _four_lines(doc)
    from scdm.sketch_solver import solve_report
    cons = list(sk.constraints)
    cons[5] = (S.DIST, 0, 1, 0.020)
    pts, segs = S.read_points(sk)
    solve_report(pts, cons, segments=segs, max_iter=200)
    S.write_points(sk, pts)
    assert S.sketch_loops(sk.curves) == []          # the outline is gone

    # ... while the extrude path repairs it by welding first (R109)
    sk2 = _four_lines(KernelDoc())
    doc2 = sk2 and None
    doc3 = KernelDoc()
    sk3 = _four_lines(doc3)
    rep = SKM.extrude_active(doc3, 5.0, 1000.0)
    assert rep["ok"] and rep["welded"] == 4
    assert len(S.sketch_loops(sk3.curves)) == 1
    assert K.volume(rep["bodies"][0].shape) == pytest.approx(_mm3(10, 8, 5),
                                                             rel=1e-9)


def test_the_drive_welds_so_the_rectangle_survives():
    doc = KernelDoc()
    sk = _four_lines(doc)
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    body = rep["bodies"][0]
    # R109: the extrude welded the corners itself (4 constraints on top of 7)
    assert rep["welded"] == 4 and len(sk.constraints) == 11

    drive = SKM.set_dimension(doc, sk.id, 5, 20.0, 1000.0)
    assert drive["ok"], drive["reason"]
    assert drive["welded"] == 0 and drive["dof"] == 0
    assert len(S.sketch_loops(sk.curves)) == 1      # welded, so it holds together
    assert SKM.sync_sketch_bodies(doc, sk.id, 1000.0)["updated"] == [body.id]
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)
    assert doc.can_replay(body.id)[0] is True


# --- A-4: extrusion modes ---------------------------------------------------

def _rect_body(doc, mode, w_mm=10.0, h_mm=8.0, t_mm=5.0):
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0),
                      (w_mm / 1000.0, h_mm / 1000.0)))
    rep = SKM.extrude_active(doc, t_mm, 1000.0, mode=mode)
    assert rep["ok"], rep["reason"]
    return sk, rep["bodies"][0]


def test_extrusion_modes_share_the_volume_and_move_the_seat():
    expected = {"one": (0.0, 0.005), "symmetric": (-0.0025, 0.0025),
                "reverse": (-0.005, 0.0)}
    for mode, (zlo, zhi) in expected.items():
        doc = KernelDoc()
        _sk, body = _rect_body(doc, mode)
        assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-9), mode
        lo, hi = _bbox_z(body.shape)
        assert (lo, hi) == (pytest.approx(zlo, abs=1e-12),
                            pytest.approx(zhi, abs=1e-12)), mode
        stack = doc.feature_stack(body.id)
        assert stack.features[0].params.get("mode", "one") == mode
        assert doc.can_replay(body.id)[0] is True, mode
        assert doc.edit_feature(body.id, 0, "height", 8.0)["ok"]
        assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 8), rel=1e-9)
        lo2, hi2 = _bbox_z(body.shape)               # the seat follows the height
        assert hi2 - lo2 == pytest.approx(0.008, rel=1e-9)
        if mode == "symmetric":
            assert lo2 == pytest.approx(-0.004, abs=1e-12)


def test_unknown_mode_is_refused():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
    with pytest.raises(ValueError):
        S.place_extrusion(K.make_box(0.001, 0.001, 0.001), "sideways", 0.005,
                          (0.0, 0.0, 1.0))


def test_scripted_pull_honours_the_mode():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
    msg = SCR.OPS["sketch.pull"](doc, {"distance": 5.0, "sketch": 0,
                                       "mode": "symmetric"}, 1000.0)[1]
    assert "草图拉伸" in msg
    body = doc.bodies[0]
    lo, hi = _bbox_z(body.shape)
    assert (lo, hi) == (pytest.approx(-0.0025, abs=1e-12),
                        pytest.approx(0.0025, abs=1e-12))


# --- the GUI path -----------------------------------------------------------

def test_gui_pull_respects_the_symmetric_option():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import scdm_gui
    box = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "box.scdoc")
    v = scdm_gui.ScdmViewer(path=box)
    try:
        v.left.show_options("tool.pull")
        v.left.set_checked("tool.pull", 0, True)          # 对称
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
        v.on_command("sketch.pull")
        body = v.session().kdoc.bodies[-1]
        lo, hi = _bbox_z(body.shape)
        assert (lo, hi) == (pytest.approx(-0.0025, abs=1e-12),
                            pytest.approx(0.0025, abs=1e-12))
        assert v.session().kdoc.feature_stack(body.id).features[0].params[
            "mode"] == "symmetric"
        assert v._mode() == SKM.MODE_SOLID
    finally:
        v.close()

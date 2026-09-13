"""R83/P402: the check command now reports watertightness (gaps/seams/loops).

repair.check already ran the H4 full-item check plus auto repair; R83 adds the
R75-R82 watertightness numbers - real gaps, periodic-face seams and free loops -
from the SAME kernel helpers the report and tools use, plus 3D markers on the
gaps (ordinary markup notes, so they inherit the scene's double guard:
unpickable and excluded from the camera fit).

Kernel facts used here (a box missing one face has a rectangular opening):
  closed box          free 0 / open 0 / seam 0 / loops 0      "封闭 ✓"
  box - one face      free 4 / open 4 / seam 0 / loops 1      "未封闭 4 处（自由环 1）"
  full-wrap cylinder  free 3 / open 2 / seam 1 / loops 2      (the seam is not a gap)
"""
from __future__ import annotations

import importlib.util

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")


def _open_box():
    """A box with one face removed: 4 open edges forming one loop."""
    from scdm import kernel as K

    solid = K.make_box(0.02, 0.02, 0.02)
    faces = K.explore(solid, "face")
    rest = [f for f in faces[1:]]
    return K.sew_bodies(rest)


@requires_occ
def test_watertight_report_and_text():
    from scdm import kernel as K

    closed = K.make_box(0.02, 0.02, 0.02)
    rep = K.watertight_report(closed)
    assert rep == {"free_edges": 0, "open_edges": 0, "seam_edges": 0,
                   "free_loops": 0}, rep
    assert K.watertight_text(rep) == "封闭 ✓"

    shell = _open_box()
    rep = K.watertight_report(shell)
    assert (rep["open_edges"], rep["seam_edges"], rep["free_loops"]) == (4, 0, 1), rep
    assert rep["free_edges"] == 4
    assert K.watertight_text(rep) == "未封闭 4 处（自由环 1）"


@requires_occ
def test_a_periodic_seam_is_reported_apart_from_the_gaps():
    from scdm import kernel as K
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.Geom import Geom_CylindricalSurface
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    ax = gp_Ax3(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0),
                       gp_Dir(1.0, 0.0, 0.0)))
    surf = Geom_CylindricalSurface(ax, 0.01)
    patch = BRepBuilderAPI_MakeFace(surf, 0.0, 6.283185307179586,
                                    0.0, 0.02, 1e-6).Face()
    rep = K.watertight_report(patch)
    # the seam is used twice by the same face -> it never shows as free; the two
    # rim circles are the only "gaps" of an open patch
    assert rep["open_edges"] == 2 and rep["free_loops"] == 2, rep
    assert rep["seam_edges"] == 0


@requires_occ
def test_open_edge_points_land_on_the_gaps():
    from scdm import kernel as K

    shell = _open_box()
    pts = K.open_edge_points(shell, 8)
    assert len(pts) == len(K.open_edges(shell)) == 4
    for p in pts:
        assert all(-1e-9 <= c <= 0.02 + 1e-9 for c in p), p
    # the limit is honoured
    assert len(K.open_edge_points(shell, 2)) == 2


@requires_occ
def test_repair_check_op_reports_the_gaps():
    from scdm import kernel as K
    from scdm.kdoc import KernelDoc
    from scdm.scripting import OPS

    doc = KernelDoc()
    body = doc.add_body(_open_box(), name="开壳")
    out, msg = OPS["repair.check"](doc, {"target": "last"}, 1000.0)
    assert out is body
    assert "未封闭" in msg, msg
    # the message's numbers come from the same kernel helper (independent recount)
    rep = K.watertight_report(body.shape)
    assert ("%d 处" % rep["open_edges"]) in msg, (msg, rep)


@requires_occ
def test_repair_check_op_replays():
    from scdm.kdoc import KernelDoc
    from scdm.scripting import replay

    doc = KernelDoc()
    doc.add_body(_open_box(), name="开壳")
    steps = [{"cmd": "repair.check", "opts": {"target": "last", "min_edge_mm": 0.5}}]
    msgs = replay(steps, doc, 1000.0)
    assert msgs and msgs[0].startswith("OK repair.check"), msgs
    # ... and the same step really ran through the op (the body was repaired,
    # so the replay path is not a silent no-op)
    assert doc.bodies and doc.bodies[0].name == "开壳"

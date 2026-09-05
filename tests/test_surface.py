"""H6: surface-page kernel — untrim/extend/offset/thicken/patch/blend."""
from __future__ import annotations

import math

import pytest

from scdm import kernel as K
from scdm import surface as S

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def _cyl_lateral():
    cyl = K.make_cylinder(0.005, 0.02)
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    return next(f for f in K.explore(cyl, "face")
                if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder)


def _plane_face():
    return K.make_plane_face((0, 0, 0), (0, 0, 1), 0.01)


def test_untrim_cylinder_drops_seam():
    lat = _cyl_lateral()
    a0 = K.area(lat)
    u = S.untrim(lat)
    # untrimmed wraps the full 2*pi circumference with expanded V
    assert K.area(u) > a0 * 2


def test_untrim_plane_expands():
    pl = _plane_face()
    u = S.untrim(pl)
    assert K.area(u) > K.area(pl) * 3   # expanded by 1x each side


def test_extend_plane_grows():
    pl = _plane_face()
    pe = S.extend_face(pl, 0.01, in_u=True, after=True)
    assert K.area(pe) == pytest.approx(K.area(pl) + 0.01 * 0.02)


def test_offset_cylinder_radius():
    lat = _cyl_lateral()
    of = S.offset_face(lat, 0.001)
    surf = S.surface_of(of)
    u1, u2, v1, v2 = surf.Bounds()
    p = surf.Value(0.5 * (u1 + u2), 0.5 * (max(v1, -1) + min(v2, 1)))
    d = math.sqrt(p.X() ** 2 + p.Y() ** 2)
    assert d == pytest.approx(0.006, abs=1e-6)


def test_thicken_prism_volume():
    pl = _plane_face()
    th = S.thicken(pl, 0.001)
    assert K.volume(th) == pytest.approx(K.area(pl) * 0.001, rel=1e-6)


def test_patch_fill_square():
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCC.Core.gp import gp_Pnt
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in ((0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)):
        poly.Add(gp_Pnt(x, y, 0))
    poly.Close()
    pf = S.patch_fill(list(K.explore(poly.Wire(), "edge")))
    assert K.area(pf) == pytest.approx(1e-4, rel=1e-6)


def test_blend_loft_between_circles():
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Circ, gp_Pnt
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    c1 = gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0.01)
    c2 = gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0.02), gp_Dir(0, 0, 1)), 0.02)
    w1 = S.make_wire_from_edges([BRepBuilderAPI_MakeEdge(c1).Edge()])
    w2 = S.make_wire_from_edges([BRepBuilderAPI_MakeEdge(c2).Edge()])
    bl = S.blend_loft(w1, w2)
    assert len(K.explore(bl, "face")) >= 1
    assert K.area(bl) > 0

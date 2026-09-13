"""R73: two decode fixes on the official boundary geometry (P362).

The R73 headline came out of the ref-family diff: the *counts* of the official
library were exact while the geometry was not watertight.  Two decode bugs were
behind a large part of it, both proved against the model's own boundary:

1. a cone record stores its x direction as a VECTOR whose length is the radius.
   SampleModel1 disagrees with the separate radius token (|ref| = 0.015 vs
   0.001) and only |ref| puts the face's boundary curves ON the surface:
   41/41 faces exact to 1e-16, versus 5/41 for the token.
2. a straight edge's recorded parameter range is expressed in that same vector's
   units, while `gp_Dir` normalises it - edge 88 of SampleModel1 decoded its
   far endpoint at -3.996 m instead of 0.002 m.  The vertices are independent of
   the range (P45 precedence) and now win.

Measured effect (tools/ref_family_diff.py): free edges / free loops
  SampleModel1  270/84 -> 129/53
  SampleModel4  441/112 -> 418/111
  samplemodel2 3542/547 -> 2546/464
  samplemodel3 0/0, samplemodel5 0/0, samplemodel6 2/2 unchanged
and the face counts are unchanged except samplemodel2 1810 -> 1812 (of 1813).
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")

spec = importlib.util.spec_from_file_location(
    "ref_family_diff", ROOT / "tools" / "ref_family_diff.py")
diff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diff)

# Free-edge / free-loop ceilings: "must not get worse", the same shape as the
# import BASELINE floors.  Measured: R72 -> R73 -> R74
#   SampleModel1: 270/84  -> 129/53  -> 56/24
#   SampleModel4: 441/112 -> 418/111 -> 423/113
#   samplemodel2: 3542/547 -> 2546/464 -> 2325/438
#   samplemodel3 0/0, samplemodel5 0/0, samplemodel6 2/2 (unchanged)
# R75 changed the metric: free_edges() now counts GAPS only (a periodic
# face's seam is not a gap) - measured seams 0 / 18 / 73.
# R76 tightened these after the cylinder trim policy (gaps/loops):
#   SampleModel1 56/24 -> 36/4, SampleModel4 405/113 -> 405/96,
#   samplemodel2 2252/438 -> 2227/396, samplemodel6 2/2 (policy off).
FREE_CEILING = {
    "SampleModel1.scdoc": (40, 6),
    "SampleModel4.scdoc": (410, 100),
    "samplemodel2.scdoc": (2300, 400),
    "samplemodel3.scdoc": (0, 0),
    "samplemodel5.scdoc": (0, 0),
    "samplemodel6.scdoc": (2, 2),
}


def _face_from(model, face, surf):
    from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                         BRepBuilderAPI_MakeFace,
                                         BRepBuilderAPI_MakeWire)

    mk = BRepBuilderAPI_MakeWire()
    for lp in model.loops_of_face(face):
        for ce in model.coedges_of_loop(lp):
            ee = model.e(ce.edge) if ce.edge >= 0 else None
            curve = import_sab_curve(model, ee)
            if curve is None:
                return None
            mk.Add(BRepBuilderAPI_MakeEdge(curve).Edge())
    if not mk.IsDone():
        return None
    mf = BRepBuilderAPI_MakeFace(surf, mk.Wire())
    return mf.Face() if mf.IsDone() else None


def import_sab_curve(model, edge):
    from scdm import import_sab

    return import_sab._edge_curve(model, edge) if edge is not None else None


def test_straight_edge_range_is_scaled_and_vertex_wins():
    """A scaled direction must not move the edge's endpoints (R73 fix 2)."""
    from scdm import import_sab
    from OCC.Core.Geom import Geom_Line
    from OCC.Core.gp import gp_Dir, gp_Pnt

    # 6 mm edge on +x, stored with a NON-unit direction (|dir| = 0.001) and a
    # range of [-4, 2] in that vector's units: the raw reading lands at -0.004
    # and +0.002 (1000x too long), the vertices say 0.002 and 0.008.
    edge = SimpleNamespace(idx=1, curve=5, v1=10, v2=11, pstart=-4.0, pend=2.0)
    curve = SimpleNamespace(kind="straight", origin=(0.004, 0.0, 0.0),
                            direction=(0.001, 0.0, 0.0))
    verts = {10: (0.008, 0.0, 0.0), 11: (0.002, 0.0, 0.0)}
    pts = {10: SimpleNamespace(origin=verts[10]),
           11: SimpleNamespace(origin=verts[11])}
    model = SimpleNamespace(
        e=lambda i: {5: curve, 10: pts[10], 11: pts[11]}.get(i),
        point_of_vertex=lambda v: v.origin if v is not None else None)
    trimmed = import_sab._edge_curve(model, edge)
    got = [trimmed.Value(trimmed.FirstParameter()).Coord(),
           trimmed.Value(trimmed.LastParameter()).Coord()]
    want = [verts[10], verts[11]]   # v1 first: the vertices give the order
    for a, b in zip(got, want):
        assert max(abs(a[i] - b[i]) for i in range(3)) < 1e-12, (got, want)
    # the range itself is still available when the vertices are missing
    model2 = SimpleNamespace(e=lambda i: {5: curve}.get(i),
                             point_of_vertex=lambda v: None)
    raw = import_sab._edge_curve(model2, edge)
    assert abs(raw.LastParameter() - 2.0) < 1e-12


@requires_occ
@requires_lib
def test_cone_radius_comes_from_the_ref_direction_vector():
    """Fix 1, as a measurement: boundary ON the |ref| surface, not the token."""
    from scdm import import_sab
    from scdm.document import load_scdoc
    from OCC.Core.Geom import Geom_CylindricalSurface
    from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    data = load_scdoc(os.path.join(LIB, "SampleModel1.scdoc"))
    on_ref = on_token = total = disagree = 0
    for m in data["models"]:
        for f in m.of_kind("face"):
            kind, s = import_sab._surface_kind(m, f)
            if (kind != "cone" or s is None or abs(s.semangle or 0.0) > 1e-9
                    or not s.origin or not s.normal or not s.xdir or not s.radius):
                continue
            axis = tuple(c / math.sqrt(sum(x * x for x in s.normal))
                         for c in s.normal)
            ax = gp_Ax3(gp_Ax2(gp_Pnt(*s.origin), gp_Dir(*axis), gp_Dir(*s.xdir)))
            xlen = math.sqrt(sum(c * c for c in s.xdir))
            if abs(xlen - s.radius) > 1e-9:
                disagree += 1

            def worst(radius):
                surf = Geom_CylindricalSurface(ax, radius)
                d = 0.0
                for lp in m.loops_of_face(f):
                    for ce in m.coedges_of_loop(lp):
                        ee = m.e(ce.edge) if ce.edge >= 0 else None
                        c = import_sab._edge_curve(m, ee) if ee is not None else None
                        if c is None:
                            return None
                        lo, hi = c.FirstParameter(), c.LastParameter()
                        for i in range(5):
                            pr = GeomAPI_ProjectPointOnSurf(
                                c.Value(lo + (hi - lo) * i / 4.0), surf)
                            if pr.NbPoints():
                                d = max(d, pr.LowerDistance())
                return d

            total += 1
            a, b = worst(xlen), worst(s.radius)
            if a is not None and a <= 1e-9:
                on_ref += 1
            if b is not None and b <= 1e-9:
                on_token += 1
    # SampleModel1 has 41 cone records: 38 cylinders (the 3 truncated cones
    # agree on both readings) and 36 of those disagree with the token.
    assert total == 38, total
    assert disagree == 36, disagree
    assert on_ref == total, on_ref
    assert on_token <= 6, on_token


@requires_occ
@requires_lib
def test_free_edge_ceiling_per_sample():
    """The watertightness budget: R73 numbers are ceilings, not targets."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    for name, (max_edges, max_loops) in sorted(FREE_CEILING.items()):
        data = load_scdoc(os.path.join(LIB, name))
        kdoc = import_sab.import_scdoc_bundle(data)
        edges = loops = 0
        for b in kdoc.bodies:
            if (b.name or "").startswith("网格导入"):
                continue
            edges += diff.free_edges(b.shape)
            loops += len(K._free_boundary_wires(b.shape))
        assert (edges, loops) <= (max_edges, max_loops), \
            "%s free edges/loops %d/%d > %d/%d" % (name, edges, loops,
                                                    max_edges, max_loops)


@requires_occ
@requires_lib
def test_ref_counters_are_per_import_not_per_process():
    """R73 catch: opening a second file must not inherit the first's losses."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    first = import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "SampleModel4.scdoc")))
    assert first.import_report["ref_unbuilt"] == 33
    second = import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "samplemodel6.scdoc")))
    assert second.import_report["ref_unbuilt"] == 0
    assert second.import_report["ref_faces"] == 0
    assert second.import_report["ref_built"] == 0

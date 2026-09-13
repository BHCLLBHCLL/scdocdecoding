"""R74: the ellipse-arc rebuild is exact on the official library (P367).

R73 fixed the straight edges; the arcs were still decoded from a recorded range
that can belong to another trimming of the same surface (samplemodel2 edge 2372
decoded 13.5 m away).  R74 takes the endpoints from the vertices and only
replaces the recorded range when it demonstrably misses them, which exposed two
more traps, both MEASURED here:

1. `Geom_TrimmedCurve` on a PERIODIC basis curve turns a DECREASING span into
   the COMPLEMENT arc (samplemodel2 edge 71: 4.71 -> 10.94, a 4.8 m sweep
   across a 42 mm strip, and the face was dropped).  Spans handed over must be
   increasing.
2. a planar face whose point bbox is exceeded by more than its own diagonal is
   not bounded by that branch at all - a gross-overshoot test settles it.  The
   same test on a CURVED face is harmful (its bbox is chord-based), so the test
   is restricted to planar faces.

Measured effect (tools/ref_family_diff.py, free edges / free loops):
  SampleModel1  129/53  ->  56/24      samplemodel2  2546/464 -> 2325/438
  samplemodel4  418/111 -> 423/113     samplemodel3/5 unchanged (0/0)
  samplemodel2 faces 1812 -> 1813 == the SAB count, 0 dropped
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = r"C:\\Program Files\\ANSYS Inc\\v195\\scdm\\Library\\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


def _ellipse_of(import_sab, model, edge):
    from OCC.Core.Geom import Geom_Ellipse
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    c = model.e(edge.curve) if edge.curve is not None and edge.curve >= 0 else None
    if c is None or c.kind != "ellipse" or not c.origin or not c.normal or not c.xdir:
        return None, None
    ratio = c.ratio if c.ratio else 1.0
    major = c.xdir
    mlen = math.sqrt(sum(v * v for v in major))
    if mlen < 1e-12 or ratio <= 0.0:
        return None, None
    ax = gp_Ax2(gp_Pnt(*c.origin), gp_Dir(*c.normal), gp_Dir(*major))
    return c, Geom_Ellipse(ax, mlen, mlen * ratio)


@requires_occ
def test_decreasing_span_gives_the_complement_arc():
    """The OCC trap R74 had to normalise away (periodic basis curve)."""
    from OCC.Core.Geom import Geom_Ellipse, Geom_TrimmedCurve
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt

    el = Geom_Ellipse(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0),
                             gp_Dir(1.0, 0.0, 0.0)), 1.0, 1.0)
    short = Geom_TrimmedCurve(el, -0.05, 0.05)      # increasing: the小 arc
    flipped = Geom_TrimmedCurve(el, 0.05, -0.05)    # decreasing: complement
    assert short.LastParameter() - short.FirstParameter() < 0.2
    assert flipped.LastParameter() - flipped.FirstParameter() > 6.0


@requires_occ
@requires_lib
def test_arc_spans_are_increasing_and_land_on_the_vertices():
    """Every arc the importer hands to the kernel is increasing (R74)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "SampleModel1.scdoc"))
    checked = wrong_range = 0
    for m in data["models"]:
        for f in m.of_kind("face"):
            for lp in m.loops_of_face(f):
                for ce in m.coedges_of_loop(lp):
                    ee = m.e(ce.edge) if ce.edge >= 0 else None
                    if ee is None:
                        continue
                    c, el = _ellipse_of(import_sab, m, ee)
                    if el is None:
                        continue
                    checked += 1
                    t0 = ee.pstart if ee.pstart is not None else 0.0
                    t1 = ee.pend if ee.pend is not None else 1.0
                    p1, p2 = import_sab._vertices_of(m, ee)
                    if not import_sab._arc_range_matches_vertices(el, p1, p2, t0, t1):
                        wrong_range += 1
                        span = import_sab._arc_span(m, ee, c, el, f)
                        assert span is None or span[0] <= span[1], (ee.idx, span)
                        assert span is not None, "edge %d has no usable arc" % ee.idx
                    cur = import_sab._edge_curve(m, ee, f)
                    assert cur is not None
                    a = cur.Value(cur.FirstParameter())
                    b = cur.Value(cur.LastParameter())

                    def _d(q, p):
                        return max(abs(p[i] - q.Coord(i + 1)) for i in range(3))

                    # the range may name the vertices in either order
                    assert min(max(_d(a, p1), _d(b, p2)),
                               max(_d(a, p2), _d(b, p1))) < 1e-6, ee.idx
    assert checked > 150, checked
    assert wrong_range == 44, wrong_range


@requires_occ
@requires_lib
def test_samplemodel2_is_face_exact():
    """R74: 1813 faces == the SAB count, and nothing is dropped any more."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    import_sab._faces_from_model.unbuilt = 0
    import_sab._faces_from_model.skipped = 0
    kdoc = import_sab.import_scdoc_bundle(data)
    faces = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        faces += len(K.explore(b.shape, "face"))
    assert faces == 1813
    assert import_sab._faces_from_model.unbuilt == 1      # the ref-family face
    assert import_sab._faces_from_model.skipped == 0


@requires_occ
@requires_lib
def test_the_complement_arc_regression_case_is_gone():
    """The gross-overshoot guard, as an outcome (samplemodel2 face 62).

    Face 62 is a 42 mm strip whose ellipse edge stores a 2*pi sweep; the
    complement reading built an 18.6 m2 face out of it and the face was
    dropped.  The guard keeps the branch inside the face's own bbox.
    """
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    checked = 0
    for m in data["models"]:
        f = m.e(62)
        if f is None or f.kind != "face":
            continue
        kind, plane = import_sab._surface_kind(m, f)
        assert kind == "plane"
        face = import_sab._planar_face_from_wires(m, f, plane)
        assert face is not None
        fbox = import_sab._face_bbox(f)
        bb = import_sab._shape_bbox(face, accurate=False)
        diag = math.sqrt(sum((fbox[1][i] - fbox[0][i]) ** 2 for i in range(3)))
        for i in range(3):
            assert bb[0][i] > fbox[0][i] - diag and bb[1][i] < fbox[1][i] + diag
        assert K.area(face) < 1.0, K.area(face)
        checked += 1
    assert checked == 2      # the strip on both sides of the model
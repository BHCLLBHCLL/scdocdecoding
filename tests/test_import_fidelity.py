"""P29/P30/P37: official-library import fidelity, correctness and performance.

Baseline measured 2026-09-12 (tools/import_fidelity.py --time). The floors are
the R7/P45 values - they must not regress:

  sample          SAB b/f    R6     R7/P45   R7/P46   load/import      drift
  SampleModel1    1/109      96     109      109      0.38 / 1.71 s    0.0%
  SampleModel4    2/177      92      92      143      1.18 / 1.43 s    0.0%
  samplemodel2   37/1813    1334    1721     1811     3.72 / 5.83 s    0.6%
  samplemodel3    1/111      11     111      111      0.43 / 0.12 s    0.0%
  samplemodel5   80/1288    1285    1288     1288     3.76 / 2.79 s    0.0%
  samplemodel6    1/28       28      28       28      0.25 / 0.06 s    0.0%

P46 added the analytic surfaces the official library actually uses: truncated
cones (the cone record stores sin/cos of the half angle, so token 10 is NOT the
angle), tori (two radii between the axis and the x direction) and spheres, plus
multi-ring planar faces and a curve-sampling fallback for two-edge sliver
loops.  SampleModel4 went 92 -> 156 and samplemodel2 1721 -> 1860.

samplemodel2 now rebuilds MORE faces than the SAB declares (1860 vs 1813): the
surplus is one SAB face cut into pieces by the bbox boolean (6 tori + 2 cones),
and its 0.6% drift is the same effect.  The remaining gap to --strict is the
official spline cluster (52 faces on SampleModel4) whose payload record is a
"nubs" scope rather than the "nurbs"+"both" pair our writer emits.

Four of the six samples are now EXACT (bodies, faces AND bbox).  R6's drift of
122% on samplemodel2 came from cylinder faces built as full 2*pi patches on a
7.14 m radius surface; P45 rebuilds them from the face's own bbox (axial range
by projection, angular range by intersecting the circle with the projected
bbox) and drops nothing outside a 50%-of-diagonal margin.

P45 also cross-validates straight-edge endpoints: the vertex point is compared
with the value derived from the edge's parameter range, and the vertex wins on
disagreement. That is what closed samplemodel3 (11 -> 111 faces) and lifted
samplemodel5 to exact. R5's higher counts on SampleModel1 included bogus faces
built from those mis-decoded ranges.

Remaining gaps are registered P46 items: SampleModel4 (81 spline/torus faces)
and samplemodel2 (93) still fail to rebuild.
"""
from __future__ import annotations

import os
import time
from types import SimpleNamespace

import pytest

from scdoc_parser import topology as T

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")
requires_occ = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("OCC"), reason="kernel absent")

# sample -> (sab bodies, sab faces, min bodies, min faces, max load, max import,
#            max bbox drift)
BASELINE = {
    "SampleModel1.scdoc": (1, 109, 1, 109, 5.0, 10.0, 0.01),
    "SampleModel4.scdoc": (2, 177, 2, 140, 5.0, 10.0, 0.01),
    "samplemodel2.scdoc": (37, 1813, 37, 1805, 15.0, 15.0, 0.01),
    "samplemodel3.scdoc": (1, 111, 1, 111, 5.0, 10.0, 0.01),
    "samplemodel5.scdoc": (80, 1288, 80, 1288, 15.0, 10.0, 0.01),
    "samplemodel6.scdoc": (1, 28, 1, 28, 5.0, 10.0, 0.01),
}


def test_entity_accessor_is_none_safe():
    """P29: optional pointers are None in official streams; e() must not raise."""
    model = T.SabModel.__new__(T.SabModel)
    model.entities = []
    assert model.e(None) is None
    assert model.e(-1) is None
    assert model.e(99) is None


def test_face_from_polygon_tolerates_repeated_points():
    """P29: official loops repeat points; dedupe instead of failing Close."""
    from scdm import kernel as K

    pts = [(0.0, 0.0, 0.0), (0.01, 0.0, 0.0), (0.01, 0.0, 0.0),
           (0.01, 0.01, 0.0), (0.0, 0.01, 0.0), (0.0, 0.0, 0.0)]
    face = K.face_from_polygon(pts)
    assert K.area(face) == pytest.approx(1e-4, rel=1e-6)
    with pytest.raises(K.KernelError):
        K.face_from_polygon([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)])


@requires_occ
def test_sew_bodies_keeps_every_face():
    """P29: sewing must not collapse to the first lobe (two separate squares)."""
    from scdm import kernel as K

    a = K.face_from_polygon([(0.0, 0.0, 0.0), (0.01, 0.0, 0.0),
                             (0.01, 0.01, 0.0), (0.0, 0.01, 0.0)])
    b = K.translate(a, (0.05, 0.0, 0.0))
    sewn = K.sew_bodies([a, b])
    assert len(K.explore(sewn, "face")) == 2


def test_pointer_roles_are_positional_and_variant_tolerant():
    """P37: two official face layouts must decode the same topology pointers.

    Layout A: P I I P P P P P P F F F V V F
    Layout B: P I I P I I P P P P P F F F V V F   (two ints inside the run)
    """
    def ent(kind, tokens):
        e = SimpleNamespace(kind=kind, idx=0, tokens=tokens)
        return SimpleNamespace(record=SimpleNamespace(tokens=tokens), kind=kind,
                              idx=0)

    model = T.SabModel.__new__(T.SabModel)
    model.entities = []

    def tok(kind, value=None):
        return SimpleNamespace(kind=kind, value=value)

    layout_a = ([tok('ptr')] + [tok('int'), tok('int')]
                + [tok('ptr')] * 6 + [tok('flag_a'), tok('flag_a'), tok('flag_a'),
                                      tok('vec3'), tok('vec3'), tok('flag_a')])
    layout_b = (layout_a[:3] + [layout_a[3], tok('int'), tok('int')]
                + layout_a[4:])
    run_a = model._ptr_run(SimpleNamespace(tokens=layout_a))
    run_b = model._ptr_run(SimpleNamespace(tokens=layout_b))
    # both layouts expose exactly six pointers, so the positional role mapping
    # (run[1]=v1/next, run[2]=..., run[4]=curve/surface) applies to both ...
    assert len(run_a) == len(run_b) == 6
    # ... even though layout B shifts every pointer two tokens to the right,
    # which is what the old fixed-index decode got wrong.
    assert run_a[1] == 4 and run_b[1] == 6


@requires_lib
@requires_occ
@pytest.mark.parametrize("name", sorted(BASELINE))
def test_import_fidelity_correctness_and_budget(name):
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle
    from scdm import kernel as K
    from scdm import additive as A

    (sb, sf, min_b, min_f, max_load, max_import, max_drift) = BASELINE[name]
    t0 = time.time()
    data = load_scdoc(os.path.join(LIB, name))
    t1 = time.time()
    kdoc = import_scdoc_bundle(data)
    t2 = time.time()

    bodies = faces = 0
    lo = [1e30] * 3
    hi = [-1e30] * 3
    slo = [1e30] * 3
    shi = [-1e30] * 3
    for m in data["models"]:
        for v in m.of_kind("vertex"):
            p = m.point_of_vertex(v)
            if p is None:
                continue
            for i in range(3):
                slo[i] = min(slo[i], p[i])
                shi[i] = max(shi[i], p[i])
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        bodies += 1
        faces += len(K.explore(b.shape, "face"))
        a, c = A.shape_bbox(b.shape)
        for i in range(3):
            lo[i] = min(lo[i], a[i])
            hi[i] = max(hi[i], c[i])

    assert bodies >= min_b, "%s bodies=%d" % (name, bodies)
    assert faces >= min_f, "%s faces=%d" % (name, faces)
    assert (t1 - t0) < max_load, "%s load %.2fs" % (name, t1 - t0)
    assert (t2 - t1) < max_import, "%s import %.2fs" % (name, t2 - t1)
    if bodies:
        span_s = max(shi[i] - slo[i] for i in range(3))
        span_i = max(hi[i] - lo[i] for i in range(3))
        drift = abs(span_i - span_s) / (span_s or 1.0)
        assert drift <= max_drift, "%s bbox drift %.1f%%" % (name, drift * 100)


@requires_lib
@requires_occ
def test_samplemodel6_is_exact():
    """R6: the first official sample reaches exact fidelity (1 body / 28 faces)."""
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle
    from scdm import kernel as K

    kdoc = import_scdoc_bundle(load_scdoc(os.path.join(LIB, "samplemodel6.scdoc")))
    assert len(kdoc.bodies) == 1
    assert len(K.explore(kdoc.bodies[0].shape, "face")) == 28


@requires_lib
@requires_occ
def test_mesh_fallback_is_opt_in_and_reported():
    """P30: the expensive whole-document mesh fallback is off by default."""
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    kdoc = import_scdoc_bundle(data)
    assert not any((b.name or "").startswith("网格导入") for b in kdoc.bodies)
    assert kdoc.import_warnings, "failed parts must be reported"


def test_circle_hull_arcs_merge_across_the_seam():
    """P45: the angular window of a cylinder patch is exact and contiguous.

    The regression case is the diamond projection of samplemodel6 face 4: its
    circle meets the hull on both sides of the 0/2*pi seam, which used to come
    back as two arcs and split one hole into two faces.
    """
    import math

    from scdm.import_sab import _circle_hull_arcs, _proj_hull

    d = 0.07071067811865475
    hull = _proj_hull([(0.0, 0.0), (d, -d), (2 * d, 0.0), (d, d)])
    arcs = _circle_hull_arcs(0.1, hull)
    assert len(arcs) == 1, arcs
    assert arcs[0][0] == pytest.approx(1.75 * math.pi, abs=1e-6)
    assert arcs[0][1] == pytest.approx(0.5 * math.pi, abs=1e-6)

    # a circle that misses the hull entirely has no window at all
    far = _proj_hull([(1.0, 1.0), (1.2, 1.0), (1.2, 1.2), (1.0, 1.2)])
    assert _circle_hull_arcs(0.1, far) == []

    # a circle strictly inside an uncut hull keeps the full ring
    square = _proj_hull([(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)])
    full = _circle_hull_arcs(0.05, square)
    assert len(full) == 1 and full[0][1] == pytest.approx(2.0 * math.pi)


@requires_lib
def test_straight_edge_endpoints_cross_validate_against_vertices():
    """P45: when the parameter range and the vertices disagree, the vertex wins.

    samplemodel3 is the worst official case (80 of its 104 straight edges), and
    it is also the sample whose face count jumped 11 -> 111 once fixed.
    """
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "samplemodel3.scdoc"))
    checked = disagreed = 0
    for m in data["models"]:
        for ed in m.of_kind("edge"):
            c = m.e(ed.curve) if ed.curve is not None and ed.curve >= 0 else None
            if (c is None or c.kind != "straight" or not c.origin
                    or not c.direction or ed.pstart is None or ed.pend is None):
                continue
            p1 = m.point_of_vertex(m.e(ed.v1))
            p2 = m.point_of_vertex(m.e(ed.v2))
            if p1 is None or p2 is None:
                continue
            q1 = tuple(c.origin[i] + c.direction[i] * ed.pstart
                       for i in range(3))
            q2 = tuple(c.origin[i] + c.direction[i] * ed.pend for i in range(3))
            if max(abs(q1[i] - p1[i]) for i in range(3)) > 1e-3:
                disagreed += 1
            checked += 1
            ep = m.edge_endpoints(ed)
            assert ep is not None
            for got, want in ((ep[0], p1), (ep[1], p2)):
                assert max(abs(got[i] - want[i]) for i in range(3)) < 1e-9
    assert checked > 50
    assert disagreed > 10, "samplemodel3 is the cross-validation regression case"


@requires_occ
def test_face_from_polygons_keeps_inner_rings():
    """P46: a planar face with holes is outer wire + inner wires, not ring[0]."""
    from scdm import kernel as K
    from scdm.import_sab import _face_from_polygons
    from types import SimpleNamespace

    outer = [(0.0, 0.0, 0.0), (0.01, 0.0, 0.0),
             (0.01, 0.01, 0.0), (0.0, 0.01, 0.0)]
    inner = [(0.003, 0.003, 0.0), (0.007, 0.003, 0.0),
             (0.007, 0.007, 0.0), (0.003, 0.007, 0.0)]
    plane = SimpleNamespace(kind="plane", origin=(0.0, 0.0, 0.0),
                            normal=(0.0, 0.0, 1.0))
    face = _face_from_polygons([inner, outer], plane)
    assert face is not None
    assert K.area(face) == pytest.approx(1e-4 - 1.6e-5, rel=1e-6)
    # a degenerate ring is dropped rather than passed to the kernel
    assert _face_from_polygons([[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]], plane) is None


@requires_lib
def test_cone_record_is_a_sine_cosine_pair():
    """P46: token 10/11 of a cone surface are sin/cos of the half angle.

    samplemodel6 carries both spellings - cos=+1 (plain) and cos=-1 (the same
    cylinder with the axis stored flipped); reading token 10 as the angle made
    the second one a 180-degree cone and lost 6 faces.
    """
    from scdm.document import load_scdoc
    from scdm.import_sab import _surface_kind

    data = load_scdoc(os.path.join(LIB, "samplemodel6.scdoc"))
    seen = {"plain": 0, "flipped": 0}
    for m in data["models"]:
        for f in m.of_kind("face"):
            kind, s = _surface_kind(m, f)
            if kind != "cone" or s is None:
                continue
            assert s.sin_angle is not None and s.cos_angle is not None
            assert abs(s.sin_angle ** 2 + s.cos_angle ** 2 - 1.0) < 1e-9
            if abs(s.sin_angle) < 1e-9 and s.cos_angle > 0:
                seen["plain"] += 1
            elif abs(s.sin_angle) < 1e-9 and s.cos_angle < 0:
                seen["flipped"] += 1
    assert seen["plain"] and seen["flipped"], seen


@requires_lib
@requires_occ
def test_official_spline_cluster_builds_from_the_nubs_scope():
    """P46b: the official spline payload is a 'nubs' scope, not nurbs+both.

    Verified against the SAT text the official SabSatConverter prints for the
    same file: degree 3/3, 33 + 4 knots, sum(mults) 38/12, i.e. 36 x 10 control
    points stored as plain XYZ triples (non-rational).
    """
    from scdm.document import load_scdoc
    from scdm.import_sab import _bspline_surfaces, _surface_kind

    data = load_scdoc(os.path.join(LIB, "SampleModel4.scdoc"))
    grids = []
    for m in data["models"]:
        for f in m.of_kind("face"):
            kind, s = _surface_kind(m, f)
            if kind != "spline":
                continue
            for surf in _bspline_surfaces(m, s):
                grids.append((surf.NbUPoles(), surf.NbVPoles(),
                              surf.UDegree(), surf.VDegree()))
    assert grids, "no official spline surface could be read"
    assert (36, 10, 3, 3) in grids, sorted(set(grids))[:6]
    assert all(u >= 2 and v >= 2 and du >= 1 and dv >= 1
               for (u, v, du, dv) in grids)


@requires_lib
def test_torus_radii_are_decoded():
    """P46: a torus stores two radii between the axis and the x direction."""
    from scdm.document import load_scdoc
    from scdm.import_sab import _surface_kind

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    tors = []
    for m in data["models"]:
        for f in m.of_kind("face"):
            kind, s = _surface_kind(m, f)
            if kind == "torus" and s is not None:
                tors.append(s)
    assert len(tors) > 10, len(tors)
    assert all(s.major and s.minor and s.major > s.minor for s in tors)


def test_import_summary_reports_parts_faces_and_fallback():
    """P47: the GUI line is built from the structured report, Qt-free."""
    from scdm.import_sab import import_summary

    report = {"parts": 25, "failed_parts": ["0:23"], "unbuilt_faces": 2,
              "dropped_faces": 4, "mesh_bodies": ["网格导入 0:23"]}
    text = import_summary(report, ["SAB 重建：2 个面未能重建"], None)
    assert "1/25 个部件未重建" in text
    assert "2 个面未重建" in text and "4 个面被丢弃" in text
    assert "未重建部件：0:23" in text
    assert "1 个部件走网格兜底" in text
    # nothing to say -> empty string, and an error still surfaces
    assert import_summary({}, [], None) == ""
    assert "内核不可用" in import_summary({}, [], "内核不可用（x）")
    # many failures are truncated but counted
    many = import_summary({"parts": 9, "failed_parts": ["a", "b", "c", "d", "e"]},
                          [], None)
    assert "5/9 个部件未重建" in many and "等" in many


@requires_lib
def test_facets_nodes_map_per_model():
    """P47: the facets stream is sectioned per body, so a part can be meshed
    alone.  Every triangle must belong to exactly one part."""
    from scdm.document import load_scdoc
    from scdm.import_sab import _facets_nodes_of_model

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    fac = data["fac"]
    total = sum(len(f.triangles) for f in fac.faces)
    per_part = [sum(len(x.triangles)
                    for x in _facets_nodes_of_model(m, fac))
                for m in data["models"]]
    assert total > 1000
    assert sum(per_part) == total, (sum(per_part), total)
    assert sum(1 for n in per_part if n) == len(per_part)


@requires_lib
@requires_occ
def test_mesh_fallback_meshes_only_the_failed_part(monkeypatch):
    """P47: 'always' adds one mesh body per FAILED part, not one for the file."""
    from scdm.document import load_scdoc
    from scdm import import_sab
    from scdm import kernel as K

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    target = data["models"][0]
    real = import_sab._faces_from_model

    def failing(model, body, box=None):
        if model is target:
            return []
        return real(model, body, box)

    monkeypatch.setattr(import_sab, "_faces_from_model", failing)
    kdoc = import_sab.import_scdoc_bundle(data, mesh_fallback="always")
    mesh = [b for b in kdoc.bodies if (b.name or "").startswith("网格导入")]
    assert len(mesh) == 1, [b.name for b in mesh]
    assert kdoc.import_report["failed_parts"] == ["2:399"]
    assert kdoc.import_report["mesh_bodies"] == [mesh[0].name]
    # the mesh body carries only that part's triangles, not the file's
    nodes = import_sab._facets_nodes_of_model(target, data["fac"])
    expected = sum(len(n.triangles) for n in nodes)
    got = len(K.explore(mesh[0].shape, "face"))
    assert abs(got - expected) <= max(1, expected * 0.1), (got, expected)
    total = sum(len(f.triangles) for f in data["fac"].faces)
    assert got < total / 2


@requires_lib
@requires_occ
def test_import_reports_a_part_to_body_hierarchy():
    """R22/P127: the read-only official hierarchy is available to the GUI."""
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle

    kdoc = import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "samplemodel2.scdoc")))
    hier = kdoc.import_report.get("hierarchy") or []
    assert len(hier) > 10, len(hier)
    assert all(h["name"] and h["bodies"] for h in hier)
    # every imported body belongs to exactly one part
    ids = [b for h in hier for b in h["bodies"]]
    assert len(ids) == len(set(ids)) == len(kdoc.bodies)


@requires_lib
@requires_occ
def test_p133_hierarchy_groups_toggle_visibility_only():
    """R23/P133: part groups show/hide bodies and never touch geometry."""
    from scdm.document import load_scdoc
    from scdm.import_sab import (apply_group_visibility,
                                 import_hierarchy_groups,
                                 import_scdoc_bundle)

    kdoc = import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "samplemodel2.scdoc")))
    groups = import_hierarchy_groups(kdoc)
    assert len(groups) == len(kdoc.import_report["hierarchy"]) > 10
    assert all(g["imported"] and g["items"] for g in groups)

    g = groups[0]
    ids = {bid for _k, bid in g["items"]}
    shapes = {b.id: b.shape for b in kdoc.bodies}
    assert apply_group_visibility(kdoc, g, False) == len(ids)
    assert all(b.visible is (b.id not in ids) for b in kdoc.bodies)
    apply_group_visibility(kdoc, g, True)
    assert all(b.visible for b in kdoc.bodies)
    assert {b.id: b.shape for b in kdoc.bodies} == shapes, "geometry must not change"


@requires_lib
@requires_occ
def test_import_warnings_report_unbuilt_faces():
    """P45: decoder loss is surfaced in doc.import_warnings, not swallowed."""
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle

    kdoc = import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "samplemodel2.scdoc")))
    assert any("未能重建" in w for w in kdoc.import_warnings), \
        kdoc.import_warnings

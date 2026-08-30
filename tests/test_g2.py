"""G2 series unit tests (kernel-level, GUI-agnostic)."""
from __future__ import annotations

import numpy as np
import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def test_edge_polyline_box_edge():
    box = K.make_box(10 / 1000, 10 / 1000, 10 / 1000)
    edges = K.explore(box, "edge")
    assert edges
    pts = K.edge_polyline(edges[0], deflection=1e-4)
    assert len(pts) >= 2
    d = [abs(a - b) for a, b in zip(pts[0], pts[-1])]
    assert max(d) > 1e-3 or len(pts) > 2  # endpoints differ (non-degenerate)


def test_edge_polyline_invalid_returns_empty():
    assert K.edge_polyline(None) == []


# --- G2-07 mesh edit ops --------------------------------------------------------

from scdm import facets as F  # noqa: E402


def _cube_shared():
    """Unit cube as 12 triangles over 8 shared corners."""
    v = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)],
                 dtype=np.float64)
    def i(x, y, z):
        return x * 4 + y * 2 + z
    quads = [
        (i(0, 0, 0), i(1, 0, 0), i(1, 1, 0), i(0, 1, 0)),
        (i(0, 0, 1), i(1, 0, 1), i(1, 1, 1), i(0, 1, 1)),
        (i(0, 0, 0), i(0, 1, 0), i(0, 1, 1), i(0, 0, 1)),
        (i(1, 0, 0), i(1, 1, 0), i(1, 1, 1), i(1, 0, 1)),
        (i(0, 0, 0), i(1, 0, 0), i(1, 0, 1), i(0, 0, 1)),
        (i(0, 1, 0), i(1, 1, 0), i(1, 1, 1), i(0, 1, 1)),
    ]
    tris = []
    for q in quads:
        tris.append((q[0], q[1], q[2]))
        tris.append((q[0], q[2], q[3]))
    return v, np.array(tris, dtype=np.int64)


def _cube_soup():
    """Same cube exploded into a per-triangle vertex soup (36 verts)."""
    v, t = _cube_shared()
    flat_v = v[t.reshape(-1)]
    flat_t = np.arange(len(flat_v), dtype=np.int64).reshape(-1, 3)
    return flat_v, flat_t


def test_weld_merges_soup():
    vs, ts = _cube_soup()
    wv, wt = F.weld(vs, ts, tol=1e-6)
    assert len(wv) == 8
    assert len(wt) == 12
    wv2, wt2 = F.weld(wv, wt, tol=1e-6)
    assert len(wv2) == 8 and len(wt2) == 12  # idempotent


def test_laplacian_smooth_shrinks_but_keeps_centroid():
    v, t = _cube_shared()
    c0 = v.mean(axis=0)
    v1 = F.laplacian_smooth(v, t, iters=5, factor=0.5)
    assert not np.allclose(v, v1)
    assert np.allclose(v1.mean(axis=0), c0, atol=1e-9)  # symmetric shape keeps centre


def test_reduce_grid_collapses_and_preserves_small_cell():
    v, t = _cube_shared()
    rv, rt = F.reduce_grid(v, t, cell=1.5)
    assert len(rv) == 1 and len(rt) == 0  # whole cube in one cell
    rv2, rt2 = F.reduce_grid(v, t, cell=0.5)
    assert len(rv2) == 8 and len(rt2) == 12  # untouched


def test_fill_holes_closes_open_cube():
    vs, ts = _cube_soup()
    wv, wt = F.weld(vs, ts, tol=1e-6)
    # drop the top face (2 triangles: indices 2,3 per quad order)
    open_t = np.delete(wt, [2, 3], axis=0)
    assert len(F.boundary_loops(open_t)) == 1
    filled, n = F.fill_holes(wv, open_t)
    assert n == 2
    assert F.boundary_loops(filled) == []


def test_mesh_to_shell_from_welded_cube():
    vs, ts = _cube_soup()
    wv, wt = F.weld(vs, ts, tol=1e-6)
    shell = F.mesh_to_shell(wv, wt)
    faces = K.explore(shell, "face")
    assert len(faces) == 12


# --- G3-01 tool option semantics -------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.tools.direct import get_tool  # noqa: E402


def test_pull_to_face_and_copy():
    ses = SimpleNamespace(kdoc=KernelDoc(), scale=1000.0)
    box = ses.kdoc.add_body(K.make_box(10 / 1000, 10 / 1000, 10 / 1000), name="B")
    faces = K.explore(box.shape, "face")
    zc = [K.face_normal_center(f)[1][2] for f in faces]
    lo = zc.index(min(zc))
    # target: top plane of a 3mm plate sitting at z=0..3mm
    plate = K.make_box(20 / 1000, 20 / 1000, 3 / 1000, origin=(-5 / 1000, -5 / 1000, 0))
    pn = pc = None
    for f in K.explore(plate, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.9:
            pn, pc = n, c
            break
    get_tool("tool.pull").apply(
        ses, {"body_id": box.id, "face_i": lo,
              "to_face_target": {"normal": pn, "center": pc}},
        {"to_face": True, "distance": 5.0})
    assert abs(K.volume(box.shape) - 0.01 * 0.01 * 0.007) < 1e-10
    # copy pull: leaves the original and adds a pulled copy
    n0 = len(ses.kdoc.bodies)
    zc2 = [K.face_normal_center(f)[1][2] for f in K.explore(box.shape, "face")]
    get_tool("tool.pull").apply(ses, {"body_id": box.id, "face_i": zc2.index(max(zc2))},
                                {"copy": True, "distance": 5.0})
    assert len(ses.kdoc.bodies) == n0 + 1


def test_move_to_point_and_to_face():
    ses = SimpleNamespace(kdoc=KernelDoc(), scale=1000.0)
    box = ses.kdoc.add_body(K.make_box(10 / 1000, 10 / 1000, 10 / 1000), name="B")
    get_tool("tool.move").apply(ses, {"body_id": box.id, "pick_point": (0.05, 0.0, 0.005)},
                                {"to_point": True})
    c = K.cog(box.shape)
    assert abs(c[0] - 0.05) < 1e-9
    # to_face: move up until the bottom face meets a plate top at z=3mm
    plate = K.make_box(20 / 1000, 20 / 1000, 3 / 1000, origin=(-5 / 1000, -5 / 1000, 0))
    for f in K.explore(plate, "face"):
        n, cc = K.face_normal_center(f)
        if n[2] > 0.9:
            break
    get_tool("tool.move").apply(ses, {"body_id": box.id,
                                      "pick_face": {"normal": n, "center": cc}},
                                {"to_face": True})
    cz = K.cog(box.shape)[2]
    assert abs(cz - (0.003 + 0.005)) < 1e-9


# --- G3-02 edge ring selection ----------------------------------------------------

def test_edge_loop_box_face_ring():
    box = K.make_box(10 / 1000, 10 / 1000, 10 / 1000)
    n_edges = len(K.explore(box, "edge"))
    for ei in (0, 5, 13, 23):
        if ei >= n_edges:
            continue
        loop = K.edge_loop(box, ei)
        assert 3 <= len(loop) <= 8  # a face boundary ring (box: 4 edges)
        assert ei in loop or K.edge_loop(box, ei)  # picked edge maps into a ring
    loop = K.edge_loop(box, 0)
    # all loop edges must be valid indices
    assert all(0 <= i < n_edges for i in loop)
    assert len(set(loop)) == len(loop)  # no duplicates


def test_edge_loop_out_of_range():
    box = K.make_box(10 / 1000, 10 / 1000, 10 / 1000)
    assert K.edge_loop(box, 9999) == []


# --- G4-01/02 sketch plane mapping + drawing helpers ------------------------------

from scdm import sketch as S  # noqa: E402


def test_extrude_sketch_on_zx_plane():
    curves = [("rect", (0, 0), (0.01, 0.01))]
    solid = S.extrude_sketch(curves, 0.005, "zx")
    assert abs(K.volume(solid) - 0.01 * 0.01 * 0.005) < 1e-12
    lo, hi = None, None
    import scdm.additive as A
    lo, hi = A.shape_bbox(solid)
    assert abs((hi[1] - lo[1]) - 0.005) < 1e-9  # thickness along Y (zx normal)


def test_extrude_sketch_on_yz_plane():
    curves = [("rect", (0, 0), (0.01, 0.02))]
    solid = S.extrude_sketch(curves, 0.004, "yz")
    assert abs(K.volume(solid) - 0.01 * 0.02 * 0.004) < 1e-12


def test_offset_polygon_grows_square():
    sq = [[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01]]
    out = S.offset_polygon(sq, 0.001)
    xs = [p[0] for p in out]
    ys = [p[1] for p in out]
    assert abs(min(xs) + 0.001) < 1e-6 and abs(max(xs) - 0.011) < 1e-6
    assert abs(min(ys) + 0.001) < 1e-6 and abs(max(ys) - 0.011) < 1e-6


def test_tangent_from_point():
    segs = S.tangent_from_point([0.0, 0.0], [0.05, 0.0], 0.01)
    assert len(segs) == 2
    for a, b in segs:
        # tangency: distance from circle centre to the tangent point == r
        assert abs(math.hypot(b[0] - 0.05, b[1] - 0.0) - 0.01) < 1e-9
    assert S.tangent_from_point([0.05, 0.0], [0.05, 0.0], 0.01) == []  # inside


def test_circumcenter():
    cc = S.circumcenter([0.0, 0.0], [0.02, 0.0], [0.01, 0.02])
    assert cc is not None
    (cx, cy), r = cc
    assert abs(cx - 0.01) < 1e-9 and abs(cy - 0.0075) < 1e-9
    assert abs(r - 0.0125) < 1e-9
    assert S.circumcenter([0, 0], [0.01, 0], [0.02, 0]) is None  # collinear


def test_catmull_rom_smooths_chain():
    sm = S.catmull_rom([[0.0, 0.0], [0.01, 0.008], [0.02, 0.0]])
    assert len(sm) > 3
    assert abs(sm[0][0]) < 1e-12 and abs(sm[-1][0] - 0.02) < 1e-9


import math  # noqa: E402


# --- G5-02 repair ------------------------------------------------------------------

def test_fill_missing_faces_caps_open_box():
    box = K.make_box(10 / 1000, 10 / 1000, 10 / 1000)
    faces = K.explore(box, "face")
    open_shell = K.sew_faces(faces[:5])
    solid, added = K.fill_missing_faces(open_shell)
    assert added == 1
    assert abs(K.volume(solid) - 0.01 ** 3) < 1e-12


def test_solidify_shell():
    box = K.make_box(10 / 1000, 10 / 1000, 10 / 1000)
    solid = K.solidify_shell(K.sew_faces(K.explore(box, "face")))
    assert abs(K.volume(solid) - 0.01 ** 3) < 1e-12


# --- G6-02 HLR drawing views -------------------------------------------------------

def test_hlr_three_views_box():
    from scdm.drawing import extents, three_views
    box = K.make_box(0.01, 0.02, 0.03)
    views = dict(three_views(box))
    e_front = extents(views["主视"])
    e_top = extents(views["俯视"])
    e_right = extents(views["右视"])
    assert abs((e_front[2] - e_front[0]) - 0.01) < 1e-6   # X width
    assert abs((e_front[3] - e_front[1]) - 0.03) < 1e-6   # Z height
    assert abs((e_top[2] - e_top[0]) - 0.01) < 1e-6 and abs((e_top[3] - e_top[1]) - 0.02) < 1e-6
    assert abs((e_right[2] - e_right[0]) - 0.02) < 1e-6 and abs((e_right[3] - e_right[1]) - 0.03) < 1e-6
    # closed box: each view's outline is a closed rectangle loop
    for v in (e_front, e_top, e_right):
        assert v is not None


# --- G6-03 share topology / midsurface ---------------------------------------------

def test_share_topology_imprints_overlapping_boxes():
    b1 = K.make_box(0.01, 0.01, 0.01, origin=(0, 0, 0))
    b2 = K.make_box(0.01, 0.01, 0.01, origin=(0.005, 0, 0))
    groups = K.share_topology([b1, b2])
    assert len(groups) == 2
    assert all(len(g) == 2 for g in groups)  # each box split at the shared interface
    total = sum(K.volume(p) for g in groups for p in g)
    assert abs(total - 2 * 0.01 ** 3) < 1e-12  # volume preserved


def test_midsurface_plate():
    plate = K.make_box(0.02, 0.02, 0.002)  # 20x20x2mm plate
    face, thickness = K.midsurface_plate(plate)
    assert abs(thickness - 0.002) < 1e-9
    assert abs(K.area(face) - 0.02 * 0.02) < 1e-9


def test_midsurface_concave_plate():
    # L-shaped plate: two fused 20x20x2 blocks offset by (10,10) -> 700 mm2 outline
    b1 = K.make_box(0.02, 0.02, 0.002)
    b2 = K.make_box(0.02, 0.02, 0.002, origin=(0.01, 0.01, 0))
    face, thickness = K.midsurface_plate(K.fuse(b1, b2))
    assert abs(thickness - 0.002) < 1e-9
    assert abs(K.area(face) - 0.0007) < 1e-9
    import scdm.additive as A
    lo, hi = A.shape_bbox(face)
    assert abs(lo[2] - 0.001) < 1e-9 and abs(hi[2] - 0.001) < 1e-9  # sits at mid plane


# --- custom sketch planes + section outline ----------------------------------------

def test_extrude_sketch_custom_offset_plane():
    axes = S.sketch_axes("custom", (0, 0, 0.005), (0, 0, 1), (1, 0, 0))
    solid = S.extrude_sketch([("rect", (0, 0), (0.01, 0.01))], 0.01, axes=axes)
    import scdm.additive as A
    lo, hi = A.shape_bbox(solid)
    assert abs(lo[2] - 0.005) < 1e-9 and abs(hi[2] - 0.015) < 1e-9
    assert abs(K.volume(solid) - 0.01 ** 3) < 1e-12


def test_section_outline_and_chain():
    box = K.make_box(0.01, 0.01, 0.01)
    polys = K.section_outline(box, (0, 0, 0.005), (0, 0, 1))
    assert len(polys) == 4  # square cross-section, 4 straight edges
    rings = S.chain_polylines(polys)
    assert len(rings) == 1
    ring = rings[0]
    assert len(ring) == 4  # closed square without duplicated closing point
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    assert abs(max(xs) - min(xs) - 0.01) < 1e-6
    assert abs(max(ys) - min(ys) - 0.01) < 1e-6
    # uv projection onto the custom axes matches the slice
    axes = S.sketch_axes("custom", (0, 0, 0.005), (0, 0, 1), (1, 0, 0))
    uv = [S.world_to_uv(axes, p) for p in ring]
    assert abs(max(u for u, _ in uv) - 0.01) < 1e-6


# --- G6-01b: cylinder SAB writing (official Circular.scdoc layout) ------------------

def test_cylinder_scdoc_matches_official_record_shapes():
    import os
    import tempfile
    from collections import Counter

    from scdoc_parser import sab as sab_mod, opc
    from scdm.scdoc_write import write_scdoc

    doc = KernelDoc()
    doc.add_body(K.make_cylinder(0.005, 0.01), name="Cyl1")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        write_scdoc(path, doc, name="cyl")
        pkg = opc.parse_package(path)
        sf = sab_mod.tokenize(pkg.read(pkg.find_geometry()[0].name))
        kinds = Counter(r.kind for r in sf.records)
        assert kinds["cone"] == 1 and kinds["ellipse"] == 2
        assert kinds["face"] == 3 and kinds["edge"] == 3   # 2 circles + seam
        assert kinds["plane"] == 2 and kinds["loop"] == 3 and kinds["coedge"] == 6
        assert kinds["straight"] == 1 and kinds["vertex"] == 2 and kinds["point"] == 2
        cone = [r for r in sf.records if r.kind == "cone"][0]
        toks = [t.kind for t in cone.tokens]
        assert toks.count("double") == 4  # ratio, sine, cosine, R
        ellipse = [r for r in sf.records if r.kind == "ellipse"][0]
        assert [t.kind for t in ellipse.tokens].count("vec3") == 1
        assert [t.kind for t in ellipse.tokens].count("vec3b") == 2
    finally:
        os.remove(path)


def test_mixed_box_and_cylinder_scdoc():
    import os
    import tempfile
    from collections import Counter

    from scdoc_parser import sab as sab_mod, opc
    from scdm.scdoc_write import write_scdoc

    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="Box1")
    doc.add_body(K.make_cylinder(0.005, 0.01), name="Cyl1")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        write_scdoc(path, doc, name="mixed")
        pkg = opc.parse_package(path)
        sf = sab_mod.tokenize(pkg.read(pkg.find_geometry()[0].name))
        kinds = Counter(r.kind for r in sf.records)
        assert kinds["face"] == 9 and kinds["edge"] == 15   # 12 planar + 3 cyl
        assert kinds["body"] == 2 and kinds["cone"] == 1
        assert kinds["straight"] == 13 and kinds["ellipse"] == 2
        assert kinds["coedge"] == 30 and kinds["loop"] == 9
    finally:
        os.remove(path)


def test_cylinder_scdoc_self_read_via_facets():
    """Written cylinder scdoc falls back to a facet-mesh body on self-read."""
    import os
    import tempfile

    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle
    from scdm.scdoc_write import write_scdoc

    doc = KernelDoc()
    doc.add_body(K.make_cylinder(0.005, 0.01), name="Cyl1")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        write_scdoc(path, doc, name="cyl")
        k2 = import_scdoc_bundle(load_scdoc(path))
        assert len(k2.bodies) == 1
        assert "网格" in k2.bodies[0].name
        v = K.volume(k2.bodies[0].shape)
        assert abs(v - 3.14159 * 0.005 ** 2 * 0.01) < 0.05e-6  # mesh approximation
    finally:
        os.remove(path)

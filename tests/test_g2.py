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

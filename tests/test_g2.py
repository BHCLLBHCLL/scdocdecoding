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

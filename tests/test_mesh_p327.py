"""P327/R62: mesh quality gates (countable verdicts) + volume meshing.

A gate returns the LIST of violations (index, metric, value, limit, excess) so
the caller sees what failed; the volume fill is compared against K.volume() with
the relative gap reported as the discretization error.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import mesh as ME  # noqa: E402


def _sliver():
    """One very thin triangle: huge aspect, tiny area, near-zero jacobian."""
    return {"vertices": [(0.0, 0.0, 0.0), (0.02, 0.0, 0.0), (0.01, 1e-5, 0.0)],
            "triangles": [(0, 1, 2)], "deflection": 0.0}


def test_p327_gates_pass_on_a_box_and_flag_the_closed_form_excess():
    box = K.make_box(0.02, 0.02, 0.02)
    mesh = ME.mesh_shape(box, deflection=0.001)
    verdict = ME.check_quality(mesh)
    assert verdict["ok"] is True and verdict["count"] == 0
    assert verdict["triangles"] == 12 and verdict["degenerate"] == 0
    # a stricter minimum angle flags every one of the 12 triangles, each with its
    # own closed-form excess (45 - 50 = -5 -> 5 degrees over the limit)
    strict = ME.check_quality(mesh, {"min_angle_min": 50.0})
    assert strict["ok"] is False and strict["count"] == 12
    v = strict["violations"][0]
    assert v["metric"] == "min_angle_deg"
    assert v["value"] == pytest.approx(45.0, rel=1e-12)
    assert v["limit"] == 50.0 and v["excess"] == pytest.approx(5.0, rel=1e-9)
    assert 0 <= v["index"] < 12
    # quality_min can also be pushed over the box's sqrt(3)/2
    q = ME.check_quality(mesh, {"quality_min": 0.9})
    assert q["count"] == 12
    assert q["violations"][0]["excess"] == pytest.approx(0.9 - math.sqrt(3) / 2,
                                                         rel=1e-9)


def test_p327_gates_report_every_metric_of_a_sliver():
    mesh = _sliver()
    verdict = ME.check_quality(mesh)
    assert verdict["ok"] is False
    metrics = {v["metric"] for v in verdict["violations"]}
    assert {"aspect", "min_angle_deg", "jacobian", "quality"} <= metrics
    by = {v["metric"]: v for v in verdict["violations"]}
    # closed form: a = 0.02, b ~ 0.01, c ~ 0.01 -> aspect far above the limit
    assert by["aspect"]["value"] > 24.0
    assert by["jacobian"]["value"] < 0.03
    assert by["min_angle_deg"]["value"] < 1.0
    # a gate is a decision: relax it and the verdict flips
    loose = ME.check_quality(mesh, {"aspect_max": 1e6, "min_angle_min": 0.0,
                                    "jacobian_min": 0.0, "quality_min": 0.0})
    assert loose["ok"] is True
    with pytest.raises(K.KernelError):
        ME.check_quality({"vertices": [], "triangles": []})


def test_p327_tet_fill_of_a_grid_aligned_box_is_exact():
    box = K.make_box(0.02, 0.02, 0.02)
    fill = ME.tet_fill(box, 0.005)
    assert fill["cells"] == 64                     # 4 x 4 x 4 cells
    stats = ME.tet_stats(fill, shape=box)
    assert stats["tets"] == 64 * 6                 # each cell -> 6 tetrahedra
    assert stats["degenerate"] == 0
    assert stats["volume"] == pytest.approx(8.0e-6, rel=1e-12)
    assert stats["volume_rel_error"] == pytest.approx(0.0, abs=1e-15)
    assert stats["min_volume"] == pytest.approx(0.005 ** 3 / 6.0, rel=1e-12)
    # the six tetrahedra of a cell are equal analytically, but they differ in
    # the last ULP: compare with a tolerance, not with ==
    assert stats["max_volume"] == pytest.approx(stats["min_volume"], rel=1e-12)
    # the per-tetrahedron closed form on a hand example
    p, q, r, s = (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)
    assert ME.tet_volume(p, q, r, s) == pytest.approx(1.0 / 6.0, rel=1e-15)


def test_p327_tet_fill_converges_on_a_curved_shape():
    sphere = K.make_sphere(0.01)
    ref = K.volume(sphere)
    coarse = ME.tet_stats(ME.tet_fill(sphere, 0.005), shape=sphere)
    fine = ME.tet_stats(ME.tet_fill(sphere, 0.00125), shape=sphere)
    # counts are countable: an 8x smaller cell gives ~8x more cells
    assert fine["cells"] > 20 * coarse["cells"]
    assert fine["tets"] == fine["cells"] * 6
    for st in (coarse, fine):
        assert st["degenerate"] == 0
        assert st["volume"] == pytest.approx(ref, rel=0.10)
    assert fine["volume_rel_error"] < coarse["volume_rel_error"]
    assert fine["volume_rel_error"] < 0.03


def test_p327_volume_mesh_illegal_input():
    box = K.make_box(0.02, 0.02, 0.02)
    with pytest.raises(K.KernelError):
        ME.tet_fill(box, 0.0)
    with pytest.raises(K.KernelError):
        ME.tet_fill(box, -0.001)
    with pytest.raises(K.KernelError):
        ME.tet_fill(None, 0.001)
    with pytest.raises(K.KernelError):      # cells bigger than the body
        ME.tet_fill(K.make_sphere(0.0005), 0.01)
    with pytest.raises(K.KernelError):
        ME.tet_stats({"vertices": [], "tets": []})


def test_p327_true_bounding_box_handles_curved_shapes():
    """A full sphere has only pole vertices; the vertex-based box collapsed."""
    sphere = K.make_sphere(0.01)
    lo, hi = K.bounding_box(sphere)
    assert hi[0] == pytest.approx(0.01, abs=1e-6)
    assert lo[2] == pytest.approx(-0.01, abs=1e-6)
    box = K.make_box(0.02, 0.03, 0.04)
    lo, hi = K.bounding_box(box)
    # Bnd_Box includes the shape tolerance (~1e-7 m) on each side
    assert (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) == pytest.approx(
        (0.02, 0.03, 0.04), abs=1e-6)

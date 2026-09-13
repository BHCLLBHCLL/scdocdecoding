"""P323/P324/R61: surface meshing and countable quality metrics.

Acceptance: the triangle-area sum is checked against K.area() WITH the relative
discretization error reported (not hidden), degenerate triangles are counted, the
closed-form per-triangle metrics are verified on an equilateral triangle, and the
report round trips.
"""
from __future__ import annotations

import math
import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import mesh as ME  # noqa: E402

A = 0.01


def _equilateral():
    h = A * math.sqrt(3.0) / 2.0
    return {"vertices": [(0.0, 0.0, 0.0), (A, 0.0, 0.0), (A / 2.0, h, 0.0)],
            "triangles": [(0, 1, 2)], "deflection": 0.0}


def test_p323_box_mesh_is_countable_and_exact():
    box = K.make_box(0.02, 0.02, 0.02)
    mesh = ME.mesh_shape(box, deflection=0.001)
    stats = ME.mesh_stats(mesh, shape=box)
    # a box tessellates into 12 triangles over 8 WELDED vertices
    assert stats["triangles"] == 12
    assert stats["vertices"] == 8
    assert stats["degenerate"] == 0
    # planar faces are exact: no discretization error at all
    assert stats["area"] == pytest.approx(6 * 0.02 ** 2, rel=1e-12)
    assert stats["area_ref"] == pytest.approx(6 * 0.02 ** 2, rel=1e-12)
    assert stats["area_rel_error"] == pytest.approx(0.0, abs=1e-15)
    # a box face splits into right isoceles triangles: closed-form metrics
    assert stats["quality"]["min"] == pytest.approx(math.sqrt(3) / 2, rel=1e-12)
    assert stats["min_angle_deg"]["min"] == pytest.approx(45.0, rel=1e-12)
    assert stats["jacobian"]["min"] == pytest.approx(math.sqrt(2) / 2, rel=1e-12)


def test_p323_curved_shape_reports_its_discretization_error():
    # the angular criterion (0.5 rad -> ~13 segments on this circle) dominates
    # until the linear deflection is finer than its sagitta (~2.9e-4), so the
    # coarse/fine pair has to straddle that: 1e-3 vs 1e-5
    cyl = K.make_cylinder(0.01, 0.03)
    fine = ME.mesh_stats(ME.mesh_shape(cyl, deflection=1e-5), shape=cyl)
    coarse = ME.mesh_stats(ME.mesh_shape(cyl, deflection=1e-3), shape=cyl)
    ref = K.area(cyl)
    for st in (fine, coarse):
        assert st["degenerate"] == 0
        assert st["area"] < ref                      # chords cut inside
        assert st["area_rel_error"] < 0.05
        assert st["area"] == pytest.approx(st["area_ref"], rel=0.05)
    # refining the deflection shrinks the error and adds triangles
    assert fine["area_rel_error"] < coarse["area_rel_error"]
    assert fine["triangles"] > coarse["triangles"]
    assert fine["quality"]["min"] < 1.0


def test_p323_equilateral_metrics_are_closed_form():
    m = ME.triangle_metrics(*_equilateral()["vertices"])
    assert m["area"] == pytest.approx(A * A * math.sqrt(3) / 4.0, rel=1e-12)
    assert m["quality"] == pytest.approx(1.0, rel=1e-12)
    assert m["aspect"] == pytest.approx(math.sqrt(3.0), rel=1e-12)
    assert m["min_angle_deg"] == pytest.approx(60.0, rel=1e-12)
    assert m["jacobian"] == pytest.approx(math.sin(math.radians(60.0)), rel=1e-12)
    assert m["max_edge"] == pytest.approx(A, rel=1e-12)


def test_p323_distribution_is_closed_form_on_a_hand_sample():
    d = ME.distribution([4.0, 1.0, 3.0, 2.0])
    assert d["min"] == 1.0 and d["max"] == 4.0
    assert d["median"] == pytest.approx(2.5, rel=1e-15)     # (2+3)/2
    assert d["p5"] == pytest.approx(1.15, rel=1e-12)
    assert d["p95"] == pytest.approx(3.85, rel=1e-12)
    assert ME.distribution([]) == {"min": 0.0, "p5": 0.0, "median": 0.0,
                                   "p95": 0.0, "max": 0.0}
    assert ME.distribution([7.0])["median"] == 7.0


def test_p323_mesh_illegal_and_report_round_trip():
    empty = K.compound([])
    with pytest.raises(K.KernelError):
        ME.mesh_shape(empty)
    with pytest.raises(K.KernelError):
        ME.mesh_shape(None)
    eq = _equilateral()
    eq["triangles"] = []
    with pytest.raises(K.KernelError):
        ME.mesh_stats(eq)
    # every triangle degenerate -> refused instead of reporting zeros
    with pytest.raises(K.KernelError):
        ME.mesh_stats(_equilateral(), tol_area=1.0)
    box = K.make_box(0.02, 0.02, 0.02)
    rep = ME.quality_report(box, deflection=0.001, name="box")
    assert rep["name"] == "box" and rep["triangles"] == 12
    tmp = tempfile.mkdtemp(prefix="p323_")
    try:
        jp = os.path.join(tmp, "r.json")
        cp = os.path.join(tmp, "r.csv")
        ME.write_report(jp, rep)
        ME.write_report(cp, rep, fmt="csv")
        back = ME.read_report(jp)
        assert back == rep
        csv_text = open(cp, encoding="utf-8").read()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert "quality" in csv_text and "area_rel_error" in csv_text

"""H-gap#1: full sketch constraint solver (LM, DOF, conflicts, params)."""
from __future__ import annotations

import math

import pytest

from scdm import sketch as S
from scdm.params import ParamTable
from scdm.sketch_solver import SketchSolver


def _rect_pts():
    return [[0.0, 0.0], [0.012, 0.003], [0.013, 0.012], [0.002, 0.011]]


def _rect_cons():
    return [("h", 0, 1), ("v", 1, 2), ("h", 2, 3), ("v", 3, 0),
            ("dist", 0, 1, 0.02), ("dist", 1, 2, 0.01)]


# -- convergence & exactness -------------------------------------------------
def test_rectangle_converges_exact():
    pts = _rect_pts()
    rep = S.solve_constraints(pts, _rect_cons(),
                              segments=[(0, 1), (1, 2), (2, 3), (3, 0)])
    assert rep.converged
    assert rep.max_residual < 1e-9
    assert abs(pts[1][0] - pts[0][0] - 0.02) < 1e-9
    assert abs(pts[2][1] - pts[1][1] - 0.01) < 1e-9
    # H/V constraints exact
    assert pts[0][1] == pytest.approx(pts[1][1])
    assert pts[1][0] == pytest.approx(pts[2][0])


def test_dof_analysis_rectangle():
    pts = _rect_pts()
    rep = S.solve_constraints(pts, _rect_cons(),
                              segments=[(0, 1), (1, 2), (2, 3), (3, 0)])
    # 8 vars; 4 HV + 2 DIST = 6 independent rows; coincident corners of the
    # polygon are separate points here -> 2 remaining translation DOF
    assert rep.dof == 2
    assert rep.redundant == 0


def test_fully_constrained_rectangle_dof_zero():
    pts = _rect_pts()
    cons = _rect_cons() + [("fixed", 0, 0.0, 0.0), ("fixed", 1, 0.02, 0.0)]
    rep = S.solve_constraints(pts, cons,
                              segments=[(0, 1), (1, 2), (2, 3), (3, 0)])
    assert rep.dof == 0
    assert rep.converged
    assert pts[0] == pytest.approx([0.0, 0.0], abs=1e-9)


# -- over-constraint / conflict ----------------------------------------------
def test_conflicting_constraints_detected():
    pts = [[0.0, 0.0], [0.01, 0.0]]
    # distance 0.02 between two points that are also coincident → conflict
    rep = S.solve_constraints(
        pts, [("coin", 0, 1), ("dist", 0, 1, 0.02)], max_iter=100)
    assert not rep.converged
    assert rep.conflicting
    assert rep.message == "约束冲突或过约束"


def test_redundant_constraint_still_converges():
    pts = [[0.0, 0.0], [0.02, 0.0]]
    # same DIST twice: redundant rows, consistent values → converges
    rep = S.solve_constraints(
        pts, [("dist", 0, 1, 0.02), ("dist", 0, 1, 0.02)])
    assert rep.converged
    assert pts[1][0] == pytest.approx(0.02)


# -- drag anchoring -----------------------------------------------------------
def test_drag_pin_overrides_and_reconverges():
    pts = _rect_pts()
    cons = _rect_cons()
    S.solve_constraints(pts, cons,
                        segments=[(0, 1), (1, 2), (2, 3), (3, 0)])
    # user drags corner 0 to a new place: pin it and re-solve
    from scdm.sketch_solver import SketchSolver
    solver = SketchSolver(pts, [(0, 1), (1, 2), (2, 3), (3, 0)], {}, cons)
    solver.pinned[0] = (0.005, 0.004)
    rep = solver.solve()
    assert rep.converged
    assert pts[0] == pytest.approx([0.005, 0.004])
    # H/V constraints still satisfied after drag
    assert pts[0][1] == pytest.approx(pts[1][1])
    assert pts[1][0] == pytest.approx(pts[2][0])


# -- parameter table expressions ----------------------------------------------
def test_dimension_expression_from_param_table():
    t = ParamTable()
    t.set("width", 0.02)
    t.set("height", "width / 2")
    pts = _rect_pts()
    cons = [("h", 0, 1), ("v", 1, 2), ("h", 2, 3), ("v", 3, 0),
            ("dist", 0, 1, "width"), ("dist", 1, 2, "height")]
    rep = S.solve_constraints(pts, cons,
                              segments=[(0, 1), (1, 2), (2, 3), (3, 0)],
                              param_table=t)
    assert rep.converged
    assert abs(pts[1][0] - pts[0][0] - 0.02) < 1e-9   # 20 mm / 1000
    assert abs(pts[2][1] - pts[1][1] - 0.01) < 1e-9   # height = width/2


def test_dimension_expression_updates_on_param_change():
    # horizontal segment: DIST target == dx; expression re-evaluated per solve
    t = ParamTable()
    t.set("width", 0.02)
    pts = [[0.0, 0.0], [0.012, 0.0], [0.013, 0.0], [0.002, 0.0]]
    cons = [("dist", 0, 1, "width")]
    S.solve_constraints(pts, cons, param_table=t)
    assert abs(pts[1][0] - pts[0][0] - 0.02) < 1e-9
    t.set("width", 0.05)
    pts2 = [[0.0, 0.0], [0.012, 0.0], [0.013, 0.0], [0.002, 0.0]]
    S.solve_constraints(pts2, cons, param_table=t)
    assert abs(pts2[1][0] - pts2[0][0] - 0.05) < 1e-9


# -- circle radius / tangent with solver variables ------------------------------
def test_radius_constraint_on_circle():
    pts = [[0.0, 0.0]]              # circle centre
    circles = {0: 0.002}
    rep = S.solve_constraints(pts, [("radius", 0, 0.005)], circles=circles)
    assert rep.converged
    assert circles[0] == pytest.approx(0.005)


def test_tangent_line_circle_converges():
    pts = [[0.0, -0.005], [0.0, 0.005], [0.005, 0.0]]
    segs = [(0, 1)]
    circles = {2: 0.001}
    rep = S.solve_constraints(
        pts, [("tangent", 0, 2, 0.001)], segments=segs, circles=circles)
    assert rep.converged
    # distance from centre to line == radius
    p, q, c = pts[0], pts[1], pts[2]
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    dist = abs((c[0] - p[0]) * (-(q[1] - p[1]) / L)
               + (c[1] - p[1]) * ((q[0] - p[0]) / L))
    assert dist == pytest.approx(circles[2], abs=1e-6)


# -- legacy semantics preserved --------------------------------------------------
def test_equal_averages_both_segments():
    pts = [[0.0, 0.0], [0.01, 0.0], [0.0, 0.002], [0.004, 0.002]]
    S.solve_constraints(pts, [("equal", 0, 1)], segments=[(0, 1), (2, 3)])
    d1 = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    d2 = math.hypot(pts[3][0] - pts[2][0], pts[3][1] - pts[2][1])
    assert d1 == pytest.approx(d2)
    assert d1 == pytest.approx(0.007)   # legacy average semantics


def test_parallel_reference_side_stays():
    pts = [[0.0, 0.0], [0.01, 0.0], [0.0, 0.0], [0.005, 0.005]]
    S.solve_constraints(pts, [("par", 0, 1)], segments=[(0, 1), (2, 3)])
    assert pts[2] == pytest.approx([0.0, 0.0], abs=1e-9)  # pivot stays
    assert pts[3][1] == pytest.approx(pts[2][1], abs=1e-8)  # seg2 horizontal

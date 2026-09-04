"""H3: assembly mates solver + motion tests."""
from __future__ import annotations

import math

import pytest

from scdm import kernel as K
from scdm import mates as M

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def _frame_of_face(shape, index=0):
    return M.frame_of(K.explore(shape, "face")[index])


def _cog(shape):
    return K.cog(shape)


# -- pure solver math -----------------------------------------------------
def test_dof_table():
    assert M.DOFS[M.RIGID] == 0
    assert M.DOFS[M.REVOLUTE] == 1
    assert M.DOFS[M.CYLINDRICAL] == 2
    assert M.DOFS[M.PLANAR] == 3
    assert M.DOFS[M.BALL] == 3
    assert M.DOFS[M.SCREW] == 1
    assert M.DOFS[M.DISTANCE] == 6


def test_rigid_aligns_origins():
    fa = M.Frame((0.01, 0, 0), (0, 0, 1))
    fb = M.Frame((0, 0, 0), (0, 0, 1))
    m = M.solve_transform(M.Mate(M.RIGID, fa, fb))
    assert M._apply(m, fb.origin) == pytest.approx(fa.origin)


def test_revolute_maps_axis():
    fa = M.Frame((0, 0, 0), (0, 0, 1))
    fb = M.Frame((0, 0, 0), (1, 0, 0))
    m = M.solve_transform(M.Mate(M.REVOLUTE, fa, fb))
    assert M._apply(m, fb.axis) == pytest.approx(fa.axis, abs=1e-9)


def test_screw_pitch_coupling():
    fa = M.Frame((0, 0, 0), (0, 0, 1))
    fb = M.Frame((0, 0, 0), (0, 0, 1))
    # one full turn at 1 mm/turn pitch -> 1 mm slide
    m = M.solve_transform(M.Mate(M.SCREW, fa, fb, value=0.001,
                                 angle=2 * math.pi))
    assert M._apply(m, fb.origin)[2] == pytest.approx(0.001)


def test_ball_point_coincidence():
    fa = M.Frame((0.005, 0, 0), (0, 0, 1))
    fb = M.Frame((0, 0, 0), (0, 0, 1))
    m = M.solve_transform(M.Mate(M.BALL, fa, fb))
    assert M._apply(m, fb.origin) == pytest.approx(fa.origin)


def test_distance_offset():
    fa = M.Frame((0, 0, 0), (1, 0, 0))
    fb = M.Frame((0, 0, 0), (1, 0, 0))
    m = M.solve_transform(M.Mate(M.DISTANCE, fa, fb, value=0.02))
    assert M._apply(m, fb.origin)[0] == pytest.approx(0.02)


# -- OCCT body-level motion ----------------------------------------------
def test_revolute_motion_rotates_body():
    """Motion drag: driving angle 90° about A's axis."""
    box = K.make_box(0.01, 0.01, 0.01)
    fa = M.Frame((0, 0, 0), (0, 0, 1))          # A's hinge axis
    fb = M.Frame((0.01, 0, 0), (0, 0, 1))       # B's reference on the axis
    m = M.solve_transform(M.Mate(M.REVOLUTE, fa, fb, angle=math.pi / 2))
    moved = K.apply_mat4(box, m)
    # kinematic convention: B's reference lands ON the joint (origin), then
    # the whole body rotates 90° about Z: corner-referenced box occupies
    # x,y in [-0.01, 0]
    assert _cog(moved)[0] == pytest.approx(-0.005, abs=1e-9)
    assert _cog(moved)[1] == pytest.approx(-0.005, abs=1e-9)
    assert _cog(moved)[2] == pytest.approx(0.005, abs=1e-9)


def test_cylindrical_slide_and_turn():
    cyl = K.make_cylinder(0.004, 0.01)
    fa = M.Frame((0, 0, 0), (0, 0, 1))
    fb = M.Frame((0, 0, 0), (0, 0, 1))
    m = M.solve_transform(M.Mate(M.CYLINDRICAL, fa, fb,
                                 angle=math.pi / 2, slide=0.005))
    moved = K.apply_mat4(cyl, m)
    # same-origin frames: the slide adds to the original cog z=0.005
    assert _cog(moved)[2] == pytest.approx(0.01)


def test_frame_extraction_kinds():
    box = K.make_box(0.01, 0.01, 0.01)
    fr = _frame_of_face(box, 0)
    assert fr.axis is not None
    cyl = K.make_cylinder(0.004, 0.01)
    fr2 = _frame_of_face(cyl, 0)
    # the cylindrical face's axis is Z
    assert abs(abs(fr2.axis[2]) - 1.0) < 1e-9
    edges = K.explore(box, "edge")
    fr3 = M.frame_of(edges[0])  # straight line edge
    assert fr3.origin is not None

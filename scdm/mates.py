"""H3: assembly mates (kinematic pairs) and motion solver.

Mate types mirror SpaceClaim's constraint set:
  RIGID      full frame alignment            DOF 0
  REVOLUTE   axis alignment + point on axis  DOF 1 (rotation)
  CYLINDRICAL axis alignment + point on axis DOF 2 (rotation + slide)
  PLANAR     plane coincidence               DOF 3 (2 slide + rotation)
  BALL       point coincidence               DOF 3 (orientation free)
  SCREW      axis aligned, coupled d=pitch*u DOF 1 (coupled)
  DISTANCE   origins held at a fixed offset  DOF 6 (position only constrained)

solve_transform() returns a 4x4 row-major tuple matrix M with
[p; 0 0 0 1] such that B's pose = M @ B's original pose.  Motion drag =
solve with an explicit driving parameter (angle in radians / slide
distance in metres).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]
Mat4 = Tuple[Tuple[float, float, float, float], ...]

RIGID = "rigid"
REVOLUTE = "revolute"
CYLINDRICAL = "cylindrical"
PLANAR = "planar"
BALL = "ball"
SCREW = "screw"
DISTANCE = "distance"

DOFS = {RIGID: 0, REVOLUTE: 1, CYLINDRICAL: 2, PLANAR: 3, BALL: 3,
        SCREW: 1, DISTANCE: 6}


@dataclass
class Frame:
    origin: Vec3
    axis: Vec3  # unit


@dataclass
class Mate:
    mtype: str
    ref_a: Frame
    ref_b: Frame
    value: float = 0.0        # distance (m) / pitch (m per turn)
    angle: float = 0.0        # driving angle (rad) for revolute/screw/cyl
    slide: float = 0.0        # driving slide (m) for cylindrical/planar


# ----------------------------------------------------------------------
# small vector helpers
# ----------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    if n < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def _rot_axis_to(b: Vec3, a: Vec3):
    """Rotation (axis, angle) taking unit vector b onto unit vector a."""
    c = _cross(b, a)
    s = _norm(c)
    d = _dot(b, a)
    if s < 1e-12:
        if d > 0:
            return (0.0, 0.0, 1.0), 0.0
        # antiparallel: 180 degrees about any perpendicular
        perp = _unit(_cross(b, (1.0, 0.0, 0.0)
                            if abs(b[0]) < 0.9 else (0.0, 1.0, 0.0)))
        return perp, math.pi
    return _unit(c), math.atan2(s, d)


def _mat4_from_axis_angle(axis: Vec3, angle: float, pivot: Vec3) -> Mat4:
    """Row-major 4x4: rotation about (pivot, axis): M = T(pivot) R T(-pivot)."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    r = ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
         (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
         (t * x * z - s * y, t * y * z + s * x, t * z * z + c))
    px, py, pz = pivot
    out = []
    for i in range(3):
        tx = -(r[i][0] * px + r[i][1] * py + r[i][2] * pz)
        out.append((r[i][0], r[i][1], r[i][2],
                    r[i][0] * px + r[i][1] * py + r[i][2] * pz + tx))
    out.append((0.0, 0.0, 0.0, 1.0))
    return tuple(out)


def _mat4_mul(a: Mat4, b: Mat4) -> Mat4:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4))
        for i in range(4))


def _mat4_translate(v: Vec3) -> Mat4:
    return ((1, 0, 0, v[0]), (0, 1, 0, v[1]), (0, 0, 1, v[2]),
            (0.0, 0.0, 0.0, 1.0))


def _apply(m: Mat4, p: Vec3) -> Vec3:
    return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3])


# ----------------------------------------------------------------------
# solver
# ----------------------------------------------------------------------
def solve_transform(mate: Mate) -> Mat4:
    """Transform matrix positioning B (frame ref_b) w.r.t. A (frame ref_a)."""
    t = mate.mtype
    fa, fb = mate.ref_a, mate.ref_b
    if t == RIGID:
        # rotate fb.axis onto fa.axis about fb.origin, then translate origins
        axis, ang = _rot_axis_to(_unit(fb.axis), _unit(fa.axis))
        m = _mat4_from_axis_angle(axis, ang, fb.origin)
        m = _mat4_mul(_mat4_translate(_sub(fa.origin, fb.origin)), m)
        return m
    if t in (REVOLUTE, CYLINDRICAL, SCREW):
        axis, ang = _rot_axis_to(_unit(fb.axis), _unit(fa.axis))
        m = _mat4_from_axis_angle(axis, ang, fb.origin)
        # then bring fb.origin's projection onto fa.origin
        m = _mat4_mul(_mat4_translate(_sub(fa.origin, fb.origin)), m)
        theta = mate.angle
        if t == SCREW:
            d = mate.value * theta / (2.0 * math.pi)
        else:
            d = 0.0
        if t == CYLINDRICAL:
            d += mate.slide
        a = _unit(fa.axis)
        m = _mat4_mul(
            _mat4_translate((a[0] * d, a[1] * d, a[2] * d)), m)
        m = _mat4_mul(
            _mat4_from_axis_angle(a, theta, fa.origin), m)
        return m
    if t == PLANAR:
        # plane coincidence: flip B's plane onto A's plane (normals opposed),
        # slide in-plane (u, v along A's frame), rotate about A's normal
        axis, ang = _rot_axis_to(_unit(fb.axis), _unit(_neg(fa.axis)))
        m = _mat4_from_axis_angle(axis, ang, fb.origin)
        # target: fb.origin maps to fa.origin + in-plane offset
        target = (fa.origin[0] + mate.slide * 0.0, fa.origin[1],
                  fa.origin[2])
        target = _add(fa.origin, _inplane_offset(fa.axis, mate.slide))
        m = _mat4_mul(_mat4_translate(_sub(target, fb.origin)), m)
        m = _mat4_mul(
            _mat4_from_axis_angle(_unit(fa.axis), mate.angle, fa.origin), m)
        return m
    if t == BALL:
        return _mat4_translate(_sub(fa.origin, fb.origin))
    if t == DISTANCE:
        a = _unit(fa.axis)
        target = _add(fa.origin, (a[0] * mate.value, a[1] * mate.value,
                                  a[2] * mate.value))
        return _mat4_translate(_sub(target, fb.origin))
    raise ValueError("unknown mate type " + str(t))


def _neg(a):
    return (-a[0], -a[1], -a[2])


def _inplane_offset(axis: Vec3, d: float) -> Vec3:
    # slide along the frame's first perpendicular
    perp = _unit(_cross(axis, (1.0, 0.0, 0.0)
                        if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)))
    return (perp[0] * d, perp[1] * d, perp[2] * d)


# ----------------------------------------------------------------------
# OCCT bridge (kept out of the pure math above)
# ----------------------------------------------------------------------
def frame_of(face_or_edge) -> Frame:
    """Extract a mate frame from an OCCT face (plane/cylinder) or edge
    (line/circle)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomAbs import (GeomAbs_Plane, GeomAbs_Cylinder,
                                  GeomAbs_Line, GeomAbs_Circle)
    from OCC.Core.TopoDS import topods
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
    sh = face_or_edge
    if sh.ShapeType() == TopAbs_FACE:
        ad = BRepAdaptor_Surface(topods.Face(sh))
        if ad.GetType() == GeomAbs_Plane:
            n = ad.Plane().Axis().Direction()
            d = ad.Plane().Location()
            return Frame((d.X(), d.Y(), d.Z()), (n.X(), n.Y(), n.Z()))
        if ad.GetType() == GeomAbs_Cylinder:
            cy = ad.Cylinder()
            loc = cy.Location()
            n = cy.Axis().Direction()
            return Frame((loc.X(), loc.Y(), loc.Z()), (n.X(), n.Y(), n.Z()))
        raise ValueError("配合参考面须为平面或圆柱面")
    if sh.ShapeType() == TopAbs_EDGE:
        ad = BRepAdaptor_Curve(topods.Edge(sh))
        if ad.GetType() == GeomAbs_Line:
            p = ad.Value(ad.FirstParameter())
            d = ad.Line().Direction()
            return Frame((p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z()))
        if ad.GetType() == GeomAbs_Circle:
            c = ad.Circle()
            loc = c.Location()
            n = c.Axis().Direction()
            return Frame((loc.X(), loc.Y(), loc.Z()), (n.X(), n.Y(), n.Z()))
        raise ValueError("配合参考边须为直线或圆")
    raise ValueError("配合参考须为面或边")

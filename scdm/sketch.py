"""M3 sketch: 2D constraint solver + closed-loop extrusion.

Fixed-point relaxation over a point set with segments and circles. Constraint kinds:
point-pair (DIST/H/V/COIN), segment-pair (EQUAL/PAR/PERP), and mixed
(TANGENT line-circle, MIDPOINT, FIXED pin). GUI-agnostic and unit-tested.
Closed loops (rect or a chain of line segments) are extruded to a solid via OCCT.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Point2 = List[float]  # mutable [x, y]

# constraint kinds
DIST = "dist"
HORIZONTAL = "h"
VERTICAL = "v"
COINCIDENT = "coin"
PERPENDICULAR = "perp"
EQUAL = "equal"
PARALLEL = "par"
TANGENT = "tangent"
MIDPOINT = "mid"
FIXED = "fixed"

# constraint tuple shapes:
#   point-pair:   (kind, i, j[, value])
#   segment-pair: (EQUAL|PAR|PERP, s1, s2)
#   mixed:        (TANGENT, seg, center_pt, radius)
#                 (MIDPOINT, pt, seg)
#                 (FIXED, pt, x, y)


def solve_constraints(points: Sequence[Point2], constraints: Sequence[tuple],
                      segments: Optional[Sequence[Tuple[int, int]]] = None,
                      iters: int = 40, param_table=None,
                      circles: Optional[Dict[int, float]] = None,
                      max_iter: Optional[int] = None) -> "SolveReport":
    """Solve sketch constraints; points are mutated in place.

    Delegates to the H-series damped-least-squares solver
    (`scdm.sketch_solver.SketchSolver`) with DOF analysis, over-constraint
    detection and convergence reporting; `iters` maps to max_iter.
    The optional 'segments' list maps segment indices to (i, j) point-index
    pairs and is required by EQUAL/PAR/PERP/TANGENT/MIDPOINT constraints.
    Returns a SolveReport (legacy callers may ignore it).
    """
    from scdm.sketch_solver import SketchSolver
    solver = SketchSolver(points, segments, circles or {}, constraints,
                          param_table)
    # reference-side semantics (SpaceClaim UX): for entity-pair constraints
    # the FIRST entity stays ~fixed while the second adjusts
    def seg(s):
        return segments[s] if segments and 0 <= s < len(segments) else None
    for c in constraints:
        if c[0] in ("par", "perp"):
            s1 = seg(c[1])
            if s1:
                solver.anchor(*s1)   # reference segment stays put
            s2 = seg(c[2])
            if s2 and s2[0] < len(points):
                # pivot: the adjusted segment rotates about its start point
                solver.pinned[s2[0]] = tuple(points[s2[0]])
        elif c[0] == "mid":
            s0 = seg(c[2])
            if s0:
                solver.anchor(*s0)
        elif c[0] == "tangent":
            s0 = seg(c[1])
            if s0:
                solver.anchor(*s0)
    return solver.solve(max_iter=max_iter or iters)


def _seglen(a: Point2, b: Point2) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _scale_seg(points, i, j, length, fixed_point):
    """Set the segment length by moving the far endpoint around the fixed one."""
    p, q = points[i], points[j]
    far = q if fixed_point == i else p
    base = points[i] if fixed_point == i else points[j]
    d = _seglen(p, q) or 1e-12
    ux, uy = (far[0] - base[0]) / d, (far[1] - base[1]) / d
    far[0] = base[0] + ux * length
    far[1] = base[1] + uy * length


def _rotate_seg_to(points, i, j, angle, fixed):
    """Rotate endpoint j (or i) about the fixed endpoint to the given angle."""
    p, q = points[i], points[j]
    if fixed == i:
        d = _seglen(p, q) or 1e-12
        q[0] = p[0] + d * math.cos(angle)
        q[1] = p[1] + d * math.sin(angle)
    else:
        d = _seglen(p, q) or 1e-12
        p[0] = q[0] - d * math.cos(angle)
        p[1] = q[1] - d * math.sin(angle)


def solve_dimensions(points: Sequence[Point2], dims: Sequence[Tuple[int, int, float]],
                     iters: int = 40, param_table=None) -> List[float]:
    """Drive (i, j, target_distance) dimensions to their targets.

    Returns the final solved distances in dims order.
    """
    constraints = [(DIST, i, j, d) for (i, j, d) in dims]
    solve_constraints(points, constraints, iters=iters, param_table=param_table)
    return [math.hypot(points[j][0] - points[i][0], points[j][1] - points[i][1])
            for (i, j, _d) in dims]


def sketch_outline(curves: Sequence[tuple]) -> Optional[List[Point2]]:
    """Return the 2D outer loop of a sketch as an ordered point list, or None.

    Supports: ('rect', p1, p2) and chains of ('line', p1, p2) forming a closed loop.
    """
    def xy(t):
        return [float(t[0]), float(t[1])]

    for c in curves:
        if c[0] == "rect":
            p1, p2 = xy(c[1]), xy(c[2])
            return [p1, [p2[0], p1[1]], p2, [p1[0], p2[1]]]
        if c[0] == "poly":
            return [xy(p) for p in c[1]]
    # otherwise collect line segments and try to form a closed loop
    segs = []
    for c in curves:
        if c[0] == "line":
            segs.append((xy(c[1]), xy(c[2])))
    if not segs:
        return None
    loop = [segs[0][0], segs[0][1]]
    used = [False] * len(segs)
    used[0] = True
    for _ in range(len(segs)):
        tip = loop[-1]
        moved = False
        for k, (a, b) in enumerate(segs):
            if used[k]:
                continue
            if _near(a, tip):
                loop.append(b); used[k] = True; moved = True; break
            if _near(b, tip):
                loop.append(a); used[k] = True; moved = True; break
        if not moved:
            break
    if len(loop) >= 3 and _near(loop[0], loop[-1]):
        return loop[:-1] if _near(loop[0], loop[-1]) else loop
    return None


def _near(a: Point2, b: Point2, tol: float = 1e-9) -> bool:
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def extrude_sketch(curves: Sequence[tuple], thickness: float, plane: str = "xy",
                   axes: Optional[Axes] = None):
    """Build a solid by extruding the sketch's closed loop by thickness.

    Loop coordinates are plane-local (u, v); the face is built on the sketch plane
    (named datum or custom axes) and prisms along the plane normal.
    Raises ValueError when no closed loop.
    """
    from scdm import kernel as K
    outline = sketch_outline(curves)
    if outline is None:
        raise ValueError("草图没有闭环（画矩形或闭合线段）")
    ax = axes if axes is not None else sketch_axes(plane)
    pts = [axes_to_world(ax, u, v) for (u, v) in outline]
    face = K.face_from_polygon(pts)
    n = ax[3]
    return K.prism(face, (n[0] * thickness, n[1] * thickness, n[2] * thickness))


PLANE_NORMALS = {"xy": (0.0, 0.0, 1.0), "zx": (0.0, 1.0, 0.0), "yz": (1.0, 0.0, 0.0)}

_AXES = {
    "xy": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "zx": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "yz": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
}

Axes = Tuple[Tuple[float, float, float], Tuple[float, float, float],
             Tuple[float, float, float], Tuple[float, float, float]]


def _unit3(v):
    L = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / L, v[1] / L, v[2] / L)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def sketch_axes(plane: str = "xy", origin=(0.0, 0.0, 0.0),
                normal=None, xdir=None) -> Axes:
    """Resolve a sketch plane to (origin, u, v, n). Named planes are the
    through-origin datum planes; plane == 'custom' uses the stored fields."""
    if plane == "custom" and normal is not None:
        n = _unit3(normal)
        if xdir is None:
            a = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
            u = _unit3(_cross(n, a))
        else:
            x = _unit3(xdir)
            d = x[0] * n[0] + x[1] * n[1] + x[2] * n[2]
            u = _unit3((x[0] - d * n[0], x[1] - d * n[1], x[2] - d * n[2]))
        v = _cross(n, u)
        return (tuple(origin), u, v, n)
    u, v = _AXES.get(plane, _AXES["xy"])
    n = PLANE_NORMALS.get(plane, (0.0, 0.0, 1.0))
    return ((0.0, 0.0, 0.0), u, v, n)


def axes_to_world(axes: Axes, u: float, v: float) -> Tuple[float, float, float]:
    o, ux, vx, _n = axes
    return (o[0] + u * ux[0] + v * vx[0],
            o[1] + u * ux[1] + v * vx[1],
            o[2] + u * ux[2] + v * vx[2])


def world_to_uv(axes: Axes, p) -> Tuple[float, float]:
    o, ux, vx, _n = axes
    d = (p[0] - o[0], p[1] - o[1], p[2] - o[2])
    return (d[0] * ux[0] + d[1] * ux[1] + d[2] * ux[2],
            d[0] * vx[0] + d[1] * vx[1] + d[2] * vx[2])


def plane_normal(plane: str) -> Tuple[float, float, float]:
    return PLANE_NORMALS.get(plane, (0.0, 0.0, 1.0))


def local_to_world(plane: str, u: float, v: float) -> Tuple[float, float, float]:
    """Plane-local sketch coordinates -> world 3D on the datum plane."""
    if plane == "zx":
        return (u, 0.0, v)
    if plane == "yz":
        return (0.0, u, v)
    return (u, v, 0.0)


def offset_polygon(pts: Sequence[Point2], distance: float) -> List[Point2]:
    """Miter-offset a closed polygon; positive = outward for CCW input."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        d1 = _unit2(p1[0] - p0[0], p1[1] - p0[1])
        d2 = _unit2(p2[0] - p1[0], p2[1] - p1[1])
        n1 = (d1[1], -d1[0])  # outward for CCW
        n2 = (d2[1], -d2[0])
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(bx, by) or 1.0
        cos_half = max(0.2, (n1[0] * bx + n1[1] * by) / L)
        s = distance / cos_half
        out.append([p1[0] + bx / L * s, p1[1] + by / L * s])
    return out


def _unit2(x, y):
    L = math.hypot(x, y) or 1.0
    return (x / L, y / L)


def point_segment_distance(p, a, b):
    """(distance, t) from point p to segment a-b; t in [0,1] is the projection."""
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    px, py = float(p[0]), float(p[1])
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t


def chain_polylines(polys: Sequence[Sequence[Point2]],
                    tol: float = 1e-7) -> List[List[Point2]]:
    """Join open polylines sharing endpoints into rings (section outlines).

    Closed rings are returned without the duplicated closing point.
    """
    segs = [list(p) for p in polys if len(p) >= 2]

    def key(q):
        return (round(q[0] / tol), round(q[1] / tol), round(q[2] / tol))

    rings, used = [], [False] * len(segs)
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        ring = list(segs[i])
        grew = True
        while grew:
            grew = False
            tip = key(ring[-1])
            for j, t in enumerate(segs):
                if used[j]:
                    continue
                if key(t[0]) == tip:
                    ring.extend(t[1:])
                    used[j] = True
                    grew = True
                    break
                if key(t[-1]) == tip:
                    ring.extend(list(reversed(t[:-1])))
                    used[j] = True
                    grew = True
                    break
        if len(ring) >= 3 and key(ring[0]) == key(ring[-1]):
            rings.append(ring[:-1])
        elif len(ring) >= 2:
            rings.append(ring)
    return rings


def tangent_from_point(p, c, r) -> List[Tuple[Point2, Point2]]:
    """Tangent segments from external point p to circle (c, r); 0 or 2 results."""
    dx, dy = c[0] - p[0], c[1] - p[1]
    d2 = dx * dx + dy * dy
    d = math.sqrt(d2)
    if d <= r or d < 1e-12:
        return []
    base = math.atan2(dy, dx)
    alpha = math.asin(max(-1.0, min(1.0, r / d)))
    L = math.sqrt(max(d2 - r * r, 0.0))
    out = []
    for s in (1.0, -1.0):
        ang = base + s * alpha
        out.append(([p[0], p[1]], [p[0] + L * math.cos(ang), p[1] + L * math.sin(ang)]))
    return out


def circumcenter(p1, p2, p3):
    """Centre and radius through three points, or None when collinear."""
    ax, ay = float(p1[0]), float(p1[1])
    bx, by = float(p2[0]), float(p2[1])
    cx, cy = float(p3[0]), float(p3[1])
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return [ux, uy], math.hypot(ux - ax, uy - ay)


def catmull_rom(points: Sequence[Point2], samples: int = 12) -> List[Point2]:
    """Smooth an open point chain with Catmull-Rom interpolation."""
    if len(points) < 3:
        return [list(p) for p in points]
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(samples):
            t = j / float(samples)
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append([x, y])
    out.append([pts[-2][0], pts[-2][1]])
    return out

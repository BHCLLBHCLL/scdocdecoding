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
                      iters: int = 40) -> None:
    """Relax points against constraints; points are mutated in place.

    The optional 'segments' list maps segment indices to (i, j) point-index pairs and
    is required by EQUAL/PAR/PERP/TANGENT/MIDPOINT constraints.
    """
    segs = list(segments) if segments else []

    def sp(s):
        return segs[s] if 0 <= s < len(segs) else None

    for _ in range(iters):
        for c in constraints:
            kind = c[0]
            if kind == FIXED:
                _, i, x, y = c
                if 0 <= i < len(points):
                    points[i][0], points[i][1] = float(x), float(y)
                continue
            if kind in (EQUAL, PARALLEL, PERPENDICULAR):
                s1, s2 = sp(c[1]), sp(c[2])
                if s1 is None or s2 is None:
                    continue
                (a1, b1), (a2, b2) = s1, s2
                if max(a1, b1, a2, b2) >= len(points):
                    continue
                p1, p2 = points[a1], points[b1]
                q1, q2 = points[a2], points[b2]
                d1 = _seglen(p1, p2); d2 = _seglen(q1, q2)
                if kind == EQUAL and d1 and d2:
                    avg = (d1 + d2) / 2.0
                    _scale_seg(points, a1, b1, avg, fixed_point=a1)
                    _scale_seg(points, a2, b2, avg, fixed_point=a2)
                elif kind == PARALLEL and d2:
                    _rotate_seg_to(points, a2, b2, math.atan2(p2[1] - p1[1], p2[0] - p1[0]), fixed=a2)
                elif kind == PERPENDICULAR and d2:
                    base = math.atan2(p2[1] - p1[1], p2[0] - p1[0]) + math.pi / 2.0
                    _rotate_seg_to(points, a2, b2, base, fixed=a2)
                continue
            if kind == TANGENT:
                s = sp(c[1])
                ci = c[2]
                radius = c[3]
                if s is None or ci >= len(points):
                    continue
                a, b = s
                if max(a, b) >= len(points):
                    continue
                p, q = points[a], points[b]
                cc = points[ci]
                if _seglen(p, q) < 1e-12:
                    continue
                nx, ny = -(q[1] - p[1]), (q[0] - p[0])
                nl = math.hypot(nx, ny) or 1.0
                nx, ny = nx / nl, ny / nl
                dist = (cc[0] - p[0]) * nx + (cc[1] - p[1]) * ny
                err = abs(dist) - radius
                sign = 1.0 if dist >= 0 else -1.0
                shift = sign * err / 2.0
                p[0] += nx * shift; p[1] += ny * shift
                q[0] += nx * shift; q[1] += ny * shift
                continue
            if kind == MIDPOINT:
                pt_i, s = c[1], sp(c[2])
                if s is None or pt_i >= len(points):
                    continue
                a, b = s
                if max(a, b) >= len(points):
                    continue
                p, q = points[a], points[b]
                points[pt_i][0] = (p[0] + q[0]) / 2.0
                points[pt_i][1] = (p[1] + q[1]) / 2.0
                continue
            # point-pair kinds
            i, j = c[1], c[2]
            val = c[3] if len(c) > 3 else None
            if i >= len(points) or j >= len(points):
                continue
            p, q = points[i], points[j]
            dx, dy = q[0] - p[0], q[1] - p[1]
            if kind == DIST and val:
                d = math.hypot(dx, dy) or 1e-12
                err = (d - val) / 2.0
                ux, uy = dx / d, dy / d
                p[0] += ux * err; p[1] += uy * err
                q[0] -= ux * err; q[1] -= uy * err
            elif kind == HORIZONTAL:
                err = (q[1] - p[1]) / 2.0
                p[1] += err; q[1] -= err
            elif kind == VERTICAL:
                err = (q[0] - p[0]) / 2.0
                p[0] += err; q[0] -= err
            elif kind == COINCIDENT:
                mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
                p[0], p[1] = mx, my
                q[0], q[1] = mx, my


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
                     iters: int = 40) -> List[float]:
    """Drive (i, j, target_distance) dimensions to their targets.

    Returns the final solved distances in dims order.
    """
    constraints = [(DIST, i, j, d) for (i, j, d) in dims]
    solve_constraints(points, constraints, iters=iters)
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


def extrude_sketch(curves: Sequence[tuple], thickness: float, plane: str = "xy"):
    """Build a solid by extruding the sketch's closed loop by thickness.

    For plane 'xy' the loop lives on z=0 and is extruded along +z. Returns a shape,
    or raises ValueError when no closed loop is found.
    """
    from scdm import kernel as K
    outline = sketch_outline(curves)
    if outline is None:
        raise ValueError("草图没有闭环（画矩形或闭合线段）")
    pts = [(x, y, 0.0) for x, y in outline]
    face = K.face_from_polygon(pts)
    vec = {"xy": (0, 0, 1), "zx": (0, 1, 0), "yz": (1, 0, 0)}.get(plane, (0, 0, 1))
    return K.prism(face, (vec[0] * thickness, vec[1] * thickness, vec[2] * thickness))

"""M3 sketch: minimal 2D constraint solver + closed-loop extrusion.

The solver is deliberately small (distance / horizontal / vertical / coincident /
perpendicular) with a few fixed-point relaxation passes. It drives point coordinates
and is GUI-agnostic so it can be unit-tested. Closed loops (rect or a chain of line
segments) are extruded to a solid via the OCCT kernel.
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


def solve_constraints(points: Sequence[Point2], constraints: Sequence[tuple],
                      iters: int = 30) -> None:
    """Relax a point set against a list of constraints.

    Each constraint is (kind, i, j, value) where value is a distance for DIST and
    ignored for the others. Points are mutated in place.
    """
    for _ in range(iters):
        for c in constraints:
            kind, i, j, val = c[0], c[1], c[2], (c[3] if len(c) > 3 else None)
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
            elif kind == PERPENDICULAR and i >= 0 and j - 1 >= 0:
                # rotate q about p by the signed angle needed to make pq perpendicular
                d = math.hypot(dx, dy) or 1e-12
                ang = math.atan2(dy, dx) + math.pi / 2.0
                q[0] = p[0] + d * math.cos(ang)
                q[1] = p[1] + d * math.sin(ang)


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

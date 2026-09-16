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


CIRCLE_SEGMENTS = 64


def circle_ring(cx: float, cy: float, r: float,
                segments: int = CIRCLE_SEGMENTS) -> List[Point2]:
    """Closed polygon approximation of a circle (P10: circles can extrude)."""
    return [[cx + r * math.cos(math.tau * i / segments),
             cy + r * math.sin(math.tau * i / segments)]
            for i in range(segments)]


def polygon_area(pts: Sequence[Point2]) -> float:
    """Shoelace area of a closed polygon (absolute value)."""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def sketch_outline(curves: Sequence[tuple]) -> Optional[List[Point2]]:
    """Return the 2D outer loop of a sketch as an ordered point list, or None.

    Supports: ('rect', p1, p2), ('circle', centre, r), ('poly', [pts]) and
    chains of ('line', p1, p2) forming a closed loop.
    """
    def xy(t):
        return [float(t[0]), float(t[1])]

    def dedupe(pts):
        if len(pts) > 2 and _near(pts[0], pts[-1]):
            return pts[:-1]
        return pts

    for c in curves:
        if c[0] == "rect":
            p1, p2 = xy(c[1]), xy(c[2])
            return [p1, [p2[0], p1[1]], p2, [p1[0], p2[1]]]
        if c[0] == "circle":
            ctr = xy(c[1])
            return circle_ring(ctr[0], ctr[1], float(c[2]))
        if c[0] == "poly":
            return dedupe([xy(p) for p in c[1]])
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


def sketch_loops(curves: Sequence[tuple]) -> List[tuple]:
    """Every closed loop of a sketch, in curve order (R107/A-1).

    Each entry is `("circle", centre, r)` or `("poly", [pts...])`.  A
    rectangle is a polygon loop, a polyline is a polygon loop, free lines are
    chained into loops, and *disjoint* loops stay separate - which is what lets
    one sketch produce several bodies.

    Unlike `sketch_outline()` (the single outer loop the old extrude used) this
    keeps the loop's own geometry, so a circle stays a circle.
    """
    loops: List[tuple] = []
    pending: List[tuple] = []
    for c in curves:
        if not c:
            continue
        if c[0] == "rect":
            p1 = [float(c[1][0]), float(c[1][1])]
            p2 = [float(c[2][0]), float(c[2][1])]
            loops.append(("poly", [p1, [p2[0], p1[1]], p2, [p1[0], p2[1]]]))
        elif c[0] == "circle":
            loops.append(("circle", [float(c[1][0]), float(c[1][1])],
                          float(c[2])))
        elif c[0] == "poly":
            pts = [[float(p[0]), float(p[1])] for p in c[1]]
            if len(pts) > 2 and _near(pts[0], pts[-1]):
                pts = pts[:-1]
            if len(pts) >= 3:
                loops.append(("poly", pts))
        elif c[0] == "line":
            pending.append(([float(c[1][0]), float(c[1][1])],
                            [float(c[2][0]), float(c[2][1])]))
    used = [False] * len(pending)
    for i, (a, b) in enumerate(pending):
        if used[i]:
            continue
        used[i] = True
        loop = [a, b]
        while True:
            tip = loop[-1]
            if len(loop) >= 4 and _near(tip, loop[0]):
                loops.append(("poly", loop[:-1]))
                break
            nxt = None
            for k, (p, q) in enumerate(pending):
                if used[k]:
                    continue
                if _near(p, tip):
                    nxt = (k, q)
                    break
                if _near(q, tip):
                    nxt = (k, p)
                    break
            if nxt is None:
                break
            used[nxt[0]] = True
            loop.append(nxt[1])
    return loops


def extrude_loops(curves: Sequence[tuple], thickness: float, plane: str = "xy",
                  axes: Optional[Axes] = None) -> List[Any]:
    """One solid per closed loop (R107/A-1 + A-2).

    A circle loop becomes a real cylinder (`K.make_cylinder`), so
    `extrude of a circle` is exact instead of a polygon approximation; polygon
    loops go through the same face+prism path as `extrude_sketch@.
    """
    from scdm import kernel as K
    ax = axes if axes is not None else sketch_axes(plane)
    n = ax[3]
    out = []
    for loop in sketch_loops(curves):
        if loop[0] == "circle":
            c, r = loop[1], loop[2]
            out.append(K.make_cylinder(r, thickness,
                                       origin=axes_to_world(ax, c[0], c[1]),
                                       axis=n))
        else:
            pts = [axes_to_world(ax, u, v) for (u, v) in loop[1]]
            face = K.face_from_polygon(pts)
            out.append(K.prism(face, (n[0] * thickness, n[1] * thickness,
                                      n[2] * thickness)))
    if not out:
        raise ValueError("草图没有闭环（画矩形、圆或闭合线段）")
    return out


#: how an extrusion is placed relative to the sketch plane (R108/A-4)
EXTRUDE_MODES = ("one", "symmetric", "reverse")


def place_extrusion(solid, mode: str, thickness: float, normal):
    """Shift an extrusion along its normal (R108/A-4).

    `one`: the sketch plane is the start face (the historic behaviour);
    `symmetric`: it is the middle (the body straddles the plane);
    `reverse`: the extrusion goes the other way.  All three have the same
    volume for the same thickness - the difference is where the body sits, which
    is exactly what the tests check.
    """
    from scdm import kernel as K
    if mode in (None, "", "one"):
        return solid
    if mode == "symmetric":
        f = -0.5 * float(thickness)
    elif mode == "reverse":
        f = -float(thickness)
    else:
        raise ValueError("未知拉伸方式：%s" % mode)
    return K.translate(solid, tuple(f * float(n) for n in normal))


def min_vertex_gap(sk) -> Optional[float]:
    """Smallest distance between two distinct sketch vertices (R109/A-1).

    Used to tell "no closed loop because the corners are a hair apart" from
    "there is nothing to extrude at all".
    """
    pts, _segs, kinds = read_points(sk, with_kinds=True)
    verts = [p for i, p in enumerate(pts) if kinds[i] == "vertex"]
    best = None
    for i in range(len(verts)):
        for j in range(i + 1, len(verts)):
            d = math.hypot(verts[i][0] - verts[j][0], verts[i][1] - verts[j][1])
            if best is None or d < best:
                best = d
    return best


def weld_coincident(sk, tol: float = 1e-4, snap: bool = True,
                    report=None) -> int:
    """Weld sketch vertices that meet within `tol` (R108/A-1, R109 tolerance).

    Separately drawn lines only *touch* in coordinates: without a COINCIDENT
    constraint a solve moves the ends apart and the outline tears open (R107
    measured exactly that).  `tol` is in sketch units (metres); the default
    1e-4 = 0.1 mm is the coincidence tolerance a CAD tool uses when the user
    *thinks* two corners are connected.

    With `snap` the later points of a group are also moved onto its leader, so the
    outline is closed **immediately** - a COINCIDENT constraint alone would only
    close it at the next solve, and `sketch_loops()` would still see a gap.
    Only vertices take part: never a circle centre or its radius handle.

    Returns how many constraints were added; pass a `report` dict to also get
    {"added", "moved", "groups"}.
    """
    pts, _segs, kinds = read_points(sk, with_kinds=True)
    known = set()
    for c in getattr(sk, "constraints", []) or []:
        if c and c[0] == COINCIDENT and len(c) >= 3:
            known.add(frozenset((int(c[1]), int(c[2]))))
    groups: List[List[int]] = []
    for i, p in enumerate(pts):
        if kinds[i] != "vertex":
            continue
        for g in groups:
            if any(abs(p[0] - pts[m][0]) <= tol and abs(p[1] - pts[m][1]) <= tol
                   for m in g):
                g.append(i)
                break
        else:
            groups.append([i])
    added = 0
    moved = 0
    for g in groups:
        if len(g) < 2:
            continue
        lead = pts[g[0]]
        for k in range(1, len(g)):
            other = pts[g[k]]
            if (snap and (abs(other[0] - lead[0]) > 1e-15
                          or abs(other[1] - lead[1]) > 1e-15)):
                other[0], other[1] = lead[0], lead[1]
                moved += 1
            pair = frozenset((g[0], g[k]))
            if pair in known:
                continue
            sk.constraints.append((COINCIDENT, g[0], g[k]))
            known.add(pair)
            added += 1
    if snap and moved:
        write_points(sk, pts)
    if report is not None:
        report.update(added=added, moved=moved, groups=len(groups))
    return added


def read_points(sk, with_kinds: bool = False):
    """(points, segments[, kinds]) of a sketch in solver variables (R107/A-3).

    One implementation for the solver, the GUI and the dimension editor: a
    line/rect contributes its two corner variables, a circle its centre and a
    radius handle, a polyline its vertices.  `kinds` (R108/A-1) says where each
    variable came from, so the welding pass can tell a real vertex from a circle
    centre or its radius handle.
    """
    pts: List[list] = []
    segments: List[tuple] = []
    kinds: List[str] = []
    for c in sk.curves:
        if c[0] in ("line", "rect"):
            base = len(pts)
            for p in (c[1], c[2]):
                # a point may be a 2-tuple (rect/line are often written that way)
                pz = float(p[2]) if len(p) > 2 else 0.0
                pts.append([float(p[0]), float(p[1]), pz])
                kinds.append("vertex")
            segments.append((base, base + 1))
        elif c[0] == "circle":
            # a circle centre may be a 2-tuple (R108: the welding pass hit this)
            cz = float(c[1][2]) if len(c[1]) > 2 else 0.0
            for p in ((c[1][0], c[1][1], cz),
                      (c[1][0] + c[2], c[1][1], cz)):
                pts.append([float(p[0]), float(p[1]), float(p[2])])
                kinds.append("circle")
        elif c[0] == "poly":
            base = len(pts)
            for p in c[1]:
                pts.append([float(p[0]), float(p[1]), 0.0])
                kinds.append("vertex")
            for k in range(len(c[1]) - 1):
                segments.append((base + k, base + k + 1))
    return (pts, segments, kinds) if with_kinds else (pts, segments)


def write_points(sk, pts) -> None:
    """Write solved variables back into the sketch curves (R107/A-3)."""
    idx = 0
    for i, c in enumerate(sk.curves):
        if c[0] in ("line", "rect"):
            p1 = tuple(pts[idx])
            p2 = tuple(pts[idx + 1]) if idx + 1 < len(pts) else c[2]
            sk.curves[i] = (c[0], p1, p2)
            idx += 2
        elif c[0] == "circle":
            sk.curves[i] = (c[0], tuple(pts[idx])[:2] + (c[1][2],), c[2])
            idx += 2
        elif c[0] == "poly":
            n = len(c[1])
            new_pts = [[pts[idx + k][0], pts[idx + k][1]] for k in range(n)]
            sk.curves[i] = (c[0], new_pts)
            idx += n


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


GLYPH_LABELS = {
    "h": "H", "v": "V", "par": "∥", "perp": "⊥", "equal": "=",
    "coin": "●", "mid": "M", "fixed": "▣", "tangent": "T",
    "dist": "↔", "radius": "R",
}


def constraint_glyphs(constraints, points, segments):
    """P21: (label, uv, value_mm) markers for a sketch's applied constraints.

    Positions are derived from the CURRENT points/segments, so a constraint
    whose indices no longer resolve (the sketch was edited) is skipped instead
    of raising. Dimension values are reported in mm.
    """
    out = []
    n = len(points or ())

    def mid(i, j):
        if i < n and j < n:
            return [(points[i][0] + points[j][0]) / 2.0,
                    (points[i][1] + points[j][1]) / 2.0]
        return None

    def seg_mid(s):
        if segments and 0 <= s < len(segments):
            a, b = segments[s]
            return mid(a, b)
        return None

    for c in constraints or ():
        kind = c[0]
        label = GLYPH_LABELS.get(kind)
        if label is None:
            continue
        uv = None
        value = None
        if kind == "dist":
            uv = mid(c[1], c[2])
            value = float(c[3]) * 1000.0 if c[3] is not None else None
        elif kind in ("h", "v", "coin"):
            uv = mid(c[1], c[2])
        elif kind in ("par", "perp", "equal"):
            m1, m2 = seg_mid(c[1]), seg_mid(c[2])
            if m1 and m2:
                uv = [(m1[0] + m2[0]) / 2.0, (m1[1] + m2[1]) / 2.0]
        elif kind == "mid":
            uv = (mid(c[1], c[1]) if c[1] < n else None) or seg_mid(c[2])
        elif kind == "fixed":
            uv = [float(c[2]), float(c[3])]
        elif kind == "tangent":
            if c[2] < n:
                uv = [points[c[2]][0], points[c[2]][1]]
            value = float(c[3]) * 1000.0 if len(c) > 3 and c[3] else None
        if uv is None:
            continue
        out.append({"kind": kind, "label": label, "uv": uv, "value_mm": value})
    return out


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


def snap_uv(uv, points, segments, tol, snap_end: bool = True,
            snap_mid: bool = True, grid_step: Optional[float] = None,
            anchors=None, snap_coincident: bool = False):
    """Snap a sketch-plane pick; returns (uv, kind).

    SpaceClaim UX order: entity snaps win over the grid and the nearest entity
    wins; kind is 'coincident' | 'endpoint' | 'midpoint' | 'grid' | None.
    P2: these options used to be stored but never consulted by the picker.
    P19: 'coincident' snaps to existing sketch anchors (point entities and
    circle centres) and takes priority over endpoint / midpoint.
    """
    # 重合 has absolute priority: an existing sketch anchor wins even when a
    # midpoint happens to be closer to the raw pick.
    coincident = None
    if snap_coincident:
        for p in anchors or ():
            d = math.hypot(p[0] - uv[0], p[1] - uv[1])
            if d <= tol and (coincident is None or d < coincident[0]):
                coincident = (d, [float(p[0]), float(p[1])])
    if coincident is not None:
        return coincident[1], "coincident"
    best = None
    if snap_end:
        for p in points or ():
            d = math.hypot(p[0] - uv[0], p[1] - uv[1])
            if d <= tol and (best is None or d < best[0]):
                best = (d, [float(p[0]), float(p[1])], "endpoint")
    if snap_mid:
        for seg in segments or ():
            a, b = seg[0], seg[1]
            if 0 <= a < len(points) and 0 <= b < len(points):
                m = [(points[a][0] + points[b][0]) / 2.0,
                     (points[a][1] + points[b][1]) / 2.0]
                d = math.hypot(m[0] - uv[0], m[1] - uv[1])
                if d <= tol and (best is None or d < best[0]):
                    best = (d, m, "midpoint")
    if best is not None:
        return best[1], best[2]
    if grid_step and grid_step > 0:
        return [round(v / grid_step) * grid_step for v in uv], "grid"
    return [float(uv[0]), float(uv[1])], None


def _seg_intersection(a, b, c, d, eps: float = 1e-12):
    """Parameter (t, u) of the intersection of segments ab and cd, else None."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < eps:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if eps < t < 1.0 - eps and eps < u < 1.0 - eps:
        return t, u
    return None


def _lerp(a, b, t):
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]


def split_at_intersections(curves: Sequence[tuple]):
    """P19: split every line segment at its interior crossings.

    Non-line curves and untouched lines are returned unchanged. This is the
    geometric core of trim (and of extend): both need the crossing points.
    """
    segs = [c for c in curves if c[0] == "line"]
    cuts = [[] for _ in segs]
    for i in range(len(segs)):
        a, b = segs[i][1], segs[i][2]
        for j in range(i + 1, len(segs)):
            c, d = segs[j][1], segs[j][2]
            hit = _seg_intersection(a, b, c, d)
            if hit is None:
                continue
            t, u = hit
            cuts[i].append(t)
            cuts[j].append(u)
    out = []
    for k, c in enumerate(segs):
        a, b = c[1], c[2]
        ts = [0.0] + sorted(cuts[k]) + [1.0]
        for lo, hi in zip(ts, ts[1:]):
            out.append(("line", tuple(_lerp(a, b, lo)), tuple(_lerp(a, b, hi))))
    for c in curves:
        if c[0] != "line":
            out.append(c)
    return out


def trim_at(curves: Sequence[tuple], pick, tol: float = 0.005):
    """P19: remove the line segment nearest pick, after splitting crossings.

    Returns (remaining_curves, n_removed).
    """
    split = split_at_intersections(curves)
    best_i = None
    best_d = None
    for i, c in enumerate(split):
        if c[0] != "line":
            continue
        mid = [(c[1][0] + c[2][0]) / 2.0, (c[1][1] + c[2][1]) / 2.0]
        d = math.hypot(mid[0] - pick[0], mid[1] - pick[1])
        if best_d is None or d < best_d:
            best_d, best_i = d, i
    if best_i is None or best_d is None or best_d > tol:
        return list(curves), 0
    return [c for i, c in enumerate(split) if i != best_i], 1


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

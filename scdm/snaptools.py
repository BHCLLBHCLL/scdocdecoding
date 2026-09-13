"""P287/R52: 图纸吸附靶点（端点 / 中点 / 交点 / 网格）。

Snapping is a pure function of (point, targets, tol) in view coordinates
(metres).  The sheet canvas calls it while dragging a dimension handle, and the
tests assert the result lands EXACTLY on the target (1e-12), not merely near it:
a snap that is only "close" silently pulls a dimension line off the geometry it
measures, which is worse than no snap at all.

Target priority on a distance tie: endpoint > intersection > midpoint.  An
endpoint is the most specific statement about the geometry, so it wins when two
targets coincide.

Grid snapping (when `grid > 0`) is unconditional - that is what a grid is for -
so a snap kind of '' means "no target was near and no grid was asked for".
"""
from __future__ import annotations

import math
from typing import Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Target = Tuple[float, float, str]

PRIORITY = {"end": 0, "cross": 1, "mid": 2}

# O(n^2) crossings are only collected for sheets this small (a drawing view has
# tens of segments; a tessellated mesh masquerading as one would not)
MAX_CROSS_SEGMENTS = 64


def segments(views: Iterable) -> List[Tuple[Point, Point]]:
    """Every non-degenerate segment of a [(name, [polyline, ...]), ...] view."""
    out: List[Tuple[Point, Point]] = []
    for _name, polys in views or ():
        for poly in polys or ():
            for a, b in zip(poly, poly[1:]):
                p = (float(a[0]), float(a[1]))
                q = (float(b[0]), float(b[1]))
                if math.dist(p, q) > 1e-12:
                    out.append((p, q))
    return out


def segment_crossing(p1: Point, p2: Point, p3: Point, p4: Point) -> Optional[Point]:
    """Exact intersection of two segments, or None when parallel/outside.

    Solved with the 2x2 Cramer form, so axis-aligned input lands on the exact
    coordinate instead of a near miss.
    """
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-15:
        return None
    dx = (p3[0] - p1[0], p3[1] - p1[1])
    t = (dx[0] * d2[1] - dx[1] * d2[0]) / den
    u = (dx[0] * d1[1] - dx[1] * d1[0]) / den
    lo, hi = -1e-12, 1.0 + 1e-12
    if lo <= t <= hi and lo <= u <= hi:
        return (p1[0] + t * d1[0], p1[1] + t * d1[1])
    return None


class SnapIndex:
    """Endpoint / midpoint / intersection targets of a sheet (+ optional grid)."""

    def __init__(self, views=(), grid: float = 0.0):
        self.grid = float(grid or 0.0)
        self.targets: List[Target] = []
        self.rebuild(views)

    def rebuild(self, views) -> None:
        """Re-read the targets from `views`.

        Call it whenever the drawing changes: an endpoint whose edge was deleted
        must stop attracting the dimension handle (the P287 illegal case).
        """
        segs = segments(views)
        pts: List[Target] = []
        for (p, q) in segs:
            pts.append((p[0], p[1], "end"))
            pts.append((q[0], q[1], "end"))
            pts.append(((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0, "mid"))
        if len(segs) <= MAX_CROSS_SEGMENTS:
            for i in range(len(segs)):
                for j in range(i + 1, len(segs)):
                    x = segment_crossing(segs[i][0], segs[i][1],
                                         segs[j][0], segs[j][1])
                    if x is not None:
                        pts.append((x[0], x[1], "cross"))
        self.targets = pts

    def nearest(self, p: Point, tol: float):
        """(point, kind, distance) of the best target within tol, else None."""
        best = None
        for (x, y, kind) in self.targets:
            d = math.hypot(x - p[0], y - p[1])
            if d > tol:
                continue
            key = (d, PRIORITY.get(kind, 9), x, y)
            if best is None or key < best[0]:
                best = (key, (x, y), kind, d)
        if best is None:
            return None
        return best[1], best[2], best[3]

    def grid_point(self, p: Point) -> Point:
        """Nearest grid node (exact multiples of `grid`)."""
        g = self.grid
        return (round(p[0] / g) * g, round(p[1] / g) * g)

    def snap(self, p: Point, tol: float) -> Tuple[Point, str]:
        """Snap `p`: nearest target within tol, else the grid node, else p."""
        hit = self.nearest(p, tol)
        if hit is not None:
            return hit[0], hit[1]
        if self.grid > 0:
            return self.grid_point(p), "grid"
        return (float(p[0]), float(p[1])), ""

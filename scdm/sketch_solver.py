"""H-gap #1: full 2D sketch constraint solver (damped least squares).

Replaces the fixed-iteration relaxation in `scdm.sketch.solve_constraints`
with a Levenberg–Marquardt solver over the sketch variable vector:

    variables = [x0, y0, x1, y1, ...] + circle radii

Each constraint contributes residual rows; the Jacobian is numerical
(central differences).  Convergence, DOF (rank of J vs variable count),
redundant-row count and conflict detection are all reported.

Constraint tuple forms (superset of the legacy sketch.py grammar):
    (DIST, i, j, value)               value may be float or expression str
    (HORIZONTAL, i, j) (VERTICAL, i, j)
    (COINCIDENT, i, j)
    (EQUAL, s1, s2) (PARALLEL, s1, s2) (PERPENDICULAR, s1, s2)
    (TANGENT, seg, center_i, radius)  radius may be float or expression str
    (MIDPOINT, pt, seg)
    (FIXED, pt, x, y)
    (RADIUS, center_i, radius)
    (POINT_ON, seg, pt)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from scdm.params import eval_expr

Point2 = List[float]

# constraint kinds (mirror sketch.py + extensions)
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
RADIUS = "radius"
POINT_ON = "point_on"

_ROW_KINDS = {DIST: 1, HORIZONTAL: 1, VERTICAL: 1, COINCIDENT: 2,
              PERPENDICULAR: 1, EQUAL: 1, PARALLEL: 1, TANGENT: 1,
              MIDPOINT: 2, FIXED: 2, RADIUS: 1, POINT_ON: 1}


@dataclass
class SolveReport:
    converged: bool
    iterations: int
    max_residual: float
    dof: int                    # variables - rank(J)
    redundant: int              # constraint rows - rank(J)
    conflicting: bool           # not converged AND dof <= 0
    message: str = ""


class SketchSolver:
    """Damped-least-squares solver over sketch points (+ circle radii)."""

    def __init__(self, points: Sequence[Point2],
                 segments: Optional[Sequence[Tuple[int, int]]] = None,
                 circles: Optional[Dict[int, float]] = None,
                 constraints: Sequence[tuple] = (),
                 param_table=None):
        self.points: List[Point2] = [p for p in points]  # keep refs: mutate caller lists in place
        self.segments: List[Tuple[int, int]] = list(segments or [])
        self.circles: Dict[int, float] = circles if circles is not None else {}
        self.constraints = list(constraints)
        self.table = param_table
        self.pinned: Dict[int, Tuple[float, float]] = {}
        # anchor points: move ~never during solve (reference-side geometry);
        # var indices derived from point indices
        self.anchor_points: set = set()
        # dimension expressions resolved once against the table + numbers
        self._resolved: Dict[Tuple, float] = {}
        for c in self.constraints:
            for v in c[3:]:
                if isinstance(v, str) and v not in self._resolved:
                    ns = self.table.resolve() if self.table is not None else {}
                    try:
                        self._resolved[v] = eval_expr(v, ns)
                    except ValueError:
                        # fall back: try own numeric params as namespace
                        if self.table is not None:
                            self._resolved[v] = eval_expr(v, {})
                        else:
                            raise

    # -- variable vector -------------------------------------------------
    def _nvars(self) -> int:
        return 2 * len(self.points) + len(self.circles)

    def _gather(self) -> List[float]:
        x: List[float] = []
        for p in self.points:
            x += [p[0], p[1]]
        x += list(self.circles.values())
        return x

    def _scatter(self, x: List[float]) -> None:
        for i, p in enumerate(self.points):
            p[0], p[1] = x[2 * i], x[2 * i + 1]
        for k, r in zip(self.circles.keys(), x[2 * len(self.points):]):
            self.circles[k] = r

    # -- helpers ----------------------------------------------------------
    def _seg(self, s: int) -> Optional[Tuple[int, int]]:
        return self.segments[s] if 0 <= s < len(self.segments) else None

    def _radius_of(self, center_i: int, x: List[float]) -> Optional[float]:
        # radius variable lookup by center point index
        for k, r in zip(self.circles.keys(), x[2 * len(self.points):]):
            if k == center_i:
                return r
        return None

    def _num(self, v) -> float:
        if isinstance(v, str):
            if v in self._resolved:
                return self._resolved[v]
            return float(v)     # numeric literal stored as string
        return float(v)

    def anchor(self, *point_indices: int) -> None:
        """Anchor points: they move ~never (reference-side geometry)."""
        self.anchor_points.update(point_indices)

    def _var_weights(self, n: int, anchor_w: float = 1e6) -> List[float]:
        w = [1.0] * n
        for pi in self.anchor_points:
            if 0 <= pi < len(self.points):
                w[2 * pi] = anchor_w
                w[2 * pi + 1] = anchor_w
        return w

    # -- residuals ----------------------------------------------------------
    def residuals(self, x: List[float]) -> List[float]:
        """Constraint residual rows at variable vector x."""
        # apply x to a shadow copy so residual helpers read consistent state
        for i in range(len(self.points)):
            self.points[i][0], self.points[i][1] = x[2 * i], x[2 * i + 1]
        for k, r in zip(self.circles.keys(), x[2 * len(self.points):]):
            self.circles[k] = r

        out: List[float] = []
        for c in self.constraints:
            kind = c[0]
            if kind == FIXED:
                _, i, fx, fy = c
                if 0 <= i < len(self.points):
                    out += [self.points[i][0] - fx, self.points[i][1] - fy]
                else:
                    out += [0.0, 0.0]
                continue
            if kind in (EQUAL, PARALLEL, PERPENDICULAR):
                s1, s2 = self._seg(c[1]), self._seg(c[2])
                if s1 is None or s2 is None:
                    continue
                (a1, b1), (a2, b2) = s1, s2
                if max(a1, b1, a2, b2) >= len(self.points):
                    continue
                p1, p2 = self.points[a1], self.points[b1]
                q1, q2 = self.points[a2], self.points[b2]
                d1 = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                d2 = math.hypot(q2[0] - q1[0], q2[1] - q1[1])
                if kind == EQUAL:
                    out.append(d1 - d2)
                elif kind == PARALLEL:
                    cr = ((p2[0] - p1[0]) * (q2[1] - q1[1])
                          - (p2[1] - p1[1]) * (q2[0] - q1[0]))
                    out.append(cr if d1 > 1e-12 and d2 > 1e-12 else 0.0)
                else:  # PERPENDICULAR
                    dt = ((p2[0] - p1[0]) * (q2[0] - q1[0])
                          + (p2[1] - p1[1]) * (q2[1] - q1[1]))
                    out.append(dt if d1 > 1e-12 and d2 > 1e-12 else 0.0)
                continue
            if kind == TANGENT:
                s = self._seg(c[1])
                ci = c[2]
                if s is None or ci >= len(self.points):
                    continue
                a, b = s
                if max(a, b) >= len(self.points):
                    continue
                p, q = self.points[a], self.points[b]
                cc = self.points[ci]
                L = math.hypot(q[0] - p[0], q[1] - p[1])
                if L < 1e-12:
                    out.append(0.0)
                    continue
                nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
                dist = (cc[0] - p[0]) * nx + (cc[1] - p[1]) * ny
                r = self._radius_of(ci, x)
                rad = r if r is not None else self._num(c[3])
                out.append(abs(dist) - rad)
                continue
            if kind == MIDPOINT:
                pt_i, s = c[1], self._seg(c[2])
                if s is None or pt_i >= len(self.points):
                    continue
                a, b = s
                if max(a, b) >= len(self.points):
                    continue
                p, q = self.points[a], self.points[b]
                out += [self.points[pt_i][0] - (p[0] + q[0]) / 2.0,
                        self.points[pt_i][1] - (p[1] + q[1]) / 2.0]
                continue
            if kind == POINT_ON:
                s, pt_i = self._seg(c[1]), c[2]
                if s is None or pt_i >= len(self.points):
                    continue
                a, b = s
                if max(a, b) >= len(self.points):
                    continue
                p, q = self.points[a], self.points[b]
                pt = self.points[pt_i]
                L2 = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
                if L2 < 1e-24:
                    out.append(0.0)
                    continue
                t = ((pt[0] - p[0]) * (q[0] - p[0])
                     + (pt[1] - p[1]) * (q[1] - p[1])) / L2
                t = max(0.0, min(1.0, t))
                cx, cy = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
                cr = ((q[0] - p[0]) * (pt[1] - cy)
                      - (q[1] - p[1]) * (pt[0] - cx))
                out.append(cr / math.sqrt(L2))
                continue
            if kind == RADIUS:
                ci, rv = c[1], self._num(c[2])
                r = self._radius_of(ci, x)
                out.append((r - rv) if r is not None else 0.0)
                continue
            # point-pair kinds
            i, j = c[1], c[2]
            if i >= len(self.points) or j >= len(self.points):
                continue
            p, q = self.points[i], self.points[j]
            dx, dy = q[0] - p[0], q[1] - p[1]
            if kind == DIST:
                val = self._num(c[3]) if len(c) > 3 else 0.0
                d = math.hypot(dx, dy)
                out.append(d - val)
            elif kind == HORIZONTAL:
                out.append(p[1] - q[1])
            elif kind == VERTICAL:
                out.append(p[0] - q[0])
            elif kind == COINCIDENT:
                out += [p[0] - q[0], p[1] - q[1]]
        # pinned points (drag anchors) are hard residuals
        for i, (fx, fy) in self.pinned.items():
            if 0 <= i < len(self.points):
                out += [self.points[i][0] - fx, self.points[i][1] - fy]
        return out

    # -- analysis -----------------------------------------------------------
    def _jacobian(self, x: List[float], r0: List[float]) -> List[List[float]]:
        n = len(x)
        m = len(r0)
        h = 1e-7
        J = [[0.0] * n for _ in range(m)]
        for j in range(n):
            xp = list(x); xp[j] += h
            rp = self.residuals(xp)
            for i in range(m):
                J[i][j] = (rp[i] - r0[i]) / h
        return J

    @staticmethod
    def _rank(J: List[List[float]], tol: float = 1e-9) -> int:
        """Numerical rank via Gram–Schmidt on rows."""
        rows = [row[:] for row in J if any(abs(v) > tol for v in row)]
        basis: List[List[float]] = []
        rank = 0
        for row in rows:
            v = row[:]
            for b in basis:
                dp = sum(a * c for a, c in zip(v, b))
                v = [a - dp * c for a, c in zip(v, b)]
            nrm = math.sqrt(sum(a * a for a in v))
            if nrm > 1e-7:
                basis.append([a / nrm for a in v])
                rank += 1
        return rank

    # -- solve ---------------------------------------------------------------
    def solve(self, max_iter: int = 200, tol: float = 1e-10,
              damping: float = 1e-3) -> SolveReport:
        x = self._gather()
        lam = damping
        r = self.residuals(x)
        iters = 0
        converged = math.sqrt(sum(v * v for v in r)) < tol
        for it in range(max_iter):
            iters = it + 1
            r = self.residuals(x)
            cost = sum(v * v for v in r)
            if math.sqrt(cost) < tol:
                converged = True
                break
            J = self._jacobian(x, r)
            n = len(x)
            # normal equations (J^T J + lam*diag) delta = -J^T r
            JT = [[J[i][j] for i in range(len(J))] for j in range(n)]
            a = [[sum(J[i][j1] * J[i][j2] for i in range(len(J)))
                  for j2 in range(n)] for j1 in range(n)]
            wv = self._var_weights(n)
            for k in range(n):
                # anchors get lam-independent constant stiffness so they
                # hold to ~1e-10 even as lam collapses
                a[k][k] += (1e10 if wv[k] > 1.0 else lam)
            g = [-sum(J[i][j] * r[i] for i in range(len(J))) for j in range(n)]
            delta = _gauss_solve(a, g)
            if delta is None:
                lam *= 3.0
                continue
            x_new = [x[k] + delta[k] for k in range(n)]
            r_new = self.residuals(x_new)
            new_cost = sum(v * v for v in r_new)
            if new_cost < cost:
                x = x_new
                lam = max(lam / 3.0, 1e-12)
                if math.sqrt(new_cost) < tol:
                    converged = True
                    break
            else:
                lam *= 3.0
                if lam > 1e12:
                    break
        r = self.residuals(x)
        max_res = max((abs(v) for v in r), default=0.0)
        # DOF analysis at the solved point (the jacobian perturbs state, so
        # the solved state is re-scattered afterwards)
        J = self._jacobian(x, r)
        rank = self._rank(J)
        nv = self._nvars()
        rows = len(r)
        dof = nv - rank
        redundant = max(0, rows - rank)
        # an under-constrained sketch always converges (free drift); failure
        # to converge means the constraints are inconsistent (conflicting)
        conflicting = not converged
        self._scatter(x)
        msg = ""
        if converged:
            msg = "收敛"
        elif conflicting:
            msg = "约束冲突或过约束"
        else:
            msg = "未收敛（可能欠约束漂移）"
        return SolveReport(converged, iters, max_res, dof, redundant,
                           conflicting, msg)


def _gauss_solve(a: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """Gaussian elimination with partial pivoting; None on singular."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-14:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        for r in range(n):
            if r != col and abs(m[r][col]) > 1e-300:
                f = m[r][col] / pv
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def solve_report(points: Sequence[Point2],
                 constraints: Sequence[tuple],
                 segments: Optional[Sequence[Tuple[int, int]]] = None,
                 circles: Optional[Dict[int, float]] = None,
                 param_table=None,
                 max_iter: int = 200) -> SolveReport:
    """Full solve with report; points are mutated in place (legacy API)."""
    solver = SketchSolver(points, segments, circles, constraints, param_table)
    return solver.solve(max_iter=max_iter)

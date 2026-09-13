"""P323/P324/R61: 面网格与可数质量指标（CAE 域首批）。

Meshing is a DERIVED artifact (rule 77): computed on demand, never written into
the document; what leaves the session is the REPORT.

Every per-triangle metric is closed form:
    area      = |e1 x e2| / 2
    quality   = 4*sqrt(3)*A / (a**2 + b**2 + c**2)   (exactly 1 for equilateral)
    aspect    = a / (2 * inradius)                   (sqrt(3) for equilateral)
    min_angle = smallest of the three angles (law of cosines)
    jacobian  = 2*A / (|e1| * |e2|) = sin(angle(e1, e2))  (sqrt(3)/2 equilateral)

The triangle-area sum approximates `K.area`: the RELATIVE gap is reported as
the discretization error instead of being hidden behind a loose tolerance, and
the counts (triangles / welded vertices / degenerate triangles) are the
countable half of the acceptance.
"""
from __future__ import annotations

import csv
import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

from scdm import kernel as K

DIST_KEYS = ("min", "p5", "median", "p95", "max")


def _percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile on a sorted copy (closed form, testable)."""
    if not values:
        return 0.0
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * max(0.0, min(1.0, q))
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def distribution(values: Sequence[float]) -> Dict[str, float]:
    """{min, p5, median, p95, max} of a sample (empty -> zeros)."""
    vals = [float(v) for v in values]
    return {"min": min(vals) if vals else 0.0,
            "p5": _percentile(vals, 0.05),
            "median": _percentile(vals, 0.5),
            "p95": _percentile(vals, 0.95),
            "max": max(vals) if vals else 0.0}


def triangle_metrics(p, q, r) -> Dict[str, float]:
    """Closed-form metrics of one triangle (see the module docstring)."""
    e1 = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
    e2 = (r[0] - p[0], r[1] - p[1], r[2] - p[2])
    e3 = (r[0] - q[0], r[1] - q[1], r[2] - q[2])
    cx = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
          e1[0] * e2[1] - e1[1] * e2[0])
    area = 0.5 * math.sqrt(sum(c * c for c in cx))
    l1 = math.sqrt(sum(v * v for v in e1))
    l2 = math.sqrt(sum(v * v for v in e2))
    l3 = math.sqrt(sum(v * v for v in e3))
    lsum = l1 * l1 + l2 * l2 + l3 * l3
    quality = (4.0 * math.sqrt(3.0) * area / lsum) if lsum > 0 else 0.0
    semi = (l1 + l2 + l3) / 2.0
    r_in = (area / semi) if semi > 0 else 0.0
    longest = max(l1, l2, l3)
    aspect = (longest / (2.0 * r_in)) if r_in > 0 else float("inf")
    jac = (2.0 * area / (l1 * l2)) if l1 > 0 and l2 > 0 else 0.0

    def _angle(x, y, z):
        if x <= 0 or y <= 0:
            return 0.0
        c = max(-1.0, min(1.0, (x * x + y * y - z * z) / (2.0 * x * y)))
        return math.degrees(math.acos(c))

    angles = [_angle(l1, l2, l3), _angle(l2, l3, l1), _angle(l3, l1, l2)]
    return {"area": area, "quality": quality, "aspect": aspect,
            "min_angle_deg": min(angles), "jacobian": jac,
            "max_edge": longest, "min_edge": min(l1, l2, l3)}


def mesh_shape(shape, deflection: float = 0.001, angle: float = 0.5,
               weld_tol: float = 1e-7) -> Dict:
    """Triangulate a shape into a welded mesh ({"vertices", "triangles", ...}).

    OCCT emits a vertex copy per face, so welding is what makes the vertex count
    a meaningful number (a box is 12 triangles over 8 vertices, not 24).
    """
    if shape is None or shape.IsNull():
        raise K.KernelError("网格化：形状为空")
    # OCCT's incremental mesher never COARSENS an existing triangulation, so a
    # coarse request on an already finely meshed shape silently returns the old
    # mesh (measured: 0.0005 and 0.005 deflection gave byte-identical stats).
    # Clearing first is what makes the requested deflection the real one.
    try:
        K._occ()["breptools"].Clean(shape)
    except Exception:
        pass
    verts, tris = K._mesh_tris(shape, deflection)
    if not tris:
        raise K.KernelError("网格化：形状没有可三角化的面")
    import numpy as np
    from scdm import facets as F
    v = np.asarray(verts, dtype=np.float64)
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    v, t = F.weld(v, t, tol=weld_tol)
    if len(t) == 0:
        raise K.KernelError("网格化：焊接后没有有效三角形")
    return {"vertices": [(float(p[0]), float(p[1]), float(p[2]))
                         for p in v.tolist()],
            "triangles": [(int(a), int(b), int(c)) for a, b, c in t.tolist()],
            "deflection": float(deflection), "angle": float(angle),
            "weld_tol": float(weld_tol)}


def mesh_stats(mesh: Dict, shape=None, tol_area: float = 1e-12) -> Dict:
    """Countable stats + area check + quality distributions of a mesh."""
    verts = mesh.get("vertices") or []
    tris = mesh.get("triangles") or []
    if not verts or not tris:
        raise K.KernelError("网格统计：空网格")
    areas: List[float] = []
    qualities: List[float] = []
    aspects: List[float] = []
    angles: List[float] = []
    jacobians: List[float] = []
    degenerate = 0
    flipped = 0
    for (i, j, k) in tris:
        m = triangle_metrics(verts[i], verts[j], verts[k])
        if m["area"] <= tol_area:
            degenerate += 1
            continue
        areas.append(m["area"])
        qualities.append(m["quality"])
        aspects.append(m["aspect"])
        angles.append(m["min_angle_deg"])
        jacobians.append(m["jacobian"])
    if not areas:
        raise K.KernelError("网格统计：全部三角形退化（tol_area=%g）" % tol_area)
    out = {
        "triangles": len(tris), "vertices": len(verts),
        "degenerate": degenerate, "valid": len(areas),
        "area": sum(areas),
        "min_area": min(areas), "max_area": max(areas),
        "quality": distribution(qualities),
        "aspect": distribution(aspects),
        "min_angle_deg": distribution(angles),
        "jacobian": distribution(jacobians),
        "deflection": float(mesh.get("deflection", 0.0)),
    }
    if shape is not None:
        ref = float(K.area(shape))
        out["area_ref"] = ref
        out["area_rel_error"] = (abs(out["area"] - ref) / ref) if ref > 0 else 0.0
    return out


def quality_report(shape, deflection: float = 0.001, tol_area: float = 1e-12,
                   name: str = "") -> Dict:
    """One-call report: mesh + stats (what P324 writes out)."""
    mesh = mesh_shape(shape, deflection=deflection)
    stats = mesh_stats(mesh, shape=shape, tol_area=tol_area)
    stats["name"] = name
    return stats


def write_report(path: str, report: Dict, fmt: str = "json") -> str:
    """Write a mesh report as JSON or CSV (one row per metric)."""
    fmt = str(fmt).lower()
    if fmt == "csv":
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric"] + list(DIST_KEYS))
            for key in ("quality", "aspect", "min_angle_deg", "jacobian"):
                d = report.get(key) or {}
                w.writerow([key] + ["%.9g" % float(d.get(k, 0.0))
                                    for k in DIST_KEYS])
            w.writerow(["triangles", report.get("triangles", 0), "", "", "", ""])
            w.writerow(["vertices", report.get("vertices", 0), "", "", "", ""])
            w.writerow(["degenerate", report.get("degenerate", 0), "", "", "", ""])
            w.writerow(["area", "%.9g" % report.get("area", 0.0), "", "", "", ""])
            w.writerow(["area_rel_error", "%.9g" % report.get("area_rel_error", 0.0),
                        "", "", "", ""])
        return path
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def read_report(path: str) -> Dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

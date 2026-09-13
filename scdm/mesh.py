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

# ----------------------------------------------------------------------
# P327: 质量门槛（可判定的验收）+ 体网格首批（体素四面体填充）
# ----------------------------------------------------------------------
DEFAULT_GATES = {"aspect_max": 24.0, "min_angle_min": 5.0, "jacobian_min": 0.03,
                 "quality_min": 0.05, "degenerate_max": 0}


def check_quality(mesh: Dict, gates: Optional[Dict] = None,
                  tol_area: float = 1e-12) -> Dict:
    """P327: 门槛判定——返回**超限清单**而不是布尔。

    Each violation is countable on its own: which triangle, which metric, the
    value, the limit and by how much it is over.  A gate is a decision, so the
    caller must be able to see what failed instead of just hearing "no".
    """
    g = dict(DEFAULT_GATES)
    g.update({k: float(v) for k, v in (gates or {}).items()})
    verts = mesh.get("vertices") or []
    tris = mesh.get("triangles") or []
    if not verts or not tris:
        raise K.KernelError("质量门槛：空网格")
    violations: List[Dict] = []
    degenerate = 0

    def bump(idx: int, metric: str, value: float, limit: float,
             kind: str = "max"):
        excess = (value - limit) if kind == "max" else (limit - value)
        if excess > 0:
            violations.append({"index": idx, "metric": metric,
                               "value": float(value), "limit": float(limit),
                               "excess": float(excess)})

    for idx, (i, j, k) in enumerate(tris):
        m = triangle_metrics(verts[i], verts[j], verts[k])
        if m["area"] <= tol_area or not math.isfinite(m["aspect"]):
            degenerate += 1
            continue
        bump(idx, "aspect", m["aspect"], g["aspect_max"])
        bump(idx, "min_angle_deg", m["min_angle_deg"], g["min_angle_min"],
             kind="min")
        bump(idx, "jacobian", m["jacobian"], g["jacobian_min"], kind="min")
        bump(idx, "quality", m["quality"], g["quality_min"], kind="min")
    if degenerate > g["degenerate_max"]:
        violations.append({"index": -1, "metric": "degenerate",
                           "value": float(degenerate),
                           "limit": float(g["degenerate_max"]),
                           "excess": float(degenerate - g["degenerate_max"])})
    return {"ok": not violations, "count": len(violations),
            "violations": violations, "triangles": len(tris),
            "degenerate": degenerate, "gates": g}


def tet_volume(p, q, r, s) -> float:
    """Closed form: |det(q-p, r-p, s-p)| / 6."""
    e1 = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
    e2 = (r[0] - p[0], r[1] - p[1], r[2] - p[2])
    e3 = (s[0] - p[0], s[1] - p[1], s[2] - p[2])
    det = (e1[0] * (e2[1] * e3[2] - e2[2] * e3[1])
           - e1[1] * (e2[0] * e3[2] - e2[2] * e3[0])
           + e1[2] * (e2[0] * e3[1] - e2[1] * e3[0]))
    return abs(det) / 6.0


# the standard 6-tetrahedron split of a cube around the diagonal 0-6
_CUBE_TETS = ((0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6),
              (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6))


def tet_fill(shape, cell: float, tol: float = 1e-9, boundary: str = "voxel",
             keep_boundary_shapes: bool = False,
             deflection: Optional[float] = None) -> Dict:
    """P327/P335: 体网格——体素四面体填充；@@boundary="clip"@@ 时边界格按精确裁剪计入。

    voxel: a cell whose centre is inside is kept whole (6 tetrahedra) - the
    volume error is O(cell) (the boundary layer is missing).
    clip:  the INTERIOR cells are still real tetrahedra, but every cell in the
    boundary band (the 26-neighbourhood of an interior cell) is intersected with
    the solid and its exact clipped volume is added, so the total volume matches
    @@K.volume(shape)@@ at boolean precision instead of O(cell).  A wall thinner
    than one cell can still be missed - voxel grids are the wrong tool there, and
    saying so is better than pretending.
    """
    from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TopAbs import TopAbs_IN, TopAbs_ON
    if shape is None or shape.IsNull():
        raise K.KernelError("体网格：形状为空")
    c = float(cell)
    if c <= 0:
        raise K.KernelError("体网格：格边长必须为正")
    # the chord deflection for the boundary fan is tied to the CELL, so the
    # fill's volume error scales with cell**2 (second order) instead of O(cell)
    dfx = float(deflection) if deflection is not None else c * 0.02
    if dfx <= 0:
        raise K.KernelError("体网格：弦差必须为正")
    # a REAL bounding box (K.bounding_box): the vertex-based boxes only see
    # vertices, and a full sphere has just its two poles - the grid collapsed to
    # a 1x1xn line (4 cells for a 20 mm sphere at 5 mm cells)
    lo, hi = K.bounding_box(shape)
    nx = max(1, int(math.ceil((hi[0] - lo[0]) / c - 1e-9)))
    ny = max(1, int(math.ceil((hi[1] - lo[1]) / c - 1e-9)))
    nz = max(1, int(math.ceil((hi[2] - lo[2]) / c - 1e-9)))
    mode = str(boundary).lower()
    if mode not in ("voxel", "clip", "tets"):
        raise K.KernelError("体网格：boundary 只能是 voxel / clip / tets")
    clf = BRepClass3d_SolidClassifier(shape)
    verts: List[Tuple[float, float, float]] = []
    tets: List[Tuple[int, int, int, int]] = []
    inside: set = set()
    cells = 0
    partial: set = set()
    for ix in range(nx):
        x0 = lo[0] + ix * c
        for iy in range(ny):
            y0 = lo[1] + iy * c
            for iz in range(nz):
                z0 = lo[2] + iz * c
                clf.Perform(gp_Pnt(x0 + c / 2.0, y0 + c / 2.0, z0 + c / 2.0), tol)
                if clf.State() not in (TopAbs_IN, TopAbs_ON):
                    continue
                inside.add((ix, iy, iz))
                if mode in ("clip", "tets"):
                    # sample the corners a hair INSIDE the cell: a point exactly
                    # on a face makes SolidClassifier answer OUT as often as ON,
                    # which mis-classified every cell of an axis-aligned box
                    eps = c * 1e-6
                    all_in = True
                    for cx in (x0 + eps, x0 + c - eps):
                        for cy in (y0 + eps, y0 + c - eps):
                            for cz in (z0 + eps, z0 + c - eps):
                                clf.Perform(gp_Pnt(cx, cy, cz), tol)
                                if clf.State() not in (TopAbs_IN, TopAbs_ON):
                                    all_in = False
                                    break
                            if not all_in:
                                break
                        if not all_in:
                            break
                    if not all_in:
                        partial.add((ix, iy, iz))
                        continue
                base = len(verts)
                verts.extend([(x0, y0, z0), (x0 + c, y0, z0),
                              (x0 + c, y0 + c, z0), (x0, y0 + c, z0),
                              (x0, y0, z0 + c), (x0 + c, y0, z0 + c),
                              (x0 + c, y0 + c, z0 + c), (x0, y0 + c, z0 + c)])
                tets.extend([tuple(base + i for i in t) for t in _CUBE_TETS])
                cells += 1
    if not cells:
        raise K.KernelError("体网格：没有格心落在实体内（格边长 %g 太大？）" % c)
    out = {"vertices": verts, "tets": tets, "cells": cells, "cell": c,
           "counts": (nx, ny, nz), "boundary": mode,
           "boundary_cells": 0, "boundary_volume": 0.0,
           "boundary_tets": 0, "boundary_tet_volume": 0.0,
           "boundary_tet_degenerate": 0,
           "deflection": dfx}
    if mode in ("clip", "tets"):
        # the boundary band: outside cells touching a solid cell (26-neighbours),
        # plus the cells whose centre was inside but whose corners are not (an
        # inside centre does NOT make the whole cell inside: keeping such cells
        # whole AND adding the clip over-counted the volume by 12.7%)
        cand = set(partial)
        for (ix, iy, iz) in inside:
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    for dz in (-2, -1, 0, 1, 2):
                        k = (ix + dx, iy + dy, iz + dz)
                        if (k not in inside and 0 <= k[0] < nx and 0 <= k[1] < ny
                                and 0 <= k[2] < nz):
                            cand.add(k)
        shapes = []
        for (ix, iy, iz) in sorted(cand):
            x0, y0, z0 = lo[0] + ix * c, lo[1] + iy * c, lo[2] + iz * c
            box = K.make_box(c, c, c, origin=(x0, y0, z0))
            piece = K.common(box, shape)
            v = float(K.volume(piece))
            if v <= tol:
                continue
            out["boundary_cells"] += 1
            out["boundary_volume"] += v
            if mode == "tets":
                # P339: a real tetrahedralisation of the clipped piece - fan the
                # boundary triangles to the piece centroid.  The piece's volume
                # then comes from the CHORD boundary, so the fill's error is
                # O(deflection**2) instead of the exact-boolean residual of the
                # clip mode (which did not shrink with the cell).
                fan = tetrahedralize_piece(piece, deflection=dfx)
                out["boundary_tets"] += len(fan["tets"])
                out["boundary_tet_volume"] += fan["volume"]
                out["boundary_tet_degenerate"] += fan["degenerate"]
                base_v = len(verts)
                verts.extend(fan["vertices"])
                tets.extend([(a + base_v, b + base_v, d + base_v, e + base_v)
                             for (a, b, d, e) in fan["tets"]])
            if keep_boundary_shapes:
                shapes.append(piece)
        if keep_boundary_shapes:
            out["boundary_shapes"] = shapes
    return out


def tetrahedralize_piece(piece, deflection: float = 0.001,
                         tol_volume: float = 1e-18) -> Dict:
    """P339: fan a clipped piece's boundary triangles to its centroid.

    One tetrahedron per boundary triangle, so the tet count is countable
    (= triangle count) and the volume comes from the chord boundary - which is
    exactly why the fill's error becomes second order in the deflection.
    """
    if piece is None or piece.IsNull():
        raise K.KernelError("裁剪片四面体化：形状为空")
    centre = K.cog(piece)
    verts: List[Tuple[float, float, float]] = [centre]
    tets: List[Tuple[int, int, int, int]] = []
    degenerate = 0
    faces = K.tessellate_faces(piece, deflection)
    if not faces:
        raise K.KernelError("裁剪片四面体化：没有可三角化的面")
    for fd in faces:
        fv = fd["vertices"]
        for (i, j, k) in fd["triangles"]:
            base = len(verts)
            verts.extend([fv[i], fv[j], fv[k]])
            v = tet_volume(centre, fv[i], fv[j], fv[k])
            if v <= tol_volume:
                degenerate += 1
                continue
            tets.append((0, base, base + 1, base + 2))
    if not tets:
        raise K.KernelError("裁剪片四面体化：全部退化")
    return {"vertices": verts, "tets": tets, "degenerate": degenerate,
            "volume": sum(tet_volume(verts[a], verts[b], verts[d], verts[e])
                          for (a, b, d, e) in tets)}


def tet_stats(fill: Dict, shape=None, tol_volume: float = 1e-18) -> Dict:
    """Volume sum + closed-form check against @@K.volume(shape)@@."""
    verts = fill.get("vertices") or []
    tets = fill.get("tets") or []
    if not verts or not tets:
        raise K.KernelError("体网格统计：空网格")
    vols: List[float] = []
    degenerate = 0
    for (a, b, cc, d) in tets:
        v = tet_volume(verts[a], verts[b], verts[cc], verts[d])
        if v <= tol_volume:
            degenerate += 1
            continue
        vols.append(v)
    if not vols:
        raise K.KernelError("体网格统计：全部四面体退化")
    bvol = float(fill.get("boundary_volume", 0.0))
    out = {"tets": len(tets), "vertices": len(verts),
           "cells": int(fill.get("cells", 0)),
           "degenerate": degenerate, "valid": len(vols),
           "volume": sum(vols), "min_volume": min(vols),
           "max_volume": max(vols), "cell": float(fill.get("cell", 0.0)),
           "boundary": str(fill.get("boundary", "voxel")),
           "boundary_cells": int(fill.get("boundary_cells", 0)),
           "boundary_volume": bvol,
           # P339: the boundary fan (one tetrahedron per boundary triangle)
           "boundary_tets": int(fill.get("boundary_tets", 0)),
           "boundary_tet_volume": float(fill.get("boundary_tet_volume", 0.0)),
           "boundary_tet_degenerate": int(fill.get("boundary_tet_degenerate", 0)),
           # P335/P339: "clip" adds the exact clipped piece volumes to the tet
           # sum; "tets" already counted the pieces as tetrahedra, so adding
           # them again would double count
           "volume_clip": (sum(vols) + bvol
                           if str(fill.get("boundary", "voxel")) == "clip"
                           else sum(vols))}
    if shape is not None:
        ref = float(K.volume(shape))
        out["volume_ref"] = ref
        out["volume_rel_error"] = (abs(out["volume"] - ref) / ref) if ref > 0 else 0.0
        out["volume_clip_rel_error"] = (abs(out["volume_clip"] - ref) / ref
                                        if ref > 0 else 0.0)
    return out


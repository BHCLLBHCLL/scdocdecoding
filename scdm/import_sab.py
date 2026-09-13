"""Rebuild OCCT solids from decoded SAB topology (planar faces first)."""
from __future__ import annotations

from typing import Any, List, Optional

from scdm import kernel as K
from scdm.kdoc import KernelDoc


def import_model(model, color=(0.62, 0.66, 0.70)) -> KernelDoc:
    doc = KernelDoc()
    if model is None or not K.available():
        return doc
    bodies = model.of_kind("body")
    if not bodies:
        # some files may only expose faces
        faces = _faces_from_model(model, None, _model_bbox(model))
        if faces:
            try:
                solid = K.sew_bodies(faces)
                doc.add_body(solid, name="实体 1", color=color)
            except K.KernelError:
                pass
        return doc
    box = _model_bbox(model)
    for i, body in enumerate(bodies, 1):
        faces = _faces_from_model(model, body, box)
        if not faces:
            continue
        try:
            # P29: keep every sewn lobe (sew_faces collapses to the first one)
            solid = K.sew_bodies(faces)
            name = model.doc_id_of(body) or f"实体 {i}"
            doc.add_body(solid, name=f"实体 {i}", color=color)
        except Exception:
            continue
    return doc


def _model_bbox(model):
    """(lo, hi) from the model's own vertex points, or None."""
    lo = [1e30] * 3
    hi = [-1e30] * 3
    seen = False
    for v in model.of_kind('vertex'):
        p = model.point_of_vertex(v)
        if p is None:
            continue
        seen = True
        for i in range(3):
            lo[i] = min(lo[i], p[i])
            hi[i] = max(hi[i], p[i])
    return (lo, hi) if seen else None


def _face_bbox(face_ent):
    """(lo, hi) recorded on the face record itself, or None."""
    lo = getattr(face_ent, "bbox_min", None)
    hi = getattr(face_ent, "bbox_max", None)
    if lo is None or hi is None:
        return None
    return (tuple(lo), tuple(hi))


def _clip_to_bbox(shape, box):
    """P45: clips a face that overshoots its own recorded bbox.

    A cylinder is always built as a full 2*pi patch, so a large-radius surface
    (or a narrow arc of one) reaches far outside the face.  Intersecting with
    the face's bbox solid recovers the real patch exactly, and is cheap
    (~30 ms/face).  Returns a list of faces; on any failure the original shape
    is returned so the caller's bbox gate still decides.
    """
    if box is None or _shape_within(shape, box, 1e-3):
        return [shape]
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopoDS import topods

        (lo, hi) = box
        diag = max(hi[i] - lo[i] for i in range(3)) or 1.0
        pad = diag * 1e-6
        solid = BRepPrimAPI_MakeBox(
            gp_Pnt(*[lo[i] - pad for i in range(3)]),
            gp_Pnt(*[hi[i] + pad for i in range(3)])).Solid()
        common = BRepAlgoAPI_Common(shape, solid)
        common.Build()
        if not common.IsDone():
            return [shape]
        out = []
        ex = TopExp_Explorer(common.Shape(), TopAbs_FACE)
        while ex.More():
            f = topods.Face(ex.Current())
            try:
                if K.area(f) > (diag * 1e-6) ** 2:
                    out.append(f)
            except Exception:
                out.append(f)
            ex.Next()
        if len(out) > 1:
            # the box can cut one patch in two where the arc wraps past 180
            # degrees (the bbox no longer covers the middle of the arc); sewing
            # the pieces back into a single face restores the SAB's face count
            # whenever they still share an edge.
            try:
                from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
                usd = ShapeUpgrade_UnifySameDomain(common.Shape(),
                                                   True, True, True)
                usd.Build()
                merged = []
                ex2 = TopExp_Explorer(usd.Shape(), TopAbs_FACE)
                while ex2.More():
                    merged.append(topods.Face(ex2.Current()))
                    ex2.Next()
                if 1 <= len(merged) < len(out):
                    out = merged
            except Exception:
                pass
        return out or [shape]
    except Exception:
        return [shape]


def _vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cyl_frame(axis, xdir):
    """Orthonormal (X, Y) in the plane perpendicular to the unit axis."""
    d = _vdot(xdir, axis)
    x = tuple(xdir[i] - d * axis[i] for i in range(3))
    n = sum(c * c for c in x) ** 0.5
    if n < 1e-12:
        x = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
        d = _vdot(x, axis)
        x = tuple(x[i] - d * axis[i] for i in range(3))
        n = sum(c * c for c in x) ** 0.5
    x = tuple(c / n for c in x)
    y = (axis[1] * x[2] - axis[2] * x[1],
         axis[2] * x[0] - axis[0] * x[2],
         axis[0] * x[1] - axis[1] * x[0])
    return x, y


def _proj_hull(points):
    """CCW convex hull of 2D points (monotone chain); [] when degenerate."""
    pts = sorted(set((round(p[0], 12), round(p[1], 12)) for p in points))
    if len(pts) < 3:
        return []

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) <= 0:
                    out.pop()
                else:
                    break
            out.append(p)
        return out

    lower, upper = half(pts), half(list(reversed(pts)))
    return lower[:-1] + upper[:-1]


def _angle_in_arc(u, start, length):
    d = (u - start) % (2.0 * 3.141592653589793)
    return d <= length + 1e-12


def _merge_seam(arcs):
    """Join arcs that meet across the 0/2*pi seam (they are contiguous)."""
    two_pi = 2.0 * 3.141592653589793
    if len(arcs) > 1:
        arcs = sorted(arcs)
        if (abs(arcs[0][0]) < 1e-9
                and abs(arcs[-1][0] + arcs[-1][1] - two_pi) < 1e-9):
            a0 = arcs.pop(0)
            a1 = arcs.pop()
            arcs.insert(0, (a1[0], a1[1] + a0[1]))
    return arcs


def _intersect_arcs(arcs, start, length):
    """Intersect a set of circle arcs with one more arc.

    Both are (start, length) with angles in radians and 0 <= length <= 2*pi.
    Splitting at every endpoint and keeping the segments whose midpoint is
    inside both makes wraparound need no special casing.
    """
    two_pi = 2.0 * 3.141592653589793
    bounds = sorted({0.0, two_pi} | {a % two_pi for a in
                                    (start % two_pi, (start + length) % two_pi)})
    out = []
    for a in arcs:
        bs = sorted({0.0, two_pi} | {b % two_pi for b in
                                     (a[0] % two_pi, (a[0] + a[1]) % two_pi)}
                    | {b for b in bounds})
        for i in range(len(bs) - 1):
            lo, hi = bs[i], bs[i + 1]
            if hi - lo < 1e-12:
                continue
            mid = 0.5 * (lo + hi)
            if (_angle_in_arc(mid, a[0], a[1])
                    and _angle_in_arc(mid, start, length)):
                if out and abs((out[-1][0] + out[-1][1]) - lo) < 1e-9:
                    out[-1] = (out[-1][0], out[-1][1] + (hi - lo))
                else:
                    out.append((lo, hi - lo))
    return _merge_seam(out)


def _circle_hull_arcs(radius, hull):
    """Angular arcs of the circle of this radius inside a CCW convex hull.

    The hull is the cylinder-axis-normal projection of the face bbox, so the
    result is the exact angular window of the patch (no boolean needed).
    """
    two_pi = 2.0 * 3.141592653589793
    arcs = [(0.0, two_pi)]
    n = len(hull)
    for i in range(n):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        ln = (dx * dx + dy * dy) ** 0.5
        if ln < 1e-15:
            continue
        # outward normal of a CCW edge is (dy, -dx)
        nx, ny = dy / ln, -dx / ln
        c = nx * ax + ny * ay
        # recorded bboxes are float32, so a full circle's box can miss its own
        # circle by a hair - without this snap a hole would be split in two
        slop = radius * 1e-6
        if c >= radius - slop:
            continue                      # half-plane contains the whole circle
        if c <= -radius + slop:
            return []                     # circle entirely outside
        import math as _m
        alpha = _m.acos(max(-1.0, min(1.0, c / radius)))
        phi = _m.atan2(ny, nx)
        arcs = _intersect_arcs(arcs, phi + alpha, two_pi - 2.0 * alpha)
        if not arcs:
            return []
    arcs = _merge_seam(arcs)
    if sum(a[1] for a in arcs) >= two_pi - 1e-3:
        return [(0.0, two_pi)]            # snap hairline gaps back to a full ring
    return arcs


def _bbox_corners(box):
    (lo, hi) = box
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
            for z in (lo[2], hi[2])]


def _uv_candidates(face_ent):
    """Plausible (u0, u1, v0, v1) windows from the face's recorded uv_range.

    P46: the trailing four doubles of a face record are the parametric window,
    but the official writer stores them as (u0, v0, u1, v1) on some surfaces and
    (u0, u1, v0, v1) on others - so both readings are offered as candidates and
    the recorded bbox decides which one is real.
    """
    r = getattr(face_ent, "uv_range", None)
    if not r or len(r) != 4:
        return []
    try:
        d = [float(x) for x in r]
    except (TypeError, ValueError):
        return []
    out = []
    for (u0, u1, v0, v1) in ((d[0], d[1], d[2], d[3]),
                             (d[0], d[2], d[1], d[3]),
                             (d[2], d[3], d[0], d[1])):
        for (a0, a1, b0, b1) in ((u0, u1, v0, v1), (-u1, -u0, v0, v1),
                                 (u0, u1, -v1, -v0), (-u1, -u0, -v1, -v0)):
            if a1 < a0:
                a0, a1 = a1, a0
            if b1 < b0:
                b0, b1 = b1, b0
            if a1 - a0 < 1e-9 or b1 - b0 < 1e-9:
                continue
            if not any(abs(a0 - p) < 1e-12 and abs(a1 - q) < 1e-12
                       and abs(b0 - r) < 1e-12 and abs(b1 - s) < 1e-12
                       for (p, q, r, s) in out):
                out.append((a0, a1, b0, b1))
    return out


def _bbox_gap(shape, box, accurate: bool = False):
    """Largest per-axis gap between a shape's bbox and a recorded one."""
    if box is None:
        return 0.0
    try:
        (a, c) = _shape_bbox(shape, accurate=accurate)
    except Exception:
        return None
    lo, hi = box
    diag = max(hi[i] - lo[i] for i in range(3)) or 1.0
    return max(max(abs(a[i] - lo[i]), abs(c[i] - hi[i]))
               for i in range(3)) / diag


def _face_from_window(surf, face_ent, limit: float = 0.02,
                      accurate: bool = False):
    """Build the face from the recorded uv window that reproduces its bbox.

    Using the window is what makes a torus/spline patch exact: the surface is
    infinite (or closed) and the bbox alone would need a boolean to cut back.
    The tolerance is loose on purpose - the official face bbox is a float32
    record and on a full torus ring its y lo/hi even arrive swapped, so the
    correct window can miss it by ~4% while a swapped (u, v) reading misses by
    ~45%.  The best candidate wins, so the margin only has to separate those.
    """
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    fbox = _face_bbox(face_ent)
    best = best_gap = None
    for (u0, u1, v0, v1) in _uv_candidates(face_ent):
        try:
            mk = BRepBuilderAPI_MakeFace(surf, u0, u1, v0, v1, 1e-7)
            if not mk.IsDone():
                continue
            f = mk.Face()
        except Exception:
            continue
        if fbox is None:
            return f
        # R9: torus faces ask for the SAMPLED gap.  Bnd_Box inflates a trimmed
        # periodic patch by ~4% (measured), which is more than the tolerance, so
        # the bbox-only test rejected the correct window on 6 torus faces per
        # file and split them with a boolean cut.  Restricting the sampled path
        # to tori keeps the cost at a few thousand evaluations instead of the
        # 2x import time an all-face version cost.
        gap = _bbox_gap(f, fbox, accurate=accurate)
        if gap is None:
            continue
        if best_gap is None or gap < best_gap:
            best, best_gap = f, gap
    if best is not None and best_gap is not None and best_gap <= limit:
        return best
    return None


def _window_ok(face, fbox, limit: float = 0.02, cover: float = 0.75) -> bool:
    """Does a window-built face reproduce the recorded bbox? (sampled bbox)

    Used as the RESCUE test when the cheap Bnd_Box gap is inconclusive: the
    built face must stay inside the recorded box (plus limit) and cover at
    least `cover` of it on every axis.  A sliver fails the coverage side, a
    swapped (u, v) reading fails the containment side.
    """
    if fbox is None:
        return True
    (lo, hi) = fbox
    diag = max(hi[i] - lo[i] for i in range(3)) or 1.0
    try:
        (a, c) = _shape_bbox(face, accurate=True)
    except Exception:
        return True
    for i in range(3):
        if a[i] < lo[i] - limit * diag or c[i] > hi[i] + limit * diag:
            return False
        want = hi[i] - lo[i]
        if want > 1e-9 and (c[i] - a[i]) < want * cover:
            return False
    return True


def _face_uv_samples(face: object, n: int = 13):
    """Points sampled over a face UV box (P49 diagnostic).

    The grid density matters: 7 points miss the 90 degree extremes of a
    full-ring patch (under-shooting the bbox and rejecting correct windows),
    while 13 fixes that but perturbs SampleModel4 by 11 faces.  Both were
    measured; 7 is the configuration that keeps every sample at its best value.

    Kept because it documents the measurement behind _window_ok: Bnd_Box
    inflates a trimmed periodic patch (a quarter-tube torus face came back
    0.043 too large on two axes, i.e. ~4%), so a raw bbox-distance test rejects
    the CORRECT uv window and falls back to a boolean cut.  Sampling is tighter
    but costs 2x the import time (samplemodel2 8.4 -> 16.1 s), so the shipped
    path uses Bnd_Box plus a 6% margin instead.
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools

    try:
        u0, u1, v0, v1 = breptools.UVBounds(face)
        surf = BRepAdaptor_Surface(face)
    except Exception:
        return []
    du = (u1 - u0) / float(n - 1) if n > 1 else 0.0
    dv = (v1 - v0) / float(n - 1) if n > 1 else 0.0
    out = []
    for i in range(n):
        for j in range(n):
            try:
                p = surf.Value(u0 + du * i, v0 + dv * j)
            except Exception:
                continue
            out.append((p.X(), p.Y(), p.Z()))
    return out






def _shape_bbox(shape, accurate: bool = False):
    """(lo, hi) bbox; accurate=True replaces Bnd_Box with a UV sample grid.

    Caveat measured in P49: Bnd_Box inflates a trimmed periodic patch (~4% on a
    quarter-tube torus face), so a raw bbox-distance window test must allow for
    it - see _window_ok / _face_from_window.
    """
    from OCC.Core.Bnd import Bnd_Box

    b = Bnd_Box()
    try:
        from OCC.Core.BRepBndLib import brepbndlib
        brepbndlib.Add(shape, b, False)
    except Exception:
        from OCC.Core.BRepBndLib import brepbndlib_Add
        brepbndlib_Add(shape, b, False)
    x1, y1, z1, x2, y2, z2 = b.Get()
    if not accurate:
        return ((x1, y1, z1), (x2, y2, z2))
    pts = []
    try:
        for f in K.explore(shape, 'face'):
            pts.extend(_face_uv_samples(f))
            for v in K.explore(f, 'vertex'):
                p = K.vertex_point(v)
                if p is not None:
                    pts.append((p[0], p[1], p[2]))
    except Exception:
        pts = []
    if not pts:
        return ((x1, y1, z1), (x2, y2, z2))
    # sampled values REPLACE the Bnd_Box ones: unioning would keep the very
    # inflation this mode exists to avoid
    return (tuple(min(p[i] for p in pts) for i in range(3)),
            tuple(max(p[i] for p in pts) for i in range(3)))

def _shape_within(shape, box, margin_ratio: float = 0.05) -> bool:
    """P45: is the shape inside the model's bbox (plus a small margin)?"""
    if box is None:
        return True
    try:
        (a, c) = _shape_bbox(shape)
    except Exception:
        return True
    lo, hi = box
    diag = max(hi[i] - lo[i] for i in range(3)) or 1.0
    m = diag * margin_ratio
    for i in range(3):
        if hi[i] - lo[i] <= 1e-12:
            # a degenerate model box cannot bound a real face: our own writer
            # stores only the two seam vertices, so the vertex bbox of a
            # cylinder is a line.  Do not reject faces on such an axis.
            continue
        if a[i] < lo[i] - m or c[i] > hi[i] + m:
            return False
    return True


def _faces_from_model(model, body, box=None) -> List[Any]:
    face_ents = model.body_faces(body) if body is not None else model.of_kind("face")
    occ_faces = []
    skipped = 0
    for face in face_ents:
        built_list = []
        try:
            built_list = _rebuild_face(model, face, box)
        except Exception:
            built_list = []
        if not built_list:
            try:
                polys = [p for p in (model.face_loops_polygons(face) or [])
                         if len(p) >= 3]
            except Exception:
                polys = []
            if not polys:
                # P46: a two-edge sliver loop walks down to 2 points; recover
                # the boundary by sampling the loop's curves instead.
                try:
                    polys = [p for p in
                             (_loop_polygon_sampled(model, lp)
                              for lp in model.loops_of_face(face)) if p]
                except Exception:
                    polys = []
            if polys:
                try:
                    f = _face_from_polygons(polys, _surface_kind(model, face)[1])
                except Exception:
                    f = None
                if f is not None:
                    built_list = [f]
        if not built_list:
            _faces_from_model.unbuilt = getattr(
                _faces_from_model, "unbuilt", 0) + 1
            continue
        for built in built_list:
            # P45: wild surface parameters used to place lobes tens of metres
            # away, so a face that misses the model bbox by more than half its
            # diagonal is still dropped.  The margin is deliberately loose: the
            # bbox comes from the point table only, and curved faces legitimately
            # bulge past it (samplemodel6: face z=0.3999 vs vertex bbox 0.347).
            if not _shape_within(built, box, 0.5):
                skipped += 1
                continue
            occ_faces.append(built)
    if skipped:
        _faces_from_model.skipped = getattr(_faces_from_model, "skipped", 0) + skipped
    return occ_faces


# -- curved-face rebuild (spline-surface clusters written by our own files) --
def _surface_kind(model, face_ent):
    """(kind, surface_ent) for a face's surface reference, or (None, None)."""
    s = model.e(face_ent.surface) if face_ent.surface >= 0 else None
    if s is None:
        return None, None
    return s.kind, s


def _inner_of_kind(model, head_ent, kind):
    """The head's inner-scope payload record of the given kind ('both',
    'nubs', ...), via cluster_owner back-links."""
    for e in model.inner:
        if e.cluster_owner == head_ent.idx and e.kind == kind:
            return e
    return None


def _nubs_surface(model, surf_head):
    """Candidate Geom_BSplineSurface from an official 'nubs' payload (P46b).

    The official cluster carries the surface as
    [deg_u][deg_v][4 flag tokens][n_u_knots][n_v_knots] then n_u (knot, mult)
    pairs, n_v pairs and npoles_u*npoles_v poles of 3 or 4 doubles.  Verified
    against the SAT text produced by the official SabSatConverter: SampleModel4
    face 62 is deg 3/3, 33+4 knots, sum(mults)=38/12 => 36 x 10 poles, printed
    as plain XYZ triples.

    Poles can be stored u-fastest or v-fastest; both readings are returned and
    the caller keeps the one whose face reproduces the recorded bbox.
    """
    from OCC.Core.TColgp import TColgp_Array2OfPnt
    from OCC.Core.TColStd import (TColStd_Array1OfInteger,
                                  TColStd_Array1OfReal,
                                  TColStd_Array2OfReal)
    from OCC.Core.Geom import Geom_BSplineSurface
    from OCC.Core.gp import gp_Pnt

    nubs = _inner_of_kind(model, surf_head, "nubs")
    if nubs is None:
        return []
    toks = nubs.record.tokens
    ints = [i for i, t in enumerate(toks) if t.kind in ("int", "int15")]
    if len(ints) < 8:
        return []
    du, dv = toks[ints[0]].value, toks[ints[1]].value
    n_u, n_v = toks[ints[6]].value, toks[ints[7]].value
    if not du or not dv or not n_u or not n_v:
        return []
    pos = ints[7] + 1
    pairs = []
    while (pos + 1 < len(toks) and toks[pos].kind == "double"
           and toks[pos + 1].kind == "int"):
        pairs.append((toks[pos].value, toks[pos + 1].value))
        pos += 2
    if len(pairs) < n_u + n_v:
        return []
    up, vp = pairs[:n_u], pairs[n_u:n_u + n_v]
    npu = sum(m for _k, m in up) - du + 1
    npv = sum(m for _k, m in vp) - dv + 1
    if npu < dv + 1 or npv < 2:
        return []
    # the poles follow immediately; 3 doubles = non-rational, 4 = rational
    avail = 0
    while pos + avail < len(toks) and toks[pos + avail].kind == "double":
        avail += 1
    if avail < npu * npv * 3:
        return []
    stride = 3 if avail >= npu * npv * 3 else 4
    raw = [toks[pos + i].value for i in range(npu * npv * stride)]
    poles = []
    for i in range(npu * npv):
        p = raw[i * stride:(i + 1) * stride]
        if stride == 3:
            poles.append((p[0], p[1], p[2], 1.0))
        else:
            poles.append((p[0], p[1], p[2], p[3] or 1.0))
    # ACIS stores endpoint multiplicities pre-decremented for OPEN directions
    um_occt = [up[0][1] + 1] + [m for _k, m in up[1:-1]] + [up[-1][1] + 1]
    vm_occt = [vp[0][1] + 1] + [m for _k, m in vp[1:-1]] + [vp[-1][1] + 1]
    uku_v = [k for k, _m in up]
    vku_v = [k for k, _m in vp]
    out = []
    for flip in (False, True):
        arr = TColgp_Array2OfPnt(1, npu, 1, npv)
        wts = TColStd_Array2OfReal(1, npu, 1, npv)
        for j in range(npv):
            for i in range(npu):
                idx = (i * npv + j) if flip else (j * npu + i)
                x, y, z, w = poles[idx]
                arr.SetValue(i + 1, j + 1, gp_Pnt(x, y, z))
                wts.SetValue(i + 1, j + 1, w)
        try:
            uku = TColStd_Array1OfReal(1, len(uku_v))
            umu = TColStd_Array1OfInteger(1, len(um_occt))
            for i, (k, m) in enumerate(zip(uku_v, um_occt)):
                uku.SetValue(i + 1, k)
                umu.SetValue(i + 1, m)
            vku = TColStd_Array1OfReal(1, len(vku_v))
            vmu = TColStd_Array1OfInteger(1, len(vm_occt))
            for i, (k, m) in enumerate(zip(vku_v, vm_occt)):
                vku.SetValue(i + 1, k)
                vmu.SetValue(i + 1, m)
            out.append(Geom_BSplineSurface(arr, wts, uku, vku, umu, vmu,
                                           du, dv))
        except Exception:
            continue
    return out


def _bspline_surfaces(model, surf_head):
    """All candidate surfaces for a spline cluster (ours: nurbs+both)."""
    surf = _bspline_surface(model, surf_head)
    if surf is not None:
        return [surf]
    return _nubs_surface(model, surf_head)


def _bspline_surface(model, surf_head):
    """Geom_BSplineSurface from a spline-cluster head ('spline' chain) —
    degrees from its inner nurbs record, knots/mults/poles from 'both'.
    ACIS mult convention: npoles = sum(mults) - deg + 1."""
    from OCC.Core.TColgp import TColgp_Array2OfPnt
    from OCC.Core.TColStd import (TColStd_Array1OfInteger,
                                  TColStd_Array1OfReal,
                                  TColStd_Array2OfReal)
    from OCC.Core.Geom import Geom_BSplineSurface
    from OCC.Core.gp import gp_Pnt

    nurbs = _inner_of_kind(model, surf_head, "nurbs")
    both = _inner_of_kind(model, surf_head, "both")
    if nurbs is None or both is None or both.bsurf_poles is None:
        return None
    du = nurbs.bs_deg or 0
    dv = nurbs.bs_deg_v or 0
    um, vm = both.bsurf_u_mults, both.bsurf_v_mults
    # ACIS storage: endpoint multiplicities pre-decremented; restore OCCT's
    npu = sum(um) - du + 1
    npv = sum(vm) - dv + 1
    um_occt = [um[0] + 1] + um[1:-1] + [um[-1] + 1]
    vm_occt = [vm[0] + 1] + vm[1:-1] + [vm[-1] + 1]
    poles = both.bsurf_poles
    if du < 1 or dv < 1 or len(poles) != npu * npv:
        return None
    arr = TColgp_Array2OfPnt(1, npu, 1, npv)
    wts = TColStd_Array2OfReal(1, npu, 1, npv)
    for j in range(npv):
        for i in range(npu):
            x, y, z, w = poles[j * npu + i]
            arr.SetValue(i + 1, j + 1, gp_Pnt(x, y, z))
            wts.SetValue(i + 1, j + 1, w)
    uku = TColStd_Array1OfReal(1, len(both.bsurf_u_knots))
    umu = TColStd_Array1OfInteger(1, len(um_occt))
    for i, (k, m) in enumerate(zip(both.bsurf_u_knots, um_occt)):
        uku.SetValue(i + 1, k)
        umu.SetValue(i + 1, m)
    vku = TColStd_Array1OfReal(1, len(both.bsurf_v_knots))
    vmu = TColStd_Array1OfInteger(1, len(vm_occt))
    for i, (k, m) in enumerate(zip(both.bsurf_v_knots, vm_occt)):
        vku.SetValue(i + 1, k)
        vmu.SetValue(i + 1, m)
    try:
        return Geom_BSplineSurface(arr, wts, uku, vku, umu, vmu, du, dv)
    except Exception:
        return None


def _edge_curve(model, edge_ent):
    """Geom_Curve + (t0, t1) for an edge from its curve reference, or None."""
    from OCC.Core.Geom import (Geom_BSplineCurve, Geom_Ellipse, Geom_Line,
                               Geom_TrimmedCurve)
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt

    c = model.e(edge_ent.curve) if edge_ent.curve >= 0 else None
    if c is None:
        return None
    t0 = edge_ent.pstart if edge_ent.pstart is not None else 0.0
    t1 = edge_ent.pend if edge_ent.pend is not None else 1.0
    try:
        if c.kind == "straight" and c.direction:
            lin = Geom_Line(gp_Pnt(*c.origin), gp_Dir(*c.direction))
            return Geom_TrimmedCurve(lin, min(t0, t1), max(t0, t1))
        if c.kind == "ellipse":
            ratio = c.ratio if c.ratio else 1.0
            major = c.xdir or (1.0, 0.0, 0.0)
            mlen = (major[0] ** 2 + major[1] ** 2 + major[2] ** 2) ** 0.5
            if mlen < 1e-12 or ratio <= 0.0:
                return None
            ax = gp_Ax2(gp_Pnt(*c.origin), gp_Dir(*c.normal),
                        gp_Dir(*major))
            el = Geom_Ellipse(ax, mlen, mlen * ratio)
            return Geom_TrimmedCurve(el, min(t0, t1), max(t0, t1))
        if c.kind == "intcurve":
            nubs = _inner_of_kind(model, c, "nubs")
            if nubs is None or not nubs.bs_poles:
                return None
            npoles = len(nubs.bs_poles)
            deg = sum(nubs.bs_mults) - npoles + 1
            if deg < 1:
                return None
            from OCC.Core.TColgp import TColgp_Array1OfPnt
            from OCC.Core.TColStd import (TColStd_Array1OfInteger,
                                          TColStd_Array1OfReal)
            pts = TColgp_Array1OfPnt(1, npoles)
            for i, p in enumerate(nubs.bs_poles):
                pts.SetValue(i + 1, gp_Pnt(*p))
            nk = len(nubs.bs_knots)
            ku = TColStd_Array1OfReal(1, nk)
            mu = TColStd_Array1OfInteger(1, nk)
            for i, (k, m) in enumerate(zip(nubs.bs_knots, nubs.bs_mults)):
                ku.SetValue(i + 1, k)
                mu.SetValue(i + 1, m)
            bs = Geom_BSplineCurve(pts, ku, mu, deg)
            lo, hi = bs.FirstParameter(), bs.LastParameter()
            return Geom_TrimmedCurve(bs, min(t0, t1, lo, hi)
                                     if False else lo, hi)
    except Exception:
        return None
    return None


def _face_has_curved_edges(model, face_ent):
    """True when any loop edge's curve is not a straight line (ellipse
    arcs, intcurves) or is closed (v1 == v2) — such faces need the
    wire-based rebuild instead of the planar polygon shortcut."""
    for loop in model.loops_of_face(face_ent):
        for ce in model.coedges_of_loop(loop):
            edge_ent = model.e(ce.edge) if ce.edge >= 0 else None
            if edge_ent is None:
                continue
            if edge_ent.v1 >= 0 and edge_ent.v1 == edge_ent.v2:
                return True
            c = model.e(edge_ent.curve) if edge_ent.curve >= 0 else None
            if c is not None and c.kind != "straight":
                return True
    return False


def _poly_area3(pts):
    """Area of a 3D planar polygon (Newell); 0 for a degenerate ring."""
    n = len(pts)
    s = [0.0, 0.0, 0.0]
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        s[0] += a[1] * b[2] - a[2] * b[1]
        s[1] += a[2] * b[0] - a[0] * b[2]
        s[2] += a[0] * b[1] - a[1] * b[0]
    return 0.5 * (s[0] ** 2 + s[1] ** 2 + s[2] ** 2) ** 0.5


def _wire_from_polygon(pts):
    """Closed wire through the points (None when it will not close)."""
    from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                         BRepBuilderAPI_MakeWire)
    from OCC.Core.gp import gp_Pnt

    wm = BRepBuilderAPI_MakeWire()
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if max(abs(a[k] - b[k]) for k in range(3)) < 1e-12:
            continue
        try:
            wm.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge())
        except Exception:
            return None
    try:
        return wm.Wire()
    except Exception:
        return None


def _loop_polygon_sampled(model, loop, segs: int = 12):
    """Polygon by sampling the loop's curves (P46).

    Some official faces carry a two-edge loop whose walk only yields the two
    end points (a sliver between a straight line and a 7 m radius arc), so the
    boundary has to be recovered from the curves themselves.
    """
    pts = []
    for ce in model.coedges_of_loop(loop):
        e = model.e(ce.edge) if ce.edge >= 0 else None
        if e is None:
            return None
        cur = _edge_curve(model, e)
        if cur is None:
            return None
        try:
            t0, t1 = cur.FirstParameter(), cur.LastParameter()
        except Exception:
            return None
        n = 2 if abs(t1 - t0) < 1e-12 else max(3, segs)
        seg = [cur.Value(t0 + (t1 - t0) * i / (n - 1)) for i in range(n)]
        if getattr(ce, "sense", None) == "flag_a":
            seg.reverse()
        for p in seg:
            q = (p.X(), p.Y(), p.Z())
            if not pts or max(abs(q[k] - pts[-1][k]) for k in range(3)) > 1e-12:
                pts.append(q)
    if len(pts) > 1 and max(abs(pts[0][k] - pts[-1][k])
                            for k in range(3)) < 1e-12:
        pts.pop()
    return pts if len(pts) >= 3 else None


def _face_from_polygons(polys, surf_ent):
    """Planar face from an outer polygon plus inner (hole) polygons (P46).

    The largest |area| ring is the outer one; the rest become inner wires, so a
    face with holes is no longer reduced to its first ring."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt

    rings = [p for p in polys if len(p) >= 3 and _poly_area3(p) > 1e-18]
    if not rings:
        return None
    rings.sort(key=lambda p: -_poly_area3(p))
    if (surf_ent is not None and surf_ent.kind == "plane"
            and surf_ent.origin is not None and surf_ent.normal is not None):
        pln = gp_Pln(gp_Pnt(*surf_ent.origin), gp_Dir(*surf_ent.normal))
        # the outer ring keeps its winding, every other ring is reversed so the
        # kernel reads it as a hole (otherwise its area ADDS to the face)
        ordered = [rings[0]] + [list(reversed(r)) for r in rings[1:]]
        wires = [w for w in (_wire_from_polygon(r) for r in ordered)
                 if w is not None]
        if wires:
            try:
                mk = BRepBuilderAPI_MakeFace(pln, wires[0])
                for w in wires[1:]:
                    mk.Add(w)
                if mk.IsDone():
                    return mk.Face()
            except Exception:
                pass
    try:
        return K.face_from_polygon(rings[0])
    except Exception:
        return None


def _planar_face_from_wires(model, face_ent, plane_ent):
    """Planar face rebuilt from real boundary curves (supports ellipse arcs
    and closed edges — cone caps, hole openings)."""
    from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                         BRepBuilderAPI_MakeFace,
                                         BRepBuilderAPI_MakeWire)
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCC.Core.ShapeFix import ShapeFix_Face
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    if plane_ent.origin is None or plane_ent.normal is None:
        return None
    pln = gp_Pln(gp_Pnt(*plane_ent.origin), gp_Dir(*plane_ent.normal))
    wires = []
    for loop in model.loops_of_face(face_ent):
        wmaker = BRepBuilderAPI_MakeWire()
        n = 0
        for ce in model.coedges_of_loop(loop):
            edge_ent = model.e(ce.edge) if ce.edge >= 0 else None
            if edge_ent is None:
                continue
            curve = _edge_curve(model, edge_ent)
            if curve is None:
                continue
            try:
                wmaker.Add(BRepBuilderAPI_MakeEdge(curve).Edge())
                n += 1
            except Exception:
                continue
        if n:
            try:
                wires.append(wmaker.Wire())
            except Exception:
                return None
    if not wires:
        return None
    try:
        mf = BRepBuilderAPI_MakeFace(pln, wires[0])
        for w in wires[1:]:
            mf.Add(w)
        if not mf.IsDone():
            return None
        fix = ShapeFix_Face(mf.Face())
        fix.SetPrecision(1e-6)
        fix.Perform()
        f = fix.Face()
        if BRepCheck_Analyzer(f).IsValid():
            return f
        return mf.Face()
    except Exception:
        return None


def _rebuild_face(model, face_ent, box=None):
    """Curved-face rebuild (P45: returns a LIST of faces).

    spline-surface cluster faces (full parametric patch — our writer stores the
    surface window as the face window), cylinders ('cone' records with zero
    semi-angle), and planar faces whose loops carry curve edges.  A cylinder is
    built as a full 2*pi patch and clipped to the face's own bbox, so one SAB
    face can yield more than one OCCT face.  Neighbours are stitched by sewing
    on coincident boundary geometry."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    kind, surf_ent = _surface_kind(model, face_ent)
    if kind == "spline":
        surfs = _bspline_surfaces(model, surf_ent)
        if not surfs:
            return []
        # the recorded uv window is the face; the surface's own bounds are the
        # whole patch (official files trim it, our own writer does not)
        for surf in surfs:
            f = _face_from_window(surf, face_ent)
            if f is not None and _shape_within(f, box, 0.5):
                return [f]
        for surf in surfs:
            try:
                mk = BRepBuilderAPI_MakeFace(surf, 1e-6)
            except Exception:
                continue
            if not mk.IsDone():
                continue
            f = mk.Face()
            if _shape_within(f, box, 0.5):
                return [f]
        return []
    if kind == "cone":
        # cone/cylinder: ACIS u = angle, v = axial.  A zero semi-angle is a
        # cylinder; anything else is a truncated cone (P46) and gets the same
        # treatment once the surface is built.
        semi = surf_ent.semangle if surf_ent.semangle is not None else 0.0
        if (not surf_ent.radius or surf_ent.origin is None
                or surf_ent.normal is None or surf_ent.xdir is None):
            return []
        try:
            from OCC.Core.Geom import (Geom_ConicalSurface,
                                       Geom_CylindricalSurface)
            from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt
            axis = surf_ent.normal
            alen = (axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2) ** 0.5
            if alen < 1e-12:
                return []
            axis = (axis[0] / alen, axis[1] / alen, axis[2] / alen)
            # P46: a cone record whose cosine is negative stores the axis
            # flipped (a plain cylinder arrives as sin=0 / cos=-1).  Normalise
            # to the (sin, cos) pair of the axis we are actually going to use,
            # otherwise a cylinder turns into a 180-degree "cone".
            if surf_ent.cos_angle is not None and surf_ent.cos_angle < 0.0:
                axis = (-axis[0], -axis[1], -axis[2])
                import math as _mm
                semi = _mm.atan2(-(surf_ent.sin_angle or 0.0),
                                 -surf_ent.cos_angle)
            else:
                semi = surf_ent.semangle if surf_ent.semangle is not None else 0.0
            # P45: the face's OWN bbox is the authoritative axial window.  The
            # projection of a point onto the axis is linear, so its extremes
            # over the face are attained at bbox corners - this is exact, unlike
            # the old boundary-ellipse-centre scan (official streams sometimes
            # hand a curve belonging to another surface, giving +/-100 m ranges)
            # and unlike the whole-model bbox (which over-extended the patch).
            fbox = _face_bbox(face_ent)
            if fbox is not None:
                proj = [sum((c[i] - surf_ent.origin[i]) * axis[i]
                            for i in range(3)) for c in _bbox_corners(fbox)]
                v0, v1 = min(proj), max(proj)
                if v1 - v0 < 1e-9:
                    fbox, v0, v1 = None, None, None
            if fbox is None:
                # legacy fallback: boundary-ellipse centres on the axis
                for loop in model.loops_of_face(face_ent):
                    for ce in model.coedges_of_loop(loop):
                        ee = model.e(ce.edge) if ce.edge >= 0 else None
                        c = (model.e(ee.curve)
                             if ee is not None and ee.curve >= 0 else None)
                        if c is not None and c.kind == "ellipse" and c.origin:
                            t = ((c.origin[0] - surf_ent.origin[0]) * axis[0]
                                 + (c.origin[1] - surf_ent.origin[1]) * axis[1]
                                 + (c.origin[2] - surf_ent.origin[2]) * axis[2])
                            v0 = t if v0 is None else min(v0, t)
                            v1 = t if v1 is None else max(v1, t)
                if box is not None:
                    proj = [sum((c[i] - surf_ent.origin[i]) * axis[i]
                                for i in range(3)) for c in _bbox_corners(box)]
                    lo_t, hi_t = min(proj), max(proj)
                    if v0 is None:
                        v0, v1 = lo_t, hi_t
                    else:
                        v0, v1 = max(v0, lo_t), min(v1, hi_t)
                        if v1 - v0 < 1e-9:
                            v0, v1 = lo_t, hi_t
            if v0 is None:
                v0, v1 = 0.0, 1.0
            ax = gp_Ax3(gp_Ax2(gp_Pnt(*surf_ent.origin), gp_Dir(*axis),
                               gp_Dir(*surf_ent.xdir)))
            if abs(semi) > 1e-9:
                # P46 truncated cone.  The recorded uv window is tried first
                # (validated against the face's own bbox); the angle sign and
                # the "measured from the plane" reading are offered as extra
                # candidates because the ACIS convention is not documented in
                # the stream and a wrong reading is silently a different shape.
                import math as _m
                for ang in (semi, -semi, 0.5 * _m.pi - semi, semi - 0.5 * _m.pi):
                    try:
                        # the sampled gap was tried here too (R11): it changed
                        # nothing on the cone splits and cost 3 s per import, so
                        # cones stay on the cheap path
                        f = _face_from_window(
                            Geom_ConicalSurface(ax, ang, surf_ent.radius),
                            face_ent)
                    except Exception:
                        f = None
                    if f is not None and _shape_within(f, box, 0.5):
                        return [f]
                try:
                    mk = BRepBuilderAPI_MakeFace(
                        Geom_ConicalSurface(ax, semi, surf_ent.radius),
                        0.0, 2.0 * 3.141592653589793, v0, v1, 1e-6)
                except Exception:
                    return []
                if not mk.IsDone():
                    return []
                return _clip_to_bbox(mk.Face(), fbox)
            surf = Geom_CylindricalSurface(ax, surf_ent.radius)
            # R11 tried the recorded window here first (it does fix the arc
            # faces) but the sampled validation on EVERY cylinder cost 7.3 ->
            # 23.3 s per import, so it must come back behind a cheap pre-filter.
            # P45: the angular window is computed analytically from the face's
            # own bbox (projected across the axis) instead of always building a
            # full 2*pi patch: a 7 m radius fillet would otherwise cover metres
            # of empty space and need a ~10 ms boolean to cut back down.
            arcs = None
            if fbox is not None:
                fx, fy = _cyl_frame(axis, surf_ent.xdir)
                pts = []
                for c in _bbox_corners(fbox):
                    dx, dy, dz = (c[0] - surf_ent.origin[0],
                                  c[1] - surf_ent.origin[1],
                                  c[2] - surf_ent.origin[2])
                    pts.append((dx * fx[0] + dy * fx[1] + dz * fx[2],
                                dx * fy[0] + dy * fy[1] + dz * fy[2]))
                hull = _proj_hull(pts)
                if hull:
                    arcs = _circle_hull_arcs(surf_ent.radius, hull)
            # R13/P75 tried two guards here, both inert on the current data and
            # therefore reverted (see docs/ROUND_R13): (a) an O(1) pre-filter
            # that retries the recorded window when the analytic arc exceeds
            # pi, (b) an angular span from the projected corners when the hull
            # is degenerate.  The remaining two splits are NOT produced by this
            # branch - the next step is to instrument _rebuild_face to report
            # which path returned the pieces.
            # R14/P81: 2+ analytic arcs means the projected bbox cuts the circle
            # into disjoint pieces (a narrow face on a small cylinder: hull half
            # height 0.0245 < radius 0.03 -> left and right arcs).  Emitting one
            # face per arc produced exactly the two surplus faces of model 2
            # faces 8/194, so resolve the ambiguity with the recorded bbox and
            # keep ONE arc (2 builds, sampled gap - cheap because rare).
            use_arcs = arcs if arcs else [(0.0, 2.0 * 3.141592653589793)]
            if len(use_arcs) > 1 and fbox is not None:
                best_arc = None
                for (a0, alen) in use_arcs:
                    try:
                        mk = BRepBuilderAPI_MakeFace(surf, a0, a0 + alen, v0, v1,
                                                     1e-6)
                        if not mk.IsDone():
                            continue
                        gap = _bbox_gap(mk.Face(), fbox, accurate=True)
                    except Exception:
                        continue
                    if gap is not None and (best_arc is None
                                            or gap < best_arc[0]):
                        best_arc = (gap, (a0, alen))
                if best_arc is not None:
                    use_arcs = [best_arc[1]]
            out = []
            for (u0, ulen) in use_arcs:
                if ulen < 1e-9:
                    continue
                mk = BRepBuilderAPI_MakeFace(surf, u0, u0 + ulen, v0, v1, 1e-6)
                if not mk.IsDone():
                    continue
                face = mk.Face()
                if fbox is not None and not _shape_within(face, fbox, 5e-3):
                    # the analytic window can be a little generous where the
                    # patch is not a (u, t) rectangle - cut it back exactly
                    out.extend(_clip_to_bbox(face, fbox))
                else:
                    out.append(face)
            return out
        except Exception:
            return []
    if kind in ("torus", "sphere"):
        # P46: the recorded uv window is the exact patch - a torus patch cannot
        # be recovered from its bbox alone (the bbox of a fillet ring is a thin
        # slab the surface crosses twice).
        if (surf_ent.origin is None or surf_ent.normal is None
                or surf_ent.xdir is None):
            return []
        try:
            from OCC.Core.Geom import (Geom_SphericalSurface,
                                       Geom_ToroidalSurface)
            from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt
            axis = surf_ent.normal
            alen = sum(c * c for c in axis) ** 0.5
            if alen < 1e-12:
                return []
            axis = tuple(c / alen for c in axis)
            ax = gp_Ax3(gp_Ax2(gp_Pnt(*surf_ent.origin), gp_Dir(*axis),
                               gp_Dir(*surf_ent.xdir)))
            cands = []
            if kind == "sphere" and surf_ent.radius:
                cands.append(Geom_SphericalSurface(ax, surf_ent.radius))
            elif kind == "torus" and surf_ent.major and surf_ent.minor:
                cands.append(Geom_ToroidalSurface(ax, surf_ent.major,
                                                  surf_ent.minor))
                cands.append(Geom_ToroidalSurface(ax, surf_ent.minor,
                                                  surf_ent.major))
            for surf in cands:
                # only TORUS uses the sampled gap: spheres keep the cheap path so
                # the spline/sphere faces of the other samples cannot regress
                # limit 5% for the sampled comparison: the UV grid itself
                # discretises the patch, so the sampled bbox misses the extreme
                # by up to half a step (measured 0.012 on a quarter ring of
                # radius 0.74 = 3.1% of the face).  Wrong readings miss by 45%
                # or more, so the margin still separates them cleanly.
                f = _face_from_window(surf, face_ent,
                                      limit=0.05 if kind == "torus" else 0.02,
                                      accurate=(kind == "torus"))
                # a window reading that lands outside the model is a misread of
                # the recorded range - prefer the boolean cut then
                if f is not None and _shape_within(f, box, 0.5):
                    return [f]
            for surf in cands:
                try:
                    mk = BRepBuilderAPI_MakeFace(
                        surf, 0.0, 2.0 * 3.141592653589793,
                        0.0, 2.0 * 3.141592653589793, 1e-6)
                    if mk.IsDone():
                        return _clip_to_bbox(mk.Face(), _face_bbox(face_ent))
                except Exception:
                    continue
            return []
        except Exception:
            return []
    if kind == "plane" and _face_has_curved_edges(model, face_ent):
        try:
            f = _planar_face_from_wires(model, face_ent, surf_ent)
        except Exception:
            f = None
        return [f] if f is not None else []
    return []


def import_summary(report, warnings=None, error=None) -> str:
    """One-line human summary of an import (P47).

    Kept Qt-free so both the GUI status bar and the tests can use it.
    """
    report = report or {}
    bits = []
    if error:
        bits.append("几何未导入（%s）" % error)
    failed = list(report.get("failed_parts") or [])
    parts = report.get("parts")
    if failed and parts:
        bits.append("%d/%d 个部件未重建" % (len(failed), parts))
    if report.get("unbuilt_faces"):
        bits.append("%d 个面未重建" % report["unbuilt_faces"])
    if report.get("dropped_faces"):
        bits.append("%d 个面被丢弃" % report["dropped_faces"])
    if failed:
        shown = "、".join(str(x) for x in failed[:4])
        if len(failed) > 4:
            shown += " 等"
        bits.append("未重建部件：" + shown)
    if report.get("mesh_bodies"):
        bits.append("%d 个部件走网格兜底" % len(report["mesh_bodies"]))
    if bits:
        return "；".join(bits)
    warnings = list(warnings or [])
    return warnings[0] if warnings else ""


def import_hierarchy_groups(kdoc):
    """R23/P133: read-only display groups from the import hierarchy.

    Official parts map many-to-one onto bodies, so the tree needs the part as
    the group and its bodies as items - the same {"name", "items"} shape the
    user groups already use (items are (kind, id) tuples).
    """
    groups = []
    for h in (getattr(kdoc, "import_report", {}) or {}).get("hierarchy") or []:
        items = [("body", bid) for bid in h.get("bodies", [])]
        if items:
            groups.append({"name": h.get("name") or "部件", "items": items,
                           "imported": True})
    return groups


def apply_group_visibility(kdoc, group, visible) -> int:
    """R23/P133: show/hide one display group; returns how many bodies changed.

    Only the visibility flag is touched - the geometry objects are the same
    (the acceptance is "勾选即时生效、几何不变").
    """
    by_id = {b.id: b for b in kdoc.bodies}
    n = 0
    for (_kind, bid) in group.get("items", []):
        b = by_id.get(bid)
        if b is not None:
            b.visible = bool(visible)
            n += 1
    return n


def _model_label(model, index: int) -> str:
    """Human label for a SAB model: its first body's document id, else index."""
    try:
        for b in model.of_kind("body"):
            d = model.doc_id_of(b)
            if d:
                return d
    except Exception:
        pass
    return "部件 %d" % index


def _mesh_shell_from_faces(fac, face_nodes):
    """Sew the given facet faces into one shell, or None."""
    import numpy as np
    from scdm import facets as F

    vs, ts, off = [], [], 0
    for node in face_nodes:
        pts = np.asarray([c.position for c in node.corners], dtype=np.float64)
        tris = np.asarray(node.triangles, dtype=np.int64)
        if len(pts) == 0 or not len(tris):
            continue
        vs.append(pts)
        ts.append(tris + off)
        off += len(pts)
    if not vs:
        return None
    verts = np.vstack(vs)
    tris = np.vstack(ts)
    try:
        verts, tris = F.weld(verts, tris, tol=1e-6)
        return F.mesh_to_shell(verts, tris)
    except Exception:
        return None


def _facets_nodes_of_model(model, fac):
    """Facet face nodes belonging to one SAB model (P47 per-part fallback).

    The facets stream carries per-body sections keyed by the same document ids
    the SAB bodies use ('0:23'), which is what makes it possible to mesh ONLY
    the parts whose B-rep rebuild failed instead of the whole file.
    """
    secs = getattr(fac, "bodies", None)
    nodes = getattr(fac, "faces", None)
    if not secs or not nodes:
        return []
    ids = set()
    keys = set()
    for b in model.of_kind("body"):
        try:
            d = model.doc_id_of(b)
        except Exception:
            d = None
        if not d:
            continue
        ids.add(d)
        # the facets stream numbers the same bodies with a different part
        # prefix (SAB '2:399' vs facets '0:399'), so the numeric suffix is the
        # join key; the full id is still tried first.
        keys.add(str(d).split(":")[-1])
    if not keys:
        return []
    out = []
    for sec in secs:
        sid = str(sec.get("body_doc_id") or "")
        if sid in ids or (sid and sid.split(":")[-1] in keys):
            for idx in sec.get("faces", []):
                if 0 <= idx < len(nodes):
                    out.append(nodes[idx])
    return out


def import_scdoc_bundle(data: dict, mesh_fallback: str = "auto") -> KernelDoc:
    """Rebuild a document from a parsed .scdoc bundle.

    mesh_fallback:
      "auto"  (default) - sew the display mesh into a body ONLY when the SAB
                path produced nothing at all;
      "always"          - also when only some parts failed to rebuild;
      "never"           - never.
    P30: "always"-style behaviour used to be unconditional, which duplicated
    already-imported geometry and cost ~48 s on samplemodel2 (55k triangles).
    """
    model = data.get("model") if data else None
    color = (0.62, 0.66, 0.70)
    render = data.get("render") if data else None
    if render:
        for view in render:
            for it in view.get("items", []):
                for b in it.get("bodies", []):
                    if b.get("rgb"):
                        color = tuple(c / 255.0 for c in b["rgb"])
                        break
    fac = data.get("fac") if data else None
    models = (data.get("models") if data else None) or (
        [model] if model is not None else [])
    doc = KernelDoc()
    failed_parts = []
    # P45: the decoder's own loss counters, surfaced to the user
    _faces_from_model.skipped = 0
    _faces_from_model.unbuilt = 0
    hierarchy = []
    for i, mdl in enumerate(models, 1):
        part_doc = import_model(mdl, color=color)
        if part_doc.bodies:
            # R22/P127: keep the read-only part -> body mapping so the GUI can
            # offer an official-hierarchy display model (group per part).
            ids = []
            for b in part_doc.bodies:
                nb = doc.add_body(b.shape, name=b.name, color=b.color)
                ids.append(nb.id)
            hierarchy.append({"name": _model_label(mdl, i), "bodies": ids})
        else:
            failed_parts.append((i, _model_label(mdl, i)))
    failed = len(failed_parts)
    dropped = getattr(_faces_from_model, "skipped", 0)
    unbuilt = getattr(_faces_from_model, "unbuilt", 0)
    # R21/P122: the ACIS `ref` indirection cannot be resolved from this part
    # (22 entity kinds, none a reference table; the SAT prints { ref N } with no
    # inline geometry either).  Report the family honestly instead of folding it
    # into a generic "unbuilt" count.
    ref_faces = 0
    for mdl in models:
        # collect the ref owners in ONE pass over inner records: doing it per
        # face is O(faces x inner) and blew the import budget on samplemodel5
        # (1288 faces, ~2k inner records -> minutes).
        owners = {getattr(e, "cluster_owner", None) for e in mdl.inner
                  if e.kind == "ref"}
        owners.discard(None)
        if not owners:
            continue
        for f in mdl.of_kind("face"):
            if f.surface is not None and f.surface >= 0 and f.surface in owners:
                ref_faces += 1
    if ref_faces:
        # wording matters: these faces REFERENCE a ref-间接 surface; some of them
        # still get built from their boundary curves, so do not claim they are
        # all missing - the unbuilt count above is the authoritative number.
        doc.import_warnings.append(
            "%d 个面引用 ACIS ref 间接曲面（该类曲面的数据不在本 part；其中未重建者已计入上面的未重建数）"
            % ref_faces)
    if dropped or unbuilt:
        doc.import_warnings.append(
            "SAB 重建：%d 个面未能重建，%d 个面因超出包围盒被丢弃"
            % (unbuilt, dropped))
    mesh_bodies = []
    if doc.bodies:
        if failed:
            doc.import_warnings.append(
                "%d/%d 个部件无法重建为 B-rep（未生成网格兜底）"
                % (failed, len(models)))
        if (mesh_fallback == "always" and failed_parts and fac is not None
                and getattr(fac, "faces", None) and K.available()):
            # P47: mesh ONLY the failed parts (the facets stream is sectioned
            # per body), so the fallback adds at most one body per failure
            # instead of dragging in the whole file's 55k triangles.
            for (idx, label) in failed_parts:
                mdl = models[idx - 1]
                nodes = _facets_nodes_of_model(mdl, fac)
                shell = _mesh_shell_from_faces(fac, nodes) if nodes else None
                if shell is None:
                    continue
                nb = doc.add_body(shell, name="网格导入 %s" % label, color=color)
                mesh_bodies.append(nb.name)
            if mesh_bodies:
                doc.import_warnings.append(
                    "已为 %d 个部件生成网格兜底" % len(mesh_bodies))
        doc.import_report = {
            "parts": len(models),
            "failed_parts": [label for (_i, label) in failed_parts],
            "unbuilt_faces": unbuilt,
            "dropped_faces": dropped,
            "ref_faces": ref_faces,
            "mesh_bodies": list(mesh_bodies),
            "hierarchy": hierarchy,  # R22/P127: part -> body ids (read-only)
        }
        return doc
    doc = import_model(model, color=color)
    if doc.bodies:
        return doc
    # facet-mesh fallback: sew the display mesh into a shell body (marks
    # 「网格导入」through the name) — used when the SAB carries faces the
    # topology layer cannot rebuild (e.g. cylindrical faces).
    # P30: default "auto" runs this only when nothing was rebuilt at all.
    if (mesh_fallback != "never" and fac is not None
            and getattr(fac, "faces", None) and K.available()):
        shell = _mesh_shell_from_faces(fac, list(fac.faces))
        if shell is not None:
            doc.add_body(shell, name="网格导入 %s" % _model_label(model, 1),
                         color=color)
            doc.import_warnings.append("整文件网格兜底（SAB 未重建出任何实体）")
    if not doc.bodies and fac is not None and getattr(fac, "faces", None):
        xs, ys, zs = [], [], []
        for f in fac.faces:
            for c in f.corners:
                xs.append(c.position[0]); ys.append(c.position[1]); zs.append(c.position[2])
        if xs and K.available():
            dx = max(xs) - min(xs); dy = max(ys) - min(ys); dz = max(zs) - min(zs)
            if min(dx, dy, dz) > 1e-12:
                box = K.make_box(dx, dy, dz, origin=(min(xs), min(ys), min(zs)))
                doc.add_body(box, name="实体 1", color=color)
                doc.import_warnings.append("兜底：仅按包围盒生成了占位实体")
    doc.import_report = {
        "parts": len(models),
        "failed_parts": [label for (_i, label) in failed_parts],
        "unbuilt_faces": unbuilt,
        "dropped_faces": dropped,
        "mesh_bodies": [b.name for b in doc.bodies
                        if (b.name or "").startswith("网格导入")],
    }
    return doc

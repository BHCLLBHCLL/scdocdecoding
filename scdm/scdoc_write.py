"""M5-01: native .scdoc writer (OPC zip + document.xml + SAB binary).

Writes the 5-part package the project's own parser reads back:
  [Content_Types].xml, _rels/.rels, SpaceClaim/document.xml,
  SpaceClaim/_rels/document.xml.rels, SpaceClaim/Geometry/<name>.sab

Layout follows the reverse-engineered SAB grammar validated against box.scdoc:
16-byte magic, raw int32 blob-len, 3 T_STRING + 3 T_DOUBLE + flag + product-id
preamble, then 0x0D/0x0E records with little-endian scalars, 0-based pointers over
0x0D records only, each record ending in 0x11 and the file ending with the
'End-of-ACIS-data' record. Token discipline: pointer payloads and the header blob
length are raw little-endian int32; all record ints/doubles carry T_INT/T_DOUBLE
markers.

Scope: solids whose faces are planar (boxes / prisms / extruded sketches). Non-planar
faces raise ValueError with a clear message.
"""
from __future__ import annotations

import math
import os
import struct
import zipfile
from typing import List, Optional, Tuple

from scdm import kernel as K
from scdoc_parser import sab as _sab_mod

T_INT = 0x04
T_DOUBLE = 0x06
T_STRING = 0x07
T_PTR = 0x0C
T_RECORD = 0x0D
T_CHAIN = 0x0E
T_TERM = 0x11
T_VEC3 = 0x13
T_VEC3B = 0x14
T_FLAG_A = 0x0A
T_FLAG_B = 0x0B
T_INT15 = 0x15
T_ID = 0x25

MAGIC = b"ACIS BinaryFileT"
END_NAME = "End-of-ACIS-data"


def _ri(v) -> bytes:  # raw int32
    return struct.pack("<i", int(v))


def _rd(v) -> bytes:  # raw double
    return struct.pack("<d", float(v))


def _ti(v) -> bytes:  # T_INT token
    return bytes([T_INT]) + _ri(v)


def _td(v) -> bytes:  # T_DOUBLE token
    return bytes([T_DOUBLE]) + _rd(v)


def _s(v: str) -> bytes:
    b = v.encode("latin-1")
    return bytes([T_STRING, len(b)]) + b


def _p(i) -> bytes:
    return bytes([T_PTR]) + _ri(i)


def _v3(x, y, z) -> bytes:
    return bytes([T_VEC3]) + _rd(x) + _rd(y) + _rd(z)


def _v3b(x, y, z) -> bytes:
    return bytes([T_VEC3B]) + _rd(x) + _rd(y) + _rd(z)


class _Rec:
    def __init__(self, name: str, class_id: Optional[int], chain=()):
        self.name = name
        self.class_id = class_id
        self.chain = chain
        self.tokens = bytearray()

    def add(self, *tokens) -> "_Rec":
        for t in tokens:
            self.tokens += t
        return self

    def bytes(self, seen=None):
        """Serialize with class-name interning: the FIRST record of a class
        carries a name header (registering its class_id); later records of the
        same class use an id-only header (hdrlen=5). `seen` tracks registered
        class names. The class_id values are the official ACIS subtype ids
        (verified against box.scdoc)."""
        seen = seen if seen is not None else {}
        out = bytearray()
        for cname, cid in self.chain:
            if cid is not None and seen.get(cname) == cid:
                out += bytes([T_CHAIN, 5, T_ID]) + _ri(cid)
                continue
            hdrlen = len(cname) + (5 if cid is not None else 0)
            out += bytes([T_CHAIN, hdrlen]) + cname.encode("latin-1")
            if cid is not None:
                out += bytes([T_ID]) + _ri(cid)
                seen[cname] = cid
        if self.class_id is not None and seen.get(self.name) == self.class_id:
            out += bytes([T_RECORD, 5, T_ID]) + _ri(self.class_id)
            out += self.tokens
            out += bytes([T_TERM])
            return bytes(out)
        hdrlen = len(self.name) + (5 if self.class_id is not None else 0)
        out += bytes([T_RECORD, hdrlen]) + self.name.encode("latin-1")
        if self.class_id is not None:
            out += bytes([T_ID]) + _ri(self.class_id)
            seen[self.name] = self.class_id
        out += self.tokens
        out += bytes([T_TERM])
        return bytes(out)


def _round(v, nd=9):
    return round(float(v), nd)


def _cyl_info(solid):
    """Detect a plain cylinder (1 cylindrical face + 2 planar end caps).

    Returns dict(origin, axis, major_unit, R, h, bbox) or None. The layout is
    modelled on the official beam-profile Circular.scdoc (ACIS cone surface +
    ellipse curves, no seam edge, no pcuves).
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCC.Core.TopoDS import topods
    faces = K.explore(solid, "face")
    if len(faces) != 3:
        return None
    cyl = [f for f in faces if K.face_cylinder_radius(f) is not None]
    planes = [f for f in faces if K.face_cylinder_radius(f) is None]
    if len(cyl) != 1 or len(planes) != 2:
        return None
    ax = K.cyl_axis(cyl[0])
    if ax is None:
        return None
    _adir, aloc = ax
    R = K.face_cylinder_radius(cyl[0])
    centres = []
    for f in planes:
        adapt = BRepAdaptor_Surface(topods.Face(f))
        if adapt.GetType() != GeomAbs_Plane:
            return None
        _n, c = K.face_normal_center(f)
        centres.append(c)
    (c1, c2) = centres
    d = (c2[0] - c1[0], c2[1] - c1[1], c2[2] - c1[2])
    h = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
    if h < 1e-9:
        return None
    axis = (d[0] / h, d[1] / h, d[2] / h)
    # both cap centres must sit on the cylinder axis
    for c in centres:
        off = (c[0] - aloc[0], c[1] - aloc[1], c[2] - aloc[2])
        along = off[0] * axis[0] + off[1] * axis[1] + off[2] * axis[2]
        perp = (off[0] - along * axis[0], off[1] - along * axis[1],
                off[2] - along * axis[2])
        if math.sqrt(perp[0] ** 2 + perp[1] ** 2 + perp[2] ** 2) > 1e-7:
            return None
    # major direction: any unit vector perpendicular to the axis
    a = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (1.0, 0.0, 0.0)
    m = (axis[1] * a[2] - axis[2] * a[1], axis[2] * a[0] - axis[0] * a[2],
         axis[0] * a[1] - axis[1] * a[0])
    L = math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2) or 1.0
    major = (m[0] / L, m[1] / L, m[2] / L)
    import scdm.additive as _A
    lo, hi = _A.shape_bbox(solid)
    return {
        "origin": c1,            # cone base centre (cap A)
        "axis": axis,            # unit, points from cap A to cap B
        "major_unit": major,
        "R": R,
        "h": h,
        "cap_a": c1,
        "cap_b": c2,
        "bbox": (lo, hi),
    }


def _shape_bbox(solid):
    """Geometric axis-aligned bbox of a shape (works for closed surfaces like
    sphere/torus that have no boundary vertices)."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(solid, b)
    xmin, ymin, zmin, xmax, ymax, zmax = b.Get()
    return (xmin, ymin, zmin), (xmax, ymax, zmax)


def _sphere_info(solid):
    """Detect a closed sphere (single spherical face) and extract its params."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Sphere
    from OCC.Core.TopoDS import topods
    faces = K.explore(solid, "face")
    if len(faces) != 1:
        return None
    ad = BRepAdaptor_Surface(topods.Face(faces[0]))
    if ad.GetType() != GeomAbs_Sphere:
        return None
    sph = ad.Sphere()
    loc = sph.Location()
    d = (0.0, 0.0, 1.0)  # gp_Sphere has no axis; use the default Z axis
    lo, hi = _shape_bbox(solid)
    return {"origin": (loc.X(), loc.Y(), loc.Z()),
            "axis": d,
            "R": sph.Radius(),
            "bbox": (lo, hi)}


def _torus_info(solid):
    """Detect a closed torus (single torus face) and extract its params."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Torus
    from OCC.Core.TopoDS import topods
    faces = K.explore(solid, "face")
    if len(faces) != 1:
        return None
    ad = BRepAdaptor_Surface(topods.Face(faces[0]))
    if ad.GetType() != GeomAbs_Torus:
        return None
    tor = ad.Torus()
    loc = tor.Location()
    d = tor.Axis().Direction()
    lo, hi = _shape_bbox(solid)
    return {"origin": (loc.X(), loc.Y(), loc.Z()),
            "axis": (d.X(), d.Y(), d.Z()),
            "R": tor.MajorRadius(),
            "r": tor.MinorRadius(),
            "major_unit": (1.0, 0.0, 0.0),
            "bbox": (lo, hi)}


def _bsurface_data(face):
    """Extract an OCCT B-spline surface for the ACIS both record.

    Returns (u_deg, v_deg, u_knots, u_mults, v_knots, v_mults, poles)
    with poles flat (x, y, z, w) v-slowest, and knot multiplicities in
    ACIS storage form (endpoint mult = standard - 1).

    Non-B-spline surfaces (analytic cylinders/cones/spheres from fillets,
    holes, cones; periodic surfaces) are approximated with
    GeomConvert_ApproxSurface — tolerance scaled to the face bbox diagonal
    (P0-2 geometry-coverage fallback).
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface
    from OCC.Core.TopoDS import topods
    ad = BRepAdaptor_Surface(topods.Face(face))
    if ad.GetType() != GeomAbs_BSplineSurface:
        return _approx_bsurface(face)
    bs = ad.BSpline()
    u_deg, v_deg = bs.UDegree(), bs.VDegree()

    def stored(mults, deg):
        out = [mults[i] for i in range(len(mults))]
        out[0] -= 1
        out[-1] -= 1
        return out

    u_mults = stored([bs.UMultiplicity(i) for i in range(1, bs.NbUKnots() + 1)], u_deg)
    v_mults = stored([bs.VMultiplicity(i) for i in range(1, bs.NbVKnots() + 1)], v_deg)
    u_knots = [bs.UKnot(i) for i in range(1, bs.NbUKnots() + 1)]
    v_knots = [bs.VKnot(i) for i in range(1, bs.NbVKnots() + 1)]
    poles = []
    for j in range(1, bs.NbVPoles() + 1):
        for i in range(1, bs.NbUPoles() + 1):
            p = bs.Pole(i, j)
            w = bs.Weight(i, j)
            poles.append((p.X(), p.Y(), p.Z(), w))
    return (u_deg, v_deg, u_knots, u_mults, v_knots, v_mults, poles)


def _approx_bsurface(face, tol_scale: float = 1e-6):
    """Approximate an arbitrary face surface as a B-spline (P0-2 fallback).

    Tolerance = 1e-6 x the face bbox diagonal so dense fillet faces stay
    within the document's unit scale.  Returns the _bsurface_data tuple or
    raises KernelError-shaped ValueError when approximation fails.
    """
    import scdm.additive as _A
    from OCC.Core.GeomConvert import GeomConvert_ApproxSurface
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface
    from OCC.Core.TopoDS import topods
    (a0, b0, c0), (a1, b1, c1) = _A.shape_bbox(face)
    diag = ((a1 - a0) ** 2 + (b1 - b0) ** 2 + (c1 - c0) ** 2) ** 0.5
    tol = max(diag * tol_scale, 1e-9)
    from OCC.Core.BRep import BRep_Tool
    f = topods.Face(face)
    surf = BRep_Tool().Surface(f)
    if surf is None:
        return None
    # Periodic bases (full cylinders etc.) are rejected by
    # GeomConvert_ApproxSurface; clip to the face's UV window first so the
    # approximation sees a finite patch (P0-2 fillet/hole/cone coverage).
    if surf.IsUPeriodic() or surf.IsVPeriodic():
        from OCC.Core.BRepTools import breptools
        from OCC.Core.Geom import Geom_RectangularTrimmedSurface
        u1, u2, v1, v2 = breptools.UVBounds(f)
        surf = Geom_RectangularTrimmedSurface(surf, u1, u2, v1, v2)
    app = GeomConvert_ApproxSurface(surf, tol,
                                    __import__("OCC.Core.GeomAbs",
                                               fromlist=["GeomAbs"])
                                    .GeomAbs_C1, __import__("OCC.Core.GeomAbs",
                                               fromlist=["GeomAbs"])
                                    .GeomAbs_C1,
                                    8, 8, 500, 1)
    if not app.IsDone() or not app.HasResult():
        return None
    bs = app.Surface()  # GeomConvert_ApproxSurface always yields a B-spline

    def stored(mults):
        out = list(mults)
        out[0] -= 1
        out[-1] -= 1
        return out

    u_mults = stored([bs.UMultiplicity(i) for i in range(1, bs.NbUKnots() + 1)])
    v_mults = stored([bs.VMultiplicity(i) for i in range(1, bs.NbVKnots() + 1)])
    u_knots = [bs.UKnot(i) for i in range(1, bs.NbUKnots() + 1)]
    v_knots = [bs.VKnot(i) for i in range(1, bs.NbVKnots() + 1)]
    poles = []
    for j in range(1, bs.NbVPoles() + 1):
        for i in range(1, bs.NbUPoles() + 1):
            p = bs.Pole(i, j)
            w = bs.Weight(i, j)
            poles.append((p.X(), p.Y(), p.Z(), w))
    return (bs.UDegree(), bs.VDegree(), u_knots, u_mults, v_knots, v_mults,
            poles)


def _bsurface_raw(face):
    """The underlying Geom_Surface of a face, B-spline-converted for
    periodic/trimmed cases that GeomConvert_ApproxSurface rejects."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopoDS import topods
    from OCC.Core.Geom import Geom_BSplineSurface
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface
    f = topods.Face(face)
    surf = BRep_Tool().Surface_s(f) if hasattr(BRep_Tool(), "Surface_s")         else BRep_Tool().Surface(f)
    if surf is None:
        raise ValueError("面无底层曲面")
    ad = BRepAdaptor_Surface(f)
    if ad.GetType() == GeomAbs_BSplineSurface:
        return ad.BSpline()
    # analytical surfaces convert exactly through GeomConvert
    from OCC.Core.GeomConvert import geomconvert
    conv = geomconvert.SurfaceToBSplineSurface(surf)
    return conv


def _bcurve_data(edge):
    """Extract an OCCT B-spline curve for the ACIS nubs record."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_BSplineCurve
    from OCC.Core.TopoDS import topods
    ad = BRepAdaptor_Curve(topods.Edge(edge))
    if ad.GetType() != GeomAbs_BSplineCurve:
        return None
    c = ad.BSpline()
    deg = c.Degree()
    mults = [c.Multiplicity(i) for i in range(1, c.NbKnots() + 1)]
    mults[0] -= 1
    mults[-1] -= 1
    knots = [c.Knot(i) for i in range(1, c.NbKnots() + 1)]
    poles = []
    for i in range(1, c.NbPoles() + 1):
        p = c.Pole(i)
        poles.append((p.X(), p.Y(), p.Z()))
    return (deg, knots, mults, poles)


def _edge_curve_data(occe):
    """Classify an OCCT edge's 3D curve for the general write path.

    Returns ("ellipse", (center, normal, major_vec, ratio, t0, t1)) for
    exact circle/ellipse edges, ("bcur", (deg, knots, mults, poles, t0, t1))
    for B-spline edges, or None for straight lines (exact) — mirroring the
    official vocabulary (cyl.scdoc ellipse edges, splineedge.scdoc nubs).
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import (GeomAbs_BSplineCurve, GeomAbs_Circle,
                                  GeomAbs_Ellipse, GeomAbs_Line)
    ad = BRepAdaptor_Curve(occe)
    t = ad.GetType()
    if t == GeomAbs_Line:
        return None
    t0, t1 = ad.FirstParameter(), ad.LastParameter()
    if t1 < t0:
        t0, t1 = t1, t0
    if t in (GeomAbs_Circle, GeomAbs_Ellipse):
        if t == GeomAbs_Circle:
            g = ad.Circle()
            R, ratio = g.Radius(), 1.0
        else:
            g = ad.Ellipse()
            R = g.MajorRadius()
            ratio = g.MinorRadius() / R if R else 1.0
        axis = g.Axis().Direction()
        xdir = g.XAxis().Direction()
        loc = g.Location()
        return ("ellipse", ((loc.X(), loc.Y(), loc.Z()),
                            (axis.X(), axis.Y(), axis.Z()),
                            (xdir.X() * R, xdir.Y() * R, xdir.Z() * R),
                            ratio, t0, t1))
    if t == GeomAbs_BSplineCurve:
        d = _bcurve_data(occe)
        if d is not None:
            return ("bcur", d + (t0, t1))
    # general analytic curve: non-rational B-spline approximation over the
    # edge's parameter window (rational results are unsupported by nubs)
    try:
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.Geom import Geom_TrimmedCurve
        from OCC.Core.GeomAbs import GeomAbs_C2
        from OCC.Core.GeomConvert import GeomConvert_ApproxCurve
        crv, u0, u1 = BRep_Tool().Curve_s(occe)
        if crv is None:
            return None
        if u1 < u0:
            u0, u1 = u1, u0
        tc = Geom_TrimmedCurve(crv, u0, u1)
        app = GeomConvert_ApproxCurve(tc, 1e-7, GeomAbs_C2, 200, 8)
        if not app.IsDone() or not app.HasResult():
            return None
        bs = app.Curve()
        if bs.IsRational():
            return None
        deg = bs.Degree()
        mults = [bs.Multiplicity(i) for i in range(1, bs.NbKnots() + 1)]
        mults[0] -= 1
        mults[-1] -= 1
        knots = [bs.Knot(i) for i in range(1, bs.NbKnots() + 1)]
        poles = []
        for i in range(1, bs.NbPoles() + 1):
            p = bs.Pole(i)
            poles.append((p.X(), p.Y(), p.Z()))
        return ("bcur", (deg, knots, mults, poles, knots[0], knots[-1]))
    except Exception:
        return None


def _sample_edge_bbox(occe):
    """Edge bounding box from parameter sampling (64 spans)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    ad = BRepAdaptor_Curve(occe)
    t0, t1 = ad.FirstParameter(), ad.LastParameter()
    pts = []
    for i in range(65):
        p = ad.Value(t0 + (t1 - t0) * i / 64.0)
        pts.append((p.X(), p.Y(), p.Z()))
    xs, ys, zs = zip(*pts)
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _assemble_ring(occs):
    """Chain wire edge occurrences head-to-tail into a closed traversal.

    `occs` = [(eidx, v_start, v_end)] in wire order.  A periodic face's seam
    edge appears once in the wire but must be walked twice (once per side),
    so a dead-end inserts the reverse traversal of an already-used open
    edge.  Returns [(eidx, va, vb)] traversal-ordered, or None.
    """
    def same(a, b):
        return a == b

    if not occs:
        return None
    ring = [occs[0]]
    used = {0}
    cur = occs[0][2]
    start = occs[0][1]
    for _ in range(4 * len(occs) + 8):
        # a single closed edge is a valid ring (official cylinder caps)
        if len(used) == len(occs) and same(cur, start):
            return ring
        nxt = None
        for i, (eidx, a, b) in enumerate(occs):
            if i in used:
                continue
            if same(a, cur):
                nxt = (i, (eidx, a, b))
                break
            if same(b, cur):
                nxt = (i, (eidx, b, a))
                break
        if nxt is not None:
            used.add(nxt[0])
            ring.append(nxt[1])
            cur = nxt[1][2]
            continue
        # dead end: a periodic seam must be walked a second time
        progressed = False
        for eidx, a, b in ring:
            if same(a, b):
                continue
            if same(cur, b):
                ring.append((eidx, b, a))
                cur = a
                progressed = True
                break
            if same(cur, a):
                ring.append((eidx, a, b))
                cur = b
                progressed = True
                break
        if not progressed:
            return None
    return None


def _extract_solid(solid):
    """Return (verts, edges, faces, extras) for a solid.

    Pure-plane bodies take the byte-validated corner-polygon path.  Bodies
    with any analytic/spline face take the general path: per-face wire-walk
    edge-occurrence loops (closed circle edges, doubled periodic seams),
    exact ellipse records for circle/ellipse edges and intcurve clusters
    for true B-spline edges (P0-2 geometry coverage: fillets, holes,
    cones, torus patches).
    """
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepTools import BRepTools_WireExplorer
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.TopAbs import (TopAbs_EDGE, TopAbs_FACE, TopAbs_FORWARD,
                                 TopAbs_VERTEX, TopAbs_WIRE)
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods

    # P0-2 geometry-coverage fallback: convert analytic surfaces (fillet
    # cylinders, hole walls, cones, spheres beyond the dedicated writers)
    # to B-splines wholesale, so _bsurface_data sees BSpline faces.  A
    # pure-plane body is left untouched (byte-validated layout).
    try:
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface as _BAS
        from OCC.Core.GeomAbs import (GeomAbs_Plane as _Plane,
                                      GeomAbs_BSplineSurface as _BSP)
        _needs = False
        _fexp0 = TopExp_Explorer(solid, TopAbs_FACE)
        while _fexp0.More():
            _t = _BAS(topods.Face(_fexp0.Current())).GetType()
            if _t not in (_Plane, _BSP):
                _needs = True
                break
            _fexp0.Next()
        if _needs:
            import OCC.Core.ShapeCustom as _sc
            solid = _sc.ConvertToBSpline(solid, True, True, True, False)
    except Exception:
        pass  # conversion is best-effort; the per-face branch reports errors

    verts = []
    vmap = {}
    vexp = TopExp_Explorer(solid, TopAbs_VERTEX)
    while vexp.More():
        p = BRep_Tool().Pnt(topods.Vertex(vexp.Current()))
        key = (_round(p.X()), _round(p.Y()), _round(p.Z()))
        if key not in vmap:
            vmap[key] = len(verts)
            verts.append((p.X(), p.Y(), p.Z()))
        vexp.Next()

    def vid(shape_v):
        p = BRep_Tool().Pnt(topods.Vertex(shape_v))
        return vmap[(_round(p.X()), _round(p.Y()), _round(p.Z()))]

    def edge_vids_occ(e):
        """(v_start, v_end) following the edge's own parametric direction."""
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        ad = BRepAdaptor_Curve(e)
        pa = ad.Value(ad.FirstParameter())
        pb = ad.Value(ad.LastParameter())
        ka = (_round(pa.X()), _round(pa.Y()), _round(pa.Z()))
        kb = (_round(pb.X()), _round(pb.Y()), _round(pb.Z()))
        return vmap[ka], vmap[kb]

    # any non-plane face routes the whole body through the general path
    general = False
    _fexp0 = TopExp_Explorer(solid, TopAbs_FACE)
    while _fexp0.More():
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        if (BRepAdaptor_Surface(topods.Face(_fexp0.Current())).GetType()
                != GeomAbs_Plane):
            general = True
            break
        _fexp0.Next()

    faces = []
    edges = []
    emap = {}
    face_surf = {}   # face index -> ("bsurf", data)
    edge_curve = {}  # edge index -> ("ellipse"|"bcur", data)
    edge_bboxes = {}  # edge index -> (min, max)
    occ_edge = {}    # edge index -> representative OCCT edge

    def edge_index(a, b):
        key = (min(a, b), max(a, b))
        if key not in emap:
            emap[key] = len(edges)
            edges.append((key[0], key[1]))
        return emap[key]

    if not general:
        # ---- planar fast path (byte-validated layout) ----
        fexp = TopExp_Explorer(solid, TopAbs_FACE)
        while fexp.More():
            face = topods.Face(fexp.Current())
            nrm, ctr = K.face_normal_center(face)
            outer = None
            wexp = TopExp_Explorer(face, TopAbs_WIRE)
            while wexp.More():
                we = BRepTools_WireExplorer(topods.Wire(wexp.Current()))
                corners = []
                while we.More():
                    e = topods.Edge(we.Current())
                    ev = TopExp_Explorer(e, TopAbs_VERTEX)
                    vs = []
                    while ev.More():
                        vs.append(vid(ev.Current()))
                        ev.Next()
                    corners.append(vs[0] if we.Orientation() == TopAbs_FORWARD
                                   else vs[1])
                    we.Next()
                if outer is None:
                    outer = corners
                else:
                    for k in range(len(corners)):
                        edge_index(corners[k], corners[(k + 1) % len(corners)])
                wexp.Next()
            if outer is None:
                fexp.Next()
                continue
            poly_n = _polygon_normal(outer, verts)
            if _dot(poly_n, nrm) < 0:
                outer = list(reversed(outer))
            for k in range(len(outer)):
                edge_index(outer[k], outer[(k + 1) % len(outer)])
            faces.append({"loop": outer, "normal": nrm, "center": ctr})
            fexp.Next()
        return verts, edges, faces, {"face_surf": face_surf,
                                     "edge_curve": edge_curve,
                                     "edge_bboxes": edge_bboxes}

    # ---- general path (curved faces present) ----
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    fexp = TopExp_Explorer(solid, TopAbs_FACE)
    while fexp.More():
        face = topods.Face(fexp.Current())
        adapt = BRepAdaptor_Surface(face)
        if adapt.GetType() != GeomAbs_Plane:
            data = _bsurface_data(face)
            if data is None:
                raise ValueError("仅支持平面/双样条面的实体写出")
        else:
            data = None
        nrm, ctr = K.face_normal_center(face)
        # all wires -> edge-occurrence rings; outer wire = largest bbox area,
        # remaining wires are inner hole loops
        wire_rings = []
        wexp = TopExp_Explorer(face, TopAbs_WIRE)
        while wexp.More():
            occs = []
            we = BRepTools_WireExplorer(topods.Wire(wexp.Current()))
            while we.More():
                e = topods.Edge(we.Current())
                va, vb = edge_vids_occ(e)
                if we.Orientation() != TopAbs_FORWARD:
                    va, vb = vb, va
                eidx = edge_index(va, vb)
                occs.append((eidx, va, vb))
                occ_edge.setdefault(eidx, e)
                we.Next()
            ring = _assemble_ring(occs)
            if ring is not None:
                wmin = [min(verts[v][k] for _occ in ring for v in _occ[1:])
                        for k in range(3)]
                wmax = [max(verts[v][k] for _occ in ring for v in _occ[1:])
                        for k in range(3)]
                area = ((wmax[0] - wmin[0]) * (wmax[1] - wmin[1]) *
                        (wmax[2] - wmin[2]))
                wire_rings.append((area, ring))
            wexp.Next()
        if not wire_rings:
            fexp.Next()
            continue
        wire_rings.sort(key=lambda t: -t[0])   # outer first
        loops = []
        loop0 = []
        fbb_min = [None, None, None]
        fbb_max = [None, None, None]

        def _fb(p):
            for k in range(3):
                fbb_min[k] = p[k] if fbb_min[k] is None else min(fbb_min[k], p[k])
                fbb_max[k] = p[k] if fbb_max[k] is None else max(fbb_max[k], p[k])

        for _area, ring in wire_rings:
            loop_edges = []
            loop = []
            for eidx, va, vb in ring:
                sense = (T_FLAG_B if edges[eidx] == (va, vb) else T_FLAG_A)
                loop_edges.append((eidx, sense))
                loop.append(va)
                _fb(verts[va])
                if va != vb:
                    _fb(verts[vb])
                if eidx in edge_bboxes:
                    emin, emax = edge_bboxes[eidx]
                    _fb(emin)
                    _fb(emax)
            loops.append(loop_edges)
            if not loop0:
                loop0 = loop
        faces.append({"loop": loop0, "normal": nrm, "center": ctr,
                      "loops": loops,
                      "bbox": (tuple(fbb_min), tuple(fbb_max))})
        if data is not None:
            face_surf[len(faces) - 1] = ("bsurf", data)
        fexp.Next()
    # curve records for every non-line edge (exact ellipse / intcurve)
    for eidx, occe in occ_edge.items():
        d = _edge_curve_data(occe)
        if d is not None:
            edge_curve[eidx] = d
            edge_bboxes[eidx] = _sample_edge_bbox(occe)
    return verts, edges, faces, {"face_surf": face_surf,
                                 "edge_curve": edge_curve,
                                 "edge_bboxes": edge_bboxes}


def _polygon_normal(loop, verts):
    nx = ny = nz = 0.0
    n = len(loop)
    for k in range(n):
        a = verts[loop[k]]
        b = verts[loop[(k + 1) % n]]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    norm = (nx * nx + ny * ny + nz * nz) ** 0.5
    if norm < 1e-18:
        return (0.0, 0.0, 1.0)
    return (nx / norm, ny / norm, nz / norm)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _bbox(verts, idxs=None):
    use = [verts[i] for i in idxs] if idxs is not None else verts
    xs = [p[0] for p in use]
    ys = [p[1] for p in use]
    zs = [p[2] for p in use]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _ortho(n):
    a = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    x = (n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2], n[0] * a[1] - n[1] * a[0])
    m = (x[0] ** 2 + x[1] ** 2 + x[2] ** 2) ** 0.5 or 1.0
    return (x[0] / m, x[1] / m, x[2] / m)


def _edge_of(edges, a, b):
    for i, (u, v) in enumerate(edges):
        if {u, v} == {a, b}:
            return i
    raise ValueError("edge not found")


def _fix_partner(tokens: bytearray, partner: int) -> bytearray:
    """Replace the 7th token (coedge partner pointer) in a coedge token stream."""
    out = bytearray()
    idx = 0
    count = 0
    while idx < len(tokens):
        t = tokens[idx]
        if t in (T_PTR, T_INT):
            if t == T_PTR and count == 6:
                out += _p(partner)
                idx += 5
                count += 1
                continue
            out += tokens[idx:idx + 5]
            idx += 5
            count += 1
        else:
            out += tokens[idx:idx + 1]
            idx += 1
            count += 1
    return out


def _attrib(owner, value, nxt=None, prv=None, type_id=14675622,
            name_tag="ATTRIB_XACIS_NAME%6"):
    """Official attrib token layout (from box.scdoc):
    [t0 ptr(-1), t1 int(-1), t2 ptr NEXT, t3 ptr PREV, t4 ptr OWNER,
     t5 int type_id, t6 string name_tag, t7 string value]"""
    return (_Rec("attrib", 5, chain=[("string_attrib", 2), ("name_attrib", 3), ("gen", 4)])
            .add(_p(-1), _ti(-1), _p(-1 if nxt is None else nxt),
                 _p(-1 if prv is None else prv), _p(owner),
                 _ti(type_id), _s(name_tag), _s(value)))


def _rgb_attrib(owner, prev, rgb):
    """Per-face rgb_color appearance attrib (record layout from official box.scdoc)."""
    return (_Rec("attrib", 5, chain=[("rgb_color", 14), ("st", 15)])
            .add(_p(-1), _ti(-1), _p(-1), _p(prev), _p(owner),
                 _ti(14675654), _td(rgb[0]), _td(rgb[1]), _td(rgb[2])))


def _build_sab(items, colors=None):
    """Assemble the SAB stream via the reverse-engineered ACIS save algorithm.

    The official writer (SpaACIS.dll) keeps a FIFO worklist of entities; each
    entity's save_data writes its record and appends referenced entities that
    are not yet in the list.  A FIFO simulation seeded at the body reproduces
    the official box.scdoc record order 0..140 exactly (see
    references/disasm/verify_sab_order.py), so no interleaving template is
    needed.  See scdm/sab_emit.py for the worklist and record builders.

    items = [('planar', verts, edges, faces) | ('cyl', info)] per body;
    colors = parallel list of per-body (r, g, b) in 0..1.

    Returns (bytes, face_counts, edge_counts).
    """
    from scdm.sab_emit import (Worklist, Makers, MAGIC, END_NAME, _s, _ri,
                               _td, T_FLAG_A, T_RECORD)
    wl = Worklist()
    makers = Makers(items, colors)
    body = wl.run([("body", bi) for bi in range(len(items))], makers)
    out = bytearray()
    out += MAGIC
    blob = b"\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
    out += _ri(len(blob)) + blob
    out += _s("SpaceClaim")
    out += _s("ACIS 29.0 NT")
    out += _s("Mon Aug 24 00:13:12 2026")
    out += _td(1000.0) + _td(1e-8) + _td(1e-10)
    out += bytes([T_FLAG_A])
    out += _s("FQ8FFTTT5P7PJFMUMMYS2_J8B48CXKNEWAP4QAQV2CS3PP65QBQCNVPEFCMUSP6XAAPKK47XTA84Q")
    out += body
    out += bytes([T_RECORD, len(END_NAME)]) + END_NAME.encode("latin-1")
    # per-body face/edge counts: planar from geometry, cyl=3, sphere/torus=1
    def _fc(it):
        if it[0] == "planar":
            return len(it[3])
        return 1 if it[0] in ("sphere", "torus") else 3

    def _ec(it):
        if it[0] == "planar":
            return len(it[2])
        return 1 if it[0] in ("sphere", "torus") else 2
    face_counts = [_fc(it) for it in items]
    edge_counts = [_ec(it) for it in items]
    return bytes(out), face_counts, edge_counts


def _has_part(path, name):
    import zipfile as _z
    with _z.ZipFile(path) as z:
        return name in z.namelist()


def _strip_facets_rels(path):
    """Remove the bodyFacets relationship (facets part was dropped)."""
    import zipfile as _z
    rels_name = "SpaceClaim/_rels/document.xml.rels"
    with _z.ZipFile(path) as z:
        rels = z.read(rels_name).decode("utf-8")
    if "bodyFacets" not in rels:
        return
    import re as _re
    rels = _re.sub(r'\s*<Relationship[^>]*bodyFacets[^>]*/>', '', rels)
    with _z.ZipFile(path, "a", _z.ZIP_DEFLATED) as z:
        z.writestr(rels_name, rels.encode("utf-8"))


def _patch_rels(path):
    """Add the bodyFacets relationship to a template-derived package."""
    import zipfile as _z
    rels_name = "SpaceClaim/_rels/document.xml.rels"
    with _z.ZipFile(path) as z:
        names = z.namelist()
        if "SpaceClaim/Graphics/facets.bin" not in names:
            return
        rels = z.read(rels_name).decode("utf-8")
    if "bodyFacets" in rels:
        return
    extra = ('  <Relationship Type="http://www.spaceclaim.com/relationships/'
             'internal/bodyFacets" Target="/SpaceClaim/Graphics/facets.bin" '
             'Id="Rf1"/>\n')
    rels = rels.replace("</Relationships>", extra + "</Relationships>")
    with _z.ZipFile(path, "a", _z.ZIP_DEFLATED) as z:
        z.writestr(rels_name, rels.encode("utf-8"))


def _document_xml(name: str, face_counts: List[int], edge_counts: List[int],
                  colors=None) -> bytes:
    parts = []
    captions = []
    for i in range(len(face_counts)):
        bid = 23 + 60 * i
        c = colors[i] if colors and i < len(colors) else (0.745, 0.902, 0.961)
        rgb = f"{int(c[0] * 255)}, {int(c[1] * 255)}, {int(c[2] * 255)}"
        faces = "\n".join(
            f'        <NominalFaceDef Id="0:{27 + 3 * k + 60 * i}"/>'
            for k in range(face_counts[i]))
        edges = "\n".join(
            f'        <NominalEdgeDef Id="0:{45 + 3 * k + 60 * i}"><isReversed>False</isReversed></NominalEdgeDef>'
            for k in range(edge_counts[i]))
        parts.append(f'    <PartDef Id="0:2">\n'
                     f'      <DefaultEdgeTreatmentDef Id="0:13"><blendRadius>0</blendRadius></DefaultEdgeTreatmentDef>\n'
                     f'      <NominalBodyDef Id="0:{bid}">\n'
                     f'        <layerId>0:9</layerId>\n'
                     f'        <type>Solid</type>\n'
                     f'        <color>{rgb}</color>\n'
                     f'        <renderingStyle>Plastic</renderingStyle>\n'
                     f'        <fillStyle>Opaque</fillStyle>\n'
                     f'        <finishStyle>MediumGloss</finishStyle>\n'
                     f'{faces}\n{edges}\n'
                     f'      </NominalBodyDef>\n'
                     f'    </PartDef>')
        captions.append(
            f'    <CaptionDef Id="0:{85 + 60 * i}"><subjectId>0:{23 + 60 * i}</subjectId>'
            f'<name>Solid{i + 1}</name><type>Mutable</type></CaptionDef>')
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Document version="1.520" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:core">\n'
            f'  <nextId>109</nextId>\n'
            f'  <importPath>D:/minimal/{name}.scdoc</importPath>\n'
            f'  <importTimestamp>01/01/2026 00:00:00</importTimestamp>\n'
            f'  <Design sectionId="11111111-1111-1111-1111-111111111111" Id="0:1" xmlns="urn:nom">\n'
            + "\n".join(parts) +
            f'\n  </Design>\n'
            f'  <PresentationDef sectionId="22222222-2222-2222-2222-222222222222" Id="0:5" xmlns="urn:presentation">\n'
            f'    <LayerDef Id="0:9"><name>Layer 1</name><visible>True</visible><locked>False</locked><color>143, 175, 143</color></LayerDef>\n'
            f'    <RootCaptionDef Id="0:11" xmlns="urn:nom"><subjectId>0:2</subjectId><name>{name}</name><type>Normal</type></RootCaptionDef>\n'
            + "\n".join(captions) +
            f'\n  </PresentationDef>\n'
            f'  <DocumentSettingsDef sectionId="33333333-3333-3333-3333-333333333333" Id="0:16" xmlns="urn:presentation">\n'
            f'    <DocumentUnitsDef Id="0:17">\n'
            f'      <units><lengthProperties><type>MM</type><factor>1000</factor><symbol>mm</symbol><decimalPlaces>2</decimalPlaces></lengthProperties></units>\n'
            f'    </DocumentUnitsDef>\n'
            f'  </DocumentSettingsDef>\n'
            f'</Document>\n').encode("utf-8")


def _content_types() -> bytes:
    return (b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            b'  <Default Extension="xml" ContentType="application/xml"/>\n'
            b'  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            b'  <Default Extension="sab" ContentType="application/binary ; modeler=Acis ; version=29.0.0"/>\n'
            b'  <Default Extension="bin" ContentType="application/binary"/>\n'
            b'</Types>')


def _root_rels() -> bytes:
    return (b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            b'  <Relationship Type="http://www.spaceclaim.com/relationships/internal/mainDocument"\n'
            b'                Target="/SpaceClaim/document.xml" Id="Rm1"/>\n'
            b'</Relationships>')


def _doc_rels(sab_name: str, facets: bool = False) -> bytes:
    extra = ''
    if facets:
        extra = ('  <Relationship Type="http://www.spaceclaim.com/relationships/'
                 'internal/bodyFacets" Target="/SpaceClaim/Graphics/facets.bin" '
                 'Id="Rf1"/>\n')
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Type="http://www.spaceclaim.com/relationships/internal/partBodyGeometry#fc598e53-8ab6-41b2-b8ea-b7917346ae70:2"\n'
            f'                Target="/SpaceClaim/Geometry/{sab_name}" Id="Rg1"/>\n'
            f'{extra}'
            f'</Relationships>').encode("utf-8")


def _facets_bytes(items, tessellations, ids=None) -> bytes:
    """Graphics facets stream (bodyFacets part), OFFICIAL multi-body layout
    decoded from references/golden/assembly_sample.scdoc:

      magic 'facets  ' + version 14 + n_bodies + 1 + 0
      per body:  [body_doc_id, 0, body_update_state, 5, n_faces, 0]
                 per face: [face_doc_id, 0, node_id, corner_count]
                           + corner_count x 8 floats (pos, normal, 0, 0)
                           + [tri_index_count][packed (hi<<16|lo) pairs]
                           + [bnd_index_count][packed pairs]
                           + [edge_ref_count][(mesh_id, 2k, 1) rows]
                           + trailing 0 after every face but the body's last
                 [edge_map_count][(mesh_id, 0, doc_edge_id) rows by mid]
                 [1, 0] after every body but the last

    Planar faces carry the full official node (corner polygon + fan + closed
    boundary loop + per-edge refs with globally-unique mesh ids from 8).
    Curved faces carry ONE node per face with the whole tessellation
    (official side-face node holds 84 corners in one node; per-face edge
    refs omitted -- the reader tolerates it, proven by open sentinel).
    ids: per-body dict {"body", "update", "faces": [...], "edges": [...]}.
    """
    import struct as _s
    n_bodies = len(items)
    out = bytearray()
    out += b'facets  '
    out += _s.pack('<I', 14)
    out += _s.pack('<I', n_bodies)
    out += _s.pack('<I', 1)
    out += _s.pack('<I', 0)

    mesh_mid = 8
    for bi, it in enumerate(items):
        idb = ids[bi] if ids and bi < len(ids) else {}
        bid = idb.get("body", 23 + 60 * bi)
        upd = idb.get("update", bid)
        face_ids = idb.get("faces", [])
        edge_ids = idb.get("edges", [])
        nodes = []
        edge_map = []
        edge_mid = {}
        if (it[0] == "planar" and not (it[4].get("face_surf") or
                                       it[4].get("edge_curve")) and
                all(len(f["loop"]) >= 3 for f in it[3])):
            verts, edges, faces = it[1], it[2], it[3]
            for fi, f in enumerate(faces):
                loop = f["loop"]
                corners = [verts[vi] for vi in loop]
                nrm = f["normal"]
                n = len(corners)
                fid = (face_ids[fi] if fi < len(face_ids)
                       else 27 + 3 * fi + 60 * bi)
                node = bytearray()
                node += _s.pack('<4I', fid, 0, fid, n)
                for p in corners:
                    node += _s.pack('<8f', p[0], p[1], p[2], nrm[0], nrm[1],
                                    nrm[2], 0.0, 0.0)
                tris = []
                for k in range(1, n - 1):
                    tris += [0, k, k + 1]
                node += _s.pack('<I', len(tris))
                for k in range(0, len(tris), 2):
                    lo = tris[k]
                    hi = tris[k + 1] if k + 1 < len(tris) else tris[k]
                    node += _s.pack('<I', (hi << 16) | lo)
                bnd = []
                for k in range(n):
                    bnd += [k, (k + 1) % n]
                node += _s.pack('<I', len(bnd))
                for k in range(0, len(bnd), 2):
                    lo = bnd[k]
                    hi = bnd[k + 1] if k + 1 < len(bnd) else bnd[k]
                    node += _s.pack('<I', (hi << 16) | lo)
                rows = []
                for k in range(n):
                    a, b = loop[k], loop[(k + 1) % n]
                    eidx = _edge_of(edges, a, b)
                    if eidx not in edge_mid:
                        edge_mid[eidx] = mesh_mid
                        mesh_mid += 1
                    mid = edge_mid[eidx]
                    doc_eid = (edge_ids[eidx] if eidx < len(edge_ids)
                               else 45 + 3 * eidx + 60 * bi)
                    rows.append((mid, 2 * k, 1))
                    edge_map.append((mid, doc_eid))
                node += _s.pack('<I', len(rows))
                for mid, kk, one in rows:
                    node += _s.pack('<3I', mid, kk, one)
                nodes.append(bytes(node))
        else:
            faces = tessellations[bi] if bi < len(tessellations) else []
            for fi, fd in enumerate(faces):
                pts = fd["vertices"]
                tris = fd["triangles"]
                fn = fd.get("normal") or (0.0, 0.0, 1.0)
                n = len(pts)
                fid = (face_ids[fi] if fi < len(face_ids)
                       else 27 + 3 * fi + 60 * bi)
                node = bytearray()
                node += _s.pack('<4I', fid, 0, fid, n)
                for p in pts:
                    node += _s.pack('<8f', p[0], p[1], p[2], fn[0], fn[1],
                                    fn[2], 0.0, 0.0)
                flat = [i for t in tris for i in t]
                node += _s.pack('<I', len(flat))
                for k in range(0, len(flat), 2):
                    lo = flat[k]
                    hi = flat[k + 1] if k + 1 < len(flat) else flat[k]
                    node += _s.pack('<I', (hi << 16) | lo)
                node += _s.pack('<I', 0)   # bnd count (reader-tolerant)
                node += _s.pack('<I', 0)   # edge ref count
                nodes.append(bytes(node))
            for ei in range(len(edge_ids)):
                edge_map.append((mesh_mid, edge_ids[ei]))
                mesh_mid += 1
        out += _s.pack('<6I', bid, 0, upd, 5, len(nodes), 0)
        for i, node in enumerate(nodes):
            out += node
            if i < len(nodes) - 1:
                out += _s.pack('<I', 0)
        seen = {}
        for mid, doc in edge_map:
            seen[mid] = doc
        out += _s.pack('<I', len(seen))
        for mid, doc in sorted(seen.items()):
            out += _s.pack('<3I', mid, 0, doc)
        if bi < n_bodies - 1:
            out += _s.pack('<2I', 1, 0)
    return bytes(out)


def _facet_ids(it, gi: int) -> dict:
    """Document ids for one body's facets section (matches the assembly
    document.xml numbering: body 0:{23+60gi}, faces 0:{27+3k+60gi},
    edges 0:{45+3k+60gi}; the cylinder carries 3 edges, sphere 1,
    torus 2 -- same counts as the SAB emitter)."""
    if it[0] == "planar":
        nf, ne = len(it[3]), len(it[2])
    elif it[0] == "cyl":
        nf, ne = 3, 3
    elif it[0] == "sphere":
        nf, ne = 1, 1
    else:  # torus
        nf, ne = 1, 2
    return {"body": 23 + 60 * gi, "update": 23 + 60 * gi,
            "faces": [27 + 3 * k + 60 * gi for k in range(nf)],
            "edges": [45 + 3 * k + 60 * gi for k in range(ne)]}




def _reserialize_reorder(sab_bytes, ref_sab_bytes=None):
    """Reorder SAB records to match the official interleaved emission order.

    Uses the golden reference's kind sequence as a template when available.
    """
    import struct as _s

    T_REC, T_CHAIN, T_TERM, T_ID = 0x0D, 0x0E, 0x11, 0x25
    T_PTR, T_INT, T_DBL, T_STR = 0x0C, 0x04, 0x06, 0x07
    T_V3, T_V3B, TA, TB, T15 = 0x13, 0x14, 0x0A, 0x0B, 0x15
    KB = {'ptr': T_PTR, 'int': T_INT, 'double': T_DBL, 'string': T_STR,
          'vec3': T_V3, 'vec3b': T_V3B, 'flag_a': TA, 'flag_b': TB,
          'int15': T15, 'mark0f': 0x0F, 'mark10': 0x10}

    sf = _sab_mod.tokenize(sab_bytes)
    recs = list(sf.records)
    n = len(recs)

    def kind_of(r):
        return r.chain[0][0] if r.chain else r.name

    kinds = [kind_of(r) for r in recs]

    # group by kind (preserving stream order)
    by_kind = {}
    for i, k in enumerate(kinds):
        by_kind.setdefault(k, []).append(i)

    # determine target order
    if ref_sab_bytes:
        ref_sf = _sab_mod.tokenize(ref_sab_bytes)
        ref_seq = [kind_of(r) for r in ref_sf.records]
        # check if kind multisets match
        our_c = {}
        for k in kinds:
            our_c[k] = our_c.get(k, 0) + 1
        ref_c = {}
        for k in ref_seq:
            ref_c[k] = ref_c.get(k, 0) + 1
        if our_c == ref_c:
            # perfect kind multiset match: use reference sequence
            new_order = []
            kind_pos = {k: 0 for k in our_c}
            for k in ref_seq:
                lst = by_kind.get(k, [])
                pos = kind_pos.get(k, 0)
                if pos < len(lst):
                    new_order.append(lst[pos])
                    kind_pos[k] = pos + 1
            if len(new_order) == n:
                return _emit_bytes(new_order, recs, KB, T_REC, T_CHAIN, T_TERM,
                                   T_ID, T_PTR, T_INT, T_DBL, T_STR, T_V3, T_V3B,
                                   TA, TB, T15, _s)

    # fallback: per-face interleaved order
    new_order = []
    emitted = set()

    def emit(i):
        if i not in emitted:
            new_order.append(i)
            emitted.add(i)

    # body block
    for i in range(n):
        if kinds[i] == 'body':
            emit(i)
            # attribs owned by body
            for j in range(n):
                if kinds[j] in ('string_attrib', 'rgb_color', 'wstring_attrib') and j not in emitted:
                    r = recs[j]
                    tk = r.tokens
                    pos = 0
                    while pos < len(tk):
                        b = tk[pos]
                        if b == 0x0C:
                            v = int.from_bytes(tk[pos+1:pos+5], 'little')
                            if v == i:
                                emit(j)
                                break
                            pos += 5
                        elif b in (0x04, 0x15):
                            pos += 5
                        elif b == 0x06:
                            pos += 9
                        elif b == 0x07:
                            pos += 2 + tk[pos+1]
                        elif b in (0x13, 0x14):
                            pos += 25
                        elif b in (0x0A, 0x0B):
                            pos += 1
                        elif b == 0x25:
                            pos += 5
                        else:
                            pos += 1
    for i in range(n):
        if kinds[i] == 'lump':
            emit(i)
    for i in range(n):
        if kinds[i] == 'shell':
            emit(i)

    # per-face interleave
    face_indices = [i for i in range(n) if kinds[i] == 'face']
    # face -> loop/surface mapping via ptr scanning
    face_loop = {}
    face_surf = {}
    for fi in face_indices:
        tk = recs[fi].tokens
        pos = 0
        pc = 0
        while pos < len(tk):
            b = tk[pos]
            if b == 0x0C:
                v = int.from_bytes(tk[pos+1:pos+5], 'little')
                pc += 1
                if pc == 4 and 0 <= v < n and kinds[v] == 'loop':
                    face_loop[fi] = v
                if pc == 7 and 0 <= v < n and kinds[v] in ('plane', 'cone'):
                    face_surf[fi] = v
                pos += 5
            elif b in (0x04, 0x15):
                pos += 5
            elif b == 0x06:
                pos += 9
            elif b == 0x07:
                pos += 2 + tk[pos+1]
            elif b in (0x13, 0x14):
                pos += 25
            elif b in (0x0A, 0x0B):
                pos += 1
            elif b == 0x25:
                pos += 5
            else:
                pos += 1

    prev_loop = None
    prev_surf = None
    for fi_pos, fi in enumerate(face_indices):
        emit(fi)
        # attribs owned by this face
        for j in range(n):
            if j in emitted or kinds[j] not in ('string_attrib', 'rgb_color', 'wstring_attrib'):
                continue
            r = recs[j]
            tk = r.tokens
            pos = 0
            while pos < len(tk):
                b = tk[pos]
                if b == 0x0C:
                    v = int.from_bytes(tk[pos+1:pos+5], 'little')
                    if v == fi:
                        emit(j)
                        break
                    pos += 5
                elif b in (0x04, 0x15):
                    pos += 5
                elif b == 0x06:
                    pos += 9
                elif b == 0x07:
                    pos += 2 + tk[pos+1]
                elif b in (0x13, 0x14):
                    pos += 25
                elif b in (0x0A, 0x0B):
                    pos += 1
                elif b == 0x25:
                    pos += 5
                else:
                    pos += 1
        if fi_pos >= 1 and prev_loop is not None:
            emit(prev_loop)
        if fi_pos >= 1 and prev_surf is not None:
            emit(prev_surf)
        prev_loop = face_loop.get(fi)
        prev_surf = face_surf.get(fi)

    # deferred loop/surface from last face
    if prev_loop is not None:
        emit(prev_loop)
    if prev_surf is not None:
        emit(prev_surf)

    # remaining records
    for i in range(n):
        emit(i)

    # preserve header and tail from the original SAB
    first_rec_start = recs[0].offset
    end_marker_hdr = sab_bytes.rfind(bytes([T_REC, 16]))
    head = sab_bytes[:first_rec_start]
    tail = sab_bytes[end_marker_hdr:]
    return head + _emit_bytes(new_order, recs, KB, T_REC, T_CHAIN, T_TERM,
                              T_ID, T_PTR, T_INT, T_DBL, T_STR, T_V3, T_V3B,
                              TA, TB, T15, _s) + tail


def _emit_bytes(new_order, recs, KB, T_REC, T_CHAIN, T_TERM, T_ID,
                T_PTR, T_INT, T_DBL, T_STR, T_V3, T_V3B, TA, TB, T15, _s):
    """Re-serialize records in the given order with remapped pointers."""
    old_to_new = {}
    for new_idx, old_idx in enumerate(new_order):
        old_to_new[old_idx] = new_idx

    def tok_bytes(t, rmp):
        b = KB.get(t.kind)
        if b is None:
            return b''
        if t.kind in ('ptr', 'int', 'int15'):
            v = t.value
            if t.kind == 'ptr' and v >= 0 and rmp:
                v = rmp.get(v, v)
            return bytes([b]) + _s.pack('<i', int(v))
        if t.kind == 'double':
            return bytes([b]) + _s.pack('<d', float(t.value))
        if t.kind == 'string':
            raw = str(t.value).encode('latin-1')
            return bytes([b, len(raw)]) + raw
        if t.kind in ('vec3', 'vec3b'):
            return bytes([b]) + _s.pack('<3d', *t.value)
        if t.kind in ('flag_a', 'flag_b'):
            return bytes([b])
        return b''

    def rec_bytes(r, rmp):
        out = bytearray()
        for cname, cid in r.chain:
            hdr = len(cname) + (5 if cid is not None else 0)
            out += bytes([T_CHAIN, hdr]) + cname.encode('latin-1')
            if cid is not None:
                out += bytes([T_ID]) + _s.pack('<i', cid)
        hdr = len(r.name) + (5 if r.rec_id is not None else 0)
        out += bytes([T_REC, hdr]) + r.name.encode('latin-1')
        if r.rec_id is not None:
            out += bytes([T_ID]) + _s.pack('<i', r.rec_id)
        for t in r.tokens:
            out += tok_bytes(t, rmp)
        out += bytes([T_TERM])
        return bytes(out)

    return b''.join(rec_bytes(recs[i], old_to_new) for i in new_order)



# Official interleaved kind sequence for a 6-face planar body (from box.scdoc).
# For other face counts, the pattern generalizes: faces are emitted one per
# "batch", each batch also containing the PREVIOUS face's loop and surface.
_BOX_KIND_SEQ = [
    'body', 'string_attrib', 'lump', 'string_attrib', 'shell',
    'face', 'string_attrib',
    'face', 'loop', 'plane', 'rgb_color', 'string_attrib',
    'face', 'loop', 'plane', 'coedge', 'rgb_color', 'string_attrib',
    'face', 'loop', 'plane', 'coedge', 'coedge', 'coedge', 'coedge', 'edge',
    'rgb_color', 'string_attrib',
    'face', 'loop', 'plane', 'coedge', 'coedge', 'coedge', 'coedge', 'edge',
    'coedge', 'coedge', 'edge', 'edge', 'coedge', 'loop', 'string_attrib',
    'vertex', 'vertex', 'straight', 'rgb_color', 'string_attrib',
    'face', 'loop', 'plane', 'coedge', 'coedge', 'edge', 'coedge', 'coedge',
    'edge', 'coedge', 'string_attrib', 'vertex', 'straight',
    'coedge', 'edge', 'coedge', 'string_attrib', 'vertex', 'straight',
    'string_attrib', 'vertex', 'straight', 'plane', 'point', 'point',
    'rgb_color', 'string_attrib',
    'coedge', 'coedge', 'edge', 'edge', 'string_attrib', 'vertex', 'straight',
    'coedge', 'edge', 'coedge', 'string_attrib', 'vertex', 'straight',
    'point', 'coedge', 'string_attrib', 'straight', 'edge', 'point', 'point',
    'rgb_color', 'edge', 'string_attrib', 'straight', 'string_attrib',
    'vertex', 'straight', 'point', 'string_attrib', 'straight', 'point',
    'string_attrib', 'straight', 'string_attrib', 'straight', 'point',
]


def _reorder_to_template(sab_bytes, kind_template):
    """Reorder SAB records to match the given kind sequence template.

    Maps our records (by kind, in our emission order) to the template positions.
    Returns the reordered SAB bytes.
    """
    import struct as _s

    T_REC, T_CHAIN, T_TERM, T_ID = 0x0D, 0x0E, 0x11, 0x25
    T_PTR, T_INT, T_DBL, T_STR = 0x0C, 0x04, 0x06, 0x07
    T_V3, T_V3B, TA, TB, T15 = 0x13, 0x14, 0x0A, 0x0B, 0x15
    KB = {'ptr': T_PTR, 'int': T_INT, 'double': T_DBL, 'string': T_STR,
          'vec3': T_V3, 'vec3b': T_V3B, 'flag_a': TA, 'flag_b': TB,
          'int15': T15}

    sf = _sab_mod.tokenize(sab_bytes)
    recs = list(sf.records)
    n = len(recs)
    if n != len(kind_template):
        return sab_bytes  # can't fit

    # our records by kind (in our current order within each kind)
    by_kind = {}
    for i, r in enumerate(recs):
        k = r.chain[0][0] if r.chain else r.name
        by_kind.setdefault(k, []).append(i)

    # check if kind multiset matches
    tpl_counts = {}
    for k in kind_template:
        tpl_counts[k] = tpl_counts.get(k, 0) + 1
    our_counts = {}
    for k in kinds:
        our_counts[k] = our_counts.get(k, 0) + 1
    if our_counts != tpl_counts:
        return sab_bytes

    # map: template position -> our record index
    kind_pos = {k: 0 for k in our_counts}
    new_order = []
    for k in kind_template:
        lst = by_kind.get(k, [])
        pos = kind_pos.get(k, 0)
        if pos < len(lst):
            new_order.append(lst[pos])
            kind_pos[k] = pos + 1

    # build old->new mapping for ptr remapping
    old_to_new = {}
    for new_idx, old_idx in enumerate(new_order):
        old_to_new[old_idx] = new_idx

    # serialize
    def tok_bytes(t, rmp):
        b = KB.get(t.kind)
        if b is None:
            return b''
        if t.kind in ('ptr', 'int', 'int15'):
            v = t.value
            if t.kind == 'ptr' and v >= 0 and rmp:
                v = rmp.get(v, v)
            return bytes([b]) + _s.pack('<i', int(v))
        if t.kind == 'double':
            return bytes([b]) + _s.pack('<d', float(t.value))
        if t.kind == 'string':
            raw = str(t.value).encode('latin-1')
            return bytes([b, len(raw)]) + raw
        if t.kind in ('vec3', 'vec3b'):
            return bytes([b]) + _s.pack('<3d', *t.value)
        if t.kind in ('flag_a', 'flag_b'):
            return bytes([b])
        return b''

    def rec_bytes(r, rmp):
        out = bytearray()
        for cname, cid in r.chain:
            hdr = len(cname) + (5 if cid is not None else 0)
            out += bytes([T_CHAIN, hdr]) + cname.encode('latin-1')
            if cid is not None:
                out += bytes([T_ID]) + _s.pack('<i', cid)
        hdr = len(r.name) + (5 if r.rec_id is not None else 0)
        out += bytes([T_REC, hdr]) + r.name.encode('latin-1')
        if r.rec_id is not None:
            out += bytes([T_ID]) + _s.pack('<i', r.rec_id)
        for t in r.tokens:
            out += tok_bytes(t, rmp)
        out += bytes([T_TERM])
        return bytes(out)

    # preserve header and tail
    first_rec = min(new_order)
    head_end = 0  # we need to find where records start in the original
    # the records in the original SAB start after the header
    # we can find this by looking at the first record's offset
    # actually, we serialized from the original bytes, so we need to
    # find the boundary. Let's use the tokenized data's record offsets.
    # Actually, we should just rebuild from the original bytes.
    # The simplest: find the position of the first T_REC in the original.
    first_trec = recs[0].offset
    em_rec_start = min(i for i, r in enumerate(recs) if r.name == 'End-of-ACIS-data') if any(r.name == 'End-of-ACIS-data' for r in recs) else len(sab_bytes)
    # actually, find the end-marker record offset from the parse
    tail_start = len(sab_bytes)
    for r in reversed(recs):
        if r.name == 'End-of-ACIS-data':
            tail_start = r.offset
            break
    head = sab_bytes[:first_trec]
    tail = sab_bytes[tail_start:]

    # serialize records in new order
    body = b''.join(rec_bytes(recs[i], old_to_new) for i in new_order)
    return head + body + tail


def write_scdoc_multi(path: str, kdoc, name: str = "design") -> int:
    """H9: multi-part assembly scdoc — one SAB per component plus a
    component-hierarchy document.xml.  Returns the number of parts."""
    from scdm.sab_emit import (Worklist, Makers, _SeqCounter, MAGIC,
                               END_NAME, _s, _ri, _td, T_FLAG_A, T_RECORD)

    # one document-global def-creation counter across all part SABs
    # (official token#1 sequence: per part, body -> faces -> edges)
    doc_seq = _SeqCounter()

    def build_sab_for(items, colors, id_base: int = 0, seq=None,
                      doc_ids=None):
        wl = Worklist()
        # multi-part parts carry the official XACIS wstring identity chain
        # (assembly/STEP-import provenance; the single-part path keeps the
        # box.scdoc PNAME/rgb_color layout)
        makers = Makers(items, colors, seq=seq, xacis=True, doc_ids=doc_ids)
        makers.id_body_base = id_base
        body = wl.run([("body", bi) for bi in range(len(items))], makers)
        out = bytearray()
        out += MAGIC
        blob = b"\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
        out += _ri(len(blob)) + blob
        out += _s("SpaceClaim")
        out += _s("ACIS 29.0 NT")
        out += _s("Mon Aug 24 00:13:12 2026")
        out += _td(1000.0) + _td(1e-8) + _td(1e-10)
        out += bytes([T_FLAG_A])
        out += _s("FQ8FFTTT5P7PJFMUMMYS2_J8B48CXKNEWAP4QAQV2CS3PP65QBQCNVPEFCMUSP6XAAPKK47XTA84Q")
        out += body
        out += bytes([T_RECORD, len(END_NAME)]) + END_NAME.encode("latin-1")
        return bytes(out)

    # official SpaceClaim writes ONE body per part file (samplemodel2):
    # each body becomes its own partN.sab
    groups = []
    for b in kdoc.bodies:
        groups.append((b.name, [_item_of(b)],
                       [tuple(getattr(b, "color", None)
                              or (0.745, 0.902, 0.961))]))
    if not groups:
        raise ValueError("没有可写出的实体")

    non_planar = any(it[0] in ("cyl", "sphere", "torus")
                     for _g, items, _c in groups for it in items)

    import zipfile
    template = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "box.scdoc")
    DOC_GUID = "9d32a3b4-809e-4cc1-8dd7-f73febd3c257"
    doc_plan = _allocate_assembly_ids(groups, kdoc)
    doc_xml = _assembly_document_xml(kdoc, groups, name or "design",
                                     ids=doc_plan)
    with zipfile.ZipFile(template) as src, \
            zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            if (n.endswith(".sab") or n.endswith("facets.bin")
                    or n.endswith("checksums.bin")
                    or n.endswith("checksums.bin.rels")):
                continue
            if n.endswith("document.xml"):
                out.writestr(n, doc_xml)
            elif n.endswith("document.xml.rels"):
                rels = ['<?xml version="1.0" encoding="utf-8"?>',
                        '<Relationships xmlns="http://schemas.openxmlformats'
                        '.org/package/2006/relationships">',
                        '  <Relationship Type="http://www.spaceclaim.com/'
                        'relationships/internal/versionHistory" '
                        'Target="/SpaceClaim/versions.xml" Id="Rv1"/>']
                for gi in range(len(groups)):
                    rels.append(
                        '  <Relationship Type="http://www.spaceclaim.com/'
                        'relationships/internal/partBodyGeometry#' +
                        DOC_GUID + ':' + str(doc_plan["part"][gi]) +
                        '" Target="/SpaceClaim/Geometry/part' +
                        str(gi + 1) + 'bodies.sab" Id="Rg' + str(gi + 1) +
                        '"/>')
                if non_planar:
                    rels.append(
                        '  <Relationship Type="http://www.spaceclaim.com/'
                        'relationships/internal/bodyFacets" '
                        'Target="/SpaceClaim/Graphics/facets.bin" '
                        'Id="Rf1"/>')
                rels.append(
                    '  <Relationship Type="http://www.spaceclaim.com/'
                    'relationships/internal/renderlists" '
                    'Target="/SpaceClaim/Graphics/renderlist.xml" '
                    'Id="Rr1"/>')
                rels.append(
                    '  <Relationship Type="http://www.spaceclaim.com/'
                    'relationships/internal/windows" '
                    'Target="/SpaceClaim/UI/windows.xml" Id="Rw1"/>')
                rels.append('</Relationships>')
                out.writestr(n, "\n".join(rels).encode("utf-8"))
            elif n.endswith("windows.xml"):
                # the template's windows.xml carries the TEMPLATE document
                # GUID; the reader resolves rootPartMoniker/currentPartMoniker
                # against our document's GUID -- a mismatched GUID breaks
                # document initialization on open.
                out.writestr(n, src.read(n).replace(
                    b"fc598e53-8ab6-41b2-b8ea-b7917346ae70",
                    DOC_GUID.encode("latin-1")))
            elif n.endswith("versions.xml"):
                # versions.xml registers the DOCUMENT GUID; it must match the
                # moniker GUID used in document.xml + rels.
                out.writestr(n, src.read(n).replace(
                    b"fc598e53-8ab6-41b2-b8ea-b7917346ae70",
                    DOC_GUID.encode("latin-1")))
            else:
                out.writestr(n, src.read(n))
        # facets stream: OFFICIAL multi-body layout for EVERY body
        # (planar faces get the full official FaceNode structure; curved
        # faces fall back to one tessellation node per face)
        try:
            tessellations = []
            items_all = []
            ids_all = []
            for gi, body in enumerate(kdoc.bodies):
                it = _item_of(body)
                items_all.append(it)
                ids_all.append(doc_plan["facet_ids"][gi])
                if it[0] == "planar":
                    tessellations.append([])
                    continue
                sols = K.explore(body.shape, "solid") or [body.shape]
                sol = sols[0]
                try:
                    from scdm.kernel import tessellate_faces
                    tessellations.append(tessellate_faces(
                        sol, deflection=max(1e-5, 0.05 / 1000.0)))
                except Exception:
                    tessellations.append([])
            out.writestr("SpaceClaim/Graphics/facets.bin",
                         _facets_bytes(items_all, tessellations, ids_all))
        except Exception:
            pass
        for gi, (gname, items, colors) in enumerate(groups):
            items2 = [it[:4] for it in items]
            # attrib ids carry the GLOBAL body index (document-id alignment)
            out.writestr("SpaceClaim/Geometry/part%dbodies.sab" % (gi + 1),
                         build_sab_for(items2, colors, id_base=gi,
                                       seq=doc_seq,
                                       doc_ids=doc_plan["sab_ids"][gi]))
    return len(groups)


def _item_of(body):
    """Extract the ('planar'|'cyl'|...) item tuple for one body."""
    sols = K.explore(body.shape, "solid") or [body.shape]
    s = sols[0]
    info = _cyl_info(s)
    if info is not None:
        return ("cyl", info)
    sfo = _sphere_info(s)
    if sfo is not None:
        return ("sphere", sfo)
    tfo = _torus_info(s)
    if tfo is not None:
        return ("torus", tfo)
    return ("planar",) + _extract_solid(s)


def _counts_of(items) -> "tuple[int, int]":
    """(n_faces, n_edges) for one body item tuple (matches the SAB emitter's
    entity counts: cyl 3 edges / sphere 1 / torus 2)."""
    if items[0] == "planar":
        return len(items[3]), len(items[2])
    if items[0] == "cyl":
        return 3, 3
    if items[0] == "sphere":
        return 1, 1
    return 1, 2


def _allocate_assembly_ids(groups, kdoc):
    """P0-1: one document-global id plan consumed by document.xml, the
    per-part SAB attribs, facets.bin and rels -- they can never diverge.

    Official 60-stride layout (golden/assembly_sample.scdoc) is preserved
    while collision-free; collisions (>=4 bodies, dense bodies) bump to the
    next free id via _DocIdAllocator.
    """
    alloc = _DocIdAllocator()
    plan = {"part": [], "body": [], "faces": [], "edges": [],
            "cap_body": [], "cap_part": [], "comp": [],
            "cont_part": [], "cont_comp": [], "cont_cap": [],
            "facet_ids": []}
    for gi, (gname, items, colors) in enumerate(groups):
        nf, ne = _counts_of(items[0])
        pid = alloc.take_desired(22 + 60 * gi)
        bid = alloc.take_desired(23 + 60 * gi)
        faces = [alloc.take_desired(27 + 3 * k + 60 * gi) for k in range(nf)]
        edges = [alloc.take_desired(45 + 3 * k + 60 * gi) for k in range(ne)]
        cb = alloc.take_desired(85 + 60 * gi)
        cp = alloc.take_desired(86 + 60 * gi)
        plan["part"].append(pid)
        plan["body"].append(bid)
        plan["faces"].append(faces)
        plan["edges"].append(edges)
        plan["cap_body"].append(cb)
        plan["cap_part"].append(cp)
        plan["comp"].append(alloc.take_desired(200 + gi))
        plan["facet_ids"].append({"body": bid, "update": bid,
                                  "faces": faces, "edges": edges})
        plan.setdefault("sab_ids", [])
        plan["sab_ids"].append({"body": bid, "faces": faces, "edges": edges})
    for ci in range(len(getattr(kdoc, "components", []))):
        plan["cont_part"].append(alloc.take_desired(240 + ci))
        plan["cont_comp"].append(alloc.take_desired(260 + ci))
        plan["cont_cap"].append(alloc.take_desired(280 + ci))
    plan["next"] = max(alloc.used) + 1
    return plan


def _assembly_document_xml(kdoc, groups, name: str,
                           ids: "dict | None" = None) -> bytes:
    """Assembly document.xml replicating the OFFICIAL save skeleton.

    Field-level provenance: references/golden/assembly_sample.scdoc (the
    official SpaceClaim-written assembly) plus the TODO-9 differential
    bisection.  The official reader deserializes the WHOLE document.xml
    schema-first: a single invalid/unknown element anywhere makes it fall
    back to a blank document (root part only, no bodies) instead of
    raising.  So every section -- document-level fields, Design,
    PresentationDef, DocumentSettingsDef -- must follow the official
    skeleton verbatim; only ids / names / colors / component sources are
    substituted.

    Id scheme (document-global, verified against the official sample):
      root part 0:2, DefaultEdgeTreatmentDef 0:13,
      per body gi:  part 0:{22+60gi}, body def 0:{23+60gi},
                    faces 0:{27+3k+60gi}, edges 0:{45+3k+60gi},
                    part caption 0:{86+60gi}, body caption 0:{85+60gi},
      ComponentDefs 0:{200+i} (dedicated range, never colliding with
      body-part ids), container component parts 0:{240+ci} + their
      ComponentDefs 0:{260+ci} + captions 0:{280+ci} (official empty
      Assembly1-style container layout), Design 0:1, PresentationDef 0:5,
      AttributeTableDef 0:6, LayerDef 0:9, RootCaptionDef 0:11,
      DocumentSettingsDef 0:16, DocumentUnitsDef 0:17,
      DocumentDetailSettingsDef 0:19.
    """
    DOC_GUID = "9d32a3b4-809e-4cc1-8dd7-f73febd3c257"
    # sectionIds are FIXED section-type keys in the official reader (identical
    # in every official document); unknown sectionIds make the reader skip the
    # section and fall back to a blank document (TODO-9 bisection finding).
    SECTION_DESIGN = "6ab505a9-1afc-4b43-a7db-eb0258edde3e"
    SECTION_PRES = "595f79a0-e194-4d77-946d-55f551b8663a"
    SECTION_SETTINGS = "0ac8f8e0-608c-4b1e-a830-61e2a4bad599"

    ids = ids or {}
    part_ids = ids.get("part", [22 + gi for gi in range(len(groups))])
    body_ids = ids.get("body", [23 + gi for gi in range(len(groups))])
    face_ids = ids.get("faces", [])
    edge_ids = ids.get("edges", [])
    cap_body_ids = ids.get("cap_body", [85 + gi for gi in range(len(groups))])
    cap_part_ids = ids.get("cap_part", [86 + gi for gi in range(len(groups))])
    comp_ids = ids.get("comp", [200 + gi for gi in range(len(groups))])
    cont_part_ids = ids.get("cont_part", [])
    cont_comp_ids = ids.get("cont_comp", [])
    cont_cap_ids = ids.get("cont_cap", [])

    def body_part_def(gi, body, items, colors):
        fid = face_ids[gi]
        eid = edge_ids[gi]
        c = colors[0] if colors else (0.745, 0.902, 0.961)
        rgb = "%d, %d, %d" % (int(c[0] * 255), int(c[1] * 255),
                              int(c[2] * 255))
        faces = "".join(
            '<NominalFaceDef Id="0:%d"><updateState>0:%d</updateState>'
            '</NominalFaceDef>' % (fid[k], fid[k])
            for k in range(len(fid)))
        edges = "".join(
            '<NominalEdgeDef Id="0:%d"><updateState>0:%d</updateState>'
            '<isReversed>False</isReversed></NominalEdgeDef>'
            % (eid[k], eid[k])
            for k in range(len(eid)))
        bid = body_ids[gi]
        pid = part_ids[gi]
        return ('<PartDef Id="0:%d"><updateState>0:%d</updateState>'
                '<patternBase /><materialId>0:0</materialId>'
                '<type>Normal</type><shareTopologyOption>None</shareTopologyOption>'
                '<NominalBodyDef Id="0:%d"><updateState>0:%d</updateState>'
                '<layerId>0:9</layerId><type>Solid</type><color>%s</color>'
                '<renderingStyle>Plastic</renderingStyle>'
                '<fillStyle>Opaque</fillStyle><materialId>0:0</materialId>'
                '<modificationLock>None</modificationLock>'
                '<finishStyle>MediumGloss</finishStyle>%s%s'
                '</NominalBodyDef></PartDef>'
                % (pid, 60 + gi * 60, bid, bid, rgb, faces, edges))

    comp_xml = []
    part_xml = []
    captions = []
    for gi, (gname, items, colors) in enumerate(groups):
        body = kdoc.bodies[gi]
        part_xml.append(body_part_def(gi, body, items, colors))
        captions.append(
            '<CaptionDef Id="0:%d"><updateState>0:%d</updateState>'
            '<subjectId>0:%d</subjectId><name>%s</name><description></description>'
            '<type version="82">Normal</type></CaptionDef>'
            % (cap_body_ids[gi], cap_body_ids[gi], body_ids[gi],
               _xml_esc(body.name)))
        captions.append(
            '<CaptionDef Id="0:%d"><updateState>0:%d</updateState>'
            '<subjectId>0:%d</subjectId><name>%s</name><description></description>'
            '<type version="82">Normal</type></CaptionDef>'
            % (cap_part_ids[gi], cap_part_ids[gi], part_ids[gi],
               _xml_esc(body.name)))
    # one component instance per body part (official per-body externalization)
    for gi in range(len(groups)):
        comp_xml.append(
            '<ComponentDef Id="0:%d"><updateState>0:%d</updateState>'
            '<source sctype="SpaceClaim.BasicMoniker`1[[SpaceClaim.IEvaluation,'
            ' Core]], Core" refId="%s:%d" /><trans>1 0 0 0 0 1 0 0 0 0 1 0 '
            '0 0 0 1</trans><lastAccuracy>0</lastAccuracy>'
            '<lastEvaluatedTrans>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1'
            '</lastEvaluatedTrans></ComponentDef>'
            % (comp_ids[gi], comp_ids[gi], DOC_GUID, part_ids[gi]))
    # container component parts: one EMPTY PartDef per kdoc component plus its
    # ComponentDef instance (official assembly_sample.scdoc layout: bodies stay
    # externalized as root-level instances, the container part carries no body)
    container_parts = []
    for ci, comp in enumerate(getattr(kdoc, "components", [])):
        pid, cid = cont_part_ids[ci], cont_comp_ids[ci]
        container_parts.append(
            '<PartDef Id="0:%d"><updateState>0:%d</updateState>'
            '<patternBase /><materialId>0:0</materialId>'
            '<type>Normal</type><shareTopologyOption>None</shareTopologyOption>'
            '</PartDef>' % (pid, pid))
        comp_xml.append(
            '<ComponentDef Id="0:%d"><updateState>0:%d</updateState>'
            '<source sctype="SpaceClaim.BasicMoniker`1[[SpaceClaim.IEvaluation,'
            ' Core]], Core" refId="%s:%d" /><trans>1 0 0 0 0 1 0 0 0 0 1 0 '
            '0 0 0 1</trans><lastAccuracy>0</lastAccuracy>'
            '<lastEvaluatedTrans>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1'
            '</lastEvaluatedTrans></ComponentDef>'
            % (cid, cid, DOC_GUID, pid))
        captions.append(
            '<CaptionDef Id="0:%d"><updateState>0:%d</updateState>'
            '<subjectId>0:%d</subjectId><name>%s</name><description></description>'
            '<type version="82">Normal</type></CaptionDef>'
            % (cont_cap_ids[ci], cont_cap_ids[ci], pid, _xml_esc(comp.name)))
        part_xml.append(container_parts[-1])

    n_containers = len(container_parts)
    next_id = max(ids.get("next", 0),
                  60 * len(groups) + 300, 280 + n_containers + 40)
    design = ('<Design sectionId="%s" Id="0:1" xmlns="urn:nom">'
              '<updateState>0:141</updateState><nextId>1</nextId>'
              '<PartDef Id="0:2"><updateState>0:%d</updateState>'
              '<patternBase /><defaultEdgeTreatment sctype='
              '"SpaceClaim.BasicMoniker`1[[SpaceClaim.IDefaultEdgeTreatment,'
              ' Nom]], Core" refId="%s:13" /><materialId>0:0</materialId>'
              '<type>Normal</type><shareTopologyOption>None</shareTopologyOption>'
              '<DefaultEdgeTreatmentDef Id="0:13"><updateState>0:13</updateState>'
              '<blendRadius>0</blendRadius></DefaultEdgeTreatmentDef>%s</PartDef>'
              '%s</Design>'
              % (SECTION_DESIGN, next_id - 1, DOC_GUID, "".join(comp_xml),
                 "".join(part_xml)))

    presentation = (
        '<PresentationDef sectionId="%s" Id="0:5" xmlns="urn:presentation">'
        '<updateState>0:143</updateState><nextLayerHue>270</nextLayerHue>'
        '<decorationTableKeys /><decorationTableValues />'
        '<AttributeTableDef Id="0:6"><updateState>0:6</updateState><paths />'
        '<versionNumbers /><idRanges /><attributeIndex /><keys />'
        '<layerNames /><layerAttributes /><createdInVersion>520</createdInVersion>'
        '</AttributeTableDef>'
        '<LayerDef Id="0:9"><updateState>0:9</updateState><name>Layer 1</name>'
        '<visible>True</visible><locked>False</locked>'
        '<color>143, 175, 143</color><fillStyle>Opaque</fillStyle>'
        '<lineWeight /></LayerDef>'
        '<RootCaptionDef Id="0:11" xmlns="urn:nom"><updateState>0:21</updateState>'
        '<subjectId>0:2</subjectId><name>%s</name><description></description>'
        '<type version="82">Normal</type><isNameLocked>True</isNameLocked>'
        '</RootCaptionDef>%s</PresentationDef>'
        % (SECTION_PRES, _xml_esc(name), "".join(captions)))

    settings = (
        '<DocumentSettingsDef sectionId="%s" Id="0:16" xmlns="urn:presentation">'
        '<updateState>0:20</updateState><topViewDirection>Y</topViewDirection>'
        '<DocumentUnitsDef Id="0:17"><updateState>0:17</updateState><units>'
        '<massFactor>1</massFactor><derivedDensity>True</derivedDensity>'
        '<timeFactor>1</timeFactor>'
        '<lengthProperties><type>MM</type><factor>1000</factor>'
        '<symbolDisplay>True</symbolDisplay><annotationSymbolDisplay>True'
        '</annotationSymbolDisplay><trailingZeros>False</trailingZeros>'
        '<symbol>mm</symbol><secondSymbol>""</secondSymbol>'
        '<fractionSeparator> </fractionSeparator><decimalPlaces>2</decimalPlaces>'
        '<largestDenominator>0</largestDenominator><minorsInMajor>10</minorsInMajor>'
        '<minorTickInterval>0.001</minorTickInterval><angularPrecision>1'
        '</angularPrecision><angularTrailingZeros>False</angularTrailingZeros>'
        '</lengthProperties>'
        '<angleFactor>57.295779513082323</angleFactor><textHeightUnits>MM'
        '</textHeightUnits><newMassSymbol>g</newMassSymbol>'
        '<newMassType>GRAMS</newMassType><newMassFactor>1000</newMassFactor>'
        '<dualDimensionDisplay>False</dualDimensionDisplay>'
        '<extendedInformationDisplay>None</extendedInformationDisplay>'
        '<nearestFractionLargestDenominator>16</nearestFractionLargestDenominator>'
        '<showNearestFromBothSides>False</showNearestFromBothSides>'
        '<useTightTolerance>False</useTightTolerance>'
        '<useWorkbenchProjectUnit>False</useWorkbenchProjectUnit>'
        '<densityProperties><massType>GRAMS</massType><lengthType>MM</lengthType>'
        '<massSymbol>g</massSymbol><lengthSymbol>mm</lengthSymbol>'
        '<massFactor>1000</massFactor><lengthFactor>1000</lengthFactor>'
        '</densityProperties><angularUnits>Degrees</angularUnits></units>'
        '<alternateUnits><massFactor>1</massFactor><derivedDensity>True'
        '</derivedDensity><timeFactor>1</timeFactor>'
        '<lengthProperties><type>INCHES</type><factor>39.370078740157481</factor>'
        '<symbolDisplay>True</symbolDisplay><annotationSymbolDisplay>True'
        '</annotationSymbolDisplay><trailingZeros>True</trailingZeros>'
        '<symbol>in</symbol><secondSymbol>in</secondSymbol>'
        '<fractionSeparator>-</fractionSeparator><decimalPlaces>3</decimalPlaces>'
        '<largestDenominator>0</largestDenominator><minorsInMajor>8</minorsInMajor>'
        '<minorTickInterval>0.003175</minorTickInterval><angularPrecision>1'
        '</angularPrecision><angularTrailingZeros>False</angularTrailingZeros>'
        '</lengthProperties>'
        '<angleFactor>57.295779513082323</angleFactor><textHeightUnits>INCHES'
        '</textHeightUnits><newMassSymbol>lb</newMassSymbol>'
        '<newMassType>POUNDS</newMassType><newMassFactor>2.20462</newMassFactor>'
        '<dualDimensionDisplay>False</dualDimensionDisplay>'
        '<extendedInformationDisplay>None</extendedInformationDisplay>'
        '<nearestFractionLargestDenominator>16</nearestFractionLargestDenominator>'
        '<showNearestFromBothSides>False</showNearestFromBothSides>'
        '<useTightTolerance>False</useTightTolerance>'
        '<useWorkbenchProjectUnit>False</useWorkbenchProjectUnit>'
        '<densityProperties><massType>POUNDS</massType><lengthType>INCHES'
        '</lengthType><massSymbol>lb</massSymbol><lengthSymbol>in</lengthSymbol>'
        '<massFactor>2.20462</massFactor><lengthFactor>39.370078740157481'
        '</lengthFactor></densityProperties><angularUnits>Degrees'
        '</angularUnits></alternateUnits>'
        '<unitsSecondary><massFactor>1</massFactor><derivedDensity>True'
        '</derivedDensity><timeFactor>1</timeFactor>'
        '<lengthProperties><type>INCHES</type><factor>39.370078740157481</factor>'
        '<symbolDisplay>True</symbolDisplay><annotationSymbolDisplay>False'
        '</annotationSymbolDisplay><trailingZeros>True</trailingZeros>'
        '<symbol>in</symbol><secondSymbol></secondSymbol>'
        '<fractionSeparator></fractionSeparator><decimalPlaces>3</decimalPlaces>'
        '<largestDenominator>0</largestDenominator><minorsInMajor>10</minorsInMajor>'
        '<minorTickInterval>0.0025399999999999997</minorTickInterval>'
        '<angularPrecision>1</angularPrecision>'
        '<angularTrailingZeros>False</angularTrailingZeros></lengthProperties>'
        '<angleFactor>57.295779513082323</angleFactor><textHeightUnits>INCHES'
        '</textHeightUnits><newMassSymbol>lb</newMassSymbol>'
        '<newMassType>POUNDS</newMassType><newMassFactor>2.20462</newMassFactor>'
        '<dualDimensionDisplay>False</dualDimensionDisplay>'
        '<extendedInformationDisplay>None</extendedInformationDisplay>'
        '<nearestFractionLargestDenominator>16</nearestFractionLargestDenominator>'
        '<showNearestFromBothSides>False</showNearestFromBothSides>'
        '<useTightTolerance>False</useTightTolerance>'
        '<useWorkbenchProjectUnit>False</useWorkbenchProjectUnit>'
        '<densityProperties><massType>OUNCES</massType><lengthType>INCHES'
        '</lengthType><massSymbol>oz</massSymbol><lengthSymbol>in</lengthSymbol>'
        '<massFactor>35.27392</massFactor><lengthFactor>39.370078740157481'
        '</lengthFactor></densityProperties><angularUnits>Degrees'
        '</angularUnits></unitsSecondary>'
        '<alternateUnitsSecondary><massFactor>1</massFactor>'
        '<derivedDensity>True</derivedDensity><timeFactor>1</timeFactor>'
        '<lengthProperties><type>MM</type><factor>1000</factor>'
        '<symbolDisplay>True</symbolDisplay><annotationSymbolDisplay>False'
        '</annotationSymbolDisplay><trailingZeros>False</trailingZeros>'
        '<symbol>mm</symbol><secondSymbol></secondSymbol>'
        '<fractionSeparator></fractionSeparator><decimalPlaces>2</decimalPlaces>'
        '<largestDenominator>0</largestDenominator><minorsInMajor>10</minorsInMajor>'
        '<minorTickInterval>0.0001</minorTickInterval><angularPrecision>1'
        '</angularPrecision><angularTrailingZeros>False</angularTrailingZeros>'
        '</lengthProperties>'
        '<angleFactor>57.295779513082323</angleFactor><textHeightUnits>MM'
        '</textHeightUnits><newMassSymbol>kg</newMassSymbol>'
        '<newMassType>KILOGRAMS</newMassType><newMassFactor>1</newMassFactor>'
        '<dualDimensionDisplay>False</dualDimensionDisplay>'
        '<extendedInformationDisplay>None</extendedInformationDisplay>'
        '<nearestFractionLargestDenominator>16</nearestFractionLargestDenominator>'
        '<showNearestFromBothSides>False</showNearestFromBothSides>'
        '<useTightTolerance>False</useTightTolerance>'
        '<useWorkbenchProjectUnit>False</useWorkbenchProjectUnit>'
        '<densityProperties><massType>GRAMS</massType><lengthType>CM</lengthType>'
        '<massSymbol>g</massSymbol><lengthSymbol>cm</lengthSymbol>'
        '<massFactor>1000</massFactor><lengthFactor>100</lengthFactor>'
        '</densityProperties><angularUnits>Degrees</angularUnits>'
        '</alternateUnitsSecondary></DocumentUnitsDef>'
        '<DocumentDetailSettingsDef Id="0:19"><updateState>0:19</updateState>'
        '<settings><defaultViewProjection>ThirdAngle</defaultViewProjection>'
        '<defaultViewLayout>BottomLeft</defaultViewLayout>'
        '<sectionLineArrowSize>0.0028</sectionLineArrowSize>'
        '<sectionLineLength>0.014</sectionLineLength>'
        '<leaderCircleSize>0.0009</leaderCircleSize>'
        '<leaderArrowLength>0.0025</leaderArrowLength>'
        '<leaderArrowWidth>0.0006</leaderArrowWidth>'
        '<defaultLeaderShoulderLength>0.00564444444</defaultLeaderShoulderLength>'
        '<leaderTextBoxGap>0.00141111111</leaderTextBoxGap>'
        '<defaultFillStyle>Filled</defaultFillStyle>'
        '<enforceDimensionLine>False</enforceDimensionLine>'
        '<dimensionTextIsHorizontal>True</dimensionTextIsHorizontal>'
        '<defaultDimensionTextLocation>MiddleOfTopLine</defaultDimensionTextLocation>'
        '<tightDimensionTextDistance>False</tightDimensionTextDistance>'
        '<dimensionTextOffset>0</dimensionTextOffset>'
        '<defaultGtolFontName>SpaceClaim ASME CB</defaultGtolFontName>'
        '<extensionLineGap>0.001</extensionLineGap>'
        '<extensionLineExtend>0.002</extensionLineExtend>'
        '<dimensionLineExtend>0.006</dimensionLineExtend>'
        '<annotationCreationColor>Black</annotationCreationColor>'
        '<detailViewClippedEdgesColor>Black</detailViewClippedEdgesColor>'
        '<brokenViewClippedEdgesColor>Black</brokenViewClippedEdgesColor>'
        '<defaultToleranceVerticalPosition>Middle</defaultToleranceVerticalPosition>'
        '<fractionalScaleDivider>:</fractionalScaleDivider>'
        '<minimumDefaultHatchSpacing>0.0007</minimumDefaultHatchSpacing>'
        '<maximumDefaultHatchSpacing>0.02</maximumDefaultHatchSpacing>'
        '<detailViewBoundaryRendering>PhantomThin</detailViewBoundaryRendering>'
        '<detailViewNoteLayout>TwoLines</detailViewNoteLayout>'
        '<crossSectionArrowsRendering>PhantomThick</crossSectionArrowsRendering>'
        '<detailViewNoteScaleText>SCALE</detailViewNoteScaleText>'
        '<detailViewNoteDetailText>DETAIL</detailViewNoteDetailText>'
        '<defaultTextHeight>0.0035</defaultTextHeight>'
        '<detailViewNameTextHeightRatio>1.4</detailViewNameTextHeightRatio>'
        '<detailViewNotePlacement>Centered</detailViewNotePlacement>'
        '<crossSectionArrowOutwardDistance>0</crossSectionArrowOutwardDistance>'
        '<crossSectionArrowPenetrationDistance>0.0075</crossSectionArrowPenetrationDistance>'
        '<crossSectionArrowDirectionDisplayStyle>From</crossSectionArrowDirectionDisplayStyle>'
        '<defaultSectionNameNotePrefix>SECTION</defaultSectionNameNotePrefix>'
        '<defaultThickLineWeight>0.0007</defaultThickLineWeight>'
        '<defaultThinLineWeight>0.00035</defaultThinLineWeight>'
        '<defaultMediumLineWeight>0.000525</defaultMediumLineWeight>'
        '<defaultDetailViewClippedEdgeExtent>0</defaultDetailViewClippedEdgeExtent>'
        '<defaultBrokenViewClippedEdgeExtent>0</defaultBrokenViewClippedEdgeExtent>'
        '<defaultForeshortenedCenterSize>0.004</defaultForeshortenedCenterSize>'
        '<useThickLineWeightForAreaCrossSectionBorderLines>True'
        '</useThickLineWeightForAreaCrossSectionBorderLines>'
        '<threadDisplayStandard>AsmeSimplified</threadDisplayStandard>'
        '<centerLinesExtend>0.003</centerLinesExtend>'
        '<crossSectionArrowLineWeight>THICK</crossSectionArrowLineWeight>'
        '<detailViewBoundaryLineWeight>THIN</detailViewBoundaryLineWeight>'
        '<virtualSharpRendering>None</virtualSharpRendering>'
        '<centermarkCrossRadius>0</centermarkCrossRadius>'
        '<defaultDimensionArrowShape>Arrow</defaultDimensionArrowShape>'
        '<ordinateDimsShowZeroBaseline>True</ordinateDimsShowZeroBaseline>'
        '<ordinateDimsDimensionLineAndTextOrientation>'
        'HideCommonDimensionLineTextVertical'
        '</ordinateDimsDimensionLineAndTextOrientation>'
        '<datumSymbolAttachment>Triangle</datumSymbolAttachment>'
        '<datumSymbolFrame>Rectangular</datumSymbolFrame>'
        '<isTrimBackProportional>False</isTrimBackProportional>'
        '<showConstructionCurvesOffPlane>True</showConstructionCurvesOffPlane>'
        '<threadDiameterDimensionDesignationTextOption>Never'
        '</threadDiameterDimensionDesignationTextOption>'
        '<datumCalloutTextHeightRatio>3.5</datumCalloutTextHeightRatio>'
        '<datumTargetPointSize>0.00494975</datumTargetPointSize>'
        '<datumTargetHatchSpacing>0.001</datumTargetHatchSpacing>'
        '<datumTargetHatchAngle>0.78539816339744828</datumTargetHatchAngle>'
        '<datumCalloutLeaderShape>None</datumCalloutLeaderShape>'
        '<datumTargetLineShowEndPoints>True</datumTargetLineShowEndPoints>'
        '<weldingSymbolStandard>AWS</weldingSymbolStandard>'
        '<gdtStandard>ASME</gdtStandard>'
        '<hideAnnotationsBehindModel>False</hideAnnotationsBehindModel>'
        '<projectionArrowsStyle>Double</projectionArrowsStyle>'
        '<chamferDimensionStyle>Linear</chamferDimensionStyle>'
        '<chamferDimensionTextStyle>X45</chamferDimensionTextStyle>'
        '<showNotesForProjectedViews>False</showNotesForProjectedViews>'
        '<showNotesForAuxiliaryViews>False</showNotesForAuxiliaryViews>'
        '<projectedViewLabelPrefix>VIEW</projectedViewLabelPrefix>'
        '<auxiliaryViewLabelPrefix>VIEW</auxiliaryViewLabelPrefix>'
        '<showProjectedViewArrows>False</showProjectedViewArrows>'
        '<showAuxiliaryViewArrows>False</showAuxiliaryViewArrows>'
        '<projectionArrowLength>0.014</projectionArrowLength>'
        '<systemOfFits>HoleBasis</systemOfFits>'
        '<holeFundamentalDeviation>H_H</holeFundamentalDeviation>'
        '<shaftFundamentalDeviation>S_h</shaftFundamentalDeviation>'
        '<holeInternationalToleranceGrade>IT7</holeInternationalToleranceGrade>'
        '<shaftInternationalToleranceGrade>IT6</shaftInternationalToleranceGrade>'
        '<methodOfDesignatingTolerances>ToleranceClass'
        '</methodOfDesignatingTolerances>'
        '<assignmentArray>'
        '<item><key>Annotation</key><value><linestyleId>Solid</linestyleId>'
        '<lineWeight>THIN</lineWeight></value></item>'
        '<item><key>AreaCrossHatchingBorderLines</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THICK</lineWeight>'
        '</value></item>'
        '<item><key>BrokenOutSectionClippingEdges</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>BrokenViewClippingEdges</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>CenterLines</key><value>'
        '<linestyleId>LongDashDash</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>CrossHatching</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>CrossHatchingBorderLines</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THICK</lineWeight>'
        '</value></item>'
        '<item><key>CrossSectionCutLineTips</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>DatumTargetAreaBorder</key><value>'
        '<linestyleId>LongDashDoubleDotted</linestyleId><lineWeight>THIN'
        '</lineWeight></value></item>'
        '<item><key>DatumTargetLine</key><value>'
        '<linestyleId>LongDashDoubleDotted</linestyleId><lineWeight>THIN'
        '</lineWeight></value></item>'
        '<item><key>DetailViewClippingEdges</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>DrawingHiddenEdges</key><value>'
        '<linestyleId>Dash</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>DrawingVisibleEdges</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THICK</lineWeight>'
        '</value></item>'
        '<item><key>ProjectionArrowTipsType</key><value>'
        '<linestyleId>Solid</linestyleId><lineWeight>THIN</lineWeight>'
        '</value></item>'
        '<item><key>ProjectionArrowType</key><value>'
        '<linestyleId>LongDashDotted</linestyleId><lineWeight>THICK</lineWeight>'
        '</value></item>'
        '</assignmentArray></settings></DocumentDetailSettingsDef>'
        '</DocumentSettingsDef>' % SECTION_SETTINGS)

    xml = ('<?xml version="1.0" encoding="utf-8"?>'
           '<Document version="1.520" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xmlns="urn:core"><nextId>%d</nextId>'
           '<isNotCompletable>False</isNotCompletable>'
           '<importPath>%s.scdoc</importPath>'
           '<importComponentName></importComponentName>'
           '<importTimestamp>01/01/2026 00:00:00</importTimestamp>'
           '<loadTime>0</loadTime>'
           '<originalToReplacements_Keys /><originalToReplacements_Values />'
           '<monikerOriginalToReplacements_Keys />'
           '<monikerOriginalToReplacements_Values />'
           '<locked>False</locked>'
           '%s%s%s</Document>'
           % (next_id, _xml_esc(name), design, presentation, settings))
    return xml.encode("utf-8")


class _DocIdAllocator:
    """Document-global id allocator for assembly document.xml.

    Official-layout-first: every element asks for its DESIRED id (the
    per-body 60-stride layout validated against
    references/golden/assembly_sample.scdoc); when that id is already taken
    -- which happens for >=4 bodies or bodies with many edges/faces -- the
    allocator bumps to the next free number above.  Uniqueness across the
    whole document is guaranteed; small assemblies keep the exact official
    numbering.

    Reserved (fixed skeleton ids): 1 Design, 2 root part, 5
    PresentationDef, 6 AttributeTableDef, 7 PresentationDef2, 9 LayerDef,
    11 RootCaptionDef, 13 root DefaultEdgeTreatmentDef, 16
    DocumentSettingsDef, 17 DocumentUnitsDef, 19
    DocumentDetailSettingsDef, and the root state trio 141/143/145.
    """

    RESERVED = frozenset({1, 2, 5, 6, 7, 9, 11, 13, 16, 17, 19,
                          141, 143})

    def __init__(self):
        self.used: set = set(self.RESERVED)

    def take_desired(self, desired: int) -> int:
        """Allocate `desired`, or the next free id >= 21 when taken."""
        d = max(int(desired), 21)
        if d not in self.used and d not in self.RESERVED:
            self.used.add(d)
            return d
        d = max(d, 21)
        while d in self.used or d in self.RESERVED:
            d += 1
        self.used.add(d)
        return d


def _xml_esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))





def write_scdoc(path: str, kdoc, name: str = "design") -> None:
    """Write a native .scdoc for planar solids, cylinders, spheres, torus."""
    items = []
    colors = []
    for body in kdoc.bodies:
        sols = K.explore(body.shape, "solid") or [body.shape]
        for s in sols:
            info = _cyl_info(s)
            if info is not None:
                items.append(("cyl", info))
            else:
                sfo = _sphere_info(s)
                if sfo is not None:
                    items.append(("sphere", sfo))
                else:
                    tfo = _torus_info(s)
                    if tfo is not None:
                        items.append(("torus", tfo))
                    else:
                        items.append(("planar",) + _extract_solid(s))
            colors.append(tuple(getattr(body, "color", None) or (0.745, 0.902, 0.961)))
    if not items:
        raise ValueError("没有可写出的实体")
    sab_bytes, face_counts, edge_counts = _build_sab(items, colors)
    # record order now comes from the reverse-engineered FIFO worklist
    # (save_entity_pointer appends at first reference), no template reorder.

    # graphics facets part: always written (the official reader needs the
    # bodyFacets stream to bind bodies; planar bodies use the official
    # FaceNode layout, cylinders fall back to triangle nodes).
    tessellations = []
    if any(it[0] in ("cyl", "sphere", "torus") or
           (it[0] == "planar" and (it[4].get("face_surf") or
                                   it[4].get("edge_curve")))
           for it in items):
        for body in kdoc.bodies:
            sols = K.explore(body.shape, "solid") or [body.shape]
            for s in sols:
                # deflection relative to the body size: the fixed 0.05 mm
                # figure explodes on mm-scale models and overflows the
                # facets stream's 16-bit vertex packing (>65535 corners)
                try:
                    (a0, b0, c0), (a1, b1, c1) = _A.shape_bbox(s)
                    diag = ((a1 - a0) ** 2 + (b1 - b0) ** 2
                            + (c1 - c0) ** 2) ** 0.5
                except Exception:
                    diag = 1.0
                defl = max(1e-5, 1e-4 * diag)
                from scdm.kernel import tessellate_faces
                for _attempt in range(4):
                    try:
                        tess = tessellate_faces(s, deflection=defl)
                    except Exception:
                        tess = []
                        break
                    if all(len(fd["vertices"]) < 0xFFFF for fd in tess):
                        break
                    defl *= 4.0
                tessellations.append(tess)
    else:
        tessellations = [[] for _ in items]
    facets_bytes = _facets_bytes(items, tessellations)

    sab_name = "part1bodies.sab"
    stem = name or "design"
    # Non-geometry package parts (document.xml, rels, contentType, facets
    # registry) are taken verbatim from an official template scdoc: the
    # SpaceClaim reader builds bodies from the SAB stream only; the XML parts
    # carry presentation/metadata.  Our own _document_xml layout deviates from
    # the official one and yields 0 bodies on open, so keep the official parts.
    template = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "box.scdoc")
    cand = None
    for c in (template,
              os.path.join(os.path.dirname(os.path.dirname(
                  os.path.abspath(__file__))), "references", "golden",
                  "ref_tet.scdoc")):
        if os.path.exists(c):
            cand = c
            break
    with zipfile.ZipFile(cand) as src, \
            zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        # template package as-is except the SAB and the facets part; the
        # template's document.xml Id scheme (0:23 body / 0:27 faces / 0:45
        # edges) matches the SAB attrib values our emitter writes, and the
        # facets stream is regenerated to agree with the SAB face order.
        for n in src.namelist():
            if n.endswith(".sab"):
                out.writestr(n, sab_bytes)
            elif n.endswith("facets.bin"):
                out.writestr(n, facets_bytes)
            else:
                out.writestr(n, src.read(n))
    if facets_bytes is not None:
        _patch_rels(path)


def _write_package(path, sab_bytes, face_counts, edge_counts, colors, stem,
                   sab_name, facets_bytes):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _content_types())
        z.writestr("_rels/.rels", _root_rels())
        z.writestr("SpaceClaim/document.xml",
                   _document_xml(stem, face_counts, edge_counts, colors))
        z.writestr("SpaceClaim/_rels/document.xml.rels",
                   _doc_rels(sab_name, facets=facets_bytes is not None))
        z.writestr(f"SpaceClaim/Geometry/{sab_name}", sab_bytes)
        if facets_bytes is not None:
            z.writestr("SpaceClaim/Graphics/facets.bin", facets_bytes)

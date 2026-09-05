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
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface
    from OCC.Core.TopoDS import topods
    ad = BRepAdaptor_Surface(topods.Face(face))
    if ad.GetType() != GeomAbs_BSplineSurface:
        return None
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


def _extract_solid(solid):
    """Return (verts, edges, faces) for a planar-faced solid."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepTools import BRepTools_WireExplorer
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.TopAbs import (TopAbs_EDGE, TopAbs_FACE, TopAbs_FORWARD,
                                 TopAbs_VERTEX, TopAbs_WIRE)
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods

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

    faces = []
    edges = []
    emap = {}
    face_surf = {}   # face index -> ("bsurf", data)
    edge_curve = {}  # edge index -> ("bcur", data)

    def edge_index(a, b):
        key = (min(a, b), max(a, b))
        if key not in emap:
            emap[key] = len(edges)
            edges.append((key[0], key[1]))
        return emap[key]

    fexp = TopExp_Explorer(solid, TopAbs_FACE)
    while fexp.More():
        face = topods.Face(fexp.Current())
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        adapt = BRepAdaptor_Surface(face)
        if adapt.GetType() != GeomAbs_Plane:
            data = _bsurface_data(face)
            if data is None:
                raise ValueError("仅支持平面/双样条面的实体写出")
        else:
            data = None
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
                corners.append(vs[0] if we.Orientation() == TopAbs_FORWARD else vs[1])
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
        if data is not None:
            face_surf[len(faces) - 1] = ("bsurf", data)
        fexp.Next()
    # capture B-spline edge curves (by vertex-pair edge index)
    from OCC.Core.GeomAbs import GeomAbs_BSplineCurve
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    eexp = TopExp_Explorer(solid, TopAbs_EDGE)
    while eexp.More():
        occe = topods.Edge(eexp.Current())
        vs = []
        vex = TopExp_Explorer(occe, TopAbs_VERTEX)
        while vex.More():
            vs.append(vid(vex.Current()))
            vex.Next()
        if len(vs) >= 2:
            key = (min(vs[0], vs[-1]), max(vs[0], vs[-1]))
            if key in emap and emap[key] not in edge_curve:
                ad = BRepAdaptor_Curve(occe)
                if ad.GetType() == GeomAbs_BSplineCurve:
                    d = _bcurve_data(occe)
                    if d is not None:
                        edge_curve[emap[key]] = ("bcur", d)
        eexp.Next()
    return verts, edges, faces, {"face_surf": face_surf,
                                  "edge_curve": edge_curve}


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


def _facets_bytes(items, tessellations, first_doc_id: int = 23) -> bytes:
    """Graphics facets stream (bodyFacets part).

    Planar bodies use the official layout: one FaceNode per B-rep face with the
    polygon corners, boundary pairs, per-edge refs and the tail edge map. Plain
    cylinders use one triangle node per triangle (corner_count stays in 3..64;
    the side face would otherwise exceed it), without edge mapping.
    """
    import struct as _s
    n_faces = 0
    chunks = []          # (face-node bytes) deferred until count known -> build list
    edge_rows = []       # (mesh_edge_id, doc_num)
    node = first_doc_id
    mesh_edge_base = 1000

    # planar edge global offset (mesh ids must be unique across bodies)
    planar_eoff = {}
    _e = 0
    for bi, it in enumerate(items):
        if it[0] == "planar":
            planar_eoff[bi] = _e
            _e += len(it[2])

    for bi, it in enumerate(items):
        if it[0] == "planar":
            verts, edges, faces = it[1], it[2], it[3]
            for fi, f in enumerate(faces):
                loop = f["loop"]
                corners = [verts[vi] for vi in loop]
                nrm = f["normal"]
                n = len(corners)
                body = bytearray()
                body += _s.pack('<5I', 0, node, 0, node, n)
                for p in corners:
                    body += _s.pack('<8f', p[0], p[1], p[2], nrm[0], nrm[1], nrm[2],
                                    0.0, 0.0)
                # fan triangulation, packed 2 indices per word
                tris = []
                for k in range(1, n - 1):
                    tris += [0, k, k + 1]
                body += _s.pack('<I', len(tris))
                for k in range(0, len(tris), 2):
                    lo = tris[k]
                    hi = tris[k + 1] if k + 1 < len(tris) else 0
                    body += _s.pack('<I', (hi << 16) | lo)
                # boundary: closed loop pairs (i, i+1 wraparound)
                bnd = []
                for k in range(n):
                    bnd += [k, (k + 1) % n]
                body += _s.pack('<I', len(bnd))
                for k in range(0, len(bnd), 2):
                    lo = bnd[k]
                    hi = bnd[k + 1] if k + 1 < len(bnd) else 0
                    body += _s.pack('<I', (hi << 16) | lo)
                # edge refs: one per boundary pair
                body += _s.pack('<I', n)
                for k in range(n):
                    a, b = loop[k], loop[(k + 1) % n]
                    eidx = _edge_of(edges, a, b)
                    mid = mesh_edge_base + planar_eoff[bi] + eidx
                    edge_rows.append((mid, 45 + 3 * eidx + 60 * bi))
                    body += _s.pack('<3I', mid, 2 * k, 1)
                chunks.append(bytes(body))
                node += 3
                n_faces += 1
        else:
            faces = tessellations[bi] if bi < len(tessellations) else []
            for fd in faces:
                pts = fd["vertices"]
                tris = fd["triangles"]
                fn = fd.get("normal") or (0.0, 0.0, 1.0)
                for a, b, c in tris:
                    body = bytearray()
                    body += _s.pack('<5I', 0, node, 0, node, 3)
                    for idx in (a, b, c):
                        p = pts[idx]
                        body += _s.pack('<8f', p[0], p[1], p[2], fn[0], fn[1],
                                        fn[2], 0.0, 0.0)
                    body += _s.pack('<I', 3)
                    body += _s.pack('<I', (1 << 16) | 0)
                    body += _s.pack('<I', (2 << 16) | 2)
                    body += _s.pack('<I', 0)
                    body += _s.pack('<I', 0)
                    chunks.append(bytes(body))
                    node += 3
                    n_faces += 1

    head = bytearray()
    head += b'facets  '
    head += _s.pack('<I', 14)          # version
    head += _s.pack('<I', 1)           # w3
    head += _s.pack('<I', 1)           # w4
    head += _s.pack('<I', 0)           # w5
    head += _s.pack('<I', first_doc_id)  # w6 = owning body doc-id number
    head += _s.pack('<I', 0)           # w7
    head += _s.pack('<I', 0)           # w8
    head += _s.pack('<I', 0)           # w9
    head += _s.pack('<I', n_faces)     # w10 = declared face count
    out = bytearray(head)
    for c in chunks:
        out += c
    # tail edge map: unique (mesh_edge_id, 0, doc_num)
    seen = {}
    for mid, doc_num in edge_rows:
        seen[mid] = doc_num
    out += _s.pack('<I', len(seen))
    for mid, doc_num in sorted(seen.items()):
        out += _s.pack('<3I', mid, 0, doc_num)
    return bytes(out)




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
    from scdm.sab_emit import (Worklist, Makers, MAGIC, END_NAME, _s, _ri,
                               _td, T_FLAG_A, T_RECORD)

    def build_sab_for(items, colors, id_base: int = 0):
        wl = Worklist()
        makers = Makers(items, colors)
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
    doc_xml = _assembly_document_xml(kdoc, groups, name or "design")
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
                DOC_GUID = "9d32a3b4-809e-4cc1-8dd7-f73febd3c257"
                rels = ['<?xml version="1.0" encoding="utf-8"?>',
                        '<Relationships xmlns="http://schemas.openxmlformats'
                        '.org/package/2006/relationships">']
                for gi in range(len(groups)):
                    rels.append(
                        '  <Relationship Type="http://www.spaceclaim.com/'
                        'relationships/internal/partBodyGeometry#' +
                        DOC_GUID + ':' + str(22 + gi * 60) +
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
            else:
                out.writestr(n, src.read(n))
        np_groups = [(gname, [it for it in items
                              if it[0] in ("cyl", "sphere", "torus")], colors)
                     for gname, items, colors in groups]
        np_groups = [(g, i, c) for g, i, c in np_groups if i]
        if np_groups:
            try:
                tessellations = []
                items_all = []
                for body in kdoc.bodies:
                    sols = K.explore(body.shape, "solid") or [body.shape]
                    sol = sols[0]
                    if (_cyl_info(sol) is None and _sphere_info(sol) is None
                            and _torus_info(sol) is None):
                        continue
                    items_all.append(_item_of(body))
                    try:
                        from scdm.kernel import tessellate_faces
                        tessellations.append(tessellate_faces(
                            sol, deflection=max(1e-5, 0.05 / 1000.0)))
                    except Exception:
                        tessellations.append([])
                out.writestr("SpaceClaim/Graphics/facets.bin",
                             _facets_bytes(items_all, tessellations))
            except Exception:
                pass
        for gi, (gname, items, colors) in enumerate(groups):
            items2 = [it[:4] for it in items]
            # attrib ids carry the GLOBAL body index (document-id alignment)
            out.writestr("SpaceClaim/Geometry/part%dbodies.sab" % (gi + 1),
                         build_sab_for(items2, colors, id_base=gi))
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


def _assembly_document_xml(kdoc, groups, name: str) -> bytes:
    """Official-mechanism assembly document.xml (from assembly_sample.scdoc):

    root PartDef > ComponentDef(per component, source@refId = docGUID:target
    PartDef number, trans = instance transform) ...; each body part is a
    top-level PartDef holding its NominalBodyDef; rels tie partN.sab to
    partBodyGeometry#GUID:partId.  Body doc-ids are global (0:23+60*bi) and
    match each part SAB's attrib values.
    """
    comp_of = {}
    for comp in getattr(kdoc, "components", []):
        for bid in comp.body_ids:
            comp_of.setdefault(bid, comp)
    comp_members = {}
    loose = []
    for gi, (gname, items, colors) in enumerate(groups):
        body = kdoc.bodies[gi]
        comp = comp_of.get(body.id)
        if comp is not None:
            comp_members.setdefault(comp.id, []).append((gi, body))
        else:
            loose.append((gi, body))
    ordered = []
    for comp in getattr(kdoc, "components", []):
        if comp.id in comp_members:
            ordered.append(comp)
    DOC_GUID = "9d32a3b4-809e-4cc1-8dd7-f73febd3c257"

    def body_part_def(gi, body, items, colors):
        face_n = sum(len(it[3]) if it[0] == "planar"
                     else (1 if it[0] in ("sphere", "torus") else 3)
                     for it in items)
        edge_n = sum(len(it[2]) if it[0] == "planar"
                     else (1 if it[0] in ("sphere", "torus") else 2)
                     for it in items)
        c = colors[0] if colors else (0.745, 0.902, 0.961)
        rgb = "%d, %d, %d" % (int(c[0] * 255), int(c[1] * 255),
                              int(c[2] * 255))
        faces = "".join(
            '<NominalFaceDef Id="0:%d"><updateState>0:%d</updateState>'
            '</NominalFaceDef>' % (27 + 3 * k + gi * 60,
                                   27 + 3 * k + gi * 60)
            for k in range(face_n))
        edges = "".join(
            '<NominalEdgeDef Id="0:%d"><updateState>0:%d</updateState>'
            '<isReversed>False</isReversed></NominalEdgeDef>'
            % (45 + 3 * k + gi * 60, 45 + 3 * k + gi * 60)
            for k in range(edge_n))
        bid = 23 + gi * 60
        pid = 22 + gi * 60
        return ('<PartDef Id="0:%d"><updateState>0:%d</updateState>'
                '<patternBase /><materialId>0:0</materialId>'
                '<type>Normal</type>'
                '<shareTopologyOption>None</shareTopologyOption>'
                '<DefaultEdgeTreatmentDef Id="0:%d">'
                '<updateState>0:%d</updateState>'
                '<blendRadius>0</blendRadius></DefaultEdgeTreatmentDef>'
                '<NominalBodyDef Id="0:%d"><updateState>0:%d</updateState>'
                '<layerId>0:9</layerId><type>Solid</type><color>%s</color>'
                '<renderingStyle>Plastic</renderingStyle>'
                '<fillStyle>Opaque</fillStyle><materialId>0:0</materialId>'
                '<modificationLock>None</modificationLock>'
                '<finishStyle>MediumGloss</finishStyle>%s%s'
                '</NominalBodyDef></PartDef>'
                % (pid, 60 + gi * 60, 13 + gi * 60, 13 + gi * 60, bid,
                   bid, rgb, faces, edges))

    comp_xml = []
    part_xml = []
    captions = []
    for gi, (gname, items, colors) in enumerate(groups):
        part_xml.append(body_part_def(gi, kdoc.bodies[gi], items, colors))
        captions.append(
            '<CaptionDef Id="0:%d"><subjectId>0:%d</subjectId>'
            '<name>%s</name><type>Mutable</type></CaptionDef>'
            % (85 + gi * 60, 23 + gi * 60, kdoc.bodies[gi].name))
    # one component instance per component; members = its bodies' parts
    for comp in ordered:
        members = comp_members[comp.id]
        children = "".join(
            '<ComponentDef Id="0:%d"><updateState>0:%d</updateState>'
            '<source sctype="SpaceClaim.BasicMoniker`1[[SpaceClaim.IEvaluation,'
            ' Core]], Core" refId="%s:%d" /><trans>1 0 0 0 0 1 0 0 0 0 1 0 '
            '0 0 0 1</trans><lastAccuracy>0</lastAccuracy>'
            '<lastEvaluatedTrans>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1'
            '</lastEvaluatedTrans></ComponentDef>'
            % (200 + (hash(comp.id + str(gi)) % 5000),
               200 + (hash(comp.id + str(gi)) % 5000),
               DOC_GUID, 22 + gi * 60)
            for gi, _b in members)
        comp_xml.append(children)
    for gi, body in loose:
        comp_xml.append(
            '<ComponentDef Id="0:%d"><updateState>0:%d</updateState>'
            '<source sctype="SpaceClaim.BasicMoniker`1[[SpaceClaim.IEvaluation,'
            ' Core]], Core" refId="%s:%d" /><trans>1 0 0 0 0 1 0 0 0 0 1 0 '
            '0 0 0 1</trans><lastAccuracy>0</lastAccuracy>'
            '<lastEvaluatedTrans>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1'
            '</lastEvaluatedTrans></ComponentDef>'
            % (200 + (hash("loose" + str(gi)) % 5000),
               200 + (hash("loose" + str(gi)) % 5000),
               DOC_GUID, 22 + gi * 60))

    layer = ('<PresentationDef sectionId="22222222-2222-2222-2222-'
             '222222222222" Id="0:5" xmlns="urn:presentation">'
             '<LayerDef Id="0:9"><name>Layer 1</name><visible>True</visible>'
             '<locked>False</locked><color>143, 175, 143</color></LayerDef>'
             '</PresentationDef>')
    views = ('<SavedViewsDef sectionId="44444444-4444-4444-4444-'
             '444444444444" Id="0:6" xmlns="urn:view"></SavedViewsDef>')
    xml = ('<?xml version="1.0" encoding="utf-8"?>'
           '<Document version="1.520" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xmlns="urn:core"><nextId>2000</nextId>'
           '<importPath>%s.scdoc</importPath>'
           '<importTimestamp>01/01/2026 00:00:00</importTimestamp>'
           '<Design sectionId="11111111-1111-1111-1111-111111111111" '
           'Id="0:1" xmlns="urn:nom">'
           '<PartDef Id="0:2"><updateState>0:1999</updateState>'
           '<patternBase /><defaultEdgeTreatment sctype='
           '"SpaceClaim.BasicMoniker`1[[SpaceClaim.IDefaultEdgeTreatment,'
           ' Nom]], Core" refId="%s:13" />'
           '<materialId>0:0</materialId><type>Normal</type>'
           '<shareTopologyOption>None</shareTopologyOption>%s</PartDef>'
           '%s</Design>%s%s'
           '<DocumentSettingsDef sectionId="33333333-3333-3333-3333-'
           '333333333333" Id="0:16" xmlns="urn:presentation">'
           '<DocumentUnitsDef Id="0:17"><units><lengthProperties>'
           '<type>MM</type><factor>1000</factor><symbol>mm</symbol>'
           '<decimalPlaces>2</decimalPlaces></lengthProperties></units>'
           '</DocumentUnitsDef></DocumentSettingsDef>'
           '<PresentationDef2 sectionId="55555555-5555-5555-5555-'
           '555555555555" Id="0:7" xmlns="urn:nom">%s'
           '</PresentationDef2></Document>'
           % (name, DOC_GUID, "".join(comp_xml), "".join(part_xml), layer,
              views, "".join(captions)))
    return xml.encode("utf-8")


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
    if any(it[0] in ("cyl", "sphere", "torus") for it in items):
        for body in kdoc.bodies:
            sols = K.explore(body.shape, "solid") or [body.shape]
            for s in sols:
                try:
                    from scdm.kernel import tessellate_faces
                    tessellations.append(tessellate_faces(
                        s, deflection=max(1e-5, 0.05 / 1000.0)))
                except Exception:
                    tessellations.append([])
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

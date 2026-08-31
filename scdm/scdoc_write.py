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
import struct
import zipfile
from typing import List, Optional, Tuple

from scdm import kernel as K

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
        """Serialize. Official SAB interns class names: the FIRST record of a
        class carries a name header and REGISTERS the class id (ids are
        file-local, allocated in first-appearance order — box and cyl have
        different tables); later records of the same class use an id-only
        header (hdrlen=5, T_ID + int32). `seen` maps class name -> id and
        doubles as the allocation counter (key None)."""
        seen = seen if seen is not None else {}

        def intern(name):
            if name in seen:
                return seen[name], True
            nid = seen.get(None, 0) + 1
            seen[None] = nid
            seen[name] = nid
            return nid, False

        out = bytearray()
        for cname, _cid in self.chain:
            cid, known = intern(cname)
            if known:
                out += bytes([T_CHAIN, 5, T_ID]) + _ri(cid)
            else:
                out += bytes([T_CHAIN, len(cname) + 5]) + cname.encode("latin-1")
                out += bytes([T_ID]) + _ri(cid)
        cid, known = intern(self.name)
        if known:
            out += bytes([T_RECORD, 5, T_ID]) + _ri(cid)
        else:
            out += bytes([T_RECORD, len(self.name) + 5]) + self.name.encode("latin-1")
            out += bytes([T_ID]) + _ri(cid)
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


def _extract_solid(solid):
    """Return (verts, edges, faces) for a planar-faced solid."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepTools import BRepTools_WireExplorer
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.TopAbs import (TopAbs_FACE, TopAbs_FORWARD, TopAbs_VERTEX,
                                 TopAbs_WIRE)
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
            raise ValueError("仅支持平面面的实体写出（遇到非平面面）")
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
        fexp.Next()
    return verts, edges, faces


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
    """Assemble the SAB stream.

    items = [('planar', verts, edges, faces) | ('cyl', info)] per body;
    colors = parallel list of per-body (r, g, b) in 0..1.

    Cylindrical bodies follow the official Circular.scdoc layout: cone surface,
    ellipse curves, closed circular edges (no seam, no pcurves).

    Returns (bytes, face_counts, edge_counts).
    """
    B = len(items)
    planar = [(bi, it) for bi, it in enumerate(items) if it[0] == "planar"]
    cyls = [(bi, it) for bi, it in enumerate(items) if it[0] == "cyl"]
    C = len(cyls)
    F_p = sum(len(it[3]) for _bi, it in planar)
    E_p = sum(len(it[2]) for _bi, it in planar)
    V_p = sum(len(it[1]) for _bi, it in planar)
    F = F_p + 3 * C
    L = F_p + 3 * C          # planar: 1 loop/face; cyl: 3 loops
    CC = 2 * E_p + 6 * C     # planar: 2 coedges/edge; cyl: 6
    E = E_p + 3 * C
    V = V_p + 2 * C
    P = F_p + 2 * C          # plane surfaces: 1/planar face + 2 caps/cyl

    idx_body = 0
    idx_attrib_body = B
    idx_lump = 2 * B
    idx_shell = 3 * B
    idx_face = 4 * B
    idx_loop = idx_face + F
    idx_coedge = idx_loop + L
    idx_edge = idx_coedge + CC
    idx_vertex = idx_edge + E
    idx_point = idx_vertex + V
    idx_plane = idx_point + V
    idx_straight = idx_plane + P
    idx_cone = idx_straight + E_p + C   # planar straights + cyl seams
    idx_ellipse = idx_cone + C
    idx_face_attrib = idx_ellipse + 2 * C
    idx_edge_attrib = idx_face_attrib + F
    idx_face_rgb = idx_edge_attrib + E
    idx_body_pname = idx_face_rgb + F   # ATTRIB_XACIS_PNAME per body

    recs: List[Optional[_Rec]] = [None] * (idx_body_pname + B)

    foff_of, eoff_of, voff_of = {}, {}, {}
    f_off = e_off = v_off = 0
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff_of[bi] = f_off; eoff_of[bi] = e_off; voff_of[bi] = v_off
        f_off += len(faces); e_off += len(edges); v_off += len(verts)
    coff_of = {}
    c_off = 0
    for bi, it in planar:
        faces = it[3]
        for fi, f in enumerate(faces):
            coff_of[foff_of[bi] + fi] = c_off
            c_off += len(f["loop"])

    def coff(foff, fi):
        return coff_of[foff + fi]

    cyl_foff = F_p          # global face index where cyl faces start
    cyl_loff = F_p          # planar loops = 1 per planar face
    cyl_coff = 2 * E_p      # planar coedges = 2 per planar edge
    cyl_eoff = E_p
    cyl_voff = V_p
    cyl_poff = F_p          # plane-surface index where cyl caps start
    cyl_soff = E_p          # straight-curve index where cyl seams start

    # bodies / attribs / lumps / shells
    for bi, it in enumerate(items):
        if it[0] == "planar":
            smin, smax = _bbox(it[1])
            foff = foff_of[bi]
        else:
            lo, hi = it[1]["bbox"]
            smin, smax = lo, hi
            foff = cyl_foff
        recs[idx_body + bi] = (
            _Rec("body", 1)
            .add(_p(idx_attrib_body + bi), _ti(10), _ti(-1), _p(-1), _ti(0),
                 _p(idx_lump + bi), _p(-1), _p(-1),
                 bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))
        recs[idx_attrib_body + bi] = _attrib(
            idx_body + bi, f"0:{23 + 60 * bi}", nxt=idx_body_pname + bi)
        recs[idx_body_pname + bi] = _attrib(
            idx_body + bi, "SC:0", prv=idx_attrib_body + bi,
            type_id=14675622, name_tag="ATTRIB_XACIS_PNAME%8")
        recs[idx_lump + bi] = (
            _Rec("lump", 7)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                 _p(idx_shell + bi), _p(idx_body + bi),
                 bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))
        recs[idx_shell + bi] = (
            _Rec("shell", 9)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1), _p(-1),
                 _p(idx_face + foff), _p(-1), _p(idx_lump + bi),
                 bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))

    # faces
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff = foff_of[bi]
        for fi, f in enumerate(faces):
            g = idx_face + foff + fi
            fmin, fmax = _bbox(verts, f["loop"])
            f1 = T_FLAG_A if fi == len(faces) - 1 else T_FLAG_B
            recs[g] = (
                _Rec("face", 10)
                .add(_p(idx_face_attrib + foff + fi), _ti(4 + fi), _ti(-1), _p(-1),
                     _p(idx_face + foff + fi + 1 if fi + 1 < len(faces) else -1),
                     _p(idx_loop + foff + fi), _p(idx_shell + bi), _p(-1),
                     _p(idx_plane + foff + fi),
                     bytes([f1, T_FLAG_B, T_FLAG_A]), _v3(*fmin), _v3(*fmax),
                     bytes([T_FLAG_A]), _td(0.0), _td(0.01), _td(0.0), _td(0.01)))

    # loops (official box style: most loops end at int15, no trailing surface)
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff = foff_of[bi]
        for fi, f in enumerate(faces):
            g = idx_loop + foff + fi
            lmin, lmax = _bbox(verts, f["loop"])
            recs[g] = (
                _Rec("loop", 11)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                     _p(idx_coedge + coff(foff, fi)),
                     _p(idx_face + foff + fi),
                     bytes([T_FLAG_A]), _v3(*lmin), _v3(*lmax),
                     bytes([T_INT15]) + _ri(0)))

    # coedges
    edge_coedges = {}
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff, eoff = foff_of[bi], eoff_of[bi]
        for fi, f in enumerate(faces):
            loop = f["loop"]
            n = len(loop)
            for k in range(n):
                a, b = loop[k], loop[(k + 1) % n]
                eidx = eoff + _edge_of(edges, a, b)
                sense = T_FLAG_B if edges[eidx - eoff][0] == a else T_FLAG_A
                g = idx_coedge + coff(foff, fi) + k
                edge_coedges.setdefault(eidx, []).append(g)
                recs[g] = (
                    _Rec("coedge", 16)
                    .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                         _p(idx_coedge + coff(foff, fi) + (k + 1) % n),
                         _p(idx_coedge + coff(foff, fi) + (k - 1) % n),
                         _p(-1), _p(idx_edge + eidx), bytes([sense]),
                         _p(idx_loop + foff + fi), _p(-1)))
    for eidx, coeds in edge_coedges.items():
        if len(coeds) == 2:
            recs[coeds[0]].tokens = _fix_partner(recs[coeds[0]].tokens, coeds[1])
            recs[coeds[1]].tokens = _fix_partner(recs[coeds[1]].tokens, coeds[0])

    # edges + straights
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff, eoff, voff = foff_of[bi], eoff_of[bi], voff_of[bi]
        for ei, (v1, v2) in enumerate(edges):
            p1, p2 = verts[v1], verts[v2]
            length = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2) ** 0.5
            emin, emax = _bbox(verts, [v1, v2])
            coeds = edge_coedges.get(eoff + ei, [])
            first_co = coeds[0] if coeds else -1
            recs[idx_edge + eoff + ei] = (
                _Rec("edge", 17)
                .add(_p(idx_edge_attrib + eoff + ei), _ti(11 + eoff + ei), _ti(-1), _p(-1),
                     _p(idx_vertex + voff + v1), _td(0.0),
                     _p(idx_vertex + voff + v2), _td(length),
                     _p(first_co), _p(idx_straight + eoff + ei),
                     bytes([T_FLAG_B]), _s("unknown"),
                     bytes([T_FLAG_A]), _v3(*emin), _v3(*emax)))
            dx = (p2[0] - p1[0]) / length if length else 0.0
            dy = (p2[1] - p1[1]) / length if length else 0.0
            dz = (p2[2] - p1[2]) / length if length else 0.0
            recs[idx_straight + eoff + ei] = (
                _Rec("curve", 20, chain=[("straight", 19)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*p1), _v3b(dx, dy, dz),
                     bytes([T_FLAG_A]), _td(0.0), bytes([T_FLAG_A]), _td(length)))

    # vertices + points
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff, eoff, voff = foff_of[bi], eoff_of[bi], voff_of[bi]
        for vi in range(len(verts)):
            inc = -1
            for ei, (a, b) in enumerate(edges):
                if a == vi or b == vi:
                    inc = idx_edge + eoff + ei
                    break
            recs[idx_vertex + voff + vi] = (
                _Rec("vertex", 18)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(inc), _p(idx_point + voff + vi)))
        for pi, (x, y, z) in enumerate(verts):
            recs[idx_point + voff + pi] = (
                _Rec("point", 21).add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(x, y, z)))

    # planes
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff = foff_of[bi]
        for fi, f in enumerate(faces):
            recs[idx_plane + foff + fi] = (
                _Rec("surface", 13, chain=[("plane", 12)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*f["center"]),
                     _v3b(*f["normal"]), _v3b(*_ortho(f["normal"])),
                     bytes([T_FLAG_B] * 5)))

    # face / edge attribs + per-face rgb_color (chained: name -> rgb)
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        foff = foff_of[bi]
        col = colors[bi] if colors and bi < len(colors) else (0.745, 0.902, 0.961)
        for fi in range(len(faces)):
            recs[idx_face_attrib + foff + fi] = _attrib(
                idx_face + foff + fi, f"0:{27 + 3 * fi + 60 * bi}",
                nxt=idx_face_rgb + foff + fi)
            recs[idx_face_rgb + foff + fi] = _rgb_attrib(
                idx_face + foff + fi, idx_face_attrib + foff + fi, col)
    for bi, it in planar:
        verts, edges, faces = it[1], it[2], it[3]
        eoff = eoff_of[bi]
        for ei in range(len(edges)):
            recs[idx_edge_attrib + eoff + ei] = _attrib(
                idx_edge + eoff + ei, f"0:{45 + 3 * ei + 60 * bi}")

    # cylindrical bodies (layout from the official SpaceClaim-written cylinder
    # reference, ACIS 29: seam edge on the side face, 0..2pi circular edges,
    # vertices at param 0 (+major), surface/curve ids 15/14/16/21/20/22)
    for gi, (bi, it) in enumerate(cyls):
        info = it[1]
        R, h = info["R"], info["h"]
        org, axis = info["origin"], info["axis"]
        mu = info["major_unit"]
        major = (mu[0] * R, mu[1] * R, mu[2] * R)
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        lo, hi = info["bbox"]
        col = colors[bi] if colors and bi < len(colors) else (0.745, 0.902, 0.961)
        foff = cyl_foff + 3 * gi
        loff = cyl_loff + 3 * gi
        coffb = cyl_coff + 6 * gi
        eoff = cyl_eoff + 3 * gi
        voff = cyl_voff + 2 * gi
        poff = cyl_poff + 2 * gi
        cone_i = idx_cone + gi
        ell_b = idx_ellipse + 2 * gi

        def circ_bbox(center, _R=R, _axis=axis):
            ex = _R * math.sqrt(max(0.0, 1.0 - _axis[0] * _axis[0]))
            ey = _R * math.sqrt(max(0.0, 1.0 - _axis[1] * _axis[1]))
            ez = _R * math.sqrt(max(0.0, 1.0 - _axis[2] * _axis[2]))
            return ((center[0] - ex, center[1] - ey, center[2] - ez),
                    (center[0] + ex, center[1] + ey, center[2] + ez))

        # surfaces: top plane, bottom plane, cone (ids 15 / chain 16 / 14)
        for pi, center, nrm in ((0, cap_b, axis),
                                (1, cap_a, (-axis[0], -axis[1], -axis[2]))):
            recs[idx_plane + poff + pi] = (
                _Rec("surface", 15, chain=[("plane", 16)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*center),
                     _v3b(*nrm), _v3b(*mu), bytes([T_FLAG_B] * 5)))
        recs[cone_i] = (
            _Rec("surface", 15, chain=[("cone", 14)])
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*org),
                 _v3b(-axis[0], -axis[1], -axis[2]),
                 _v3b(mu[0] * R, mu[1] * R, mu[2] * R),
                 _td(1.0), bytes([T_FLAG_B, T_FLAG_B]),
                 _td(-0.0), _td(1.0), _td(R),
                 bytes([T_FLAG_A, T_FLAG_B, T_FLAG_B, T_FLAG_B, T_FLAG_B])))

        # vertices + points at param 0 (centre + major), one per circular edge
        major_unit_R = (mu[0] * R, mu[1] * R, mu[2] * R)
        vbot = (cap_a[0] + major_unit_R[0], cap_a[1] + major_unit_R[1],
                cap_a[2] + major_unit_R[2])
        vtop = (cap_b[0] + major_unit_R[0], cap_b[1] + major_unit_R[1],
                cap_b[2] + major_unit_R[2])
        recs[idx_vertex + voff] = (
            _Rec("vertex", 19)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                 _p(idx_edge + eoff + 2), _p(idx_point + voff)))
        recs[idx_vertex + voff + 1] = (
            _Rec("vertex", 19)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                 _p(idx_edge + eoff + 1), _p(idx_point + voff + 1)))
        recs[idx_point + voff] = (
            _Rec("point", 23).add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*vbot)))
        recs[idx_point + voff + 1] = (
            _Rec("point", 23).add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*vtop)))

        # edges: bottom circle(0..2pi), top circle(0..2pi), seam(0..h)
        bmin, bmax = circ_bbox(cap_a)
        tmin, tmax = circ_bbox(cap_b)
        recs[idx_edge + eoff] = (
            _Rec("edge", 18)
            .add(_p(idx_edge_attrib + eoff), _ti(4), _ti(-1), _p(-1),
                 _p(idx_vertex + voff), _td(0.0),
                 _p(idx_vertex + voff), _td(2.0 * math.pi),
                 _p(idx_coedge + coffb + 2), _p(ell_b + 1),
                 bytes([T_FLAG_B]), _s("unknown"),
                 bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))
        recs[idx_edge + eoff + 1] = (
            _Rec("edge", 18)
            .add(_p(idx_edge_attrib + eoff + 1), _ti(5), _ti(-1), _p(-1),
                 _p(idx_vertex + voff + 1), _td(0.0),
                 _p(idx_vertex + voff + 1), _td(2.0 * math.pi),
                 _p(idx_coedge + coffb), _p(ell_b),
                 bytes([T_FLAG_B]), _s("unknown"),
                 bytes([T_FLAG_A]), _v3(*tmin), _v3(*tmax)))
        recs[idx_edge + eoff + 2] = (
            _Rec("edge", 18)
            .add(_p(idx_edge_attrib + eoff + 2), _ti(6), _ti(-1), _p(-1),
                 _p(idx_vertex + voff), _td(0.0),
                 _p(idx_vertex + voff + 1), _td(h),
                 _p(idx_coedge + coffb + 2), _p(idx_straight + cyl_soff + gi),
                 bytes([T_FLAG_B]), _s("unknown"),
                 bytes([T_FLAG_A]),
                 _v3(min(vbot[0], vtop[0]), min(vbot[1], vtop[1]),
                     min(vbot[2], vtop[2])),
                 _v3(max(vbot[0], vtop[0]), max(vbot[1], vtop[1]),
                     max(vbot[2], vtop[2]))))
        for k, center in ((0, cap_b), (1, cap_a)):
            recs[ell_b + k] = (
                _Rec("curve", 21, chain=[("ellipse", 20)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*center),
                     _v3b(*axis), _v3b(mu[0] * R, mu[1] * R, mu[2] * R),
                     _td(1.0), bytes([T_FLAG_B, T_FLAG_B])))
        recs[idx_straight + cyl_soff + gi] = (
            _Rec("curve", 21, chain=[("straight", 22)])
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*vbot),
                 _v3b(0.0, 0.0, 0.001),
                 bytes([T_FLAG_A]), _td(0.0), bytes([T_FLAG_A]), _td(h)))

        # loops: side / top / bottom - int15 0, no trailing surface pointer
        recs[idx_loop + loff] = (
            _Rec("loop", 13)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                 _p(idx_coedge + coffb), _p(idx_face + foff),
                 bytes([T_FLAG_A]), _v3(*lo), _v3(*hi),
                 bytes([T_INT15]) + _ri(0)))
        recs[idx_loop + loff + 1] = (
            _Rec("loop", 13)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                 _p(idx_coedge + coffb), _p(idx_face + foff + 1),
                 bytes([T_FLAG_A]), _v3(*tmin), _v3(*tmax),
                 bytes([T_INT15]) + _ri(0)))
        recs[idx_loop + loff + 2] = (
            _Rec("loop", 13)
            .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                 _p(idx_coedge + coffb + 3), _p(idx_face + foff + 2),
                 bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax),
                 bytes([T_INT15]) + _ri(0)))

        # coedges: side loop (top FA, seam FA, bottom FB, seam FB), top cap (FB),
        # bottom cap (FA); [next, prev, partner, edge, sense, loop, -1]
        partner_of = (3, 2, 1, 0, 0, 0)
        co_specs = (
            (1, 3, 1, T_FLAG_A),   # side: top circle
            (2, 0, 2, T_FLAG_A),   # side: seam top->bottom
            (3, 1, 0, T_FLAG_B),   # side: bottom circle
            (0, 2, 2, T_FLAG_B),   # side: seam bottom->top
            (4, 4, 1, T_FLAG_B),   # top cap loop, top circle
            (5, 5, 0, T_FLAG_A),   # bottom cap loop, bottom circle
        )
        for ci, (next_i, prev_i, edge_i, sense) in enumerate(co_specs):
            g = idx_coedge + coffb + ci
            loop_ptr = idx_loop + loff + (0 if ci < 4 else (1 if ci == 4 else 2))
            recs[g] = (
                _Rec("coedge", 17)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                     _p(idx_coedge + coffb + next_i),
                     _p(idx_coedge + coffb + prev_i),
                     _p(idx_coedge + coffb + partner_of[ci]),
                     _p(idx_edge + eoff + edge_i), bytes([sense]),
                     _p(loop_ptr), _p(-1)))

        # faces: side cone(1) / top plane(2) / bottom plane(3)
        uv_side = (0.0, h / R, -math.pi, math.pi)
        uv_cap = (-R, R, -R, R)
        face_data = (
            (0, 1, 2, T_FLAG_B, T_FLAG_B, T_FLAG_A, uv_side, None, cone_i),
            (1, 2, 5, T_FLAG_A, T_FLAG_B, T_FLAG_A, uv_cap, cap_b,
             idx_plane + poff),
            (2, -1, 3, T_FLAG_B, T_FLAG_B, T_FLAG_A, uv_cap, cap_a,
             idx_plane + poff + 1),
        )
        for fi, next_fi, co_i, f1, f2, f3, uv, center, surf_i in face_data:
            if center is None:
                fmin, fmax = lo, hi
            else:
                fmin, fmax = circ_bbox(center)
            recs[idx_face + foff + fi] = (
                _Rec("face", 12)
                .add(_p(idx_face_attrib + foff + fi), _ti(fi + 1), _ti(-1),
                     _p(-1),
                     _p(idx_face + foff + next_fi if next_fi >= 0 else -1),
                     _p(idx_loop + loff + fi),
                     _p(idx_shell + bi), _p(-1), _p(surf_i),
                     bytes([f1, f2, f3]), _v3(*fmin), _v3(*fmax),
                     bytes([T_FLAG_A]), _td(uv[0]), _td(uv[1]), _td(uv[2]),
                     _td(uv[3])))

        # attribs + rgb (face chain: side -> top -> bottom)
        for fi in range(3):
            recs[idx_face_attrib + foff + fi] = _attrib(
                idx_face + foff + fi, f"0:{27 + 3 * fi + 60 * bi}",
                nxt=idx_face_rgb + foff + fi)
            recs[idx_face_rgb + foff + fi] = _rgb_attrib(
                idx_face + foff + fi, idx_face_attrib + foff + fi, col)
        for ei in range(3):
            recs[idx_edge_attrib + eoff + ei] = _attrib(
                idx_edge + eoff + ei, f"0:{45 + 3 * ei + 60 * bi}")

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
    seen_classes = {}
    for rec in recs:
        if rec is None:
            raise ValueError("internal: uninitialised record")
        out += rec.bytes(seen_classes)
    out += bytes([T_RECORD, len(END_NAME)]) + END_NAME.encode("latin-1")
    face_counts = [len(it[3]) if it[0] == "planar" else 3 for it in items]
    edge_counts = [len(it[2]) if it[0] == "planar" else 2 for it in items]
    return bytes(out), face_counts, edge_counts


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
                    mid = mesh_edge_base + planar_eoff[bi] + edges[k][0]
                    edge_rows.append((mid, 45 + 3 * edges[k][0] + 60 * bi))
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


def write_scdoc(path: str, kdoc, name: str = "design") -> None:
    """Write a native .scdoc for planar solids and plain cylinders."""
    items = []
    colors = []
    for body in kdoc.bodies:
        sols = K.explore(body.shape, "solid") or [body.shape]
        for s in sols:
            info = _cyl_info(s)
            if info is not None:
                items.append(("cyl", info))
            else:
                items.append(("planar",) + _extract_solid(s))
            colors.append(tuple(getattr(body, "color", None) or (0.745, 0.902, 0.961)))
    if not items:
        raise ValueError("没有可写出的实体")
    sab_bytes, face_counts, edge_counts = _build_sab(items, colors)

    # graphics facets part — only for bodies whose faces the topology layer
    # cannot rebuild (cylinders); planar-only files keep the validated layout
    facets_bytes = None
    if any(it[0] == "cyl" for it in items):
        tessellations = []
        for body in kdoc.bodies:
            sols = K.explore(body.shape, "solid") or [body.shape]
            for s in sols:
                try:
                    from scdm.kernel import tessellate_faces
                    tessellations.append(tessellate_faces(
                        s, deflection=max(1e-5, 0.05 / 1000.0)))
                except Exception:
                    tessellations.append([])
        facets_bytes = _facets_bytes(items, tessellations)

    sab_name = "part1bodies.sab"
    stem = name or "design"
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

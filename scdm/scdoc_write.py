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

    def bytes(self) -> bytes:
        out = bytearray()
        for name, cid in self.chain:
            hdrlen = len(name) + (5 if cid is not None else 0)
            out += bytes([T_CHAIN, hdrlen]) + name.encode("latin-1")
            if cid is not None:
                out += bytes([T_ID]) + _ri(cid)
        hdrlen = len(self.name) + (5 if self.class_id is not None else 0)
        out += bytes([T_RECORD, hdrlen]) + self.name.encode("latin-1")
        if self.class_id is not None:
            out += bytes([T_ID]) + _ri(self.class_id)
        out += self.tokens
        out += bytes([T_TERM])
        return bytes(out)


def _round(v, nd=9):
    return round(float(v), nd)


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


def _attrib(owner, value):
    return (_Rec("attrib", 5, chain=[("string_attrib", 2), ("name_attrib", 3), ("gen", 4)])
            .add(_p(-1), _ti(-1), _p(-1), _p(-1), _p(owner),
                 _ti(14675622), _s("ATTRIB_XACIS_NAME%6"), _s(value)))


def _build_sab(bodies):
    """Assemble the SAB stream. bodies = list of (verts, edges, faces) tuples.

    Returns (bytes, face_counts, edge_counts).
    """
    B = len(bodies)
    F = sum(len(f) for _v, _e, f in bodies)
    E = sum(len(e) for _v, e, _f in bodies)
    V = sum(len(v) for v, _e, _f in bodies)
    C = 2 * E
    P = V

    idx_body = 0
    idx_attrib_body = B
    idx_lump = 2 * B
    idx_shell = 3 * B
    idx_face = 4 * B
    idx_loop = idx_face + F
    idx_coedge = idx_loop + F
    idx_edge = idx_coedge + C
    idx_vertex = idx_edge + E
    idx_point = idx_vertex + V
    idx_plane = idx_point + P
    idx_straight = idx_plane + F
    idx_face_attrib = idx_straight + E
    idx_edge_attrib = idx_face_attrib + F

    recs: List[Optional[_Rec]] = [None] * (idx_edge_attrib + E)

    foff_of, eoff_of, voff_of = [], [], []
    coff_of = []
    f_off = e_off = v_off = c_off = 0
    for (verts, edges, faces) in bodies:
        foff_of.append(f_off); eoff_of.append(e_off); voff_of.append(v_off)
        for f in faces:
            coff_of.append(c_off)
            c_off += len(f["loop"])
        f_off += len(faces); e_off += len(edges); v_off += len(verts)

    def coff(foff, fi):
        return coff_of[foff + fi]

    # bodies / attribs / lumps / shells
    for bi, (verts, edges, faces) in enumerate(bodies):
        smin, smax = _bbox(verts)
        foff = foff_of[bi]
        recs[idx_body + bi] = (
            _Rec("body", 1)
            .add(_p(idx_attrib_body + bi), _ti(10), _ti(-1), _p(-1), _ti(0),
                 _p(idx_lump + bi), _p(-1), _p(-1),
                 bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))
        recs[idx_attrib_body + bi] = _attrib(idx_body + bi, f"0:{23 + 60 * bi}")
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
    for bi, (verts, edges, faces) in enumerate(bodies):
        foff, eoff, voff = foff_of[bi], eoff_of[bi], voff_of[bi]
        for fi, f in enumerate(faces):
            g = idx_face + foff + fi
            fmin, fmax = _bbox(verts, f["loop"])
            recs[g] = (
                _Rec("face", 10)
                .add(_p(idx_face_attrib + foff + fi), _ti(4), _ti(-1), _p(-1),
                     _p(idx_face + foff + fi + 1 if fi + 1 < len(faces) else -1),
                     _p(idx_loop + foff + fi), _p(idx_shell + bi), _p(-1),
                     _p(idx_plane + foff + fi),
                     bytes([T_FLAG_B, T_FLAG_B, T_FLAG_A]), _v3(*fmin), _v3(*fmax),
                     bytes([T_FLAG_A]), _td(0.0), _td(0.01), _td(0.0), _td(0.01)))

    # loops
    for bi, (verts, edges, faces) in enumerate(bodies):
        foff = foff_of[bi]
        for fi, f in enumerate(faces):
            g = idx_loop + foff + fi
            lmin, lmax = _bbox(verts, f["loop"])
            recs[g] = (
                _Rec("loop", 11)
                .add(_p(-1), _ti(37), _ti(-1), _p(-1), _p(-1),
                     _p(idx_coedge + coff(foff, fi)),
                     _p(idx_face + foff + fi),
                     bytes([T_FLAG_A]), _v3(*lmin), _v3(*lmax),
                     bytes([T_INT15]) + _ri(0),
                     _p(idx_plane + foff + fi), bytes([T_FLAG_B])))

    # coedges
    edge_coedges = {}
    for bi, (verts, edges, faces) in enumerate(bodies):
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
    for bi, (verts, edges, faces) in enumerate(bodies):
        foff, eoff, voff = foff_of[bi], eoff_of[bi], voff_of[bi]
        for ei, (v1, v2) in enumerate(edges):
            p1, p2 = verts[v1], verts[v2]
            length = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2) ** 0.5
            emin, emax = _bbox(verts, [v1, v2])
            coeds = edge_coedges.get(eoff + ei, [])
            first_co = coeds[0] if coeds else -1
            recs[idx_edge + eoff + ei] = (
                _Rec("edge", 17)
                .add(_p(idx_edge_attrib + eoff + ei), _ti(0), _ti(-1), _p(-1),
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
    for bi, (verts, edges, faces) in enumerate(bodies):
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
    for bi, (verts, edges, faces) in enumerate(bodies):
        foff = foff_of[bi]
        for fi, f in enumerate(faces):
            recs[idx_plane + foff + fi] = (
                _Rec("surface", 13, chain=[("plane", 12)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*f["center"]),
                     _v3b(*f["normal"]), _v3b(*_ortho(f["normal"])),
                     bytes([T_FLAG_B] * 5)))

    # face / edge attribs
    for bi, (verts, edges, faces) in enumerate(bodies):
        foff = foff_of[bi]
        for fi in range(len(faces)):
            recs[idx_face_attrib + foff + fi] = _attrib(
                idx_face + foff + fi, f"0:{27 + 3 * fi + 60 * bi}")
    for bi, (verts, edges, faces) in enumerate(bodies):
        eoff = eoff_of[bi]
        for ei in range(len(edges)):
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
    out += _s("0:1")
    for rec in recs:
        if rec is None:
            raise ValueError("internal: uninitialised record")
        out += rec.bytes()
    out += bytes([T_RECORD, len(END_NAME)]) + END_NAME.encode("latin-1")
    face_counts = [len(f) for _v, _e, f in bodies]
    edge_counts = [len(e) for _v, e, _f in bodies]
    return bytes(out), face_counts, edge_counts


def _document_xml(name: str, face_counts: List[int], edge_counts: List[int]) -> bytes:
    parts = []
    captions = []
    for i in range(len(face_counts)):
        bid = 23 + 60 * i
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
                     f'        <color>143, 166, 175</color>\n'
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
            b'</Types>')


def _root_rels() -> bytes:
    return (b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            b'  <Relationship Type="http://www.spaceclaim.com/relationships/internal/mainDocument"\n'
            b'                Target="/SpaceClaim/document.xml" Id="Rm1"/>\n'
            b'</Relationships>')


def _doc_rels(sab_name: str) -> bytes:
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Type="http://www.spaceclaim.com/relationships/internal/partBodyGeometry#fc598e53-8ab6-41b2-b8ea-b7917346ae70:2"\n'
            f'                Target="/SpaceClaim/Geometry/{sab_name}" Id="Rg1"/>\n'
            f'</Relationships>').encode("utf-8")


def write_scdoc(path: str, kdoc, name: str = "design") -> None:
    """Write a native .scdoc for the session's planar-solid bodies."""
    solids = []
    for body in kdoc.bodies:
        shape = body.shape
        sols = K.explore(shape, "solid")
        if not sols:
            sols = [shape]
        solids.extend(sols)
    if not solids:
        raise ValueError("没有可写出的实体")
    bodies = [_extract_solid(s) for s in solids]
    sab_bytes, face_counts, edge_counts = _build_sab(bodies)

    sab_name = "part1bodies.sab"
    stem = name or "design"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _content_types())
        z.writestr("_rels/.rels", _root_rels())
        z.writestr("SpaceClaim/document.xml", _document_xml(stem, face_counts, edge_counts))
        z.writestr("SpaceClaim/_rels/document.xml.rels", _doc_rels(sab_name))
        z.writestr(f"SpaceClaim/Geometry/{sab_name}", sab_bytes)

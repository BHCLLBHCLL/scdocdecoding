# -*- coding: utf-8 -*-
"""SpaceClaim facets.bin triangle-mesh parser (reverse-engineered).

facets.bin is the display-mesh counterpart of the B-rep .sab stream.  Its
structure was reverse-engineered from box.scdoc and the official
assembly_sample.scdoc (multi-body layout), and cross-validated against the
SAB geometry (every facet edge matched its B-rep edge geometrically):

Layout (all little-endian; "word" = uint32)
-------------------------------------------
Header:
  w0..w1   magic  b"facets  "
  w2       format version (14)
  w3       body count
  w4..w5   1, 0

Per body section:
  [body_doc_id, 0, body_update_state, 5, face_count, 0]
  face nodes, face_count times (each followed by a 0 separator except the
  body's last):
      [face_doc_id, 0, node_id, corner_count]     (4 words; legacy streams
      used [0, node_id, 0, node_id, corner_count] instead)
      corner_count x corner records (8 words each, float32):
          [px, py, pz, nx, ny, nz, u, v]         (metres, like the SAB)
      [n, ceil(n/2) words]   triangle vertex indices, 2 packed per word
                             (low uint16 first); n = 3 x triangle count,
                             winding CCW around the face normal
      [m, ceil(m/2) words]   boundary loop as corner-index pairs
                             (m = 2 x edge count, includes the wraparound)
      [k, k x 3 words]       edge mapping entries:
                             (mesh_edge_id, boundary_pos, flag)
                             boundary_pos indexes the flat boundary-pair
                             array (== 2 x corner index for quads);
                             flag observed as 1.
  edge table: [count, count x 3 words]  (mesh_edge_id, 0, doc_id_number)
  mapping each mesh edge to the design-tree edge id, e.g. (12, 0, 45) ->
  '0:45'.  A [1, 0] word pair follows every body but the last.

Verification on box.scdoc: 6 quad faces, 24 corners on exact B-rep
positions, 12 CCW triangles, 12 mesh edges each appearing in exactly 2
faces, and the edge table agrees with geometric matching to the SAB.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MAGIC = b'facets  '


class FacetsError(Exception):
    """Raised when the facets stream cannot be parsed."""


@dataclass
class Corner:
    position: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    uv: Tuple[float, float]


@dataclass
class EdgeRef:
    edge_id: int        # mesh-wide edge id (12..23 in box.scdoc)
    boundary_pos: int   # index into the flat boundary pair array
    flag: int           # observed 1; exact semantics undetermined

    @property
    def corner_index(self) -> int:
        """Boundary pair index -> corner index (pairs are consecutive)."""
        return self.boundary_pos // 2


@dataclass
class FaceNode:
    node_id: int
    face_doc_id: int = 0
    corners: List[Corner] = field(default_factory=list)
    triangles: List[Tuple[int, int, int]] = field(default_factory=list)
    boundary: List[Tuple[int, int]] = field(default_factory=list)
    edge_refs: List[EdgeRef] = field(default_factory=list)

    def edge_segment(self, ref: EdgeRef):
        """3D segment of the boundary edge referenced by 'ref'.

        boundary_pos indexes the FLAT corner-index array (two values per
        boundary pair), so the pair index is boundary_pos // 2."""
        i = ref.boundary_pos // 2
        if 0 <= i < len(self.boundary):
            a, b = self.boundary[i]
            if a < len(self.corners) and b < len(self.corners):
                return self.corners[a].position, self.corners[b].position
        return None


@dataclass
class FacetsFile:
    version: int = 0
    header_words: List[int] = field(default_factory=list)   # [n_bodies, 1, 0]
    bodies: List[dict] = field(default_factory=list)        # per-body sections
    faces: List[FaceNode] = field(default_factory=list)
    edge_map: Dict[int, str] = field(default_factory=dict)  # edge_id -> doc id
    node_face_map: Dict[int, int] = field(default_factory=dict)  # node_id -> face idx

    @property
    def body_doc_id(self) -> Optional[str]:
        """Doc id of the first owning body, e.g. '0:23'."""
        if self.bodies:
            return self.bodies[0].get("body_doc_id")
        return None

    def doc_id_of_edge(self, edge_id: int) -> Optional[str]:
        return self.edge_map.get(edge_id)


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def words_left(self) -> int:
        return (len(self.data) - self.pos) // 4

    def u32(self) -> int:
        if self.pos + 4 > len(self.data):
            raise FacetsError('truncated at byte %d' % self.pos)
        v = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return v

    def f32(self) -> float:
        if self.pos + 4 > len(self.data):
            raise FacetsError('truncated at byte %d' % self.pos)
        v = struct.unpack_from('<f', self.data, self.pos)[0]
        self.pos += 4
        return v

    def peek_words(self, n: int) -> List[int]:
        end = min(self.pos + 4 * n, len(self.data))
        cnt = max(0, (end - self.pos) // 4)
        if cnt == 0:
            return []
        return list(struct.unpack_from('<%dI' % cnt, self.data, self.pos))


def _packed_indices(reader: _Reader) -> List[int]:
    """[count, ceil(count/2) words] with two uint16 values per word (low first)."""
    count = reader.u32()
    nwords = (count + 1) // 2
    out: List[int] = []
    for _ in range(nwords):
        w = reader.u32()
        out.append(w & 0xFFFF)
        out.append((w >> 16) & 0xFFFF)
    return out[:count]


def _face_node(reader: _Reader) -> FaceNode:
    """Official 4-word header [face_doc_id, 0, node_id, corner_count];
    legacy 5-word streams start with a 0 word instead."""
    w0 = reader.u32()
    w1 = reader.u32()
    w2 = reader.u32()
    # P13: the second word is a PER-FILE constant (observed 0 / 1 / 4 / 7 /
    # 161 across the official library), not a fixed 0 - requiring 0 here is
    # what made 5 of the 6 official SrModels unreadable.
    if w0 == 0:
        face_doc_id = node_id = w1        # legacy [0, node_id, 0, corners]
    else:
        face_doc_id, node_id = w0, w2     # official [fid, X, node_id, corners]
    corner_count = reader.u32()
    if not (3 <= corner_count <= 1000000):
        raise FacetsError('implausible corner count %d' % corner_count)
    face = FaceNode(node_id=node_id, face_doc_id=face_doc_id)
    for _ in range(corner_count):
        p = (reader.f32(), reader.f32(), reader.f32())
        n = (reader.f32(), reader.f32(), reader.f32())
        uv = (reader.f32(), reader.f32())
        face.corners.append(Corner(position=p, normal=n, uv=uv))
    tri = _packed_indices(reader)
    face.triangles = [tuple(tri[i:i + 3]) for i in range(0, len(tri) - 2, 3)]
    bnd = _packed_indices(reader)
    face.boundary = [tuple(bnd[i:i + 2]) for i in range(0, len(bnd) - 1, 2)]
    n_refs = reader.u32()
    for _ in range(n_refs):
        face.edge_refs.append(EdgeRef(
            edge_id=reader.u32(),
            boundary_pos=reader.u32(),
            flag=reader.u32(),
        ))
    return face


def _edge_table(reader: _Reader, out: FacetsFile) -> None:
    """[count, count x (edge_id, X, doc_id_number)].

    X is the same per-file constant as in the body/face headers (P13): the
    official library uses 1 / 4 / 7 / 161 there, so it must not be required
    to be 0.
    """
    if reader.words_left() < 1:
        return
    count = reader.u32()
    if count > reader.words_left() // 3:
        raise FacetsError('edge table count %d exceeds the stream' % count)
    for _ in range(count):
        edge_id = reader.u32()
        reader.u32()                     # per-file constant (was required 0)
        doc_num = reader.u32()
        out.edge_map[edge_id] = '0:%d' % doc_num


def _parse_official_bodies(reader: _Reader, out: FacetsFile,
                           n_bodies: int) -> None:
    """Per-body sections: [bid, X, upd, Y, n_faces, Z] then face nodes.

    X/Y/Z vary across official files (0/5/0 in ours, 7/7/0 or 161/5/2 in the
    library), so only the face count is treated as structural (P13).
    """
    for bi in range(n_bodies):
        bid = reader.u32()
        reader.u32()                     # per-file constant X
        upd = reader.u32()
        reader.u32()                     # section kind (5 or 7 observed)
        n_faces = reader.u32()
        reader.u32()                     # trailer (0 / 1 / 2 observed)
        # 1 is legitimate: our curved-face writer packs a whole sphere/torus
        # tessellation into ONE face node.
        if not (1 <= n_faces <= 10000000):
            raise FacetsError('implausible body face count %d' % n_faces)
        body = {"body_doc_id": '0:%d' % bid, "update_state": upd, "faces": []}
        out.bodies.append(body)
        for fi in range(n_faces):
            node = _face_node(reader)
            out.faces.append(node)
            out.node_face_map[node.node_id] = len(out.faces) - 1
            body["faces"].append(len(out.faces) - 1)
            if fi < n_faces - 1:
                # P13: the inter-face separator carries the same per-file
                # constant (0 in our writer, 1 / 161 in official files) - it
                # is consumed but not validated.
                reader.u32()
        _edge_table(reader, out)
        if bi < n_bodies - 1:
            t1 = reader.u32()
            reader.u32()                 # observed 0 / 1 / 2, not always 0
            if t1 != 1:
                raise FacetsError('body terminator %d != 1' % t1)


def parse_facets(data: bytes) -> FacetsFile:
    if data[:8] != MAGIC:
        raise FacetsError('not a facets stream (bad magic)')
    reader = _Reader(data)
    reader.pos = 8
    out = FacetsFile()
    out.version = reader.u32()
    n_bodies = reader.u32()
    out.header_words = [n_bodies, reader.u32(), reader.u32()]
    # legacy single-body streams: [body_id, 0, 0, 0, mesh_base, 0] then faces;
    # official streams: per-body sections [body_id, X, upd, Y, n_faces, Z]
    # with Y in (5, 7) and X/Z per-file constants (P13).
    peek = reader.peek_words(6)
    parsed = False
    official_error = None
    if n_bodies and len(peek) >= 6 and peek[3] in (5, 7) \
            and 1 <= peek[4] <= 10000000:
        start = reader.pos
        try:
            _parse_official_bodies(reader, out, n_bodies)
            parsed = True
        except FacetsError as exc:
            official_error = exc
            reader.pos = start        # not the official grammar: use legacy
            out.bodies.clear()
            out.faces.clear()
            out.edge_map.clear()
            out.node_face_map.clear()
    if not parsed:
        # legacy layout: body id + 4 opaque words, face nodes, edge table
        body_id = reader.u32()
        for _ in range(4):
            reader.u32()
        out.bodies.append({"body_doc_id": '0:%d' % body_id,
                           "update_state": body_id, "faces": []})
        while reader.words_left() >= 5:
            pk = reader.peek_words(5)
            is_face = (len(pk) >= 5 and pk[0] == 0 and pk[1] == pk[3]
                       and pk[2] == 0 and 3 <= pk[4] <= 1000000)
            if not is_face:
                break
            try:
                out.faces.append(_face_node(reader))
            except FacetsError as exc:
                # P13 diagnostics: say which grammar failed and how, instead of
                # surfacing an unrelated truncation deep inside a face node.
                raise FacetsError(
                    'facets parse failed (official: %s; legacy: %s at byte %d)'
                    % (official_error, exc, reader.pos)) from exc
            out.node_face_map[out.faces[-1].node_id] = len(out.faces) - 1
            out.bodies[0]["faces"].append(len(out.faces) - 1)
        _edge_table(reader, out)
    return out


# -- mesh-level summary ------------------------------------------------------
def facets_summary(fac: FacetsFile, scale: float = 1000.0) -> Dict:
    """JSON-ready summary with validation checks (box.scdoc expectations)."""
    n_corners = sum(len(f.corners) for f in fac.faces)
    n_tris = sum(len(f.triangles) for f in fac.faces)
    edge_faces: Dict[int, List[int]] = {}
    for fi, f in enumerate(fac.faces):
        for r in f.edge_refs:
            edge_faces.setdefault(r.edge_id, []).append(fi)

    checks: List[Dict] = []

    def check(name, ok, detail):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})

    check('face_count', len(fac.faces) == 6,
          'faces=%d (expect 6)' % len(fac.faces))
    check('corner_count', n_corners == 24,
          'corners=%d (expect 24)' % n_corners)
    check('triangle_count', n_tris == 12,
          'triangles=%d (expect 12)' % n_tris)
    check('edge_count', len(fac.edge_map) == 12,
          'edges=%d (expect 12)' % len(fac.edge_map))
    check('edge_shared_by_two_faces',
          edge_faces and all(len(v) == 2 for v in edge_faces.values()),
          '%d edges, use counts=%s' % (len(edge_faces),
                                       sorted({len(v) for v in edge_faces.values()})))
    check('edge_table_covers_refs',
          set(edge_faces) == set(fac.edge_map),
          '%d refs missing from edge table'
          % len(set(edge_faces) - set(fac.edge_map)))

    faces = []
    for fi, f in enumerate(fac.faces):
        faces.append({
            'node_id': f.node_id,
            'face_doc_id': '0:%d' % f.face_doc_id,
            'corners': [{
                'position_m': list(c.position),
                'normal': list(c.normal),
                'uv': list(c.uv),
            } for c in f.corners],
            'triangles': [list(t) for t in f.triangles],
            'boundary': [list(b) for b in f.boundary],
            'edges': [{
                'edge_id': r.edge_id,
                'corner': r.corner_index,
                'doc_id': fac.doc_id_of_edge(r.edge_id),
                'flag': r.flag,
            } for r in f.edge_refs],
        })

    edges = []
    for eid in sorted(fac.edge_map):
        fis = edge_faces.get(eid, [])
        segs = []
        for fi in fis:
            f = fac.faces[fi]
            for r in f.edge_refs:
                if r.edge_id == eid:
                    seg = f.edge_segment(r)
                    if seg is None:
                        continue
                    segs.append({'face_index': fi,
                                 'segment_m': [list(seg[0]), list(seg[1])]})
        edges.append({'edge_id': eid, 'doc_id': fac.edge_map[eid],
                      'used_by_faces': fis, 'segments': segs})

    return {
        'version': fac.version,
        'body_doc_id': fac.body_doc_id,
        'bodies': [{'body_doc_id': b.get('body_doc_id'),
                    'update_state': b.get('update_state'),
                    'face_indices': b.get('faces', [])}
                   for b in fac.bodies],
        'header_words': fac.header_words,
        'counts': {
            'faces': len(fac.faces),
            'corners': n_corners,
            'triangles': n_tris,
            'edges': len(fac.edge_map),
        },
        'faces': faces,
        'edges': edges,
        'checks': checks,
    }

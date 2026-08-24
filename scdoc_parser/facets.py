"""SpaceClaim facets.bin triangle-mesh parser (reverse-engineered).

facets.bin is the display-mesh counterpart of the B-rep .sab stream.  Its
structure was reverse-engineered from box.scdoc and cross-validated against
the SAB geometry (every facet edge matched its B-rep edge geometrically):

Layout (all little-endian; "word" = uint32)
-------------------------------------------
Header (11 words):
  w0..w1   magic  b"facets  "
  w2       format version (14 in box.scdoc)
  w3..w10  opaque fields; w6 held the owning body's doc-id number (23 ->
           body '0:23') and w10 the face-node count (6) in box.scdoc.

Face nodes, repeated face-count times:
  [0, node_id, 0, node_id, corner_count]     (5 words; node ids 27, 30, ...)
  corner_count x corner records (8 words each, float32):
      [px, py, pz, nx, ny, nz, u, v]         (metres, like the SAB)
  Meta block:
      [n, ceil(n/2) words]   triangle vertex indices, 2 packed per word
                             (low uint16 first); n = 3 x triangle count,
                             winding CCW around the face normal
      [m, ceil(m/2) words]   boundary loop as corner-index pairs
                             (m = 2 x edge count, includes the wraparound)
      [k, k x 3 words]       edge mapping entries:
                             (mesh_edge_id, boundary_pos, flag)
                             boundary_pos indexes the flat boundary-pair
                             array (== 2 x corner index for quads);
                             flag observed as 1 (meaning not fully
                             determined - B-rep edge marker?).

Edge table (rest of the file):
  [count, count x 3 words]  (mesh_edge_id, 0, doc_id_number) mapping each
  mesh edge to the design-tree edge id, e.g. (12, 0, 45) -> '0:45'.

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
    corners: List[Corner] = field(default_factory=list)
    triangles: List[Tuple[int, int, int]] = field(default_factory=list)
    boundary: List[Tuple[int, int]] = field(default_factory=list)
    edge_refs: List[EdgeRef] = field(default_factory=list)

    def edge_segment(self, ref: EdgeRef):
        """3D segment of the boundary edge referenced by `ref`.

        `boundary_pos` indexes the FLAT corner-index array (two values per
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
    header_words: List[int] = field(default_factory=list)   # w3..w10 raw
    faces: List[FaceNode] = field(default_factory=list)
    edge_map: Dict[int, str] = field(default_factory=dict)  # edge_id -> doc id
    node_face_map: Dict[int, int] = field(default_factory=dict)  # node_id -> face idx

    @property
    def body_doc_id(self) -> Optional[str]:
        """Doc id of the owning body (header w6), e.g. '0:23'."""
        if len(self.header_words) >= 4:
            n = self.header_words[3]
            if n > 0:
                return f'0:{n}'
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
            raise FacetsError(f'truncated at byte {self.pos}')
        v = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return v

    def f32(self) -> float:
        if self.pos + 4 > len(self.data):
            raise FacetsError(f'truncated at byte {self.pos}')
        v = struct.unpack_from('<f', self.data, self.pos)[0]
        self.pos += 4
        return v

    def peek_words(self, n: int) -> List[int]:
        end = min(self.pos + 4 * n, len(self.data))
        cnt = max(0, (end - self.pos) // 4)
        return list(struct.unpack_from(f'<{cnt}I', self.data, self.pos))


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
    hdr = [reader.u32() for _ in range(5)]
    if hdr[0] != 0 or hdr[1] != hdr[3] or hdr[2] != 0:
        raise FacetsError(f'bad face-node header {hdr} at byte {reader.pos - 20}')
    node_id, corner_count = hdr[1], hdr[4]
    if not (3 <= corner_count <= 64):
        raise FacetsError(f'implausible corner count {corner_count}')
    face = FaceNode(node_id=node_id)
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


def parse_facets(data: bytes) -> FacetsFile:
    if data[:8] != MAGIC:
        raise FacetsError('not a facets stream (bad magic)')
    reader = _Reader(data)
    reader.pos = 8
    out = FacetsFile()
    out.version = reader.u32()
    out.header_words = [reader.u32() for _ in range(8)]

    declared_faces = out.header_words[7] if len(out.header_words) > 7 else 0
    face_count = 0
    while reader.words_left() > 0:
        peek = reader.peek_words(5)
        is_face = (len(peek) >= 5 and peek[0] == 0 and peek[1] == peek[3]
                   and peek[2] == 0 and 3 <= peek[4] <= 64)
        if declared_faces and face_count >= declared_faces:
            break
        if not is_face:
            break
        out.faces.append(_face_node(reader))
        out.node_face_map[out.faces[-1].node_id] = len(out.faces) - 1
        face_count += 1
    if declared_faces and face_count != declared_faces:
        raise FacetsError(
            f'header declares {declared_faces} faces but parsed {face_count}')

    # edge table: [count, count x (edge_id, 0, doc_id_number)]
    if reader.words_left() >= 1:
        count = reader.u32()
        for _ in range(count):
            edge_id = reader.u32()
            zero = reader.u32()
            doc_num = reader.u32()
            if zero != 0:
                raise FacetsError(f'edge table entry not (id, 0, doc): '
                                  f'({edge_id}, {zero}, {doc_num})')
            out.edge_map[edge_id] = f'0:{doc_num}'
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

    check('face_count', len(fac.faces) == 6, f'faces={len(fac.faces)} (expect 6)')
    check('corner_count', n_corners == 24, f'corners={n_corners} (expect 24)')
    check('triangle_count', n_tris == 12, f'triangles={n_tris} (expect 12)')
    check('edge_count', len(fac.edge_map) == 12,
          f'edges={len(fac.edge_map)} (expect 12)')
    check('edge_shared_by_two_faces',
          edge_faces and all(len(v) == 2 for v in edge_faces.values()),
          f'{len(edge_faces)} edges, use counts={sorted({len(v) for v in edge_faces.values()})}')
    check('edge_table_covers_refs',
          set(edge_faces) == set(fac.edge_map),
          f'{len(set(edge_faces) - set(fac.edge_map))} refs missing from edge table')

    faces = []
    for fi, f in enumerate(fac.faces):
        faces.append({
            'node_id': f.node_id,
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
                    segs.append({'face_index': fi,
                                 'segment_m': [list(seg[0]), list(seg[1])]})
        edges.append({'edge_id': eid, 'doc_id': fac.edge_map[eid],
                      'used_by_faces': fis, 'segments': segs})

    return {
        'version': fac.version,
        'body_doc_id': fac.body_doc_id,
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
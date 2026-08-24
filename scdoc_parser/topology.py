"""Semantic ACIS topology decoder: SAB token records -> B-rep model.

Field layouts (token positions, reverse-engineered from box.scdoc and
cross-validated against the SAT format documentation):

  body   t0=attribs ptr, t5=lump ptr, t9/t10=bbox vec3
  lump   t5=shell ptr, t6=body ptr
  shell  t6=first face ptr, t8=lump ptr
  face   t0=attribs, t4=next face, t5=loop, t6=shell, t8=surface,
         t9=sense (flag_a=REVERSED: face normal = -surface normal,
                   flag_b=FORWARD), t12/t13=bbox, t15..18=uv range
  loop   t5=coedge head, t6=face, t10=loop type, t11=optional surface ptr
  coedge t4=next, t5=prev, t6=partner, t7=edge, t8=sense
         (flag_b=FORWARD: traverses edge v1->v2, flag_a=REVERSED: v2->v1),
         t9=loop, t10=face (usually -1)
  edge   t0=attribs, t1=tag int, t4=vertex1, t5=param start (double),
         t6=vertex2, t7=param end, t8=coedge head, t9=curve,
         t10=sense, t11=tolerance string, t13/t14=bbox
  vertex t4=edge ptr, t5=point ptr
  point  t4=coords vec3
  plane  t4=origin vec3, t5=normal vec3b, t6=xdir vec3b
  straight t4=origin vec3, t5=direction vec3b, t7=t0 double, t9=t1 double

  string_attrib (ATTRIB_XACIS_NAME / ATTRIB_XACIS_PNAME / ...):
         t2=next attrib, t3=prev attrib, t4=owner, t6=type id,
         t7=type name string, t8=value string
  rgb_color: t2=next, t3=prev, t4=owner, t5=type id, t6..8=rgb doubles

The XACIS_NAME attribute values ('0:23', '0:27', ...) are the join keys
to document.xml NominalBodyDef/NominalFaceDef/NominalEdgeDef ids.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .sab import EntityRecord, SabFile

TOL = 1e-9


# -- small vector helpers ---------------------------------------------------
def vsub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def vadd(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def vscale(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def vdot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def vlen(a): return math.sqrt(vdot(a, a))
def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])
def vclose(a, b, tol=TOL): return vlen(vsub(a, b)) < tol


@dataclass
class Ent:
    """One decoded ACIS entity; `idx` is the 0-based pointer value."""
    idx: int
    kind: str
    record: EntityRecord
    # topology links (-1 = null)
    attribs: int = -1
    lump: int = -1
    shell: int = -1
    body: int = -1
    face: int = -1
    next: int = -1
    prev: int = -1
    partner: int = -1
    loop: int = -1
    surface: int = -1
    coedge: int = -1
    edge: int = -1
    v1: int = -1
    v2: int = -1
    point: int = -1
    owner: int = -1
    # geometry / payload
    bbox_min: Optional[Tuple[float, float, float]] = None
    bbox_max: Optional[Tuple[float, float, float]] = None
    uv_range: Optional[List[float]] = None
    origin: Optional[Tuple[float, float, float]] = None
    normal: Optional[Tuple[float, float, float]] = None
    xdir: Optional[Tuple[float, float, float]] = None
    direction: Optional[Tuple[float, float, float]] = None
    t0: Optional[float] = None
    t1: Optional[float] = None
    pstart: Optional[float] = None
    pend: Optional[float] = None
    rgb: Optional[Tuple[float, float, float]] = None
    attrib_type: Optional[str] = None
    attrib_value: Optional[str] = None
    sense: Optional[str] = None


class SabModel:
    """Decoded ACIS model with traversal, measurement and validation."""

    def __init__(self, sab: SabFile):
        self.sab = sab
        self.entities: List[Optional[Ent]] = [None] * len(sab.records)
        self.strings = self._collect_strings()
        self._decode_all()
        self.attribs_by_owner: Dict[int, List[Ent]] = {}
        for e in self.entities:
            if e is not None and e.kind in ('string_attrib', 'rgb_color'):
                self.attribs_by_owner.setdefault(e.owner, []).append(e)

    # -- string abbreviation resolution ------------------------------------
    def _collect_strings(self) -> Dict[str, str]:
        """Map '%6' -> 'ATTRIB_XACIS_NAME%6' (first full occurrence wins)."""
        seen: List[str] = []
        for r in self.sab.records:
            for t in r.tokens:
                if t.kind == 'string' and isinstance(t.value, str):
                    seen.append(t.value)
        table: Dict[str, str] = {}
        for s in seen:
            if '%' in s:
                suffix = s[s.rindex('%'):]
                table.setdefault(suffix, s)
        return table

    def _resolve_string(self, s: str) -> str:
        if s.startswith('%'):
            return self.strings.get(s, s)
        return s

    # -- decoding ------------------------------------------------------------
    def _tok(self, rec: EntityRecord, pos: int, kind: str):
        if pos >= len(rec.tokens):
            raise ValueError(f'{rec.kind} record {rec.index}: missing token #{pos}')
        t = rec.tokens[pos]
        if t.kind != kind:
            raise ValueError(
                f'{rec.kind} record {rec.index}: token #{pos} is {t.kind}, expected {kind}')
        return t.value

    def _ptr(self, rec, pos): return self._tok(rec, pos, 'ptr')
    def _dbl(self, rec, pos): return self._tok(rec, pos, 'double')
    def _v3(self, rec, pos): return tuple(self._tok(rec, pos, 'vec3'))

    def _decode_all(self):
        for idx, rec in enumerate(self.sab.records):
            self.entities[idx] = self._decode(idx, rec)

    def _decode(self, idx: int, rec: EntityRecord) -> Ent:
        e = Ent(idx=idx, kind=rec.kind, record=rec)
        k = rec.kind
        if k == 'body':
            e.attribs = self._ptr(rec, 0)
            e.lump = self._ptr(rec, 5)
            e.bbox_min = self._v3(rec, 9)
            e.bbox_max = self._v3(rec, 10)
        elif k == 'lump':
            e.shell = self._ptr(rec, 5)
            e.body = self._ptr(rec, 6)
        elif k == 'shell':
            e.face = self._ptr(rec, 6)
            e.lump = self._ptr(rec, 8)
        elif k == 'face':
            e.attribs = self._ptr(rec, 0)
            e.next = self._ptr(rec, 4)
            e.loop = self._ptr(rec, 5)
            e.shell = self._ptr(rec, 6)
            e.surface = self._ptr(rec, 8)
            e.sense = rec.tokens[9].kind if len(rec.tokens) > 9 else None
            e.bbox_min = self._v3(rec, 12)
            e.bbox_max = self._v3(rec, 13)
            e.uv_range = [self._dbl(rec, i) for i in range(15, 19)]
        elif k == 'loop':
            e.coedge = self._ptr(rec, 5)
            e.face = self._ptr(rec, 6)
            if len(rec.tokens) > 10 and rec.tokens[10].kind == 'int15':
                pass  # loop subtype (0 / 1)
            if len(rec.tokens) > 11 and rec.tokens[11].kind == 'ptr':
                e.surface = rec.tokens[11].value
        elif k == 'coedge':
            e.next = self._ptr(rec, 4)
            e.prev = self._ptr(rec, 5)
            e.partner = self._ptr(rec, 6)
            e.edge = self._ptr(rec, 7)
            e.sense = rec.tokens[8].kind if len(rec.tokens) > 8 else None
            e.loop = self._ptr(rec, 9)
            e.face = self._ptr(rec, 10)
        elif k == 'edge':
            e.attribs = self._ptr(rec, 0)
            e.v1 = self._ptr(rec, 4)
            e.pstart = self._dbl(rec, 5)
            e.v2 = self._ptr(rec, 6)
            e.pend = self._dbl(rec, 7)
            e.coedge = self._ptr(rec, 8)
            e.curve = self._ptr(rec, 9)
            e.sense = rec.tokens[10].kind if len(rec.tokens) > 10 else None
            e.bbox_min = self._v3(rec, 13)
            e.bbox_max = self._v3(rec, 14)
        elif k == 'vertex':
            e.edge = self._ptr(rec, 4)
            e.point = self._ptr(rec, 5)
        elif k == 'point':
            e.origin = self._v3(rec, 4)
        elif k == 'plane':
            e.origin = self._v3(rec, 4)
            e.normal = tuple(self._tok(rec, 5, 'vec3b'))
            e.xdir = tuple(self._tok(rec, 6, 'vec3b'))
        elif k == 'straight':
            e.origin = self._v3(rec, 4)
            e.direction = tuple(self._tok(rec, 5, 'vec3b'))
            e.t0 = self._dbl(rec, 7)
            e.t1 = self._dbl(rec, 9)
        elif k == 'string_attrib':
            e.next = self._ptr(rec, 2)
            e.prev = self._ptr(rec, 3)
            e.owner = self._ptr(rec, 4)
            e.attrib_type = self._resolve_string(self._tok(rec, 6, 'string'))
            e.attrib_value = self._tok(rec, 7, 'string')
        elif k == 'rgb_color':
            e.next = self._ptr(rec, 2)
            e.prev = self._ptr(rec, 3)
            e.owner = self._ptr(rec, 4)
            e.rgb = (self._dbl(rec, 6), self._dbl(rec, 7), self._dbl(rec, 8))
        return e

    # -- accessors -----------------------------------------------------------
    def e(self, idx: int) -> Optional[Ent]:
        if 0 <= idx < len(self.entities):
            return self.entities[idx]
        return None

    def of_kind(self, kind: str) -> List[Ent]:
        return [e for e in self.entities if e is not None and e.kind == kind]

    def doc_id_of(self, ent: Ent, prefix: str = 'ATTRIB_XACIS_NAME') -> Optional[str]:
        for a in self.attribs_by_owner.get(ent.idx, ()):
            if a.attrib_type and a.attrib_type.startswith(prefix):
                return a.attrib_value
        return None

    def rgb_of(self, ent: Ent) -> Optional[Tuple[int, int, int]]:
        for a in self.attribs_by_owner.get(ent.idx, ()):
            if a.rgb is not None:
                return tuple(round(c * 255) for c in a.rgb)
        return None

    # -- traversal -----------------------------------------------------------
    def faces_of_shell(self, shell: Ent) -> List[Ent]:
        out, seen = [], set()
        cur = self.e(shell.face)
        while cur is not None and cur.idx not in seen and cur.kind == 'face':
            seen.add(cur.idx)
            out.append(cur)
            cur = self.e(cur.next)
        return out

    def coedges_of_loop(self, loop: Ent) -> List[Ent]:
        out, seen = [], set()
        cur = self.e(loop.coedge)
        while cur is not None and cur.idx not in seen and cur.kind == 'coedge':
            seen.add(cur.idx)
            out.append(cur)
            cur = self.e(cur.next)
        return out

    def loops_of_face(self, face: Ent) -> List[Ent]:
        """All loops of the face.  Faces in box.scdoc carry a single loop;
        additional loops (holes) would chain via the loop record's t4 ptr."""
        out, seen = [], set()
        cur = self.e(face.loop)
        while cur is not None and cur.kind == 'loop' and cur.idx not in seen:
            seen.add(cur.idx)
            out.append(cur)
            nxt = cur.record.tokens[4]
            cur = self.e(nxt.value) if nxt.kind == 'ptr' else None
        return out

    def body_faces(self, body: Ent) -> List[Ent]:
        lump = self.e(body.lump)
        if lump is None:
            return []
        shell = self.e(lump.shell)
        if shell is None:
            return []
        return self.faces_of_shell(shell)

    # -- geometry ------------------------------------------------------------
    def point_of_vertex(self, vertex: Ent):
        p = self.e(vertex.point)
        return p.origin if p is not None else None

    def edge_endpoints(self, edge: Ent):
        """Endpoints from the underlying straight curve (authoritative)."""
        c = self.e(edge.curve)
        if c is None or c.kind != 'straight':
            return None
        a = vadd(c.origin, vscale(c.direction, c.t0))
        b = vadd(c.origin, vscale(c.direction, c.t1))
        return a, b

    def edge_length(self, edge: Ent) -> Optional[float]:
        ep = self.edge_endpoints(edge)
        return vlen(vsub(ep[1], ep[0])) if ep else None

    def _walk_ring(self, endpoints, flip_first: bool):
        """Chain segments head-to-tail; None if the chain breaks or won't close.

        A closed ring of segments admits exactly two consistent traversals
        (the two orientations); flipping the first segment's direction
        selects the other one, so trying both covers all cases.
        """
        poly: List[Tuple[float, float, float]] = []
        cur_pt = None
        for i, (a, b) in enumerate(endpoints):
            if i == 0 and flip_first:
                a, b = b, a
            if cur_pt is None:
                cur_pt, nxt = a, b
            elif vclose(cur_pt, a):
                nxt = b
            elif vclose(cur_pt, b):
                nxt = a
            else:
                return None  # broken loop chain
            poly.append(cur_pt)
            cur_pt = nxt
        if len(poly) == 0 or not vclose(cur_pt, poly[0]):
            return None  # ring does not close
        return poly

    def _walk_sensed(self, coedges, endpoints):
        """Canonical walk: follow the `next` chain, directing each coedge
        by its sense token (flag_b=FORWARD v1->v2, flag_a=REVERSED v2->v1).
        This is counter-clockwise around the face's effective normal, so
        outer loops yield positive signed area and hole loops negative."""
        poly: List[Tuple[float, float, float]] = []
        cur_pt = None
        for ce, (a, b) in zip(coedges, endpoints):
            if ce.sense == 'flag_a':
                a, b = b, a
            elif ce.sense != 'flag_b':
                return None  # unknown sense token -> caller falls back
            if cur_pt is None:
                cur_pt = a
            elif vclose(cur_pt, a):
                pass
            elif vclose(cur_pt, b):
                a, b = b, a
            else:
                return None  # sense flags inconsistent with geometry
            poly.append(a)
            cur_pt = b
        if len(poly) == 0 or not vclose(cur_pt, poly[0]):
            return None
        return poly

    def loop_polygon(self, loop: Ent) -> Optional[List[Tuple[float, float, float]]]:
        """Ordered 3D polygon from the coedge ring.

        Prefers the canonical sense-directed walk (CCW around the face's
        effective normal); falls back to pure endpoint chaining in either
        orientation when sense tokens are missing or inconsistent."""
        coedges = self.coedges_of_loop(loop)
        if not coedges:
            return None
        endpoints = []
        for ce in coedges:
            edge = self.e(ce.edge)
            ep = self.edge_endpoints(edge) if edge is not None else None
            if ep is None:
                return None
            endpoints.append(ep)
        poly = self._walk_sensed(coedges, endpoints)
        if poly is not None:
            return poly
        for flip in (False, True):
            poly = self._walk_ring(endpoints, flip)
            if poly is not None:
                return poly
        return None

    def face_loops_polygons(self, face: Ent) -> List[List[Tuple[float, float, float]]]:
        polys = []
        for loop in self.loops_of_face(face):
            poly = self.loop_polygon(loop)
            if poly:
                polys.append(poly)
        return polys

    @staticmethod
    def polygon_area_2d(pts2d) -> float:
        s = 0.0
        for i in range(len(pts2d)):
            x1, y1 = pts2d[i]
            x2, y2 = pts2d[(i + 1) % len(pts2d)]
            s += x1 * y2 - x2 * y1
        return s / 2.0

    def face_metrics(self, face: Ent):
        """Signed area, |area|, contribution to volume, plane description."""
        surf = self.e(face.surface)
        polys = self.face_loops_polygons(face)
        if not polys or surf is None or surf.kind != 'plane':
            return None
        n = vscale(surf.normal, 1.0 / max(vlen(surf.normal), 1e-30))
        if face.sense == 'flag_a':  # face reversed wrt surface normal
            n = vscale(n, -1.0)
        ydir = vcross(n, surf.xdir)
        total_signed = 0.0
        centroid_acc = (0.0, 0.0, 0.0)
        total_w = 0.0
        for poly in polys:
            pts2d = []
            for p in poly:
                d = vsub(p, surf.origin)
                pts2d.append((vdot(d, surf.xdir), vdot(d, ydir)))
            a = self.polygon_area_2d(pts2d)
            total_signed += a
            w = abs(a)
            for p in poly:
                centroid_acc = vadd(centroid_acc, vscale(p, w / len(poly)))
            total_w += w
        centroid = vscale(centroid_acc, 1.0 / total_w) if total_w > 0 else None
        area = abs(total_signed)
        vol_contrib = 0.0
        if centroid is not None:
            vol_contrib = vdot(centroid, n) * total_signed / 3.0
        offset = vdot(surf.origin, n)
        return {
            'area_signed': total_signed,
            'area': area,
            'volume_contrib': vol_contrib,
            'normal': n,
            'offset': offset,
        }

    def body_metrics(self, body: Ent):
        faces = self.body_faces(body)
        volume = 0.0
        area = 0.0
        for f in faces:
            m = self.face_metrics(f)
            if m:
                volume += m['volume_contrib']
                area += m['area']
        return {'faces': faces, 'volume': abs(volume), 'area': area}

    # -- human-readable plane description ------------------------------------
    @staticmethod
    def describe_plane(normal, offset, scale=1000.0):
        axis = None
        for i, v in enumerate(normal):
            if abs(v) > 0.9999:
                axis = ('XYZ'[i], round(v))
                break
        if axis is None:
            return None
        a, s = axis
        v = offset * scale
        if v == 0:
            v = 0.0  # normalize -0.0
        return f'{a}{"+" if s > 0 else "-"} @ {a.lower()}={v:g}mm'


# -- model-level summary -----------------------------------------------------
def model_summary(model: SabModel, scale: float) -> Dict:
    """JSON-ready summary of the whole SAB model with validation checks."""
    counts = {k: len(model.of_kind(k)) for k in (
        'body', 'lump', 'shell', 'face', 'loop', 'coedge', 'edge',
        'vertex', 'point', 'plane', 'straight', 'string_attrib', 'rgb_color')}

    checks: List[Dict] = []

    def check(name, ok, detail):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})

    bodies = []
    for body in model.of_kind('body'):
        doc_id = model.doc_id_of(body)
        m = model.body_metrics(body)
        faces = []
        for f in m['faces']:
            fm = model.face_metrics(f)
            surf = model.e(f.surface)
            faces.append({
                'acis_index': f.idx,
                'doc_id': model.doc_id_of(f),
                'plane': {
                    'origin_m': list(surf.origin),
                    'normal': list(fm['normal']) if fm is not None else list(surf.normal),
                    'xdir': list(surf.xdir),
                    'uv_range': f.uv_range,
                    'description': (model.describe_plane(fm['normal'], fm['offset'], scale)
                                     if fm is not None else None),
                } if surf is not None and surf.kind == 'plane' else None,
                'area_mm2': round(fm['area'] * scale * scale, 9) if fm else None,
                'loops': len(model.loops_of_face(f)),
                'rgb': model.rgb_of(f),
            })
        edges = []
        for ed in model.of_kind('edge'):
            ep = model.edge_endpoints(ed)
            edges.append({
                'acis_index': ed.idx,
                'doc_id': model.doc_id_of(ed),
                'start_m': list(ep[0]) if ep else None,
                'end_m': list(ep[1]) if ep else None,
                'length_mm': round(model.edge_length(ed) * scale, 9),
            })
        vertices = []
        for vt in model.of_kind('vertex'):
            p = model.point_of_vertex(vt)
            vertices.append({
                'acis_index': vt.idx,
                'point_m': list(p) if p else None,
            })
        # bbox from vertices
        pts = [model.point_of_vertex(v) for v in model.of_kind('vertex')]
        pts = [p for p in pts if p]
        if pts:
            bbox_min = [min(p[i] for p in pts) for i in range(3)]
            bbox_max = [max(p[i] for p in pts) for i in range(3)]
        else:
            bbox_min = list(body.bbox_min) if body.bbox_min else None
            bbox_max = list(body.bbox_max) if body.bbox_max else None
        bodies.append({
            'acis_index': body.idx,
            'doc_id': doc_id,
            'bbox_min_m': bbox_min,
            'bbox_max_m': bbox_max,
            'volume_mm3': round(m['volume'] * scale ** 3, 9),
            'surface_area_mm2': round(m['area'] * scale * scale, 9),
            'faces': faces,
            'edges': edges,
            'vertices': vertices,
        })

    # ---- validation ---------------------------------------------------------
    check('entity_counts', True,
          ', '.join(f'{k}={v}' for k, v in counts.items()))
    check('face_count', counts['face'] == 6, f"faces={counts['face']} (expect 6)")
    check('edge_count', counts['edge'] == 12, f"edges={counts['edge']} (expect 12)")
    check('vertex_count', counts['vertex'] == 8, f"vertices={counts['vertex']} (expect 8)")
    check('coedge_count', counts['coedge'] == 24, f"coedges={counts['coedge']} (expect 24)")

    lengths = [l * scale for l in (model.edge_length(e) for e in model.of_kind('edge'))
              if l is not None]
    check('edge_lengths_10mm',
          lengths and all(abs(l - 10.0) < 1e-6 for l in lengths),
          f'{len(lengths)} edges, min={min(lengths):.9g} max={max(lengths):.9g} mm (expect 10)')

    areas = []
    for b in bodies:
        for f in b['faces']:
            if f['area_mm2'] is not None:
                areas.append(f['area_mm2'])
    check('face_areas_100mm2',
          areas and all(abs(a - 100.0) < 1e-6 for a in areas),
          f'{len(areas)} faces, min={min(areas):.9g} max={max(areas):.9g} mm2 (expect 100)')

    vols = [b['volume_mm3'] for b in bodies]
    check('volume_1000mm3',
          vols and all(abs(v - 1000.0) < 1e-6 for v in vols),
          f'volume={vols} mm3 (expect [1000])')

    for b in bodies:
        if b['bbox_min_m'] and b['bbox_max_m']:
            dims = [(hi - lo) * scale for lo, hi in zip(b['bbox_min_m'], b['bbox_max_m'])]
            check('bbox_10mm_cube',
                  all(abs(d - 10.0) < 1e-6 for d in dims),
                  f'dimensions={["%.9g" % d for d in dims]} mm (expect [10, 10, 10])')

    # topology integrity
    ok_partner = all(
        (p := model.e(ce.partner)) is not None and p.partner == ce.idx
        for ce in model.of_kind('coedge'))
    check('coedge_partner_symmetry', ok_partner, 'partner links are mutual')

    ok_rings = True
    ring_sizes = []
    for lp in model.of_kind('loop'):
        ring = model.coedges_of_loop(lp)
        ring_sizes.append(len(ring))
        if len(ring) < 3 or model.loop_polygon(lp) is None:
            ok_rings = False
    check('loop_rings_closed', ok_rings, f'ring sizes={ring_sizes}')

    coedge_per_edge: Dict[int, int] = {}
    for ce in model.of_kind('coedge'):
        coedge_per_edge[ce.edge] = coedge_per_edge.get(ce.edge, 0) + 1
    check('two_coedges_per_edge',
          coedge_per_edge and all(v == 2 for v in coedge_per_edge.values()),
          f'{len(coedge_per_edge)} edges referenced (all exactly 2 coedges)')

    degree: Dict[int, int] = {}
    for ed in model.of_kind('edge'):
        for vi in (ed.v1, ed.v2):
            if vi >= 0:
                degree[vi] = degree.get(vi, 0) + 1
    check('vertex_degree_3',
          degree and all(v == 3 for v in degree.values()),
          f'{len(degree)} vertices, degrees={sorted(set(degree.values()))}')

    # vertex points match curve endpoints
    ok_vertex = True
    for ed in model.of_kind('edge'):
        ep = model.edge_endpoints(ed)
        v1, v2 = model.e(ed.v1), model.e(ed.v2)
        if not ep or v1 is None or v2 is None:
            ok_vertex = False
            break
        p1, p2 = model.point_of_vertex(v1), model.point_of_vertex(v2)
        if not (vclose(p1, ep[0]) and vclose(p2, ep[1])):
            ok_vertex = False
            break
    check('vertex_points_match_curves', ok_vertex,
          'edge vertex points coincide with straight-curve endpoints')

    # doc id linkage
    linked = sum(1 for e in model.of_kind('body') + model.of_kind('face') + model.of_kind('edge')
                 if model.doc_id_of(e) is not None)
    check('doc_id_links', linked == 1 + counts['face'] + counts['edge'],
          f'{linked}/{1 + counts["face"] + counts["edge"]} body/face/edge entities carry XACIS_NAME doc ids')

    return {
        'acis': {
            'product': model.sab.product,
            'version': model.sab.version,
            'date': model.sab.date,
            'unit_scale_to_document': model.sab.unit_scale,
            'entity_count': len(model.sab.records),
            'class_registry': {str(k): v for k, v in sorted(model.sab.classes.items())},
            'counts': counts,
        },
        'bodies': bodies,
        'checks': checks,
    }
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
    tolerance: Optional[float] = None
    bs_form: Optional[int] = None
    bs_deg: Optional[int] = None
    bs_deg_v: Optional[int] = None
    bs_knots: Optional[list] = None
    bs_mults: Optional[list] = None
    bs_poles: Optional[list] = None
    bs_poles_2d: Optional[list] = None
    ratio: Optional[float] = None
    semangle: Optional[float] = None
    sin_angle: Optional[float] = None
    cos_angle: Optional[float] = None
    radius: Optional[float] = None
    major: Optional[float] = None
    minor: Optional[float] = None
    bsurf_uperiodic: bool = False
    bsurf_vperiodic: bool = False
    bsurf_u_knots: Optional[list] = None
    bsurf_u_mults: Optional[list] = None
    bsurf_v_knots: Optional[list] = None
    bsurf_v_mults: Optional[list] = None
    bsurf_poles: Optional[list] = None   # flat (x,y,z,w), v-slowest
    cluster_owner: int = -1              # entity index of the scope head
    t_range: Optional[tuple] = None
    attrib_type: Optional[str] = None
    attrib_value: Optional[str] = None
    sense: Optional[str] = None


class SabModel:
    """Decoded ACIS model with traversal, measurement and validation.

    Pointer semantics (validated against official spline.scdoc): pointer
    values are *entity* indices — every 0x0d record that starts OUTSIDE a
    nested-subtype scope (0x0F..0x10) is one list entity; records inside a
    scope (exactsur/nurbs/both of a spline surface, exactcur/nubs/
    null_surface/nullbs of an intcurve, exppc/nubs of a pcurve) are payload
    and not addressable.  `entities` is indexed by entity index; inner
    records decode into `inner` with idx=-1.
    """

    def __init__(self, sab: SabFile):
        self.sab = sab
        self._entity_of_pos, self._pos_of_entity = self._scan_scopes()
        self.entities: List[Optional[Ent]] = [None] * len(self._pos_of_entity)
        self.inner: List[Ent] = []
        self.strings = self._collect_strings()
        self._decode_all()
        self._link_clusters()
        self.attribs_by_owner: Dict[int, List[Ent]] = {}
        for e in self.entities:
            if e is not None and e.kind in ('string_attrib', 'rgb_color'):
                self.attribs_by_owner.setdefault(e.owner, []).append(e)

    def _scan_scopes(self):
        """Record position <-> entity index maps via 0x0F/0x10 nesting."""
        depth = 0
        entity_of_pos: Dict[int, int] = {}
        pos_of_entity: Dict[int, int] = {}
        ent = 0
        for pos, rec in enumerate(self.sab.records):
            if depth == 0:
                entity_of_pos[pos] = ent
                pos_of_entity[ent] = pos
                ent += 1
            for t in rec.tokens:
                if t.kind == 'mark0f':
                    depth += 1
                elif t.kind == 'mark10':
                    depth = max(0, depth - 1)
        return entity_of_pos, pos_of_entity

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

    # optional variants: None when the token is absent or a different kind
    def _opt(self, rec, pos, kind, value):
        if pos >= len(rec.tokens):
            return None
        t = rec.tokens[pos]
        if t.kind != kind:
            return None
        return value(t)

    def _opt_ptr(self, rec, pos):
        return self._opt(rec, pos, 'ptr', lambda t: t.value)

    def _opt_v3(self, rec, pos):
        return self._opt(rec, pos, 'vec3', lambda t: tuple(t.value))

    def _opt_v3b(self, rec, pos):
        return self._opt(rec, pos, 'vec3b', lambda t: tuple(t.value))

    def _opt_dbl(self, rec, pos):
        return self._opt(rec, pos, 'double', lambda t: t.value)

    def _decode_all(self):
        depth = 0
        owner = -1
        for pos, rec in enumerate(self.sab.records):
            ent = self._entity_of_pos.get(pos, -1)
            e = self._decode(ent, rec)
            if depth > 0:
                e.cluster_owner = owner   # inner payload of a cluster head
            if ent >= 0:
                self.entities[ent] = e
                owner = ent
            else:
                self.inner.append(e)
            for t in rec.tokens:
                if t.kind == 'mark0f':
                    depth += 1
                elif t.kind == 'mark10':
                    depth = max(0, depth - 1)

    def _link_clusters(self):
        """Slice 'both' payloads' pole grids using the owning cluster's
        nurbs-record degrees (npoles = sum(mults) - deg + 1)."""
        nurbs_by_owner = {}
        for e in self.inner:
            if e.kind == 'nurbs':
                nurbs_by_owner.setdefault(e.cluster_owner, e)
        for e in self.inner:
            if (e.kind != 'both' or e.bsurf_poles is not None
                    or e.bsurf_u_knots is None):
                continue
            n = nurbs_by_owner.get(e.cluster_owner)
            if n is None or not n.bs_deg or not n.bs_deg_v:
                continue
            npu = sum(e.bsurf_u_mults) - n.bs_deg + 1
            npv = sum(e.bsurf_v_mults) - n.bs_deg_v + 1
            need = npu * npv
            if need <= 0:
                continue
            tk = e.record.tokens
            i = 6 + 2 * (len(e.bsurf_u_knots) + len(e.bsurf_v_knots))
            if i + need * 4 > len(tk):
                continue
            vals = [t.value for t in tk[i:i + need * 4]]
            if any(not isinstance(v, float) for v in vals):
                continue
            e.bsurf_poles = [tuple(vals[k:k + 4])
                             for k in range(0, need * 4, 4)]

    def _decode(self, idx: int, rec: EntityRecord) -> Ent:
        e = Ent(idx=idx, kind=rec.kind, record=rec)
        k = rec.kind
        if k == 'body':
            e.attribs = self._ptr(rec, 0)
            e.lump = self._ptr(rec, 5)
            # body bbox appears on some writers (box) but not on imported models
            e.bbox_min = self._opt_v3(rec, 9)
            e.bbox_max = self._opt_v3(rec, 10)
        elif k == 'lump':
            e.shell = self._ptr(rec, 5)
            e.body = self._ptr(rec, 6)
        elif k == 'shell':
            e.face = self._ptr(rec, 6)
            e.lump = self._ptr(rec, 8)
        elif k == 'face':
            e.attribs = self._ptr(rec, 0)
            # P37: decode topology pointers POSITIONALLY within the record's
            # pointer run instead of at fixed token indices. Official files
            # vary: layout A = P I I P P P P P P F F F V V F (6 ptrs in a row),
            # samplemodel3 = P I I P I I P P P P P F F F V V F (two ints inside
            # the run wound up shifting every topology pointer by +2, which
            # silently produced faces with no loop/surface at all).
            run = self._ptr_run(rec)
            def _p(n):
                return self._opt_ptr(rec, run[n]) if len(run) > n else None
            if len(run) >= 6:
                e.next, e.loop, e.shell, e.surface = _p(1), _p(2), _p(3), _p(5)
            else:
                e.next = self._opt_ptr(rec, 4)
                e.loop = self._opt_ptr(rec, 5)
                e.shell = self._opt_ptr(rec, 6)
                e.surface = self._opt_ptr(rec, 8)
            e.sense = next((t.kind for t in rec.tokens
                            if t.kind.startswith('flag')), None)
            vecs = [i for i, t in enumerate(rec.tokens)
                    if t.kind in ('vec3', 'vec3b')]
            if len(vecs) >= 2 and vecs[1] == vecs[0] + 1:
                e.bbox_min = self._opt_v3(rec, vecs[0])
                e.bbox_max = self._opt_v3(rec, vecs[1])
            else:
                e.bbox_min = self._opt_v3(rec, 12)
                e.bbox_max = self._opt_v3(rec, 13)
            dbl = [i for i, t in enumerate(rec.tokens) if t.kind == 'double']
            for i in range(len(dbl) - 3):
                if dbl[i + 3] == dbl[i] + 3:
                    e.uv_range = [rec.tokens[dbl[i] + j].value
                                  for j in range(4)]
                    break
        elif k == 'loop':
            # P37: positional within the pointer run (variants interleave ints)
            run = self._ptr_run(rec)
            e.coedge = self._role(rec, 2, run)
            e.face = self._role(rec, 3, run)
            st = next((t.value for t in rec.tokens if t.kind == 'int15'), None)
            if st is not None:
                e.surface = self._role(rec, 4, run)
        elif k in ('coedge', 'tcoedge'):
            run = self._ptr_run(rec)
            e.next = self._role(rec, 1, run)
            e.prev = self._role(rec, 2, run)
            e.partner = self._role(rec, 3, run)
            e.edge = self._role(rec, 4, run)
            e.loop = self._role(rec, 5, run)
            e.face = self._role(rec, 6, run)
            e.sense = next((t.kind for t in rec.tokens
                            if t.kind.startswith('flag')), None)
            if k == 'tcoedge':
                dbl = self._doubles(rec)
                if len(dbl) >= 2:
                    e.t_range = (dbl[0], dbl[1])
        elif k == 'edge':
            e.attribs = self._ptr(rec, 0)
            self._decode_edge_fields(e, rec)
        elif k in ('vertex', 'tvertex'):
            run = self._ptr_run(rec)
            e.edge = self._role(rec, 1, run)
            e.point = self._role(rec, 2, run)
            if k == 'tvertex':
                dbl = self._doubles(rec)
                if dbl:
                    e.tolerance = dbl[0]
        elif k == 'tedge':
            # same layout as edge plus a trailing tolerance double
            e.attribs = self._ptr(rec, 0)
            self._decode_edge_fields(e, rec)
            dbl = self._doubles(rec)
            if len(dbl) >= 3:
                e.tolerance = dbl[2]
        elif k == 'point':
            # P37: coordinates are the first vec3 token, not always index 4
            vecs = [i for i, t in enumerate(rec.tokens)
                    if t.kind in ('vec3', 'vec3b')]
            e.origin = (self._opt_v3(rec, vecs[0]) if vecs
                        else self._opt_v3(rec, 4))
        elif k in ('plane', 'cone', 'ellipse', 'spline', 'curve',
                   'torus', 'sphere'):
            # P37: origin/normal/xdir are the first three vec tokens
            vecs = [i for i, t in enumerate(rec.tokens)
                    if t.kind in ('vec3', 'vec3b')]
            e.origin = (self._opt_v3(rec, vecs[0]) if len(vecs) > 0
                        else self._opt_v3(rec, 4))
            e.normal = (self._opt_v3b(rec, vecs[1]) if len(vecs) > 1
                        else self._opt_v3b(rec, 5))
            e.xdir = (self._opt_v3b(rec, vecs[2]) if len(vecs) > 2
                      else self._opt_v3b(rec, 6))
            if k == 'ellipse':
                e.ratio = self._opt_dbl(rec, 7)
            if k == 'cone':
                # [.., ratio double, flags, sin(semi-angle), cos(semi-angle),
                #  base radius, flags] - P46: token 10 is the SINE and token 11
                #  the COSINE (a zero-semi cylinder stores -0.0 / 1.0), so the
                #  angle itself is atan2.  Reading token 10 as the angle made
                #  every truncated cone look like a cylinder.
                e.sin_angle = self._opt_dbl(rec, 10)
                e.cos_angle = self._opt_dbl(rec, 11)
                if e.sin_angle is not None and e.cos_angle is not None:
                    e.semangle = math.atan2(e.sin_angle, e.cos_angle)
                e.radius = self._opt_dbl(rec, 12)
            if k == 'torus':
                # [origin, axis, major double, minor double, xdir] - the two
                # radii sit between the axis and the x direction, so the
                # vec-based origin/normal/xdir decode above is already right.
                dbl = self._doubles(rec)
                if len(dbl) >= 2:
                    e.major, e.minor = dbl[0], dbl[1]
            if k == 'sphere':
                dbl = self._doubles(rec)
                if dbl:
                    e.radius = dbl[0]
        elif k == 'both':
            # B-spline SURFACE payload (inside a spline-surface 0x0F scope):
            # [u_periodic int15][v_periodic int15][u_form int15][v_form int15]
            # [#u_knots int][#v_knots int][(knot double, mult int)...]
            # [poles (x,y,z,w) 4xdouble, v-slowest][fit double + trailer...].
            # ACIS mult convention: npoles = sum(mults) - deg + 1 (the
            # degrees live in the cluster's nurbs record); the record tail
            # beyond the poles belongs to the outer cluster record.
            tk = rec.tokens
            try:
                e.bsurf_uperiodic = tk[0].kind == 'int15' and tk[0].value == 1
                e.bsurf_vperiodic = tk[1].kind == 'int15' and tk[1].value == 1
                nku = tk[4].value if tk[4].kind == 'int' else None
                nkv = tk[5].value if tk[5].kind == 'int' else None
                if nku is None or nkv is None:
                    raise ValueError('knot counts missing')
                i = 6
                kt, mt = [], []
                for _ in range(nku + nkv):
                    if (i + 1 < len(tk) and tk[i].kind == 'double'
                            and tk[i + 1].kind == 'int'):
                        kt.append(tk[i].value)
                        mt.append(tk[i + 1].value)
                        i += 2
                    else:
                        raise ValueError('bad knot pair')
                e.bsurf_u_knots, e.bsurf_u_mults = kt[:nku], mt[:nku]
                e.bsurf_v_knots, e.bsurf_v_mults = kt[nku:], mt[nku:]
                e.bsurf_poles = None  # filled by the model after degrees known
            except (ValueError, IndexError, AttributeError):
                e.bsurf_poles = None
        elif k == 'straight':
            e.origin = self._opt_v3(rec, 4)
            e.direction = self._opt_v3b(rec, 5)
            # parameter range is optional-spaceclaimed as t0/t1 (two doubles
            # after the direction); imported lines may omit it entirely.
            e.t0 = self._opt_dbl(rec, 7)
            e.t1 = self._opt_dbl(rec, 9)
        elif k == 'nubs':
            # B-spline definition: [form][int15][#knots][(val,mult)...]
            # [closed int][poles 3D | 2D(+2-double tail)]; the degree is NOT
            # stored — it is derived: sum(mults) - npoles + 1.
            if len(rec.tokens) >= 5 and rec.tokens[2].kind == 'int':
                e.bs_form = self._opt(rec, 0, 'int', lambda t: t.value)
                nk = rec.tokens[2].value
                kt, mt, i = [], [], 3
                ok = True
                for _ in range(nk):
                    if (i + 1 < len(rec.tokens)
                            and rec.tokens[i].kind == 'double'
                            and rec.tokens[i + 1].kind == 'int'):
                        kt.append(rec.tokens[i].value)
                        mt.append(rec.tokens[i + 1].value)
                        i += 2
                    else:
                        ok = False
                        break
                if ok:
                    if i < len(rec.tokens) and rec.tokens[i].kind == 'int':
                        i += 1  # optional closed/open marker (3D nubs)
                    rest = len(rec.tokens) - i
                    e.bs_knots, e.bs_mults = kt, mt
                    if rest % 3 == 0 and rest >= 3:
                        n3 = rest // 3
                        e.bs_poles = [tuple(rec.tokens[j].value
                                            for j in range(k, k + 3))
                                      for k in range(i, i + 3 * n3, 3)]
                        e.bs_deg = sum(mt) - n3 + 1
                    elif rest % 3 == 1 and rest >= 4:
                        # R78: some official 3D nubs carry a trailing double
                        # after the poles - measured on samplemodel2 as 1e-05,
                        # i.e. the fit tolerance.  The poles are the leading
                        # rest-1 tokens; without this the record looks like
                        # "nubs without poles" and 287 edges stay undecodable
                        # (66 poles, sum(mults) 68 -> degree 3).
                        n3 = (rest - 1) // 3
                        e.bs_poles = [tuple(rec.tokens[j].value
                                            for j in range(k, k + 3))
                                      for k in range(i, i + 3 * n3, 3)]
                        e.bs_deg = sum(mt) - n3 + 1
                    if rest % 2 == 0 and rest >= 2:
                        n2 = (rest - 2) // 2  # 2D carries a 2-double tail
                        if n2 > 0:
                            e.bs_poles_2d = [tuple(rec.tokens[j].value
                                                   for j in range(k, k + 2))
                                             for k in range(i, i + 2 * n2, 2)]
                            e.bs_deg = sum(mt) - n2 + 1
        elif k == 'exppc':
            e.bs_form = self._opt(rec, 0, 'int', lambda t: t.value)
        elif k == 'ref':
            e.bs_form = self._opt(rec, 0, 'int', lambda t: t.value)
        elif k in ('exactcur', 'exactsur'):
            e.bs_form = self._opt(rec, 0, 'int', lambda t: t.value)
        elif k == 'nurbs':
            e.bs_deg = self._opt(rec, 0, 'int', lambda t: t.value)
            e.bs_deg_v = self._opt(rec, 1, 'int', lambda t: t.value)
        elif k in ('intcurve', 'spline', 'surfintcur', 'surfcur', 'pcurve',
                   'sweepsur', 'sumsur', 'skinsur', 'offsur', 'parcur'):
            # [ptr attrib][int][int][ptr][flag] prefix — keep the sense flag
            if len(rec.tokens) > 4 and rec.tokens[4].kind in ('flag_a', 'flag_b'):
                e.sense = rec.tokens[4].kind
        elif k in ('string_attrib', 'wstring_attrib', 'integer_attrib'):
            e.next = self._ptr(rec, 2)
            e.prev = self._ptr(rec, 3)
            e.owner = self._ptr(rec, 4)
            e.attrib_type = self._resolve_string(self._tok(rec, 6, 'string'))
            v = rec.tokens[7] if len(rec.tokens) > 7 else None
            e.attrib_value = v.value if v is not None else None
        elif k == 'rgb_color':
            e.next = self._ptr(rec, 2)
            e.prev = self._ptr(rec, 3)
            e.owner = self._ptr(rec, 4)
            e.rgb = (self._dbl(rec, 6), self._dbl(rec, 7), self._dbl(rec, 8))
        # unknown kinds: keep the minimal Ent so record indexing stays valid
        return e

    def _ptr_run(self, rec, skip_attribs: bool = True):
        """Token indices of the record's pointer fields, in order.

        P37: the first token is usually the attribs chain; topology pointers
        follow it, possibly with ints interleaved (official layout variants).
        """
        out = []
        for i, t in enumerate(rec.tokens):
            if t.kind != 'ptr':
                continue
            if skip_attribs and i == 0:
                continue
            out.append(i)
        return out

    def _role(self, rec, n: int, run=None):
        """The n-th pointer of a record's pointer run, or None (P37)."""
        run = self._ptr_run(rec) if run is None else run
        return self._opt_ptr(rec, run[n]) if len(run) > n else None

    def _doubles(self, rec):
        return [t.value for t in rec.tokens if t.kind == 'double']

    def _decode_edge_fields(self, e, rec) -> None:
        """Edge topology + parameter range, positionally (P37 variants)."""
        run = self._ptr_run(rec)
        e.v1 = self._role(rec, 1, run)
        e.v2 = self._role(rec, 2, run)
        e.coedge = self._role(rec, 3, run)
        e.curve = self._role(rec, 4, run)
        dbl = self._doubles(rec)
        e.pstart = dbl[0] if len(dbl) > 0 else None
        e.pend = dbl[1] if len(dbl) > 1 else None
        e.sense = next((t.kind for t in rec.tokens
                        if t.kind.startswith('flag')), None)
        vecs = [i for i, t in enumerate(rec.tokens)
                if t.kind in ('vec3', 'vec3b')]
        if len(vecs) >= 2 and vecs[1] == vecs[0] + 1:
            e.bbox_min = self._opt_v3(rec, vecs[0])
            e.bbox_max = self._opt_v3(rec, vecs[1])
        else:
            e.bbox_min = self._opt_v3(rec, 13)
            e.bbox_max = self._opt_v3(rec, 14)

    # -- accessors -----------------------------------------------------------
    def e(self, idx: int) -> Optional[Ent]:
        """Entity by index; None-safe.

        P29: optional pointers are routinely absent (None) in official streams;
        a bare comparison crashed the whole import on the first such loop.
        """
        if idx is None:
            return None
        if 0 <= idx < len(self.entities):
            return self.entities[idx]
        return None

    def of_kind(self, kind: str) -> List[Ent]:
        return [e for e in self.entities if e is not None and e.kind == kind]

    def _by_pointer(self, cache_key: str, kind: str, attr: str):
        """Index of entities grouped by one of their pointer fields.

        P30: the P29 back-pointer fallbacks scanned every entity per call, which
        turned the import into O(n^2) (68 s on samplemodel2). Built once, lazily.
        """
        cache = getattr(self, "_ptr_cache", None)
        if cache is None:
            cache = self._ptr_cache = {}
        if cache_key not in cache:
            buckets = {}
            for e in self.entities:
                if e is None or e.kind != kind:
                    continue
                ref = getattr(e, attr, None)
                if ref is None or not isinstance(ref, int) or ref < 0:
                    continue
                buckets.setdefault(ref, []).append(e)
            cache[cache_key] = buckets
        return cache[cache_key]

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
        """Faces of a shell.

        Primary source is the shell's face -> next chain. P29: official files
        sometimes omit that chain (samplemodel3 links only one face), so also
        collect every face whose own shell pointer references this shell.
        """
        out, seen = [], set()
        cur = self.e(shell.face)
        while cur is not None and cur.idx not in seen and cur.kind == 'face':
            seen.add(cur.idx)
            out.append(cur)
            cur = self.e(cur.next)
        for f in self._by_pointer('faces_by_shell', 'face', 'shell').get(
                shell.idx, ()):
            if f.idx not in seen:
                seen.add(f.idx)
                out.append(f)
        return out

    def coedges_of_loop(self, loop: Ent) -> List[Ent]:
        """Coedges of a loop (chain, plus pointer-backed stragglers).

        P29: official streams may omit the coedge next-chain; every coedge that
        points back at this loop (t9) belongs to it, so merge those in.
        """
        out, seen = [], set()
        cur = self.e(loop.coedge)
        while cur is not None and cur.idx not in seen and cur.kind == 'coedge':
            seen.add(cur.idx)
            out.append(cur)
            cur = self.e(cur.next)
        for ce in self._by_pointer('coedges_by_loop', 'coedge', 'loop').get(
                loop.idx, ()):
            if ce.idx not in seen:
                seen.add(ce.idx)
                out.append(ce)
        return out

    def loops_of_face(self, face: Ent) -> List[Ent]:
        """All loops of the face (outer + holes).

        Chain: face.loop then loop-record t4. P29: official streams may omit
        that chain, so also collect every loop whose own face pointer (t6)
        references this face - otherwise faces with inner loops are lost.
        """
        out, seen = [], set()
        cur = self.e(face.loop)
        while cur is not None and cur.kind == 'loop' and cur.idx not in seen:
            seen.add(cur.idx)
            out.append(cur)
            try:
                nxt = cur.record.tokens[4]
            except Exception:
                break
            cur = self.e(nxt.value) if nxt.kind == 'ptr' else None
        for lp in self._by_pointer('loops_by_face', 'loop', 'face').get(
                face.idx, ()):
            if lp.idx not in seen:
                seen.add(lp.idx)
                out.append(lp)
        return out

    def body_faces(self, body: Ent) -> List[Ent]:
        """Faces of a body.

        P29: official streams are inconsistent here - samplemodel3 links only
        12 of its 111 faces through shell/face chains. For a SINGLE-body model
        every face belongs to that body by definition, so that is authoritative;
        multi-body models keep the shell traversal.
        """
        bodies = self.of_kind('body')
        if len(bodies) == 1:
            return self.of_kind('face')
        lump = self.e(body.lump)
        shell = self.e(lump.shell) if lump is not None else None
        if shell is not None:
            faces = self.faces_of_shell(shell)
            if faces:
                return faces
        return []

    # -- geometry ------------------------------------------------------------
    def point_of_vertex(self, vertex: Ent):
        p = self.e(vertex.point)
        return p.origin if p is not None else None

    def edge_endpoints(self, edge: Ent):
        """Endpoints of an edge (P29/P37 precedence).

        1. straight curve + the EDGE's trimmed range (pstart/pend) - the curve's
           own t0/t1 can be a wild global range (observed -100/100 on official
           files, which put endpoints 100 m away from the real geometry);
        2. the edge's vertices (v1/v2 -> vertex.point), which official files
           always carry even when the curve range is missing;
        3. the curve's t0/t1 as a last resort.
        Returns None only when nothing resolves (callers then skip the edge).
        """
        c = (self.e(edge.curve)
             if getattr(edge, 'curve', None) is not None and edge.curve >= 0
             else None)
        straight = (c is not None and c.kind == 'straight'
                    and c.origin is not None and c.direction is not None)
        t0 = getattr(edge, 'pstart', None)
        t1 = getattr(edge, 'pend', None)
        v1 = self.e(edge.v1) if getattr(edge, 'v1', None) is not None else None
        v2 = self.e(edge.v2) if getattr(edge, 'v2', None) is not None else None
        p1 = self.point_of_vertex(v1) if v1 is not None else None
        p2 = self.point_of_vertex(v2) if v2 is not None else None
        cp = None
        if straight and t0 is not None and t1 is not None:
            cp = (vadd(c.origin, vscale(c.direction, t0)),
                  vadd(c.origin, vscale(c.direction, t1)))
        if cp is not None and p1 is not None and p2 is not None:
            # P45 cross-validation: the vertex points come from the independent
            # point table, while the parameter range depends on the curve being
            # the one this edge was trimmed from.  On the official samples the
            # two disagree for ~19% of straight edges (573/3013 in samplemodel2,
            # 80/104 in samplemodel3) and every case where one of them lands
            # outside the model bbox is the CURVE-derived pair (294 vs 0), so a
            # gross disagreement means the range belongs to another trimming of
            # the same line - trust the vertices then.
            scale = max(1.0, vlen(vsub(cp[0], cp[1])),
                        vlen(vsub(p1, p2)))
            if (vlen(vsub(cp[0], p1)) > 1e-4 * scale
                    or vlen(vsub(cp[1], p2)) > 1e-4 * scale):
                return p1, p2
            return cp
        if cp is not None:
            return cp
        if p1 is not None and p2 is not None:
            return p1, p2
        if straight and c.t0 is not None and c.t1 is not None:
            return (vadd(c.origin, vscale(c.direction, c.t0)),
                    vadd(c.origin, vscale(c.direction, c.t1)))
        return None

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

    def _walk_gap(self, endpoints, rel_tol: float = 0.02):
        """R17/P99: rebuild a closed ring by GEOMETRY when the chain does not.

        Measured on the official library: the stashed next-chain plus endpoints
        can miss closure by a real gap (0.008 on model 8 face 3455, ~1% of the
        loop), which is far beyond the 1e-6 vertex tolerance, so both ordered
        walks give up and the face ends up with no polygon at all.  This walk
        ignores the chain order and just connects coincident endpoints, with a
        tolerance scaled to the loop size - it is a LAST-resort fallback, only
        reached after the ordered walks fail.
        """
        segs = [tuple(e) for e in endpoints]
        if len(segs) < 3:
            return None
        xs = [p[i] for e in segs for p in e for i in (0,)]
        ys = [p[1] for e in segs for p in e]
        zs = [p[2] for e in segs for p in e]
        diag = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        tol = max(1e-9, diag * rel_tol)
        used = [False] * len(segs)
        a, b = segs[0]
        used[0] = True
        poly = [a]
        cur = b
        while True:
            if vlen(vsub(cur, poly[0])) <= tol and len(poly) >= 3:
                return poly
            nxt = None
            for i, (p, q) in enumerate(segs):
                if used[i]:
                    continue
                if vlen(vsub(cur, p)) <= tol:
                    nxt = (i, p, q)
                    break
                if vlen(vsub(cur, q)) <= tol:
                    nxt = (i, q, p)
                    break
            if nxt is None:
                return None
            used[nxt[0]] = True
            poly.append(nxt[1])
            cur = nxt[2]

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
        # R17/P99: the ordered walks can fail on a REAL gap (see _walk_gap);
        # chain by geometry instead of giving the face no polygon at all.
        return self._walk_gap(endpoints)

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
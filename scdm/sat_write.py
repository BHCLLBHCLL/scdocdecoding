"""SAT text writer: generate ACIS SAT format from extracted topology.

The SAT text format is ACIS's canonical exchange format; each entity is one
line ending in '#', with $N entity references (0-based stream indices).
The official SabSatConverter.exe converts SAT -> SAB byte-faithfully,
giving an official-reader-compatible SAB without reimplementing the
binary interning/ordering rules.

Field grammar (derived from box.scdoc via SabSatConverter round-trip):
  body $A -1 -1 $-1 0 $L $-1 $-1 T bx1 by1 bz1 bx2 by2 bz2 #
  lump $-1 -1 -1 $-1 $-1 $SH $BD T ... #
  shell $-1 -1 -1 $-1 $-1 $-1 $F $-1 $L T ... #
  face $A -1 -1 $-1 $NEXT $LOOP $SHELL $-1 $SURF forward|reversed single T
       bbox T umin umax vmin vmax #
  loop $-1 -1 -1 $-1 $-1 $C $FACE T bbox periphery $SURF F #  (or 'unknown #')
  plane-surface $-1 -1 -1 $-1 o3 n3 u3 forward_v I I I I #
  coedge $-1 -1 -1 $-1 $NEXT $PREV $PARTNER $EDGE fwd|rev $LOOP $-1 #
  edge $A -1 -1 $-1 $V1 0 $V2 len $C $CURVE forward @7 unknown T bbox #
  vertex $-1 -1 -1 $-1 $EDGE $POINT #
  point $-1 -1 -1 $-1 x y z #
  straight-curve $-1 -1 -1 $-1 p3 d3 F 0 F len #
  attribs: see _sat_attrib helpers
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from scdm import kernel as K
from scdm.scdoc_write import _extract_solid, _cyl_info


def _num(v: float) -> str:
    """SAT number format: shortest representation with full double precision."""
    s = repr(float(v))
    if s.endswith('.0'):
        s = s[:-2]
    return s


def _str(s: str) -> str:
    return '@%d %s' % (len(s), s)


class _SatBuilder:
    def __init__(self):
        self.lines: List[str] = []
        self.refs: dict = {}   # logical key -> entity index

    def add(self, text: str, key=None) -> int:
        idx = len(self.lines)
        self.lines.append(text)
        if key is not None:
            self.refs[key] = idx
        return idx

    def r(self, key) -> str:
        """Reference string for a key ('$N'), or '$-1' when absent."""
        idx = self.refs.get(key)
        return '$-1' if idx is None else '$%d' % idx

    def text(self, product_id: str = 'X' * 77, date: str = 'Mon Jan  1 00:00:00 2026') -> str:
        head = [
            '2900 0 1 0',
            '10 SpaceClaim 12 ACIS 29.0 NT 24 %s' % date,
            '1000 1e-08 1e-10',
            'T @%d %s' % (len(product_id), product_id),
        ]
        return '\n'.join(head + self.lines + ['End-of-ACIS-data']) + '\n'


def write_sat(kdoc, name: str = 'design') -> str:
    """Generate SAT text for the session's planar bodies and plain cylinders."""
    items = []
    colors = []
    for body in kdoc.bodies:
        sols = K.explore(body.shape, 'solid') or [body.shape]
        for s in sols:
            info = _cyl_info(s)
            if info is not None:
                items.append(('cyl', info))
            else:
                items.append(('planar',) + _extract_solid(s))
            colors.append(tuple(getattr(body, 'color', None) or (0.745, 0.902, 0.961)))
    if not items:
        raise ValueError('no bodies to write')

    b = _SatBuilder()
    doc_id = 23  # first NominalBodyDef id (matches official document.xml)

    for bi, it in enumerate(items):
        if it[0] == 'planar':
            _sat_planar_body(b, it, colors[bi], bi, doc_id)
        else:
            _sat_cyl_body(b, it, colors[bi], bi, doc_id)
        doc_id += 60

    return b.text()


def _sat_cyl_body(b: _SatBuilder, it, color, bi: int, doc_id: int):
    """Cylinder as cone-surface + 2 planes + seam edge (official cyl layout)."""
    info = it[1]
    R, h = info['R'], info['h']
    org, axis = info['origin'], info['axis']
    mu = info['major_unit']
    cap_a, cap_b = info['cap_a'], info['cap_b']
    lo, hi = info['bbox']
    sbox = ' '.join(_num(v) for v in lo + hi)

    # emission order (simple segment order; SabSatConverter re-saves in
    # official order): body, name, lump, pname, shell,
    # side-face block, top-face block, bottom-face block, edges, verts, curves, points
    i_body = len(b.lines)
    i_body_name = i_body + 1
    i_lump = i_body + 2
    i_body_pname = i_body + 3
    i_shell = i_body + 4
    idx = i_shell + 1
    # faces: side(0), top(1), bottom(2) — each: face, name, rgb, loop, surf
    face_ids, face_name_ids, face_rgb_ids, loop_ids, surf_ids = [], [], [], [], []
    for _ in range(3):
        face_ids.append(idx); idx += 1
        face_name_ids.append(idx); idx += 1
        face_rgb_ids.append(idx); idx += 1
        loop_ids.append(idx); idx += 1
        surf_ids.append(idx); idx += 1
    # coedges: side loop 4 (top-circle, seam-down, bottom-circle, seam-up),
    #          top cap 1, bottom cap 1  => 6 total
    ce_side = list(range(idx, idx + 4)); idx += 4
    ce_top = idx; idx += 1
    ce_bot = idx; idx += 1
    # edges: bottom-circle(0), top-circle(1), seam(2)
    edge_ids = list(range(idx, idx + 3)); idx += 3
    edge_name_ids = list(range(idx, idx + 3)); idx += 3
    vertex_ids = [idx, idx + 1]; idx += 2
    point_ids = [idx, idx + 1]; idx += 2
    curve_ids = list(range(idx, idx + 4)); idx += 4  # 2 ellipse + straight + ...

    vbot = tuple(cap_a[k] + mu[k] * R for k in range(3))
    vtop = tuple(cap_b[k] + mu[k] * R for k in range(3))

    def circ_bbox(center):
        ex = R * math.sqrt(max(0.0, 1.0 - axis[0] * axis[0]))
        ey = R * math.sqrt(max(0.0, 1.0 - axis[1] * axis[1]))
        ez = R * math.sqrt(max(0.0, 1.0 - axis[2] * axis[2]))
        return ([center[0] - ex, center[1] - ey, center[2] - ez],
                [center[0] + ex, center[1] + ey, center[2] + ez])

    b.add('body $%d -1 -1 $-1 0 $%d $-1 $-1 T %s #'
          % (i_body_name, i_lump, sbox))
    b.add(_sat_name_attrib('$%d' % i_body_pname, '$%d' % i_body,
                           '0:%d' % doc_id))
    b.add('lump $-1 -1 -1 $-1 $-1 $%d $%d T %s #'
          % (i_shell, i_body, sbox))
    b.add(_sat_pname_attrib('$%d' % i_body_name, '$%d' % i_body))
    b.add('shell $-1 -1 -1 $-1 $-1 $-1 $%d $-1 $%d T %s #'
          % (face_ids[0], i_lump, sbox))

    # --- face blocks: side, top, bottom ---
    # side (cone)
    fb_lo, fb_hi = circ_bbox(cap_a)
    fb_hi = [max(fb_hi[k], hi[k]) for k in range(3)]
    fb_lo = [min(fb_lo[k], lo[k]) for k in range(3)]
    fbox = ' '.join(_num(v) for v in fb_lo + fb_hi)
    uv_side = (0.0, h / R, -math.pi, math.pi)
    b.add('face $%d -1 -1 $-1 $%d $%d $%d $-1 $%d forward single T %s T %s #'
          % (face_name_ids[0], face_ids[1], loop_ids[0], i_shell, surf_ids[0],
             fbox, ' '.join(_num(v) for v in uv_side)))
    b.add(_sat_name_attrib('$%d' % face_rgb_ids[0], '$%d' % face_ids[0],
                           '0:%d' % (27 + 60 * bi)))
    b.add(_sat_rgb_attrib('$%d' % face_name_ids[0], '$%d' % face_ids[0], color))
    b.add('loop $-1 -1 -1 $-1 $-1 $%d $%d T %s unknown #'
          % (ce_side[0], face_ids[0], fbox))
    b.add('cone-surface $-1 -1 -1 $-1 %s %s %s 1 I I %s 1 %s reversed I I I I #'
          % (' '.join(_num(v) for v in org),
             ' '.join(_num(-axis[k]) for k in range(3)),
             ' '.join(_num(mu[k] * R) for k in range(3)),
             _num(0.0), _num(R)))

    # top (plane)
    tb_lo, tb_hi = circ_bbox(cap_b)
    tbox = ' '.join(_num(v) for v in tb_lo + tb_hi)
    b.add('face $%d -1 -1 $-1 $%d $%d $%d $-1 $%d forward single T %s T %s #'
          % (face_name_ids[1], face_ids[2], loop_ids[1], i_shell, surf_ids[1],
             tbox, '%s %s %s %s' % (_num(-R), _num(R), _num(-R), _num(R))))
    b.add(_sat_name_attrib('$%d' % face_rgb_ids[1], '$%d' % face_ids[1],
                           '0:%d' % (30 + 60 * bi)))
    b.add(_sat_rgb_attrib('$%d' % face_name_ids[1], '$%d' % face_ids[1], color))
    b.add('loop $-1 -1 -1 $-1 $-1 $%d $%d T %s unknown #'
          % (ce_top, face_ids[1], tbox))
    b.add('plane-surface $-1 -1 -1 $-1 %s %s %s forward_v I I I I #'
          % (' '.join(_num(v) for v in cap_b),
             ' '.join(_num(v) for v in axis),
             ' '.join(_num(v) for v in mu)))

    # bottom (plane)
    b.add('face $%d -1 -1 $-1 $-1 $%d $%d $-1 $%d reversed single T %s T %s #'
          % (face_name_ids[2], loop_ids[2], i_shell, surf_ids[2],
             tbox.replace(tbox, ' '.join(_num(v) for v in tb_lo + tb_hi)),
             '%s %s %s %s' % (_num(-R), _num(R), _num(-R), _num(R))))
    b.add(_sat_name_attrib('$%d' % face_rgb_ids[2], '$%d' % face_ids[2],
                           '0:%d' % (33 + 60 * bi)))
    b.add(_sat_rgb_attrib('$%d' % face_name_ids[2], '$%d' % face_ids[2], color))
    b.add('loop $-1 -1 -1 $-1 $-1 $%d $%d T %s unknown #'
          % (ce_bot, face_ids[2], ' '.join(_num(v) for v in circ_bbox(cap_a)[0] + circ_bbox(cap_a)[1])))
    b.add('plane-surface $-1 -1 -1 $-1 %s %s %s forward_v I I I I #'
          % (' '.join(_num(v) for v in cap_a),
             ' '.join(_num(-axis[k]) for k in range(3)),
             ' '.join(_num(v) for v in mu)))

    # --- coedges (6) ---
    # side loop: top-circle(FA), seam-down(FA), bottom-circle(FB), seam-up(FB)
    side_specs = [
        (ce_side[1], ce_side[3], ce_top, edge_ids[1], 'forward'),
        (ce_side[2], ce_side[0], ce_side[3], edge_ids[2], 'forward'),
        (ce_side[3], ce_side[1], ce_bot, edge_ids[0], 'reversed'),
        (ce_side[0], ce_side[2], ce_side[1], edge_ids[2], 'reversed'),
    ]
    for i, (nxt, prv, par, e, sense) in enumerate(side_specs):
        b.add('coedge $-1 -1 -1 $-1 $%d $%d $%d $%d %s $%d $-1 #'
              % (nxt, prv, par, e, sense, loop_ids[0]))
    # top cap: partner = side's top-circle coedge (ce_side[0])
    b.add('coedge $-1 -1 -1 $-1 $%d $%d $%d $%d reversed $%d $-1 #'
          % (ce_top, ce_top, ce_side[0], edge_ids[1], loop_ids[1]))
    # bottom cap
    b.add('coedge $-1 -1 -1 $-1 $%d $%d $%d $%d forward $%d $-1 #'
          % (ce_bot, ce_bot, ce_side[2], edge_ids[0], loop_ids[2]))

    # --- edges + attribs ---
    bbot_lo, bbot_hi = circ_bbox(cap_a)
    btop_lo, btop_hi = circ_bbox(cap_b)
    bbox_bot = ' '.join(_num(v) for v in bbot_lo + bbot_hi)
    bbox_top = ' '.join(_num(v) for v in btop_lo + btop_hi)
    bbox_seam = ' '.join(_num(min(vbot[k], vtop[k])) + ' ' for k in range(0)) or \
        ' '.join(_num(v) for v in
                 [min(vbot[k], vtop[k]) for k in range(3)] +
                 [max(vbot[k], vtop[k]) for k in range(3)])
    # bottom circle (v-params 0..2pi, same vertex both ends)
    b.add('edge $%d -1 -1 $-1 $%d 0 $%d %s $%d $%d forward @7 unknown T %s #'
          % (edge_name_ids[0], vertex_ids[0], vertex_ids[0],
             _num(2 * math.pi), ce_side[2], curve_ids[0], bbox_bot))
    b.add(_sat_name_attrib('$-1', '$%d' % edge_ids[0],
                           '0:%d' % (45 + 60 * bi)))
    # top circle
    b.add('edge $%d -1 -1 $-1 $%d 0 $%d %s $%d $%d forward @7 unknown T %s #'
          % (edge_name_ids[1], vertex_ids[1], vertex_ids[1],
             _num(2 * math.pi), ce_side[0], curve_ids[1], bbox_top))
    b.add(_sat_name_attrib('$-1', '$%d' % edge_ids[1],
                           '0:%d' % (48 + 60 * bi)))
    # seam
    b.add('edge $%d -1 -1 $-1 $%d 0 $%d %s $%d $%d forward @7 unknown T %s #'
          % (edge_name_ids[2], vertex_ids[0], vertex_ids[1],
             _num(h), ce_side[1], curve_ids[2], bbox_seam))
    b.add(_sat_name_attrib('$-1', '$%d' % edge_ids[2],
                           '0:%d' % (51 + 60 * bi)))

    # --- vertices + points ---
    b.add('vertex $-1 -1 -1 $-1 $%d $%d #' % (edge_ids[2], point_ids[0]))
    b.add('vertex $-1 -1 -1 $-1 $%d $%d #' % (edge_ids[1], point_ids[1]))
    b.add('point $-1 -1 -1 $-1 %s #' % ' '.join(_num(v) for v in vbot))
    b.add('point $-1 -1 -1 $-1 %s #' % ' '.join(_num(v) for v in vtop))

    # --- curves: bottom ellipse, top ellipse, seam straight ---
    b.add('ellipse-curve $-1 -1 -1 $-1 %s %s %s 1 I I #'
          % (' '.join(_num(v) for v in cap_a),
             ' '.join(_num(v) for v in axis),
             ' '.join(_num(mu[k] * R) for k in range(3))))
    b.add('ellipse-curve $-1 -1 -1 $-1 %s %s %s 1 I I #'
          % (' '.join(_num(v) for v in cap_b),
             ' '.join(_num(v) for v in axis),
             ' '.join(_num(mu[k] * R) for k in range(3))))
    d = [vtop[k] - vbot[k] for k in range(3)]
    L = math.sqrt(sum(x * x for x in d)) or 1.0
    b.add('straight-curve $-1 -1 -1 $-1 %s %s F 0 F %s #'
          % (' '.join(_num(v) for v in vbot),
             ' '.join(_num(v / L) for v in d), _num(h)))


def _sat_planar_body(b: _SatBuilder, it, color, bi: int, doc_id: int):
    verts, edges, faces = it[1], it[2], it[3]
    n_f, n_e, n_v = len(faces), len(edges), len(verts)

    def bbox_of(idxs):
        pts = [verts[i] for i in idxs]
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        return lo, hi

    slo, shi = bbox_of(range(n_v))
    sbox = ' '.join(_num(v) for v in slo + shi)

    # --- entity indices (must match the actual emission order below) ---
    # Emission order: body, name, lump, pname, shell,
    #   per face: face, name-attrib, rgb-attrib, loop, surface, ring coedges
    #   then: edge + edge-name-attrib (interleaved), vertices, points, curves
    i_body = len(b.lines)
    i_body_name = i_body + 1
    i_lump = i_body + 2
    i_body_pname = i_body + 3
    i_shell = i_body + 4
    idx = i_shell + 1
    face_ids, face_name_ids, face_rgb_ids = [], [], []
    loop_ids, surf_ids = [], []
    ce_index = {}
    for fi, f in enumerate(faces):
        face_ids.append(idx); idx += 1
        face_name_ids.append(idx); idx += 1
        face_rgb_ids.append(idx); idx += 1
        loop_ids.append(idx); idx += 1
        surf_ids.append(idx); idx += 1
        for k in range(len(f['loop'])):
            ce_index[(fi, k)] = idx
            idx += 1
    edge_ids, edge_name_ids = [], []
    for _ in range(n_e):
        edge_ids.append(idx); idx += 1
        edge_name_ids.append(idx); idx += 1
    vertex_ids = list(range(idx, idx + n_v)); idx += n_v
    point_ids = list(range(idx, idx + n_v)); idx += n_v
    curve_ids = list(range(idx, idx + n_e)); idx += n_e

    edge_coedges = [[] for _ in range(n_e)]  # edge local idx -> [(fi,k,gid)]

    # map loop-corner pairs to edge local index (same as scdoc_write)
    emap = {}
    for ei, (a, c) in enumerate(edges):
        emap[(min(a, c), max(a, c))] = ei
    for fi, f in enumerate(faces):
        loop = f['loop']
        n = len(loop)
        for k in range(n):
            a, c = loop[k], loop[(k + 1) % n]
            ei = emap[(min(a, c), max(a, c))]
            edge_coedges[ei].append((fi, k, ce_index[(fi, k)]))

    # coedge partner: two coedges per edge
    partner = {}
    for ei, ces in enumerate(edge_coedges):
        if len(ces) == 2:
            partner[ces[0][2]] = ces[1][2]
            partner[ces[1][2]] = ces[0][2]

    def coedge_ring(fi):
        """coedge ids of face fi's loop in order."""
        return [ce_index[(fi, k)] for k in range(len(faces[fi]['loop']))]

    # --- emit body block ---
    b.add('body $%d -1 -1 $-1 0 $%d $-1 $-1 T %s #' % (i_body_name, i_lump, sbox))
    b.add(_sat_name_attrib(next_ref='$%d' % i_body_pname, owner_ref='$%d' % i_body,
                           value='0:%d' % doc_id))
    b.add('lump $-1 -1 -1 $-1 $-1 $%d $%d T %s #' % (i_shell, i_body, sbox))
    b.add(_sat_pname_attrib(prev_ref='$%d' % i_body_name, owner_ref='$%d' % i_body))
    b.add('shell $-1 -1 -1 $-1 $-1 $-1 $%d $-1 $%d T %s #'
          % (face_ids[0], i_lump, sbox))

    # --- emit faces + attribs + loops + surfaces + coedges + edges ---
    # Simple emission: face, name, rgb, loop, surface, coedges(ring),
    # then edge blocks. SabSatConverter preserves order.
    for fi, f in enumerate(faces):
        loop = f['loop']
        n = len(loop)
        flo, fhi = bbox_of(loop)
        fbox = ' '.join(_num(v) for v in flo + fhi)
        nx = face_ids[fi + 1] if fi + 1 < n_f else -1
        sense = 'forward' if f.get('sense', 1) >= 0 else 'reversed'
        uv = f.get('uv', (-0.005, 0.005, -0.005, 0.005))
        uv_s = ' '.join(_num(v) for v in uv)
        b.add('face $%d -1 -1 $-1 $%d $%d $%d $-1 $%d %s single T %s T %s #'
              % (face_name_ids[fi], nx, loop_ids[fi], i_shell, surf_ids[fi],
                 sense, fbox, uv_s))
        b.add(_sat_name_attrib(next_ref='$%d' % face_rgb_ids[fi],
                               owner_ref='$%d' % face_ids[fi],
                               value='0:%d' % (27 + 3 * fi + 60 * bi)))
        b.add(_sat_rgb_attrib(prev_ref='$%d' % face_name_ids[fi],
                              owner_ref='$%d' % face_ids[fi], color=color))
        # loop
        ltype = 'periphery $%d F' % surf_ids[fi] if fi == 0 else 'unknown'
        b.add('loop $-1 -1 -1 $-1 $-1 $%d $%d T %s %s #'
              % (ce_index[(fi, 0)], face_ids[fi], fbox, ltype))
        # surface (plane)
        c, nrm = f['center'], f['normal']
        u = f.get('xdir') or _ortho(nrm)
        b.add('plane-surface $-1 -1 -1 $-1 %s %s %s forward_v I I I I #'
              % (' '.join(_num(v) for v in c),
                 ' '.join(_num(v) for v in nrm),
                 ' '.join(_num(v) for v in u)))
        # coedges in ring order
        ring = coedge_ring(fi)
        for k, gid in enumerate(ring):
            a, c2 = loop[k], loop[(k + 1) % n]
            ei = emap[(min(a, c2), max(a, c2))]
            nxt = ring[(k + 1) % n]
            prv = ring[(k - 1) % n]
            par = partner.get(gid, -1)
            # sense: coedge is forward when its loop direction matches the
            # stored edge direction
            fwd = 'forward' if edges[ei][0] == a else 'reversed'
            b.add('coedge $-1 -1 -1 $-1 $%d $%d $%d $%d %s $%d $-1 #'
                  % (nxt, prv, par, edge_ids[ei], fwd, loop_ids[fi]))

    # edges + name attribs
    for ei, (v1, v2) in enumerate(edges):
        p1, p2 = verts[v1], verts[v2]
        length = math.dist(p1, p2)
        elo = [min(p1[k], p2[k]) for k in range(3)]
        ehi = [max(p1[k], p2[k]) for k in range(3)]
        ebox = ' '.join(_num(v) for v in elo + ehi)
        first_ce = edge_coedges[ei][0][2] if edge_coedges[ei] else -1
        b.add('edge $%d -1 -1 $-1 $%d 0 $%d %s $%d $%d forward @7 unknown T %s #'
              % (edge_name_ids[ei], vertex_ids[v1], vertex_ids[v2],
                 _num(length), first_ce, curve_ids[ei], ebox))
        b.add(_sat_name_attrib(next_ref='$-1', prev_ref='$-1',
                               owner_ref='$%d' % edge_ids[ei],
                               value='0:%d' % (45 + 3 * ei + 60 * bi)))
    # vertices + points
    for vi in range(n_v):
        inc = -1
        for ei, (a, c) in enumerate(edges):
            if a == vi or c == vi:
                inc = edge_ids[ei]
                break
        b.add('vertex $-1 -1 -1 $-1 $%d $%d #' % (inc, point_ids[vi]))
    for vi in range(n_v):
        p = verts[vi]
        b.add('point $-1 -1 -1 $-1 %s #'
              % ' '.join(_num(v) for v in p))
    # curves
    for ei, (v1, v2) in enumerate(edges):
        p1, p2 = verts[v1], verts[v2]
        d = [p2[k] - p1[k] for k in range(3)]
        L = math.sqrt(sum(x * x for x in d)) or 1.0
        b.add('straight-curve $-1 -1 -1 $-1 %s %s F 0 F %s #'
              % (' '.join(_num(v) for v in p1),
                 ' '.join(_num(v / L) for v in d),
                 _num(L)))


def _ortho(n):
    a = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    m = (n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2],
         n[0] * a[1] - n[1] * a[0])
    L = math.sqrt(sum(x * x for x in m)) or 1.0
    return (m[0] / L, m[1] / L, m[2] / L)


_ATTR_INTS = '2 1 1 1 1 1 1 1 1 1 1 1 1 1 0 1 1 1'
_RGB_INTS = '2 1 2 1 1 1 1 1 1 1 1 1 1 1 0 1 1 1'


def _sat_name_attrib(next_ref, owner_ref, value, prev_ref='$-1'):
    return ('string_attrib-name_attrib-gen-attrib $-1 -1 %s %s %s %s %s %s #'
            % (next_ref, prev_ref, owner_ref, _ATTR_INTS,
               _str('ATTRIB_XACIS_NAME'), _str(value)))


def _sat_pname_attrib(prev_ref, owner_ref):
    return ('string_attrib-name_attrib-gen-attrib $-1 -1 $-1 %s %s %s %s %s #'
            % (prev_ref, owner_ref, _ATTR_INTS,
               _str('ATTRIB_XACIS_PNAME'), _str('SC:0')))


def _sat_rgb_attrib(prev_ref, owner_ref, color):
    return ('rgb_color-st-attrib $-1 -1 $-1 %s %s %s %s #'
            % (prev_ref, owner_ref, _RGB_INTS,
               ' '.join(_num(c) for c in color)))

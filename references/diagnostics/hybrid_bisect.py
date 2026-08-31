# -*- coding: utf-8 -*-
"""Hybrid experiment: official box SAB stream with OUR records substituted in
(ptr rebound to the official stream's logical indices via semantic pairing).

usage: python _hybrid.py <comma-separated classes to replace>
  e.g.  python _hybrid.py face,loop
"""
import sys
import struct
import zipfile as zf

from scdoc_parser import sab as sab_mod

REPLACE = set(sys.argv[1].split(',')) if len(sys.argv) > 1 else set()

offi_path = 'box.scdoc'
ours_path = 'verify_box.scdoc'

data_o = zf.ZipFile(offi_path).read('SpaceClaim/Geometry/part1bodies.sab')
data_u = zf.ZipFile(ours_path).read('SpaceClaim/Geometry/part1bodies.sab')
sfo = sab_mod.tokenize(data_o)
sfu = sab_mod.tokenize(data_u)
ro, ru = sfo.records, sfu.records

T_REC, T_CHAIN, T_TERM, T_ID = 0x0D, 0x0E, 0x11, 0x25
T_PTR, T_INT, T_DBL, T_STR = 0x0C, 0x04, 0x06, 0x07
T_V3, T_V3B, TA, TB, T15 = 0x13, 0x14, 0x0A, 0x0B, 0x15
KB = {'ptr': T_PTR, 'int': T_INT, 'double': T_DBL, 'string': T_STR,
      'vec3': T_V3, 'vec3b': T_V3B, 'flag_a': TA, 'flag_b': TB, 'int15': T15}


def kind_group(recs):
    m = {}
    for i, r in enumerate(recs):
        m.setdefault(r.kind, []).append((i, r))
    return m


def plane_key_surf(r):
    n = r.tokens[5].value
    o = r.tokens[4].value
    if not isinstance(n, tuple):
        raise RuntimeError('DEBUG %s tokens=%r' % (r.kind, [(t.kind, t.value) for t in r.tokens]))
    off = round(sum(a * b for a, b in zip(n, o)), 6)
    sn = tuple(round(v, 4) for v in n)
    return ('p', off, sn if sn[0] >= 0 else tuple(-v for v in sn))


def plane_key_face(r, recs):
    return plane_key_surf(recs[r.tokens[8].value])


def edge_key(r):
    a = tuple(round(v, 6) for v in r.tokens[13].value)
    b = tuple(round(v, 6) for v in r.tokens[14].value)
    return tuple(sorted([a, b]))


def point_key(r):
    return tuple(round(v, 6) for v in r.tokens[4].value)


go, gu = kind_group(ro), kind_group(ru)


def pair(kind, keyfn):
    """map our record idx -> official record idx by geometry key"""
    mo = {keyfn(r): i for i, r in go.get(kind, [])}
    out = {}
    for i, r in gu.get(kind, []):
        k = keyfn(r)
        if k in mo:
            out[i] = mo[k]
    return out


# semantic pairing: our record idx -> official record idx (per kind)
pair_map = {}
pair_map.update(pair('plane', plane_key_surf))
pair_map.update(pair('edge', edge_key))
pair_map.update(pair('point', point_key))
# faces pair via their surface's plane key
for u_i, u_r in gu.get('face', []):
    ku = plane_key_surf(ru[u_r.tokens[8].value])
    for o_i, o_r in go.get('face', []):
        if plane_key_surf(ro[o_r.tokens[8].value]) == ku:
            pair_map[u_i] = o_i
            break
# loops via face pairing
face_pair = {u: o for u, o in pair_map.items() if ro[o].kind == 'face'}
loop_by_face_o = {r.tokens[6].value: i for i, r in go.get('loop', [])}
for i, r in gu.get('loop', []):
    owner_u = r.tokens[6].value
    if owner_u in face_pair:
        face_o = face_pair[owner_u]
        if face_o in loop_by_face_o:
            pair_map[i] = loop_by_face_o[face_o]
# coedges via (loop pair, edge pair)
loop_pair = {u: o for u, o in pair_map.items() if ro[o].kind == 'loop'}
coedge_by_le_o = {}
for i, r in go.get('coedge', []):
    t = [x.value for x in r.tokens]
    coedge_by_le_o[(t[9], t[7])] = i
for i, r in gu.get('coedge', []):
    t = [x.value for x in r.tokens]
    lp, ep = t[9], t[7]
    if lp in loop_pair and ep in pair_map:
        key = (loop_pair[lp], pair_map[ep])
        if key in coedge_by_le_o:
            pair_map[i] = coedge_by_le_o[key]
# curves via edge pairing (edge's curve ptr)
curve_by_edge_o = {r.tokens[9].value: i for i, r in go.get('curve', [])}
for i, r in gu.get('curve', []):
    pass
for i, r in gu.get('edge', []):
    cu = r.tokens[9].value
    if i in pair_map and cu < len(ru):
        co = ro[pair_map[i]].tokens[9].value
        pair_map[cu] = co
# vertices via edge pairing (edge's vertex ptrs)
for i, r in gu.get('edge', []):
    if i not in pair_map:
        continue
    co = ro[pair_map[i]]
    for tok_u, tok_o in ((r.tokens[4], co.tokens[4]), (r.tokens[6], co.tokens[6])):
        if tok_u.kind == 'ptr' and tok_u.value >= 0:
            pair_map[tok_u.value] = tok_o.value

print('paired records:', len(pair_map), '/', len(ru))




def _end_marker(data):
    # 'End-of-ACIS-data' record: T_RECORD + len 16 + name (no id)
    idx = data.rfind(b'End-of-ACIS-data')
    return idx - 2

def serialize(recs_list, seen=None, remap=None):
    """serialize a record list; ptr values pass through remap if given"""
    out = bytearray()
    seen = seen if seen is not None else {}

    OFFICIAL_IDS = {'body': 1, 'string_attrib': 2, 'name_attrib': 3, 'gen': 4,
                    'attrib': 5, 'lump': 7, 'shell': 9, 'face': 10, 'loop': 11,
                    'plane': 12, 'surface': 13, 'rgb_color': 14, 'st': 15,
                    'coedge': 16, 'edge': 17, 'vertex': 18, 'straight': 19,
                    'curve': 20, 'point': 21, 'wstring_attrib': 8, 'cone': 14,
                    'ellipse': 20}

    def intern(name):
        if name in seen:
            return seen[name], True
        nid = OFFICIAL_IDS.get(name)
        if nid is None:
            nid = max([v for v in seen.values()] or [0]) + 1
        seen[name] = nid
        return nid, False

    def tok_bytes(t, rmp):
        b = KB[t.kind]
        if t.kind in ('ptr', 'int', 'int15'):
            v = t.value
            if t.kind == 'ptr' and v >= 0 and rmp is not None:
                v = rmp.get(v, v)
            return bytes([b]) + struct.pack('<i', int(v))
        if t.kind == 'double':
            return bytes([b]) + struct.pack('<d', float(t.value))
        if t.kind == 'string':
            raw = str(t.value).encode('latin-1')
            return bytes([b, len(raw)]) + raw
        if t.kind in ('vec3', 'vec3b'):
            return bytes([b]) + struct.pack('<3d', *t.value)
        if t.kind in ('flag_a', 'flag_b'):
            return bytes([b])
        raise ValueError(t.kind)

    for r in recs_list:
        for cname, _cid in r.chain:
            cid, known = intern(cname)
            if known:
                out += bytes([T_CHAIN, 5, T_ID]) + struct.pack('<i', cid)
            else:
                out += bytes([T_CHAIN, len(cname) + 5]) + cname.encode('latin-1')
                out += bytes([T_ID]) + struct.pack('<i', cid)
        cid, known = intern(r.name)
        if known:
            out += bytes([T_REC, 5, T_ID]) + struct.pack('<i', cid)
        else:
            out += bytes([T_REC, len(r.name) + 5]) + r.name.encode('latin-1')
            out += bytes([T_ID]) + struct.pack('<i', cid)
        for t in r.tokens:
            out += tok_bytes(t, remap)
        out += bytes([T_TERM])
    return bytes(out)


# hybrid stream: official records, but for classes in REPLACE use OUR record
# (tokens), keeping official record identity; ptr values inside our tokens are
# remapped our-idx -> official-idx via pair_map.
head_end = ro[0].offset
out = bytearray(data_o[:head_end])
seen_global = {}
for i, r in enumerate(ro):
    if r.kind in REPLACE and r.kind in gu:
        # find our record(s) of same kind (single-body files pair 1:1)
        ours_i = None
        for u_idx, o_idx in pair_map.items():
            if o_idx == i and ru[u_idx].kind == r.kind:
                ours_i = u_idx
                break
        if ours_i is not None:
            # rebuild the token list: topology ptrs via pair_map; any ptr NOT in
            # the map (e.g. attrib ptr) inherits the OFFICIAL same-position value
            r_o = ro[i]
            u_r = ru[ours_i]
            fixed = []
            for pos, t in enumerate(u_r.tokens):
                if t.kind == 'ptr' and t.value >= 0 and t.value in pair_map:
                    fixed.append((t.kind, pair_map[t.value]))
                elif t.kind == 'ptr' and t.value >= 0:
                    if pos < len(r_o.tokens) and r_o.tokens[pos].kind == 'ptr':
                        fixed.append((t.kind, r_o.tokens[pos].value))
                    else:
                        fixed.append((t.kind, -1))
                else:
                    fixed.append((t.kind, t.value))
            import copy as _copy
            patched = _copy.copy(u_r)
            patched.tokens = [type(t)(k, v, 0) for (k, v), t in
                              zip(fixed, u_r.tokens)]
            out += serialize([patched], seen_global)
        else:
            out += serialize([r], seen_global)
    else:
        out += serialize([r], seen_global)
tail_start = _end_marker(data_o)
out += data_o[tail_start:]

stream = bytes(out)
sf2 = sab_mod.tokenize(stream)
print('hybrid reparse ok, records:', len(sf2.records))

src = zf.ZipFile(offi_path)
o = zf.ZipFile('_hybrid.scdoc', 'w', zf.ZIP_DEFLATED)
for n in src.namelist():
    o.writestr(n, stream if n.endswith('part1bodies.sab') else src.read(n))
o.close()
print('hybrid written (replace=%s)' % (REPLACE or 'nothing'))

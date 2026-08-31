# -*- coding: utf-8 -*-
"""Definitive coedge t4/t5/t6 semantics: for each coedge in the golden refs,
compute partner (same edge, other loop), and the loop ring order (edges share
vertices), then check which pointer slot holds which role."""
import zipfile

from scdoc_parser import sab as sab_mod
from scdoc_parser.opc import parse_package


def analyze(path):
    pkg = parse_package(path)
    d = pkg.read(pkg.find_geometry()[0].name)
    sf = sab_mod.tokenize(d)
    recs = sf.records

    coedges = {}   # stream idx -> dict
    edges = {}     # edge stream idx -> (endpoint coords set)
    points = {}    # point idx -> coords
    for i, r in enumerate(recs):
        t = [x.value for x in r.tokens]
        k = r.kind
        if k == 'coedge':
            coedges[i] = {'loop': t[9], 'edge': t[7], 'ptrs': (t[4], t[5], t[6])}
        elif k == 'edge':
            a = tuple(round(v, 6) for v in t[13])
            b = tuple(round(v, 6) for v in t[14])
            edges[i] = tuple(sorted([a, b]))
        elif k == 'point':
            points[i] = tuple(round(v, 6) for v in t[4])

    # partner: same edge, other coedge
    by_edge = {}
    for i, c in coedges.items():
        by_edge.setdefault(c['edge'], []).append(i)
    partner = {}
    for e, cs in by_edge.items():
        if len(cs) == 2:
            partner[cs[0]] = cs[1]
            partner[cs[1]] = cs[0]

    # loop ring order via shared vertices: loop's coedges; edge endpoints;
    # consecutive edges share a vertex coordinate
    loops = {}
    for i, c in coedges.items():
        loops.setdefault(c['loop'], []).append(i)

    results = {'partner': 0, 'next': 0, 'prev': 0, 'unknown': 0}
    total = 0
    details = []
    for li, cs in loops.items():
        if len(cs) < 2:
            continue
        # geometric ring: order edges so consecutive share an endpoint
        edge_of = {ci: coedges[ci]['edge'] for ci in cs}
        ring = [cs[0]]
        used = {cs[0]}
        # walk: current edge's far endpoint connects to next edge
        while len(ring) < len(cs):
            cur_e = edges[edge_of[ring[-1]]]
            found = False
            for ci in cs:
                if ci in used:
                    continue
                e = edges[edge_of[ci]]
                if set(e) & set(cur_e):
                    ring.append(ci)
                    used.add(ci)
                    found = True
                    break
            if not found:
                break
        pos = {ci: k for k, ci in enumerate(ring)}
        n = len(ring)
        for ci in cs:
            total += 1
            p = partner.get(ci)
            nxt = ring[(pos[ci] + 1) % n]
            prv = ring[(pos[ci] - 1) % n]
            t4, t5, t6 = coedges[ci]['ptrs']
            got = set()
            roles = []
            for slot, val in (('t4', t4), ('t5', t5), ('t6', t6)):
                if val == p:
                    roles.append(slot + '=partner')
                elif val == nxt:
                    roles.append(slot + '=next')
                elif val == prv:
                    roles.append(slot + '=prev')
                else:
                    roles.append('%s=?(%d)' % (slot, val))
            key = tuple(sorted(r.split('=')[0] for r in roles if '=' in r and 'partner' in r or 'next' in r or 'prev' in r))
            sig = tuple(r.split('=')[0] for r in roles)
            results_key = sig
            matched = sum(1 for rr in roles if 'partner' in rr or 'next' in rr or 'prev' in rr)
            if matched == 3:
                results['partner' if 'partner' in roles[2].split('=')[1] else 'partner'] = results.get('x', 0)
            print('  coedge loop=%d edge=%d: %s' % (li, coedges[ci]['edge'], ', '.join(roles)))
    return results


for path in ('references/golden/ref_tet.scdoc', 'references/golden/cyl.scdoc'):
    print('===', path.split('/')[-1])
    analyze(path)

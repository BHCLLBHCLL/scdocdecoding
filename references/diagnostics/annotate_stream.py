# -*- coding: utf-8 -*-
"""Semantic annotation of golden reference streams (order derivation)."""
import zipfile

from scdoc_parser import sab as sab_mod
from scdoc_parser.opc import parse_package


def annotate(path):
    pkg = parse_package(path)
    d = pkg.read(pkg.find_geometry()[0].name)
    sf = sab_mod.tokenize(d)
    recs = sf.records
    faces, loops, coedges, surfaces = {}, {}, {}, {}
    for i, r in enumerate(recs):
        t = [x.value for x in r.tokens]
        k = r.kind
        if k == 'face':
            faces[i] = {'surface': t[8], 'loop': t[5], 'next': t[4]}
        elif k == 'loop':
            loops[i] = {'face': t[6], 'coedge': t[5]}
        elif k == 'coedge':
            coedges[i] = {'edge': t[7], 'loop': t[9]}
        elif k in ('plane', 'cone'):
            surfaces[i] = k
    head = None
    pointed = set(f['next'] for f in faces.values())
    for i in faces:
        if i not in pointed:
            head = i
    order, cur = [], head
    while cur is not None and cur in faces:
        order.append(cur)
        cur = faces[cur]['next']
    fo = {fidx: n for n, fidx in enumerate(order)}
    out = []
    for i, r in enumerate(recs):
        k = r.kind
        t = [x.value for x in r.tokens]
        if k == 'face':
            out.append('F%d' % fo[i])
        elif k == 'loop':
            out.append('L(F%d)' % fo[loops[i]['face']])
        elif k == 'coedge':
            lf = loops[coedges[i]['loop']]['face']
            out.append('C(F%d,e#%d)' % (fo[lf], coedges[i]['edge']))
        elif k == 'edge':
            out.append('EDGE#%d' % i)
        elif k == 'vertex':
            out.append('V#%d' % i)
        elif k in ('plane', 'cone'):
            owner = [f for f, x in faces.items() if x['surface'] == i]
            out.append('S(F%d,%s)' % (fo[owner[0]], k[0]))
        elif k in ('straight', 'ellipse'):
            out.append('CURVE#%d(%s)' % (i, k[:4]))
        elif k == 'point':
            out.append('P#%d' % i)
        elif k == 'body':
            out.append('BODY')
        elif k == 'lump':
            out.append('LUMP')
        elif k == 'shell':
            out.append('SHELL')
        elif k == 'string_attrib':
            v = str(t[7])[:6] if len(t) > 7 else '?'
            out.append('SA(%s)' % v)
        elif k == 'rgb_color':
            out.append('RGB')
        elif k == 'wstring_attrib':
            out.append('w')
        else:
            out.append(k[:5])
    return order, out


for path in ('references/golden/ref_tet.scdoc',
             'references/golden/cyl.scdoc'):
    order, out = annotate(path)
    print('===', path.split('/')[-1], 'faces:', order)
    print(' '.join(out))
    print()

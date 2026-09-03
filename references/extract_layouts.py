# -*- coding: utf-8 -*-
"""Phase 0: auto-extract per-class SAB record layout schemas from official
streams.

For each entity kind, gather all its records across the given scdoc files,
reduce to a canonical field layout (token-kind sequence + whether each field
is a pointer/enum/geom/scalar), and report the class interning header
chain + class_id.  This is the machine-readable substrate for the Phase 1
data-driven LayoutEmitter.

Usage: python extract_layouts.py <scdoc> [<scdoc> ...]
Outputs: references/layout_extract/class_layouts.json
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scdoc_parser import opc, sab as sab_mod

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "layout_extract")

# token kind -> layout 'role' category
KIND_ROLE = {
    'ptr': 'ptr',
    'int': 'int',
    'int15': 'int15',
    'double': 'real',
    'string': 'string',
    'vec3': 'vec3',
    'vec3b': 'vec3b',
    'flag_a': 'flag_a',
    'flag_b': 'flag_b',
}


def load_records(path):
    pkg = opc.parse_package(path)
    out = []
    for gp in pkg.find_geometry():
        sf = sab_mod.tokenize(pkg.read(gp.name))
        out.extend(sf.records)
    return out


def main():
    files = sys.argv[1:]
    if not files:
        print("usage: extract_layouts.py <scdoc> ...")
        return
    bykind = {}
    for f in files:
        for r in load_records(f):
            bykind.setdefault(r.kind, []).append(r)

    layout = {}
    for kind, recs in bykind.items():
        recs.sort(key=lambda r: r.index)
        # canonical signature: longest record as reference (fields are usually
        # fixed per class; some records carry optional trailing fields)
        template = max((r for r in recs), key=lambda r: len(r.tokens), default=None)
        if not template:
            continue
        types = [KIND_ROLE.get(t.kind, t.kind) for t in template.tokens]
        # class header: chain + record name + class id
        chain = [[c, i] for c, i in template.chain]
        cls = {
            'name': template.name,
            'class_id': template.rec_id,
            'chain': chain,
            'field_types': types,
            'n': len(recs),
            # value samples per field (first up to 6 distinct) — helps hand-map
            # semantics during Phase 1
            'field_samples': [],
        }
        for i, t in enumerate(template.tokens):
            if t.kind in ('ptr', 'int', 'int15', 'double'):
                cls['field_samples'].append([t.value])
            elif t.kind in ('vec3', 'vec3b'):
                cls['field_samples'].append([list(t.value)])
            else:
                cls['field_samples'].append([None])
        # distinct value samples across this class (per field, capped)
        for i in range(min(len(types), 40)):
            vals = set()
            for r in recs:
                if i < len(r.tokens):
                    t = r.tokens[i]
                    v = t.value
                    if isinstance(v, tuple):
                        v = tuple(round(x, 6) for x in v)
                    else:
                        v = round(v, 6) if isinstance(v, float) else v
                    vals.add(str(v))
                if len(vals) >= 6:
                    break
            cls['field_samples'][i] = sorted(vals)[:6]
        layout[kind] = cls

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "class_layouts.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=1)
    print(f"wrote {out_path} with {len(layout)} classes")
    for k in sorted(layout):
        l = layout[k]
        print(f"  {k:20s} class_id={l['class_id']} n={l['n']} "
              f"fields={''.join(x[0].upper() for x in l['field_types'])}")


if __name__ == "__main__":
    main()

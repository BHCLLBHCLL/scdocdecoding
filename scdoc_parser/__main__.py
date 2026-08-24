"""CLI entry point: python -m scdoc_parser <file.scdoc> [options].

Examples
--------
  python -m scdoc_parser box.scdoc                  # human summary
  python -m scdoc_parser box.scdoc -o report.json   # full JSON report
  python -m scdoc_parser box.scdoc --parts          # list OPC parts
  python -m scdoc_parser box.scdoc --tree           # dump SAB entity records
"""
from __future__ import annotations

import argparse
import json
import sys

from . import opc, report, sab


def _print_summary(rep: dict) -> None:
    v = rep['validation']
    print(f"file: {rep['file']}")
    print(f"checks: {v['passed']}/{v['total']} passed"
          + ('' if v['all_ok'] else f'  FAILED: {v["failed"]}'))

    if rep['document']:
        d = rep['document']
        print(f"\ndocument: version={d['version']} units={d['units']['length_type']} "
              f"(factor {d['units']['factor']})")
        if d.get('import_path'):
            print(f"  imported from: {d['import_path']}")
        for b in d['bodies']:
            print(f"  body {b['id']} name={b['name']!r} color={b['color']} "
                  f"faces={len(b['face_ids'])} edges={len(b['edge_ids'])}")

    if rep['geometry']:
        g = rep['geometry']
        a = g['acis']
        print(f"\nB-rep (ACIS): {a['product']} {a['version']} {a['date']}")
        print(f"  entities={a['entity_count']} counts={a['counts']}")
        for b in g['bodies']:
            print(f"  body {b['doc_id']}: volume={b['volume_mm3']}mm3 "
                  f"area={b['surface_area_mm2']}mm2 faces={len(b['faces'])}")
            for f in b['faces']:
                plane = f['plane']['description'] if f['plane'] else '?'
                print(f"    face {f['doc_id']}: area={f['area_mm2']}mm2 plane={plane}")
            for e in b['edges'][:4]:
                print(f"    edge {e['doc_id']}: length={e['length_mm']}mm")
            if len(b['edges']) > 4:
                print(f"    ... +{len(b['edges']) - 4} more edges")

    if rep['mesh']:
        m = rep['mesh']
        print(f"\nfacet mesh: version={m['version']} body={m['body_doc_id']}")
        print(f"  counts={m['counts']}")

    print()
    for sec_name in ('geometry', 'mesh'):
        sec = rep.get(sec_name)
        if not sec:
            continue
        for c in sec.get('checks', []):
            print(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
    for c in rep['cross_checks']:
        print(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog='scdoc_parser',
        description='Reverse-engineered SpaceClaim .scdoc project file parser')
    ap.add_argument('scdoc', help='path to the .scdoc file')
    ap.add_argument('-o', '--output', help='write the full JSON report to this file')
    ap.add_argument('--parts', action='store_true', help='list OPC package parts')
    ap.add_argument('--rels', action='store_true', help='list OPC relationships')
    ap.add_argument('--tree', action='store_true', help='dump raw SAB entity records')
    ap.add_argument('--json', action='store_true', help='print JSON report to stdout')
    args = ap.parse_args(argv)

    if args.parts or args.rels:
        pkg = opc.parse_package(args.scdoc)
        if args.parts:
            for p in pkg.parts:
                print(f'{p.size:8d}  {p.compressed_size:8d}  {p.name}')
                print(f'           {p.content_type}')
        if args.rels:
            for r in pkg.relationships:
                print(f'{r.source or "<package>":40s} --{r.type_name}--> {r.target}')
        return 0

    if args.tree:
        pkg = opc.parse_package(args.scdoc)
        geom = pkg.find_geometry()
        if not geom:
            print('no geometry part found', file=sys.stderr)
            return 1
        sf = sab.tokenize(pkg.read(geom[0].name))
        print(f'{sf.product} {sf.version} {sf.date}  unit_scale={sf.unit_scale}')
        for rec in sf.records:
            print(rec.dump())
        return 0

    rep = report.build_report(args.scdoc)

    if args.json:
        json.dump(rep, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        _print_summary(rep)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            json.dump(rep, fh, indent=2, ensure_ascii=False)
        if not args.json:
            print(f'\nfull report written to {args.output}')

    return 0 if rep['validation']['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
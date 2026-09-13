# -*- coding: utf-8 -*-
"""R72/P358: countable difference table for the ACIS `ref` (indirect-surface) family.

The official library is exact on 6 of 6 samples *except* for the faces whose
surface record is a `ref` indirection: SampleModel4 references 52 of them (34
never rebuild) and samplemodel2 references 20 (1 never rebuilds).  R21 proved the
`ref` TABLE is not in this part; what R21 did not do is count, per face, WHICH
rebuild branch was taken and what the failing faces actually carry.  That is what
this tool produces - it is a measurement, not a fix.

Usage::

    python tools/ref_family_diff.py                     # table over the library
    python tools/ref_family_diff.py --md docs/REF_FAMILY_DIFF.md
    python tools/ref_family_diff.py --faces SampleModel4.scdoc
    python tools/ref_family_diff.py --json docs/ref_family_diff.json

`path` is the importer's own branch label, recorded by the off-by-default
`import_sab.trace_faces()` hook (one source of truth, rule 84; the hook costs
one global lookup per face when disabled, rule 85).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scdm.document import load_scdoc  # noqa: E402
from scdm import import_sab  # noqa: E402

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
PATHS = ("rebuild", "polygons", "sampled", "none")


def _sab_counts(data):
    c = Counter()
    for m in data["models"]:
        for kind in ("body", "face", "edge", "vertex", "loop", "coedge"):
            c[kind] += len(m.of_kind(kind))
    return c


def free_edges(shape):
    """Edges used by fewer than two faces (the watertightness measure)."""
    import OCC.Core.TopExp as _TE
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE

    m = TopTools_IndexedDataMapOfShapeListOfShape()
    _TE.topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, m)
    n = 0
    for i in range(1, m.Size() + 1):
        if m.FindFromIndex(i).Size() < 2:
            n += 1
    return n


def ref_curve_coverage(data):
    """The SAME indirection on curves: edges whose curve head owns a ref."""
    cov = {"edge": 0, "edge_payload": 0, "edge_ref_only": 0}
    for m in data["models"]:
        owners = import_sab.ref_surface_owners(m)
        if not owners:
            continue
        pay = {e.cluster_owner for e in m.inner
               if e.kind in ("nubs", "exactcur", "ellipse", "straight")}
        for ed in m.of_kind("edge"):
            if ed.curve is None or ed.curve < 0 or ed.curve not in owners:
                continue
            cov["edge"] += 1
            if ed.curve in pay:
                cov["edge_payload"] += 1
            else:
                cov["edge_ref_only"] += 1
    return cov


def measure(path):
    """One record per sample: SAB counts, branch histogram, ref-family matrix."""
    from scdm import kernel as K

    data = load_scdoc(path)
    index = {id(m): i for i, m in enumerate(data["models"])}
    sab = _sab_counts(data)
    import_sab._faces_from_model.unbuilt = 0
    import_sab._faces_from_model.unbuilt_ref = 0
    import_sab._faces_from_model.skipped = 0
    with import_sab.trace_faces() as rec:
        kdoc = import_sab.import_scdoc_bundle(data)
    bodies = faces = f_edges = f_loops = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        bodies += 1
        try:
            faces += len(K.explore(b.shape, "face"))
            f_edges += free_edges(b.shape)
            f_loops += len(K._free_boundary_wires(b.shape))
        except Exception:
            pass
    for r in rec:
        r["model"] = index.get(r["model"], -1)
    hist = Counter(r["path"] for r in rec)
    refs = [r for r in rec if r["ref"]]
    ref_hist = Counter(r["path"] for r in refs)
    other_unbuilt = Counter(r["kind"] for r in rec
                            if not r["ref"] and r["path"] == "none")
    ref_kinds = Counter(r["kind"] for r in refs)
    ref_inner = Counter(r["inner"] or "-" for r in refs)
    ref_unbuilt_inner = Counter(r["inner"] or "-" for r in refs
                                if r["path"] == "none")
    ref_unbuilt_edges = Counter(
        "curves=%s/edges=%s" % (r["curve_edges"] == r["edges"], r["edges"])
        for r in refs if r["path"] == "none" and r["edges"] < 6)
    return {
        "sample": os.path.basename(path),
        "sab": dict(sab),
        "sab_faces": len(rec),
        "bodies": bodies,
        "faces": faces,
        "unbuilt": getattr(import_sab._faces_from_model, "unbuilt", 0),
        "dropped": getattr(import_sab._faces_from_model, "skipped", 0),
        "paths": {k: hist.get(k, 0) for k in PATHS},
        "ref": {"faces": len(refs),
                "paths": {k: ref_hist.get(k, 0) for k in PATHS}},
        "ref_kinds": dict(ref_kinds),
        "ref_inner": dict(ref_inner),
        "ref_unbuilt_inner": dict(ref_unbuilt_inner),
        "ref_unbuilt_small": dict(ref_unbuilt_edges),
        "other_unbuilt": dict(other_unbuilt),
        "free_edges": f_edges,
        "free_loops": f_loops,
        "curves": ref_curve_coverage(data),
        "report": {k: v for k, v in (kdoc.import_report or {}).items()
                   if k.startswith("ref") or k in ("parts", "unbuilt_faces",
                                                    "dropped_faces")},
        "warnings": list(getattr(kdoc, "import_warnings", [])),
        "faces_detail": refs,
    }


def render_md(rows):
    out = []
    out.append("| 样例 | SAB 体/面 | 导入 体/面 | 重建分支 rebuild/polygons/sampled/none | 自由边/自由环 | ref 面 | ref 分支 | ref 重建/未重建 | 无边界边 | ref 曲线（有载荷/仅 ref） | 非 ref 未重建 | 包围盒丢弃 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        p = r["paths"]
        rp = r["ref"]["paths"]
        rep = r["report"]
        out.append("| `%s` | %d/%d | %d/%d | %d/%d/%d/%d | %d/%d | %d | %d/%d/%d/%d | **%d/%d** | %d | %d/%d | %s | %d |"
                   % (r["sample"], r["sab"].get("body", 0), r["sab"].get("face", 0),
                      r["bodies"], r["faces"], p["rebuild"], p["polygons"],
                      p["sampled"], p["none"], r["free_edges"], r["free_loops"],
                      r["ref"]["faces"],
                      rp["rebuild"], rp["polygons"], rp["sampled"], rp["none"],
                      rep.get("ref_built", 0), rep.get("ref_unbuilt", rp["none"]),
                      rep.get("ref_no_boundary", 0),
                      r["curves"]["edge_payload"], r["curves"]["edge_ref_only"],
                      ", ".join("%s=%d" % kv for kv in sorted(r["other_unbuilt"].items())) or "0",
                      r["dropped"]))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lib", default=LIB)
    ap.add_argument("--sample", action="append", default=None)
    ap.add_argument("--faces", default=None,
                    help="dump the per-face ref rows of this sample")
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if args.faces:
        r = measure(os.path.join(args.lib, args.faces))
        head = ("| 面 | 曲面头 kind | 环 | 边 | 有曲线的边 | 分支 | 建成面 | 多边形 | 采样环 | 最后尝试 | 载荷 |",
                "|---|---|---|---|---|---|---|---|---|---|---|")
        rows = []
        for d in sorted(r["faces_detail"],
                        key=lambda x: (x["path"] != "none", x["face"])):
            rows.append("| %d | %s | %d | %d | %d | %s | %d | %d | %d | %s | %s |"
                        % (d["face"], d["kind"], d["loops"], d["edges"],
                           d["curve_edges"], d["path"], d["faces"], d["polys"],
                           d["sampled"], d["tried"] or "-", d["inner"]))
        foot = ("\nref 面 %d：重建 %d / 多边形 %d / 采样 %d / 未重建 %d；包围盒丢弃 %d"
                % (r["ref"]["faces"], r["ref"]["paths"]["rebuild"],
                   r["ref"]["paths"]["polygons"], r["ref"]["paths"]["sampled"],
                   r["ref"]["paths"]["none"], r["dropped"]))
        if args.md:
            with open(args.md, "w", encoding="utf-8") as fh:
                fh.write("\n".join(head + tuple(rows)) + "\n" + foot + "\n")
            print("wrote %s" % args.md)
            return 0
        for line in head:
            print(line)
        for line in rows:
            print(line)
        print(foot)
        return 0
    names = args.sample or [os.path.basename(p) for p in
                            sorted(glob.glob(os.path.join(args.lib, "*.scdoc")))]
    rows = []
    for n in names:
        try:
            rows.append(measure(os.path.join(args.lib, n)))
        except Exception as exc:
            print("ERROR %s: %s" % (n, exc))
            return 1
    md = render_md(rows)
    print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1, sort_keys=True)
        print("wrote %s" % args.json)
    if args.md:
        head = ("# ref 族差异表（当前状态）\n\n"
                "本文件是**当前状态**快照，每轮刷新；轮次基线见 docs/ROUND_R72_20260912.md（R72 原始记录）\n"
                "与 docs/ROUND_R73_20260912.md（R73 修改后的自由边/自由环）。\n\n"
                "复算：`python tools/ref_family_diff.py --md docs/REF_FAMILY_DIFF_TABLE.md`\n\n")
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(head + md + "\n")
        print("wrote %s" % args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

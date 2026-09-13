# -*- coding: utf-8 -*-
"""R75/P371: classify every FREE edge (used by fewer than two faces).

Free edges are now the only countable gap left in the official library
(SampleModel1 56/24, SampleModel2 2325/438, the other four 0/0/2).  This tool
answers "what ARE they" before anything is changed:

  * curve type and length of the edge,
  * the surface type of its single owner face (or none),
  * whether its ends continue into other free edges (an open boundary chain)
    or into edges that two faces share (a gap next to closed material), or
    connect to nothing at all (an isolated seam/degenerate edge).

Usage::

    python tools/free_edge_report.py                 # table over the library
    python tools/free_edge_report.py --sample X.scdoc --edges
    python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scdm.document import load_scdoc  # noqa: E402
from scdm import import_sab  # noqa: E402

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
CURVES = {0: "line", 1: "circle", 2: "ellipse", 3: "hyperbola", 4: "parabola",
          5: "bezier", 6: "bspline", 7: "offset", 8: "other"}
SURFS = {0: "plane", 1: "cylinder", 2: "cone", 3: "sphere", 4: "torus",
         5: "bezier", 6: "bspline", 7: "revolution", 8: "extrusion",
         9: "offset", 10: "other"}


def _ancestors(shape):
    import OCC.Core.TopExp as _TE
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE

    m = TopTools_IndexedDataMapOfShapeListOfShape()
    _TE.topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, m)
    return m


def _edge_info(edge, face_count):
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.GCPnts import GCPnts_AbscissaPoint
    from OCC.Core.TopoDS import topods

    e = topods.Edge(edge)
    ad = BRepAdaptor_Curve(e)
    # length by sampling: GCPnts_AbscissaPoint needs a curated adaptor and
    # silently produced 0 for every edge here (R75 measured that).
    n = 20
    u0, u1 = ad.FirstParameter(), ad.LastParameter()
    pts = [ad.Value(u0 + (u1 - u0) * i / float(n)) for i in range(n + 1)]
    length = 0.0
    for i in range(n):
        length += ((pts[i + 1].X() - pts[i].X()) ** 2
                   + (pts[i + 1].Y() - pts[i].Y()) ** 2
                   + (pts[i + 1].Z() - pts[i].Z()) ** 2) ** 0.5
    p1, p2 = pts[0], pts[-1]
    chord = ((p2.X() - p1.X()) ** 2 + (p2.Y() - p1.Y()) ** 2
             + (p2.Z() - p1.Z()) ** 2) ** 0.5
    return {
        "curve": CURVES.get(int(ad.GetType()), "?"),
        "length": length,
        "chord": chord,
        "p1": (p1.X(), p1.Y(), p1.Z()),
        "p2": (p2.X(), p2.Y(), p2.Z()),
    }





def pair_gaps(body, gap_keys, samples=7, reach=0.05):
    """Pair every open edge with the nearest OTHER edge (R76/P375).

    For each gap: the distance to the closest edge of the same body, that
    edge's curve/surface and whether it is shared by two faces.  A gap whose
    partner is within a tolerance was a sewing/precision miss; a gap with no
    partner at all is a real hole.  Sampling keeps it O(gaps x edges).
    """
    from scdm import kernel as K
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.TopoDS import topods

    def _samples(edge, interior=True):
        ad = BRepAdaptor_Curve(topods.Edge(edge))
        u0, u1 = ad.FirstParameter(), ad.LastParameter()
        if interior:
            # R76: two edges that merely SHARE A VERTEX are 0 apart, which made
            # the first pairing report 46/56 "twins" that were really the gap's
            # own neighbouring edges.  Interior points only.
            fr = [0.2, 0.35, 0.5, 0.65, 0.8]
        else:
            fr = [i / float(samples) for i in range(samples + 1)]
        return [ad.Value(u0 + (u1 - u0) * f) for f in fr]

    edges = []
    for (edge, n, face) in K.edge_face_counts(body):
        try:
            surf = SURFS.get(int(BRepAdaptor_Surface(face).GetType()), "?") if face is not None else "-"
            curve = None
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve as _C
            curve = CURVES.get(int(_C(topods.Edge(edge)).GetType()), "?")
        except Exception:
            surf, curve = "?", "?"
        edges.append({"edge": edge, "n": n, "surf": surf, "curve": curve,
                      "pts": _samples(edge)})
    out = []
    for g in edges:
        if g["n"] >= 2:
            continue
        best = None
        for e in edges:
            if e is g:
                continue
            # distance from EACH interior point of the gap to the other edge,
            # then the worst of them: an overlap partner must be close along
            # the whole edge, not just somewhere
            worst = 0.0
            for a in g["pts"]:
                dmin = min(((a.X() - b.X()) ** 2 + (a.Y() - b.Y()) ** 2
                            + (a.Z() - b.Z()) ** 2) ** 0.5 for b in e["pts"])
                worst = max(worst, dmin)
            if best is None or worst < best[0]:
                best = (worst, e)
        d, e = best
        out.append({"curve": g["curve"], "surf": g["surf"],
                    "partner_curve": e["curve"], "partner_surf": e["surf"],
                    "partner_shared": e["n"] >= 2, "dist": d,
                    "twin": d <= 1e-6, "near": d <= 1e-3})
    return out

def measure(path):
    """One record per free edge.

    R75 lesson: everything that needs the ancestor map is done while the map
    is alive - pythonocc hands out views, and a view read after the map is
    collected reports size 0 (which silently turned every seam into "not a
    seam" in the first version of this tool).
    """
    from scdm import kernel as K
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface

    data = load_scdoc(path)
    kdoc = import_sab.import_scdoc_bundle(data)
    rows = []
    ends = Counter()
    bodies = []
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        bodies.append(b.shape)
        for (edge, n, face) in K.edge_face_counts(b.shape):
            if n >= 2 or face is None:
                continue
            info = _edge_info(edge, n)
            try:
                info["surf"] = SURFS.get(
                    int(BRepAdaptor_Surface(face).GetType()), "?")
            except Exception:
                info["surf"] = None
            info["seam"] = K.is_seam_edge(edge, face)
            ends[tuple(round(c, 9) for c in info["p1"])] += 1
            ends[tuple(round(c, 9) for c in info["p2"])] += 1
            rows.append(info)
    for info in rows:
        free_ends = 0
        for key in (tuple(round(c, 9) for c in info["p1"]),
                    tuple(round(c, 9) for c in info["p2"])):
            if ends.get(key, 0) - 1 > 0:
                free_ends += 1
        info["ends"] = ("chain" if free_ends == 2 else
                        "half" if free_ends == 1 else "isolated")
    return {"sample": os.path.basename(path), "edges": len(rows), "rows": rows,
            "bodies": bodies}


def summarise(rec):
    curve = Counter(r["curve"] for r in rec["rows"])
    surf = Counter(r["surf"] or "-" for r in rec["rows"])
    ends = Counter(r["ends"] for r in rec["rows"])
    lens = sorted(r["length"] for r in rec["rows"])
    tiny = sum(1 for r in rec["rows"] if r["length"] < 1e-9)
    seams = sum(1 for r in rec["rows"] if r.get("seam"))
    return {"sample": rec["sample"], "edges": rec["edges"],
            "seams": seams, "gaps": rec["edges"] - seams,
            "curve": dict(curve), "surf": dict(surf), "ends": dict(ends),
            "tiny": tiny,
            "len_median": lens[len(lens) // 2] if lens else 0.0,
            "len_max": lens[-1] if lens else 0.0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lib", default=LIB)
    ap.add_argument("--sample", action="append", default=None)
    ap.add_argument("--edges", action="store_true",
                    help="dump the free edges of the given sample")
    ap.add_argument("--pair", action="store_true",
                    help="pair every gap with the nearest other edge")
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    names = args.sample or [os.path.basename(p) for p in
                            sorted(glob.glob(os.path.join(args.lib, "*.scdoc")))]
    out = []
    for n in names:
        rec = measure(os.path.join(args.lib, n))
        if args.edges:
            print("%-7s %-8s %-9s %-9s %s" % ("curve", "surf", "length", "chord", "ends"))
            for r in sorted(rec["rows"], key=lambda x: -x["length"])[:40]:
                print("%-7s %-8s %-9.4g %-9.4g %s"
                      % (r["curve"], r["surf"] or "-", r["length"], r["chord"], r["ends"]))
        if args.pair:
            pairs = []
            for shape in rec["bodies"]:
                pairs.extend(pair_gaps(shape, None))
            twins = sum(1 for p in pairs if p["twin"])
            near = sum(1 for p in pairs if p["near"])
            shared = sum(1 for p in pairs if p["partner_shared"])
            mix = Counter("%s|%s" % (p["surf"], p["partner_surf"]) for p in pairs)
            print("== %s: %d gaps | twin(<=1e-6) %d, near(<=1e-3) %d, partner shared %d"
                  % (rec["sample"], len(pairs), twins, near, shared))
            print("   surface pairs: %s"
                  % ", ".join("%s=%d" % kv for kv in mix.most_common(8)))
            ds = sorted(p["dist"] for p in pairs)
            if ds:
                print("   distance median %.3g, max %.3g"
                      % (ds[len(ds) // 2], ds[-1]))
            rec["pairs"] = pairs
        out.append(summarise(rec))
    head = ("| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |",
            "|---|---|---|---|---|---|---|---|---|---|")
    lines = list(head)
    for s in out:
        lines.append("| `%s` | %d | %d | %d | %s | %s | %s | %d | %.3g | %.3g |"
                     % (s["sample"], s["edges"], s["seams"], s["gaps"],
                        ", ".join("%s=%d" % kv for kv in sorted(s["curve"].items())),
                        ", ".join("%s=%d" % kv for kv in sorted(s["surf"].items())),
                        ", ".join("%s=%d" % kv for kv in sorted(s["ends"].items())),
                        s["tiny"], s["len_median"], s["len_max"]))
    md = "\n".join(lines)
    print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        print("wrote %s" % args.json)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("# 自由边分类（R75/P371 当前状态）\n\n"
                     "复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`\n\n"
                     + md + "\n")
        print("wrote %s" % args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""R128/A-20: run our read-only parser over the official SpaceClaim corpus.

`D:\training\caedecoder\scdm_cases` holds 222 documents written by ANSYS
SpaceClaim 2019 R3 itself.  Each case has a `.json` with the counts SpaceClaim
read back (`actual`) and the counts the case meant to build (`expect`), so the
corpus is ground truth we did not author.

This tool parses every selected case with `scdoc_parser` and compares our numbers
with theirs.  The corpus is **read-only**: nothing is ever written into it, and
reports go to `_tmp/` unless `--json` says otherwise (writing inside the corpus is
refused).

Usage::

    python tools/scdm_cases_check.py                    # one case per category
    python tools/scdm_cases_check.py --all              # every ok case
    python tools/scdm_cases_check.py --category 03_pull
    python tools/scdm_cases_check.py --only 00_smoke_box_001_20x20x20
    python tools/scdm_cases_check.py --all --check      # exit 1 on a mismatch

The corpus location can be overridden with `SCDM_CASES` (a CI without the corpus
just skips: the tests do the same).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CASES = os.environ.get("SCDM_CASES", r"D:\training\caedecoder\scdm_cases")
DEFAULT_OUT = str(ROOT / "_tmp" / "scdm_cases_report.json")
NUMBERS = ("bodies", "faces", "edges")

#: the numbers are compared against what SpaceClaim *read back*, which is what a
#: parser can be held to; the case's original intent is reported next to it
AGAINST = ("actual", "expect")


def load_manifest(cases_dir: str) -> Dict[str, Any]:
    with open(Path(cases_dir) / "manifest.json", encoding="utf-8") as fh:
        return json.load(fh)


def select_cases(man: Dict[str, Any], categories=(), only=(),
                 one_per_category: bool = False, max_mb: float = 64.0) -> List[dict]:
    """The ok cases worth parsing: whole-corpus files are skipped on purpose."""
    out: List[dict] = []
    seen = set()
    for case in man.get("cases", []):
        if case.get("status") != "ok":
            continue
        if case.get("excluded_from_repo"):
            continue
        try:
            if float(case.get("size") or 0) > max_mb * 1e6:
                continue
        except (TypeError, ValueError):
            pass
        if categories and case.get("category") not in categories:
            continue
        if only and case.get("case_id") not in only:
            continue
        if one_per_category:
            if case.get("category") in seen:
                continue
            seen.add(case.get("category"))
        out.append(case)
    return out


def our_numbers(rep: Dict[str, Any]) -> Dict[str, Any]:
    """What our parser read out of the document (one body per solid)."""
    geom = rep.get("geometry") or {}
    bodies = geom.get("bodies") or []
    return {
        "bodies": len(bodies),
        "faces": sum(len(b.get("faces") or ()) for b in bodies),
        "edges": sum(len(b.get("edges") or ()) for b in bodies),
        "volume_mm3": round(sum(float(b.get("volume_mm3") or 0.0)
                                for b in bodies), 6),
        "checks_ok": sum(1 for c in (geom.get("checks") or []) if c.get("ok")),
        "checks_total": len(geom.get("checks") or []),
    }


def compare(want: Dict[str, Any], got: Dict[str, Any],
            tol: float = 1e-3) -> List[str]:
    """Where we disagree with the recorded numbers (empty = agreement)."""
    bad: List[str] = []
    for key in NUMBERS:
        if want.get(key) is None:
            continue
        if int(got[key]) != int(want[key]):
            bad.append("%s %s≠%s" % (key, got[key], want[key]))
    if want.get("volume_mm3") is not None:
        w, g = float(want["volume_mm3"]), float(got["volume_mm3"])
        if abs(g - w) > max(tol, abs(w) * 1e-6):
            bad.append("volume %.6g≠%.6g mm³" % (g, w))
    return bad


def run_case(cases_dir: str, case: dict, against: str = "actual",
             tol: float = 1e-3) -> Dict[str, Any]:
    from scdoc_parser import report as PARSER

    out: Dict[str, Any] = {"case_id": case.get("case_id"),
                           "category": case.get("category"),
                           "status": case.get("status"), "ok": False,
                           "problems": [], "reason": ""}
    try:
        with open(Path(cases_dir) / case["meta"], encoding="utf-8") as fh:
            meta = json.load(fh)
    except Exception as exc:
        out["reason"] = "元数据读不到：%s" % exc
        return out
    want = dict(meta.get("expect") or {})
    if against == "actual":
        for key, value in (meta.get("actual") or {}).items():
            if key in NUMBERS or key == "volume_mm3":
                want[key] = value
    out["want"] = {k: want.get(k) for k in NUMBERS + ("volume_mm3",)}
    out["expect"] = {k: (meta.get("expect") or {}).get(k)
                     for k in NUMBERS + ("volume_mm3",)}
    t0 = time.time()
    try:
        rep = PARSER.build_report(str(Path(cases_dir) / case["scdoc"]))
    except Exception as exc:
        out["reason"] = "解析失败：%s" % exc
        out["elapsed_s"] = round(time.time() - t0, 3)
        return out
    out["elapsed_s"] = round(time.time() - t0, 3)
    got = our_numbers(rep)
    out["got"] = got
    out["problems"] = compare(want, got, tol)
    out["against_expect"] = compare(dict(meta.get("expect") or {}), got, tol)
    out["validation"] = (rep.get("validation") or {}).get("all_ok")
    out["ok"] = not out["problems"]
    return out


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in rows if r.get("ok")]
    bad = [r for r in rows if not r.get("ok")]
    by_cat: Dict[str, List[int]] = {}
    for r in rows:
        slot = by_cat.setdefault(str(r.get("category")), [0, 0])
        slot[0 if r.get("ok") else 1] += 1
    return {
        "cases": len(rows), "ok": len(ok), "mismatch": len(bad),
        "seconds": round(sum(float(r.get("elapsed_s") or 0.0) for r in rows), 3),
        "by_category": {k: {"ok": v[0], "bad": v[1]}
                        for k, v in sorted(by_cat.items())},
        "first_problems": [{"case": r["case_id"], "problems": r["problems"],
                            "reason": r.get("reason", "")} for r in bad[:12]],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="parser conformance over the corpus")
    ap.add_argument("--cases", default=DEFAULT_CASES, help="corpus root")
    ap.add_argument("--all", action="store_true", help="every ok case")
    ap.add_argument("--category", action="append", default=[],
                    help="only this category (repeatable)")
    ap.add_argument("--only", action="append", default=[],
                    help="only this case id (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N cases")
    ap.add_argument("--against", default="actual", choices=list(AGAINST))
    ap.add_argument("--tol", type=float, default=1e-3, help="volume tolerance mm³")
    ap.add_argument("--json", default=DEFAULT_OUT, help="where the report goes")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when any case disagrees")
    args = ap.parse_args(argv)

    cases_dir = str(Path(args.cases))
    if not (Path(cases_dir) / "manifest.json").is_file():
        print("没有语料库：%s" % cases_dir)
        return 2
    man = load_manifest(cases_dir)
    chosen = select_cases(man, categories=args.category, only=args.only,
                          one_per_category=not args.all)
    if args.limit:
        chosen = chosen[:args.limit]
    rows = []
    for case in chosen:
        row = run_case(cases_dir, case, args.against, args.tol)
        rows.append(row)
        mark = "ok  " if row["ok"] else "FAIL"
        print("%s %-46s ours=%s want=%s %s"
              % (mark, row["case_id"], row.get("got"), row.get("want"),
                 "；".join(row["problems"]) or row.get("reason", "")))
    summary = summarise(rows)
    print("\n%d 例：%d 一致，%d 不一致，解析合计 %.1fs（对照 %s）"
          % (summary["cases"], summary["ok"], summary["mismatch"],
             summary["seconds"], args.against))
    report = {"schema": "scdm_cases_check v1", "cases_dir": cases_dir,
              "against": args.against, "manifest_cases": len(man.get("cases", [])),
              "summary": summary, "rows": rows}
    out = Path(args.json)
    try:
        if Path(cases_dir) in out.resolve().parents:
            raise SystemExit("拒绝写进语料库：%s" % out)
    except OSError:
        pass
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("报告写入 %s" % out)
    if args.check and summary["mismatch"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

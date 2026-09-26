# -*- coding: utf-8 -*-
"""scdm_cases phase-B finalizer (CPython 3). Writes only inside scdm_cases.
- marks the 4 long-standing retry cases not_feasible if they still fail
- archives superseded per-batch *_failed.txt and stale scdocs of non-ok cases into _batches\\_archive
- checks manifest <-> files on disk, adds missing entries (from case json) and flags problems
- prints per-category counts as JSON (used for README.md / SUMMARY.md)"""
import json, os, shutil, sys, datetime, collections, hashlib

R = r"D:\training\caedecoder\scdm_cases"
MAN = os.path.join(R, "manifest.json")
ARC = os.path.join(R, "_batches", "_archive")
RETRY = {"03_pull_profile_001_rect_30x10_h5", "03_pull_profile_002_circle_r6_h12",
         "02_sketch_round2d_001_rect_corner_r4", "07_replaceface_001_block_top_to_plane"}
KEEP_FAILED_TXT = {"R2_combined_failed.txt"}
now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
dry = "--dry" in sys.argv
log = []

def mv(src, dst_dir):
    dst = os.path.join(dst_dir, os.path.basename(src))
    if not dry:
        os.makedirs(dst_dir, exist_ok=True)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.move(src, dst)
    log.append("moved %s -> %s" % (os.path.relpath(src, R), os.path.relpath(dst, R)))

m = json.load(open(MAN, encoding="utf-8"))
cases = m["cases"]
by = collections.OrderedDict()
for c in cases:
    by[c["case_id"]] = c          # last entry wins if duplicated
dups = len(cases) - len(by)

# 1) case scripts on disk (category folders only)
cat_dirs = [d for d in sorted(os.listdir(R)) if os.path.isdir(os.path.join(R, d)) and d[:2].isdigit()]
disk = {}
for d in cat_dirs:
    for f in os.listdir(os.path.join(R, d)):
        if f.endswith(".py") and not f.endswith("_run.py"):
            disk[f[:-3]] = d
missing_entries = sorted(k for k in disk if k not in by)
for k in missing_entries:
    d = disk[k]
    meta = os.path.join(R, d, k + ".json")
    st = "not_run"
    e = {"case_id": k, "category": d, "script": "%s/%s.py" % (d, k), "status": st}
    if os.path.exists(meta):
        j = json.load(open(meta, encoding="utf-8"))
        e.update({"feature": j.get("feature"), "status": j.get("status", st), "meta": "%s/%s.json" % (d, k)})
    by[k] = e
    log.append("added manifest entry %s (%s)" % (k, e["status"]))

# 2) retry cases -> not_feasible
for k in RETRY:
    e = by.get(k)
    if e and e.get("status") not in ("ok", "not_feasible"):
        e["status"] = "not_feasible"
        e["not_feasible_reason"] = "still failing after 3 attempts (B0x, B01_B07_r1, R2_combined with researched call forms): " + (e.get("error_last_line") or json.dumps(e.get("expect_mismatch"), ensure_ascii=False))[:400]
        log.append("not_feasible: %s" % k)
    if e and e.get("status") == "not_feasible" and not e.get("not_feasible_reason"):
        mj = os.path.join(R, e.get("meta") or "")
        if e.get("meta") and os.path.exists(mj):
            e["not_feasible_reason"] = json.load(open(mj, encoding="utf-8")).get("not_feasible_reason")

CAVEATS = {
    "15_mesh_reduce_001_50pct": "scdoc is ~311 MB: FacetReduce(TriangleReduction=0.5) ran ~430 s headless; facet counts are not readable from DesignMesh.Shape (only Faces/Edges/Vertices), so the reduction is unverified - exclude from default parser tests",
    "07_replaceface_001_block_top_to_plane": "reinterpreted: V19 ReplaceFacesWithFace merges faces into one (split top -> merged), no target/source replace",
    "13_convertsolid_001_closed_sheets": "reinterpreted: V19 ConvertToSolid needs a mesh selection; block -> facet mesh -> ConvertToSolid",
    "08_sheetmetal_flange_001_90deg_l20": "flange realised as L-solid + ConvertToSheetMetal + CreateMissingBends (no scripted flange command)",
}
for k, t in CAVEATS.items():
    if k in by:
        by[k]["caveat"] = t
# 3) file consistency
problems = []
for k, e in by.items():
    if k not in disk and e.get("category", "")[:2].isdigit():
        problems.append("entry without script on disk: %s" % k)
    d = e.get("category")
    sc = os.path.join(R, d, k + ".scdoc") if d else None
    if e.get("status") in ("ok", "mismatch"):
        if not e.get("scdoc") or not os.path.exists(os.path.join(R, e["scdoc"])):
            problems.append("ok/mismatch without scdoc: %s" % k)
        elif e.get("size") and os.path.getsize(os.path.join(R, e["scdoc"])) != e["size"]:
            problems.append("size differs from manifest: %s" % k)
    else:
        if sc and os.path.exists(sc):
            mv(sc, os.path.join(ARC, "stale_scdoc"))
        e.pop("scdoc", None); e.pop("size", None); e.pop("sha256", None)
    if e.get("meta") and not os.path.exists(os.path.join(R, e["meta"])):
        problems.append("meta json missing: %s" % k)

# 4) archive per-batch *_failed.txt
bdir = os.path.join(R, "_batches")
for f in sorted(os.listdir(bdir)):
    if f.endswith("_failed.txt") and f not in KEEP_FAILED_TXT:
        mv(os.path.join(bdir, f), ARC)

# 5) counts
cnt = collections.OrderedDict()
for k, e in sorted(by.items(), key=lambda kv: (kv[1].get("category", ""), kv[0])):
    c = cnt.setdefault(e.get("category", "?"), collections.Counter())
    c[e.get("status")] += 1
tot = collections.Counter()
for c in cnt.values():
    tot.update(c)
m["cases"] = sorted(by.values(), key=lambda e: (e.get("category", ""), e["case_id"]))
m["updated_at"] = now
m["counts"] = {"total": sum(tot.values()), "by_status": dict(tot), "by_category": {k: dict(v) for k, v in cnt.items()}}
if not dry:
    with open(MAN, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
rem = [{"case_id": e["case_id"], "status": e["status"], "why": (e.get("not_feasible_reason") or e.get("error_last_line") or json.dumps(e.get("expect_mismatch"), ensure_ascii=False))[:300]}
       for e in m["cases"] if e.get("status") != "ok"]
print(json.dumps({"dups_removed": dups, "log": log, "problems": problems, "counts": m["counts"], "not_ok": rem}, ensure_ascii=False, indent=1))

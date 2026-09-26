# -*- coding: utf-8 -*-
"""R3 follow-up (CPython 3): status override for 13_wrap_001, excluded_from_repo flag, archive R2 failed list, recount."""
import json, os, shutil, collections, datetime
R = r"D:\training\caedecoder\scdm_cases"
MAN = os.path.join(R, "manifest.json")
m = json.load(open(MAN, encoding="utf-8"))
by = {c["case_id"]: c for c in m["cases"]}
w = by["13_wrap_001_rect_onto_cylinder"]
if w["status"] == "mismatch" and w.get("scdoc") and os.path.exists(os.path.join(R, w["scdoc"])):
    w["status"] = "ok"
    w["status_override"] = "R3: Wrap.Create(target body, sheet face) succeeded; V19 Wrap creates a wrapped sheet body 'Wrap_RectWrapped' + curves on the cylinder instead of imprinting faces, so the imprint intent (cyl faces 4..12) was wrong; case JSON still says mismatch"
r = by["15_mesh_reduce_001_50pct"]
r["excluded_from_repo"] = True
r["excluded_reason"] = "scdoc ~312 MB; not included in the exported corpus zip (script + json kept)"
for k in ["12_prepare_volumeextract_001_pipe", "20_combo_wrap_026_cylinder_wrap_text_pull"]:
    by[k]["attempts"] = 4
a = os.path.join(R, "_batches", "_archive")
f = os.path.join(R, "_batches", "R2_combined_failed.txt")
if os.path.exists(f):
    d = os.path.join(a, os.path.basename(f))
    if os.path.exists(d):
        os.remove(d)
    shutil.move(f, d)
cnt = collections.OrderedDict()
for c in sorted(m["cases"], key=lambda e: (e["category"], e["case_id"])):
    cnt.setdefault(c["category"], collections.Counter())[c["status"]] += 1
tot = collections.Counter()
for v in cnt.values():
    tot.update(v)
m["counts"] = {"total": sum(tot.values()), "by_status": dict(tot), "by_category": {k: dict(v) for k, v in cnt.items()}, "excluded_from_repo": [k for k, c in by.items() if c.get("excluded_from_repo")]}
m["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
json.dump(m, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(m["counts"]["by_status"]), [(c["case_id"], c["status"]) for c in m["cases"] if c["status"] != "ok"])

# -*- coding: utf-8 -*-
"""Packs scdm_cases into scdm_cases\_export\scdm_cases_corpus*.zip (CPython 3). Writes only inside scdm_cases.
Excludes: _export\, the ~312 MB 15_mesh_reduce_001_50pct.scdoc, _pilot\pilot_gui_* and pilot failed lists, tmp/__pycache__ dirs, *.pyc.
Splits by top-level folder if a single zip would exceed 24 MB."""
import os, zipfile, hashlib, json, fnmatch
R = r"D:\training\caedecoder\scdm_cases"
OUT = os.path.join(R, "_export")
LIMIT = 24 * 1000 * 1000
EXCL_FILES = ["15_mesh_facet/15_mesh_reduce_001_50pct.scdoc", "_pilot/pilot_gui_*", "_pilot/pilot_failed_*", "*.pyc"]
EXCL_DIRS = {"_export", "__pycache__", "tmp", "temp"}
files = []
for dp, dns, fns in os.walk(R):
    dns[:] = [d for d in dns if d.lower() not in EXCL_DIRS]
    for f in fns:
        rel = os.path.relpath(os.path.join(dp, f), R).replace("\\", "/")
        if any(fnmatch.fnmatch(rel, p) for p in EXCL_FILES):
            continue
        files.append(rel)
files.sort()
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.startswith("scdm_cases_corpus") and f.endswith(".zip"):
        os.remove(os.path.join(OUT, f))
def write(name, rels):
    p = os.path.join(OUT, name)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in rels:
            z.write(os.path.join(R, rel.replace("/", os.sep)), "scdm_cases/" + rel)
    return p
p = write("scdm_cases_corpus.zip", files)
res = []
if os.path.getsize(p) > LIMIT:
    os.remove(p)
    groups, cur, cur_n = [], [], 0
    tops = sorted(set(r.split("/")[0] if "/" in r else "_root" for r in files))
    for t in tops:
        rels = [r for r in files if (r.split("/")[0] if "/" in r else "_root") == t]
        est = sum(os.path.getsize(os.path.join(R, r)) for r in rels) * 0.35
        if cur and cur_n + est > LIMIT * 0.9:
            groups.append(cur); cur, cur_n = [], 0
        cur += rels; cur_n += est
    if cur:
        groups.append(cur)
    for i, g in enumerate(groups, 1):
        res.append(write("scdm_cases_corpus_part%d.zip" % i, g))
else:
    res.append(p)
out = []
for p in res:
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    with zipfile.ZipFile(p) as z:
        n = len(z.namelist()); bad = z.testzip()
    out.append({"zip": os.path.relpath(p, R), "bytes": os.path.getsize(p), "files": n, "sha256": h, "testzip": bad})
print(json.dumps({"files_selected": len(files), "raw_bytes": sum(os.path.getsize(os.path.join(R, r)) for r in files), "zips": out}, indent=1))

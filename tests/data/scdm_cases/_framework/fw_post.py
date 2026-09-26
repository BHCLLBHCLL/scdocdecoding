# -*- coding: utf-8 -*-
"""Post-process one scdm_cases batch result (CPython 3): validate .scdoc zips, sha256, merge manifest.
usage: python -B fw_post.py --result R.json --manifest manifest.json --root D:\\...\\scdm_cases [--failed-list F.txt] [--phase P]"""
import argparse, datetime, hashlib, json, os, zipfile

ap = argparse.ArgumentParser()
ap.add_argument("--result", required=True)
ap.add_argument("--manifest", required=True)
ap.add_argument("--root", required=True)
ap.add_argument("--failed-list", default="")
ap.add_argument("--phase", default="")
a = ap.parse_args()


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def rel(p):
    if not p:
        return None
    try:
        return os.path.relpath(p, a.root).replace("\\", "/")
    except ValueError:
        return p


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


res = load(a.result)
if res.get("fatal"):
    print("FATAL in SpaceClaim driver:", res["fatal"])
man = load(a.manifest) if os.path.exists(a.manifest) else {"schema": "scdm_cases/manifest v1", "spaceclaim_version": "2019.3.38912", "cases": []}
byid = {c["case_id"]: c for c in man.get("cases", [])}
failed, rows = [], []
for c in res.get("cases", []):
    cid, st = c["case_id"], c.get("status")
    e = {"case_id": cid, "category": c.get("category"), "feature": c.get("feature"), "status": st,
         "mode": c.get("mode"), "batch": res.get("batch"), "generated_at": c.get("generated_at"),
         "script": rel(c.get("script"))}
    if a.phase:
        e["phase"] = a.phase
    sc = c.get("scdoc")
    od = c.get("out_dir") or (os.path.dirname(c["script"]) if c.get("script") else None)
    if od and os.path.exists(os.path.join(od, cid + ".json")):
        e["meta"] = rel(os.path.join(od, cid + ".json"))
    if sc and os.path.exists(sc):
        e["scdoc"], e["size"], e["sha256"] = rel(sc), os.path.getsize(sc), sha256(sc)
        try:
            with zipfile.ZipFile(sc) as z:
                names = z.namelist()
            e["zip_ok"] = True
            e["has_document_xml"] = any(n.lower().endswith("document.xml") for n in names)
        except Exception as ex:
            e["zip_ok"] = False
            e["zip_error"] = str(ex)
    act = c.get("actual") or {}
    e["counts"] = {k: act.get(k) for k in ("bodies", "faces", "edges", "vertices", "components", "part_defs") if k in act}
    e["volume_mm3"] = act.get("volume_mm3")
    items = c.get("items") or {}
    e["items_ok"] = sorted(k for k, v in items.items() if v.get("ok"))
    e["items_failed"] = sorted(k for k, v in items.items() if not v.get("ok"))
    if c.get("expect_mismatch"):
        e["expect_mismatch"] = c["expect_mismatch"]
    err = c.get("error") or c.get("save_error")
    if err:
        e["error_last_line"] = [l for l in err.strip().splitlines() if l.strip()][-1][:300]
    byid[cid] = e
    if st == "failed" and c.get("script"):
        failed.append(c["script"])
    rows.append(e)

man["cases"] = sorted(byid.values(), key=lambda x: x["case_id"])
man["updated_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
with open(a.manifest, "w", encoding="utf-8") as f:
    json.dump(man, f, ensure_ascii=False, indent=1)
if a.failed_list:
    if failed:
        with open(a.failed_list, "w", encoding="utf-8") as f:
            f.write("\n".join(failed) + "\n")
    elif os.path.exists(a.failed_list):
        os.remove(a.failed_list)

print("batch=%s mode=%s stage=%s elapsed_s=%s summary=%s" % (res.get("batch"), res.get("mode"), res.get("stage"), res.get("elapsed_s"), res.get("summary")))
for e in rows:
    cnt = e.get("counts", {})
    print("%-62s %-8s b=%s f=%s e=%s v=%s c=%s vol=%s zip=%s ok=%s fail=%s %s" % (
        e["case_id"], e["status"], cnt.get("bodies"), cnt.get("faces"), cnt.get("edges"), cnt.get("vertices"),
        cnt.get("components"), e.get("volume_mm3"), e.get("zip_ok"), ",".join(e["items_ok"]), ",".join(e["items_failed"]),
        ("ERR: " + e["error_last_line"]) if e.get("error_last_line") else ""))
    if e.get("expect_mismatch"):
        print("    mismatch:", json.dumps(e["expect_mismatch"]))
print("manifest: %s (%d cases); failed: %d" % (a.manifest, len(man["cases"]), len(failed)))

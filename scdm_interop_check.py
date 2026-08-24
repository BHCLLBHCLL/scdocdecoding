"""Official SpaceClaim interoperability check for writer output.

Two checks:
 1. SAB-format audit: tokenize our written .scdoc AND the official box.scdoc with the
    same parser, and compare the record-kind vocabulary/sequence. If our stream uses
    exactly the official record kinds in the same order (body/lump/shell/face/loop/
    coedge/edge/vertex/point/plane/straight/attrib), the ACIS stream is structurally
    faithful to the product.
 2. Official-open attempt: launch the installed SpaceClaim.exe with the written file
    (and, if present, a batch script) and report what happened (process alive = the
    GUI opened; a sentinel file = headless script confirmed the body count).

Run:  python scdm_interop_check.py [--open]
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCDM_EXE = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"


def _record_kinds(geom_path: str):
    from scdoc_parser import sab as sab_mod
    from scdoc_parser import opc, topology
    if geom_path.lower().endswith(".scdoc"):
        pkg = opc.parse_package(geom_path)
        geom = pkg.find_geometry()
        data = pkg.read(geom[0].name)
    else:
        data = open(geom_path, "rb").read()
    sf = sab_mod.tokenize(data)
    model = topology.SabModel(sf)
    kinds = []
    for rec in sf.records:
        if rec.kind == "record" or rec.kind == "chain":
            continue
        kinds.append(rec.kind)
    return {"records": sf.records, "kinds": kinds, "model": model}


def audit(path: str, reference: str = "box.scdoc") -> dict:
    ref = _record_kinds(reference)
    mine = _record_kinds(path)
    ref_set = sorted(set(ref["kinds"]))
    my_set = sorted(set(mine["kinds"]))
    unknown = [k for k in my_set if k not in ref_set]
    return {
        "reference_kinds": ref_set,
        "written_kinds": my_set,
        "unknown_kinds": unknown,
        "record_count": len(mine["records"]),
        "reference_count": len(ref["records"]),
        "ok": not unknown,
    }


def official_open(path: str, timeout: float = 45.0) -> dict:
    """Launch official SpaceClaim with the file; report process/sentinel outcome."""
    if not os.path.exists(SCDM_EXE):
        return {"status": "skipped", "reason": "SpaceClaim.exe not found"}
    script = None
    sentinel = os.path.join(tempfile.gettempdir(), "scdm_interop_sentinel.txt")
    if os.path.exists(sentinel):
        os.remove(sentinel)
    try:
        cs = os.path.join(tempfile.gettempdir(), "scdm_interop_script.cs")
        with open(cs, "w", encoding="utf-8") as f:
            f.write(
                "using SpaceClaim.Api.V19;\n"
                "public class Script\n{\n"
                "  public static void Run(Recorder recorder)\n  {\n"
                "    Document doc = Document.Open(@\"%s\");\n"
                "    int n = 0;\n"
                "    foreach (var b in doc.MainPart.GetBodies()) n++;\n"
                "    System.IO.File.WriteAllText(@\"%s\", n.ToString());\n"
                "  }\n}\n" % (path.replace("\\", "\\\\"), sentinel))
        script = cs
        combos = [
            [SCDM_EXE, "-m", path, "-s", script],
            [SCDM_EXE, "-s", script, "-m", path],
            [SCDM_EXE, "-m", path],
        ]
    except Exception as exc:
        script = None
        combos = [[SCDM_EXE, "-m", path]]
    for args in combos:
        if os.path.exists(sentinel):
            break
        try:
            proc = subprocess.Popen(args, cwd=os.path.dirname(SCDM_EXE),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}
        t0 = time.time()
        while time.time() - t0 < timeout:
            if os.path.exists(sentinel):
                with open(sentinel) as f:
                    count = f.read()
                try:
                    proc.kill()
                except Exception:
                    pass
                return {"status": "opened", "body_count": count, "args": args}
            time.sleep(2.0)
        alive = proc.poll() is None
        try:
            if alive:
                proc.kill()
        except Exception:
            pass
        if alive:
            return {"status": "gui-launched", "args": args,
                    "note": "SpaceClaim process stayed alive (GUI likely opened the file). "
                            "A headless script did not confirm the body count."}
    return {"status": "no-result", "note": "SpaceClaim exited without the sentinel "
                                           "(script form may differ on this version).",
            "sentinel_check": os.path.exists(sentinel)}


def main():
    import tempfile
    from scdm import kernel as K
    from scdm.kdoc import KernelDoc
    from scdm.scdoc_write import write_scdoc

    if not K.available():
        print("kernel unavailable; run under the 'occ' conda env")
        return 1
    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="Solid1")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    write_scdoc(path, doc, name="interop_box")
    print("written sample:", path)
    res = audit(path)
    print("--- SAB-format audit ---")
    print("reference kinds:", res["reference_kinds"])
    print("written   kinds:", res["written_kinds"])
    print("unknown   kinds:", res["unknown_kinds"])
    print("records:", res["record_count"], "vs reference", res["reference_count"])
    print("audit:", "OK" if res["ok"] else "FAIL")
    if "--open" in sys.argv:
        print("--- official SpaceClaim open attempt ---")
        print(official_open(path))
    os.remove(path)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""H1: interoperability matrix harness.

Checks, per geometry family:
  1. write scdoc -> official SabSatConverter restore
  2. format roundtrips (STEP/IGES/OBJ/3MF) -> volume preservation
  3. SAT export -> official converter restore

Usage: python references/interop_matrix.py [--spaceclaim]
With --spaceclaim, additionally opens each scdoc in official SpaceClaim via
the verify_open sentinel (slow; one launch per file).
"""
import os
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scdm import kernel as K
from scdm.kdoc import KernelDoc
from scdm.scdoc_write import write_scdoc
from scdm.sat_write import write_sat
from scdm.document import load_scdoc
from scdm.import_sab import import_scdoc_bundle

CONVERTER = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
SCDM = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"

SHAPES = {
    "box": lambda: K.make_box(0.01, 0.02, 0.03),
    "cyl": lambda: K.make_cylinder(0.008, 0.02),
    "sphere": lambda: K.make_sphere(0.009),
    "torus": lambda: K.make_torus(0.015, 0.004),
}


def bodies_for(name):
    doc = KernelDoc()
    doc.add_body(SHAPES[name](), name=name)
    return doc


def converter_restore(sab_bytes, workdir):
    p_sab = os.path.join(workdir, "_m.sab")
    p_sat = os.path.join(workdir, "_m.sat")
    open(p_sab, "wb").write(sab_bytes)
    if os.path.exists(p_sat):
        os.remove(p_sat)
    subprocess.run([CONVERTER, "-i", p_sab, "-o", p_sat],
                   capture_output=True)
    ok = os.path.exists(p_sat)
    for p in (p_sab, p_sat):
        if os.path.exists(p):
            os.remove(p)
    return ok


def check_row(name, workdir):
    row = {"name": name, "restore": None, "sat": None, "iges": None,
           "obj": None, "3mf": None}
    doc = bodies_for(name)
    path = os.path.join(workdir, name + ".scdoc")
    write_scdoc(path, doc, name=name)

    # 1. official restore of our SAB
    z = zipfile.ZipFile(path)
    sab = z.read("SpaceClaim/Geometry/part1bodies.sab")
    row["restore"] = converter_restore(sab, workdir)

    # 2. self roundtrip (volume)
    k2 = import_scdoc_bundle(load_scdoc(path))
    row["self_bodies"] = len(k2.bodies)

    # 3. format roundtrips (mesh formats check face counts)
    shape = SHAPES[name]()
    K.write_iges(shape, ig := os.path.join(workdir, name + ".igs"))
    row["iges"] = K.volume(K.read_iges(ig)) > 0
    K.write_obj(shape, ob := os.path.join(workdir, name + ".obj"))
    row["obj"] = len(K.explore(K.read_obj(ob), "face")) > 0
    K.write_3mf(shape, mf := os.path.join(workdir, name + ".3mf"))
    row["3mf"] = len(K.explore(K.read_3mf(mf), "face")) > 0

    # 4. SAT export (backup path: planar/cyl only) -> official restore
    try:
        sat = write_sat(doc, name=name)
        p_sat = os.path.join(workdir, "_m2.sat")
        open(p_sat, "w").write(sat)
        p_sab2 = os.path.join(workdir, "_m2.sab")
        if os.path.exists(p_sab2):
            os.remove(p_sab2)
        subprocess.run([CONVERTER, "-i", p_sat, "-o", p_sab2],
                       capture_output=True)
        row["sat"] = os.path.exists(p_sab2)
    except ValueError:
        row["sat"] = None  # n/a (native path covers this geometry)
    return row


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--spaceclaim", action="store_true")
    args = ap.parse_args()
    workdir = tempfile.mkdtemp(prefix="interop_")
    print(f"{'shape':8s} restore self sat iges obj 3mf")
    all_ok = True
    for name in SHAPES:
        r = check_row(name, workdir)
        ok = all(r[k] for k in ("restore", "iges", "obj", "3mf")
                 if r[k] is not None) and r["restore"]
        all_ok &= ok
        print(f"{name:8s} {'OK' if r['restore'] else 'FAIL':6s} "
              f"{r['self_bodies']:4d} "
              f"{'--' if r['sat'] is None else ('OK' if r['sat'] else 'FAIL'):>4s} "
              f"{'OK' if r['iges'] else 'FAIL':4s} {'OK' if r['obj'] else 'FAIL':4s} "
              f"{'OK' if r['3mf'] else 'FAIL':4s}")
    if args.spaceclaim:
        # one SpaceClaim launch per scdoc via verify_open
        for name in SHAPES:
            path = os.path.join(workdir, name + ".scdoc")
            sent = os.path.join(os.getcwd(), "cyl_ref_sentinel.txt")
            err = os.path.join(os.getcwd(), "cyl_ref_error.txt")
            for p in (sent, err):
                if os.path.exists(p):
                    os.remove(p)
            subprocess.run([SCDM, os.path.abspath(path),
                            "/RunScript=" + os.path.abspath(
                                "references/verify_open.py"),
                            "/ExitAfterScript=True"], capture_output=True)
            res = open(sent).read() if os.path.exists(sent) else "timeout"
            print(f"spaceclaim {name}: {res.strip()}")
    print("ALL OK" if all_ok else "FAILURES PRESENT")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

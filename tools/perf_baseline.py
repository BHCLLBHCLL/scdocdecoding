# -*- coding: utf-8 -*-
"""P354/R71: 生成性能基线 docs/PERF_BASELINE.json（内存峰值 + 交互路径耗时）。

Usage::

    python tools/perf_baseline.py            # 测量并打印表格
    python tools/perf_baseline.py --write    # 另外写入 docs/PERF_BASELINE.json

The workload is deliberately the interactive path: build a sheet with a hole
pattern, tessellate it (what the viewport rebuilds), mesh it, and - when the
official library is present - import one sample.  Numbers are records, not
thresholds: the tests only guard against gross regressions.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scdm import kernel as K          # noqa: E402
from scdm import mesh as ME           # noqa: E402
from scdm import perf as P            # noqa: E402

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"


def workload_sheet():
    """A 20x20x2 sheet with a 5x5 hole pattern (30 holes, ~230 faces)."""
    solid = K.make_box(0.02, 0.02, 0.002)
    faces = K.explore(solid, "face")
    top = max(faces, key=lambda f: K.face_normal_center(f)[1][2])
    for i in range(5):
        for j in range(5):
            solid = K.hole_simple(solid, top, 0.001,
                                  depth=None,
                                  origin=(0.004 + i * 0.003, 0.004 + j * 0.003,
                                          0.002))
    return solid


def import_phase_memory(path: str) -> dict:
    """Parse / build memory split for one sample (R98/P438).

    Peak memory is monotonic, so the increments are the marginal cost of each
    phase: measured for samplemodel2 as parse +240.9 MB, build +153.7 MB.
    """
    from scdm import import_sab
    from scdm.document import load_scdoc

    m0 = P.peak_memory_mb()
    data = load_scdoc(path)
    m1 = P.peak_memory_mb()
    # R98: the probe below sets the module flag DIRECTLY (import_model does not
    # own it), so it must be restored - otherwise the next import in the same
    # process inherits it (measured: it broke tests/test_sphere_trim_r85).
    prev = import_sab._TRIM_PATCH
    import_sab._TRIM_CACHE.clear()
    try:
        import_sab._TRIM_PATCH = import_sab.trim_patch_policy(data["models"])
        docs = [import_sab.import_model(m) for m in data["models"]]
        m2 = P.peak_memory_mb()
    finally:
        import_sab._TRIM_PATCH = prev
        import_sab._TRIM_CACHE.clear()
    return {"parse_mb": m1 - m0, "build_mb": m2 - m1,
            "peak_after_parse_mb": m1, "peak_mb": m2,
            "bodies": sum(len(d.bodies) for d in docs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="write docs/PERF_BASELINE.json")
    ap.add_argument("--import-phases", action="store_true",
                    help="report the parse/build memory split (R98)")
    args = ap.parse_args(argv)
    if args.import_phases:
        if not os.path.isdir(LIB):
            print("official library absent" % ())
            return 1
        for name in ("SampleModel1.scdoc", "samplemodel2.scdoc"):
            path = os.path.join(LIB, name)
            if os.path.exists(path):
                print("%-20s %s" % (name, import_phase_memory(path)))
        return 0

    records = []
    sheet = workload_sheet()
    records.append(P.measure("build.sheet+25holes", workload_sheet, repeat=3))
    records.append(P.measure("tessellate.sheet", lambda: K.tessellate_mesh(sheet, 0.001), repeat=3))
    records.append(P.measure(
        "mesh.surface", lambda: ME.mesh_shape(sheet, deflection=5e-4), repeat=2,
        summary=lambda m: {"triangles": len(m["triangles"]),
                           "vertices": len(m["vertices"])}))
    records.append(P.measure("bbox+props.sheet", lambda: (K.bounding_box(sheet), K.volume(sheet), K.area(sheet)), repeat=5))
    if os.path.isdir(LIB):
        from scdm.document import load_scdoc
        sample = os.path.join(LIB, "samplemodel3.scdoc")
        if os.path.exists(sample):
            records.append(P.measure("load_scdoc.samplemodel3",
                                     lambda: load_scdoc(sample), repeat=1))
        # R96/P433: the IMPORT path (decode + rebuild + sew) changed a lot after
        # R71 (trim policies, sphere/torus trimming, the 1e-5 sewing tolerance),
        # and none of it was covered by the lines above - these two records are
        # what lets a later round catch an import regression.
        from scdm import import_sab
        for name, label in (("SampleModel1.scdoc", "import.SampleModel1"),
                            ("samplemodel2.scdoc", "import.samplemodel2")):
            path = os.path.join(LIB, name)
            if os.path.exists(path):
                records.append(P.measure(
                    label,
                    lambda p=path: import_sab.import_scdoc_bundle(load_scdoc(p)),
                    repeat=1,
                    summary=lambda k: {"bodies": len(k.bodies)}))
    print(P.table(records))
    if args.write:
        path = ROOT / "docs" / "PERF_BASELINE.json"
        P.write_baseline(str(path), records,
                         note="P354/R71 baseline + R96 import records: interactive"
                              " path, records only")
        print("written", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

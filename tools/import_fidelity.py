# -*- coding: utf-8 -*-
"""P29: SAB-vs-import fidelity report over the official SpaceClaim library.

Usage::

    python tools/import_fidelity.py            # table only
    python tools/import_fidelity.py --strict   # exit 1 when any sample differs

Compares, per sample, the topology counts decoded from SAB with the counts of
the OCCT document the importer builds. This is the acceptance instrument for
"can we actually open an official file" - a parse that yields no exception but
loses 90% of the faces is a failure.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scdm.document import load_scdoc  # noqa: E402
from scdm.import_sab import import_scdoc_bundle  # noqa: E402

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"


def _sab_counts(data):
    bodies = faces = edges = 0
    for m in data["models"]:
        bodies += len(m.of_kind("body"))
        faces += len(m.of_kind("face"))
        edges += len(m.of_kind("edge"))
    return bodies, faces, edges


def _sab_bbox(data):
    """Bounding box of the SAB's own vertex points (ground truth)."""
    lo = [1e30] * 3
    hi = [-1e30] * 3
    for m in data["models"]:
        for v in m.of_kind("vertex"):
            p = m.point_of_vertex(v)
            if p is None:
                continue
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    return (lo, hi) if lo[0] < 1e29 else None


def _imported_bbox(kdoc):
    from scdm import kernel as K
    from scdm import additive as A
    lo = [1e30] * 3
    hi = [-1e30] * 3
    seen = False
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        try:
            (a, c) = A.shape_bbox(b.shape)
        except Exception:
            continue
        seen = True
        for i in range(3):
            lo[i] = min(lo[i], a[i])
            hi[i] = max(hi[i], c[i])
    return (lo, hi) if seen else None


def _imported_counts(data):
    """(brep_bodies, brep_faces, mesh_fallbacks) - mesh bodies counted apart."""
    from scdm import kernel as K
    kdoc = import_scdoc_bundle(data)
    _imported_counts.last_import_s = time.time()
    _imported_counts.warnings = list(getattr(kdoc, "import_warnings", []))
    _imported_counts.bbox = _imported_bbox(kdoc)
    bodies = faces = mesh = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            mesh += 1
            continue
        bodies += 1
        try:
            faces += len(K.explore(b.shape, "face"))
        except Exception:
            pass
    return bodies, faces, mesh


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when any sample's fidelity differs")
    ap.add_argument("--time", action="store_true",
                    help="also report load/import wall-clock seconds")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    bad = 0
    print("%-20s %-14s %-14s %s" % ("sample", "SAB b/f/e", "imported b/f", "verdict"))
    for path in sorted(glob.glob(os.path.join(LIB, "*.scdoc"))):
        name = os.path.basename(path)
        try:
            t0 = time.time()
            data = load_scdoc(path)
            t1 = time.time()
            sb, sf, se = _sab_counts(data)
            ib, if_, mesh = _imported_counts(data)
            t2 = time.time()
        except Exception as exc:
            print("%-20s %-14s %-14s ERROR %s" % (name, "-", "-", exc))
            bad += 1
            continue
        ok = (ib == sb and if_ == sf and not mesh)
        if not ok:
            bad += 1
        extra = ("  (+%d mesh)" % mesh) if mesh else ""
        warns = getattr(_imported_counts, "warnings", [])
        if warns:
            extra += "  [" + "; ".join(warns) + "]"
        if args.time:
            extra += "  load %.2fs import %.2fs" % (t1 - t0, t2 - t1)
        sb_box = _sab_bbox(data)
        ib_box = getattr(_imported_counts, "bbox", None)
        if sb_box and ib_box:
            span_s = max(sb_box[1][i] - sb_box[0][i] for i in range(3))
            span_i = max(ib_box[1][i] - ib_box[0][i] for i in range(3))
            drift = abs(span_i - span_s) / (span_s or 1.0)
            extra += "  bbox drift %.1f%%" % (drift * 100.0)
        print("%-20s %-14s %-14s %s%s"
              % (name, "%d/%d/%d" % (sb, sf, se), "%d/%d" % (ib, if_),
                 "OK" if ok else "DIFF", extra))
    if args.strict:
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

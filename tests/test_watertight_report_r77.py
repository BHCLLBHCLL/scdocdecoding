"""R77: the relaxed trim gate (gross overshoot) and the countable watertight report.

Two changes this round:

1. the trim gate used to reject a patch reaching more than 5% of the face
   diagonal outside the face's POINT bbox.  That bbox is chord based, so a
   legitimately curved patch can reach outside it: at 5% SampleModel1 lost 2
   cylinder faces and samplemodel2 26.  The gate now uses the same scale-free
   gross-overshoot rule as the arc branch (> one full diagonal is a misread),
   measured effect: trimmable 355 -> 403 (samplemodel2), 24 -> 131
   (samplemodel5, ratio 0.99), gaps 2145 -> 1953, loops unchanged.

2. import_report now carries open_edges / seam_edges / free_loops, measured with
   the same kernel helpers the instruments use, plus a Qt-free hint.  Cost of
   the measurement: 0.05 / 0.24 / 0.03 s on samplemodel2 (2325 free edges).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")

# sample -> (cylinders, trimmable at the relaxed gate)
TRIMMABLE = {
    "SampleModel1.scdoc": (38, 33),
    "samplemodel5.scdoc": (132, 131),
    "samplemodel6.scdoc": (6, 0),
}


@requires_occ
@requires_lib
def test_relaxed_gate_accepts_the_curved_patches():
    """Chord-bbox overshoot is normal for a curved patch (R77)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    for name, (total, expected) in sorted(TRIMMABLE.items()):
        data = load_scdoc(os.path.join(LIB, name))
        got = ok = 0
        for m in data["models"]:
            box = import_sab._model_bbox(m)
            for f in m.of_kind("face"):
                kind, s = import_sab._surface_kind(m, f)
                if (kind != "cone" or s is None
                        or abs(s.semangle or 0.0) > 1e-9):
                    continue
                surf = import_sab._cylinder_surface(s)
                if surf is None:
                    continue
                got += 1
                if import_sab._trimmed_face(m, f, surf, box) is not None:
                    ok += 1
        assert got == total, (name, got)
        assert ok == expected, (name, ok)


@requires_occ
@requires_lib
def test_watertightness_is_in_the_import_report():
    """The GUI-visible numbers, measured on SampleModel1 (R77/P380)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    kdoc = import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "SampleModel1.scdoc")))
    rep = kdoc.import_report
    assert (rep["open_edges"], rep["seam_edges"], rep["free_loops"]) == (36, 0, 4)
    assert rep["parts"] == 1                     # existing keys untouched


@pytest.mark.parametrize("report,expected", [
    ({}, ""),
    ({"open_edges": 0, "free_loops": 9}, ""),
    ({"open_edges": 36}, " · 未封闭 36 处"),
    ({"open_edges": 36, "free_loops": 4}, " · 未封闭 36 处（自由环 4）"),
    ({"open_edges": 36, "free_loops": 4, "seam_edges": 18},
     " · 未封闭 36 处（自由环 4，缝边 18）"),
    ({"open_edges": 36, "seam_edges": 18}, " · 未封闭 36 处（缝边 18）"),
])
def test_watertight_hint_wording(report, expected):
    """One Qt-free source for the tree/status wording (R77/P380)."""
    from scdm.import_sab import watertight_hint

    assert watertight_hint(report) == expected

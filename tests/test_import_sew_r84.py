"""R84/P404: the import sewing tolerance is 1e-5, and why (measured).

R72 tried raising the sewing tolerance and refused: 1e-3 did not close
SampleModel1's loops and changed the shell splitting.  That measurement was
taken with the OLD geometry; R73-R83 made the boundary curves exact and the
cylinder patches truly trimmed, so the same question was re-measured:

  tol 1e-6 -> 1e-5   SampleModel4 gaps 375 -> 347, loops 86 -> 76
                     samplemodel2 gaps 1272 -> 1242, loops 359 -> 356
                     SampleModel1/3/5 0/0 and samplemodel6 3/2 unchanged
                     face counts identical everywhere, no time regression

Also measured and NOT adopted: BRepBuilderAPI_Sewing with NonManifoldMode on
the worst samplemodel2 body closes 240 -> 192 gaps, but produces non-manifold
shells - worse data for mass properties and STEP export than an open shell.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

LIB = r"C:\\Program Files\\ANSYS Inc\\v195\\scdm\\Library\\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")

# sample -> (gaps, loops) at the import tolerance
MEASURED = {
    "SampleModel1.scdoc": (0, 0),
    "SampleModel4.scdoc": (335, 72),
    "samplemodel2.scdoc": (990, 195),
    "samplemodel6.scdoc": (3, 2),
}


def test_the_tolerance_is_the_measured_one():
    from scdm import import_sab

    assert import_sab._SEW_TOL == 1e-5


@requires_occ
@requires_lib
def test_import_outcome_at_the_import_tolerance():
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    for name, (gaps, loops) in sorted(MEASURED.items()):
        kdoc = import_sab.import_scdoc_bundle(
            load_scdoc(os.path.join(LIB, name)))
        got_gaps = got_loops = 0
        for b in kdoc.bodies:
            if (b.name or "").startswith("网格导入"):
                continue
            rep = K.watertight_report(b.shape)
            got_gaps += rep["open_edges"]
            got_loops += rep["free_loops"]
        assert (got_gaps, got_loops) == (gaps, loops), name
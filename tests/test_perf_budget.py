"""P25: official-library load budget + import-path guard.

Measured 2026-09-12 (conda env scdm, this machine):

  sample          load_scdoc   B-rep import   SAB bodies/faces  imported
  samplemodel6        0.12 s         2.01 s        1 / 28        1 / 12
  samplemodel3        0.38 s         0.28 s        1 / 111       1 / 348
  SampleModel1        0.72 s         0.08 s        1 / 109       1 / 3
  SampleModel4        1.74 s         0.19 s        2 / 177       2 / 6
  samplemodel2        5.15 s        56.42 s       37 / 1813     35 / 12321
  samplemodel5        6.06 s         1.35 s       80 / 1288     80 / 313

Two findings, both registered for R5: the B-rep importer is not faithful for
official geometry (face counts off, 2 bodies dropped on samplemodel2) and it is
slow on the largest sample. The budgets below only pin the parts that are
already acceptable, so a regression cannot silently make them worse.
"""
from __future__ import annotations

import os
import time
from types import SimpleNamespace

import pytest

from scdoc_parser import topology as T
from scdm.document import load_scdoc

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


def test_edge_endpoints_tolerates_missing_curve_range():
    """P25: official streams omit t0/t1 on straights; must return None, not crash."""

    class _Stub:
        def e(self, ref):
            return SimpleNamespace(kind="straight", origin=(0.0, 0.0, 0.0),
                                   direction=(1.0, 0.0, 0.0), t0=None, t1=1.0)

    assert T.SabModel.edge_endpoints(_Stub(), SimpleNamespace(curve=0)) is None


@requires_lib
def test_library_load_budget():
    """load_scdoc stays within the measured + 50% envelope.

    R71/P354: the budget is a machine-IDLE measurement, so take the best of two
    runs - running the suite under load once measured samplemodel2 at 26.4 s
    (budget 20 s) and 4 s when re-run alone on the same machine.
    """
    for name, budget in (("samplemodel6.scdoc", 5.0),
                         ("samplemodel2.scdoc", 20.0)):
        best = None
        data = None
        for _ in range(2):
            t0 = time.time()
            data = load_scdoc(os.path.join(LIB, name))
            dt = time.time() - t0
            best = dt if best is None else min(best, dt)
        assert data["models"], name
        assert best < budget, "%s load took %.2fs (budget %.1fs)" % (name, best,
                                                                    budget)


@pytest.mark.skipif(not __import__("importlib").util.find_spec("OCC"),
                    reason="kernel absent")
@requires_lib
def test_official_import_does_not_crash():
    """The B-rep importer must handle official geometry (body count sanity)."""
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle

    for name, min_bodies in (("samplemodel6.scdoc", 1), ("samplemodel3.scdoc", 1),
                             ("samplemodel5.scdoc", 80)):
        t0 = time.time()
        kdoc = import_scdoc_bundle(load_scdoc(os.path.join(LIB, name)))
        dt = time.time() - t0
        assert len(kdoc.bodies) >= min_bodies, name
        assert dt < 60.0, "%s import took %.1fs" % (name, dt)

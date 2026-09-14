"""R97/P436: one trim verdict per face per import (the probe and the build share it).

Measured before: SampleModel1 ran 79 trim attempts over 41 distinct faces (38
wasted) because the policy probe probes faces that the build then trims again;
samplemodel2 wasted 40 of 746.  The cache key is (model id, face index, strict
flag) and it is cleared at the START of an import - clearing it inside the
rebuild (where the loss counters live) wipes the probe's verdicts, which is
exactly the bug the first version had and the second test pins down.

After: 41 and 706 uncached trims, import 1.46 -> 1.39 s and 7.13 -> 6.89 s,
with identical geometry (0/0, 335/72, 990/195 gaps/loops and the same faces).
"""
from __future__ import annotations

import importlib.util
import os
from collections import Counter
from pathlib import Path

import pytest

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


def _counting_import(monkeypatch, name):
    """Import one sample with _trimmed_face_uncached counted."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    real = import_sab._trimmed_face_uncached
    calls = Counter()

    def counted(model, face_ent, surf, box=None, strict_bbox=True):
        calls[(id(model), face_ent.idx, bool(strict_bbox))] += 1
        return real(model, face_ent, surf, box, strict_bbox)

    monkeypatch.setattr(import_sab, "_trimmed_face_uncached", counted)
    data = load_scdoc(os.path.join(LIB, name))
    kdoc = import_sab.import_scdoc_bundle(data)
    return calls, kdoc


@requires_occ
@requires_lib
def test_a_face_is_trimmed_once_per_import(monkeypatch):
    from scdm import kernel as K

    calls, kdoc = _counting_import(monkeypatch, "SampleModel1.scdoc")
    assert sum(calls.values()) == len(calls) == 41, calls
    gaps = loops = faces = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        faces += len(K.explore(b.shape, "face"))
        rep = K.watertight_report(b.shape)
        gaps += rep["open_edges"]
        loops += rep["free_loops"]
    # the cache must not change WHAT is built
    assert faces == 109 and (gaps, loops) == (0, 0)


@requires_occ
@requires_lib
def test_the_cache_is_cleared_before_the_policy_probe(monkeypatch):
    """Two imports in one process: the second must trim again (R97 bug)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    # one patch, one counter, cleared between the two imports (patching twice
    # would wrap the first counter and double-count)
    real = import_sab._trimmed_face_uncached
    calls = Counter()

    def counted(model, face_ent, surf, box=None, strict_bbox=True):
        calls[(id(model), face_ent.idx, bool(strict_bbox))] += 1
        return real(model, face_ent, surf, box, strict_bbox)

    monkeypatch.setattr(import_sab, "_trimmed_face_uncached", counted)
    import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "SampleModel1.scdoc")))
    first = Counter(calls)
    calls.clear()
    import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "SampleModel1.scdoc")))
    assert sum(first.values()) == len(first) == 41, first
    assert sum(calls.values()) == len(calls) == 41, calls


@requires_occ
@requires_lib
def test_samplemodel2_has_no_repeats_either(monkeypatch):
    calls, kdoc = _counting_import(monkeypatch, "samplemodel2.scdoc")
    assert sum(calls.values()) == len(calls) == 706, len(calls)
    assert kdoc.import_report["ref_no_curve"] == 1

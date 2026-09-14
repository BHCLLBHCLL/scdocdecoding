"""R98/P438: import memory - the split, and one release that is verifiable.

Measured for samplemodel2 (fresh process): parse (load_scdoc) +240.9 MB,
build (faces + sewing) +153.7 MB, peak 415.3 MB - i.e. the decoded SAB data is
the bigger half and it belongs to the CALLER, so the importer cannot free it.
What the importer CAN release is its own per-import cache: _TRIM_CACHE holds an
accepted candidate face for every trimmed face, so it is cleared when the import
ends (this file asserts it is empty afterwards).

scdm/perf.py gained current_memory_mb() next to peak_memory_mb(): a release can
only be shown with the current working set, not with a monotonic peak.
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

spec = importlib.util.spec_from_file_location(
    "perf_baseline", ROOT / "tools" / "perf_baseline.py")
perf_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perf_tool)


def test_current_memory_sits_below_the_peak():
    from scdm import perf as P

    peak = P.peak_memory_mb()
    now = P.current_memory_mb()
    if peak <= 0 or now <= 0:
        pytest.skip("OS memory counters unavailable on this platform")
    assert now > 5.0                     # a process with OCCT loaded is MB, not KB
    assert now <= peak + 1.0             # the current set cannot exceed the peak


@requires_occ
@requires_lib
def test_the_trim_cache_is_released_after_the_import():
    from scdm import import_sab
    from scdm.document import load_scdoc

    assert import_sab._TRIM_CACHE == {}
    import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "SampleModel1.scdoc")))
    assert import_sab._TRIM_CACHE == {}, "the import must release its cache"


@requires_occ
@requires_lib
def test_the_phase_tool_splits_parse_and_build():
    """Shape of the record (the increments are 0 once the peak is reached)."""
    rec = perf_tool.import_phase_memory(
        os.path.join(LIB, "SampleModel1.scdoc"))
    # peak memory is monotonic: in a process that already peaked (this test
    # file imports samples too) a phase can add ZERO to the peak - measured,
    # which is why the fields are recorded as increments, not absolutes
    assert rec["parse_mb"] >= 0.0 and rec["build_mb"] >= 0.0
    assert rec["peak_mb"] >= rec["peak_after_parse_mb"] >= 0.0
    assert rec["bodies"] == 1

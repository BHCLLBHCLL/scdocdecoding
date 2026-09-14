"""P354/R71: the performance baseline - memory peak and interactive-path times.

Records, not thresholds (the plan says so): the numbers live in
docs/PERF_BASELINE.json and the assertions here are generous regression guards.
Two ctypes details were measured while building it - see scdm/perf.py.

R96 added two import records to the tool's workload.  They run AFTER the sheet
and mesh work, so they are loaded numbers: measured 3.3 s (SampleModel1) and
40.3 s (samplemodel2) in that context against 1.5 s / 7.5 s standalone - the
record is honest about which one it is, and the file says so.
"""
from __future__ import annotations

import json
import os
import time

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import mesh as ME  # noqa: E402
from scdm import perf as P  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "docs", "PERF_BASELINE.json")


def test_p354_memory_counters_are_real_and_consistent():
    peak = P.peak_memory_mb()
    py_peak = P.python_peak_mb()
    if peak <= 0:
        pytest.skip("OS memory counter unavailable on this platform")
    # a Python process with OCCT loaded is megabytes, not kilobytes
    assert peak > 5.0
    # the two counters must be consistent (a Python heap lives inside the
    # process working set); the +1 MB absorbs sampling order
    assert peak + 1.0 >= py_peak


def test_p354_measure_is_json_safe_and_times_the_call():
    box = K.make_box(0.02, 0.02, 0.02)
    rec = P.measure("bbox", lambda: K.bounding_box(box), repeat=2,
                    summary=lambda r: {"span": r[1][0] - r[0][0]})
    assert rec["repeat"] == 2 and rec["per_call"] > 0.0
    assert rec["seconds"] >= rec["per_call"]
    assert rec["result"]["span"] == pytest.approx(0.02, abs=1e-6)   # Bnd_Box pad
    assert json.dumps(rec)                       # must serialize
    # without a summary the raw OCCT shape must NOT leak into the record
    rec2 = P.measure("shape", lambda: box)
    assert isinstance(rec2["result"], str) and "TopoDS" in rec2["result"]
    json.dumps(rec2)


def test_p354_baseline_file_carries_the_interactive_paths():
    assert os.path.exists(BASELINE), "docs/PERF_BASELINE.json missing"
    data = P.read_baseline(BASELINE)
    labels = [r["label"] for r in data["records"]]
    assert "build.sheet+25holes" in labels
    assert "tessellate.sheet" in labels
    assert "mesh.surface" in labels
    assert data["machine"]["python"]
    for r in data["records"]:
        assert r["per_call"] > 0.0
    # R96: the IMPORT path is recorded too (it changed a lot after R71).  The
    # records are taken AFTER the sheet/mesh workload, so they are deliberately
    # "under load" numbers (measured: 3.3 s / 40.3 s there against 1.5 s /
    # 7.5 s standalone) - see docs/ROUND_R96 for the comparison.
    if os.path.isdir(r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"):
        assert "import.SampleModel1" in labels
        assert "import.samplemodel2" in labels


def test_p354_interactive_path_stays_within_a_generous_budget():
    """The same workload as the tool, with a 5 s guard per stage (records only)."""
    t0 = time.perf_counter()
    solid = K.make_box(0.02, 0.02, 0.002)
    top = max(K.explore(solid, "face"),
              key=lambda f: K.face_normal_center(f)[1][2])
    for i in range(5):
        for j in range(5):
            solid = K.hole_simple(solid, top, 0.001, depth=None,
                                  origin=(0.004 + i * 0.003, 0.004 + j * 0.003,
                                          0.002))
    build = time.perf_counter() - t0
    # 25 through-holes leave 25 cylindrical walls plus the 6 box faces
    faces = K.explore(solid, "face")
    cyl = [f for f in faces if K.face_cylinder_radius(f) is not None]
    assert len(cyl) == 25 and len(faces) >= 31
    t1 = time.perf_counter()
    K.tessellate_mesh(solid, 0.001)
    tess = time.perf_counter() - t1
    t2 = time.perf_counter()
    mesh = ME.mesh_shape(solid, deflection=5e-4)
    mesh_dt = time.perf_counter() - t2
    assert build < 5.0 and tess < 5.0 and mesh_dt < 5.0
    assert len(mesh["triangles"]) > 0 and len(mesh["vertices"]) > 0

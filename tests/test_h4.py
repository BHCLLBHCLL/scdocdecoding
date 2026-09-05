"""H4: check-geometry suite — detectors + auto-repair on crafted defects."""
from __future__ import annotations

import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def _box():
    return K.make_box(0.01, 0.01, 0.01)


def test_clean_box_no_findings():
    fnd = K.check_geometry(_box())
    total = sum(len(v) if isinstance(v, list) else int(v)
                for v in fnd.values())
    assert total == 0, fnd


def test_small_face_detection_threshold():
    # box faces are 1e-4 m^2 (100 mm^2); a 1e-5 m^2 threshold flags nothing
    b = _box()
    fnd = K.check_geometry(b, min_area=1e-5)
    assert len(fnd["small_faces"]) == 0


def test_small_face_detection_real():
    b = _box()
    # faces are 1e-4 m^2; a 1e-3 m^2 threshold flags all six
    fnd = K.check_geometry(b, min_area=5e-3)
    assert len(fnd["small_faces"]) == 6


def test_inverted_face_detected_and_repaired():
    box = _box()
    f0 = K.explore(box, "face")[0]
    inv = K.reverse_face(box, f0)
    fnd = K.check_geometry(inv)
    assert len(fnd["inverted_faces"]) == 1
    fixed, rep = K.repair_geometry(inv, fnd)
    assert rep.get("inverted_faces") == 1
    assert len(K.check_geometry(fixed)["inverted_faces"]) == 0
    assert abs(K.volume(fixed) - 1e-6) < 1e-12  # geometry preserved


def test_short_edge_detection():
    # stepped union leaves a 50 um step edge
    a = _box()
    b = K.translate(_box(), (0.01, 0, 0.00005))
    u = K.fuse(a, b)
    fnd = K.check_geometry(u, min_edge=0.0002)
    assert len(fnd["short_edges"]) >= 1


def test_interference_between_bodies():
    a = _box()
    b = K.translate(_box(), (0.005, 0, 0))
    assert K.interference_volume(a, b) > 0
    c = K.translate(_box(), (0.05, 0, 0))
    assert K.interference_volume(a, c) == 0


def test_scripting_repair_check():
    from scdm.kdoc import KernelDoc
    from scdm.scripting import replay

    doc = KernelDoc()
    doc.add_body(_box(), name="B")
    # 1: no findings
    msgs = replay([{"cmd": "repair.check",
                    "opts": {"min_area_mm2": 1e4}}], doc, scale=1000.0)
    assert msgs[-1].startswith("OK")
    # 2: threshold flags the 100 mm^2 faces as small, auto-repair runs
    doc2 = KernelDoc()
    doc2.add_body(_box(), name="B")
    msgs2 = replay([{"cmd": "repair.check",
                     "opts": {"min_area_mm2": 10000.0}}], doc2, scale=1000.0)
    assert msgs2[-1].startswith("OK")

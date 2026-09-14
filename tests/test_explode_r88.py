"""R88/P415: assembly explode batch 2 - axis / radial / scale, countable.

Batch 1 lived entirely in the GUI (one +X step per component).  The offsets
are now computed by scdm.assembly.explode_offsets (pure maths, no kernel) and
applied by op "asm.explode", so the numbers can be asserted:

  axis    offset_i = u_axis * distance * i
  radial  offset_i = unit(center_i - pivot) * distance * i
  scale   offset_i = (center_i - pivot) * distance

anchored components never move; distance 0 restores everything (apply_explode
subtracts each component's recorded explosion first).
"""
from __future__ import annotations

import importlib.util
import math

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")

CENTRES = {"A": (0.0, 0.0, 0.0), "B": (0.10, 0.0, 0.0), "C": (0.0, 0.10, 0.0)}


def test_axis_mode_is_an_exact_arithmetic_progression():
    from scdm import assembly as ASM

    off = ASM.explode_offsets(CENTRES, mode="axis", distance=0.02,
                              axis=(0.0, 1.0, 0.0), order=["A", "B", "C"])
    assert off["A"] == (0.0, 0.02, 0.0)
    assert off["B"] == (0.0, 0.04, 0.0)
    assert off["C"] == (0.0, 0.06, 0.0)
    assert ASM.total_displacement(off) == pytest.approx(0.12, rel=1e-12)


def test_radial_mode_points_away_from_the_pivot():
    from scdm import assembly as ASM

    pivot = ASM.centroid(list(CENTRES.values()))
    off = ASM.explode_offsets(CENTRES, mode="radial", distance=0.05,
                              pivot=pivot, order=["A", "B", "C"])
    for cid, c in CENTRES.items():
        rel = [c[i] - pivot[i] for i in range(3)]
        n = math.sqrt(sum(v * v for v in rel))
        # 1st component keeps its rank: length = distance * i
        i = ["A", "B", "C"].index(cid) + 1
        assert math.dist(off[cid], (0.0, 0.0, 0.0)) == pytest.approx(0.05 * i,
                                                                     rel=1e-12)
        if n > 1e-12:
            u = [v / n for v in rel]
            got = [v / (0.05 * i) for v in off[cid]]
            assert max(abs(got[k] - u[k]) for k in range(3)) < 1e-12, cid


def test_scale_mode_is_proportional_to_the_distance_from_the_pivot():
    from scdm import assembly as ASM

    pivot = (0.0, 0.0, 0.0)
    off = ASM.explode_offsets(CENTRES, mode="scale", distance=0.5, pivot=pivot)
    assert off["B"] == pytest.approx((0.05, 0.0, 0.0), rel=1e-12)
    assert off["C"] == pytest.approx((0.0, 0.05, 0.0), rel=1e-12)
    assert off["A"] == (0.0, 0.0, 0.0)      # sits on the pivot


def test_anchored_components_and_zero_distance():
    from scdm import assembly as ASM

    off = ASM.explode_offsets(CENTRES, mode="axis", distance=0.01,
                              anchored=["B"])
    assert off["B"] == (0.0, 0.0, 0.0)
    assert off["A"] != (0.0, 0.0, 0.0)
    zero = ASM.explode_offsets(CENTRES, mode="axis", distance=0.0)
    assert all(v == (0.0, 0.0, 0.0) for v in zero.values())


def test_bad_requests_are_refused():
    from scdm import assembly as ASM

    with pytest.raises(ValueError):
        ASM.explode_offsets(CENTRES, mode="spiral", distance=0.01)
    with pytest.raises(ValueError):
        ASM.explode_offsets(CENTRES, mode="radial", distance=0.01)
    with pytest.raises(ValueError):
        ASM.explode_offsets(CENTRES, mode="axis", distance=0.01, axis=(0, 0, 0))


@requires_occ
def _doc_with_two_components():
    from scdm.kdoc import KernelDoc
    from scdm import kernel as K

    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02, origin=(0.0, 0.0, 0.0)), name="A")
    b = doc.add_body(K.make_box(0.02, 0.02, 0.02, origin=(0.10, 0.0, 0.0)), name="B")
    doc.add_component("件 A", [a.id])
    doc.add_component("件 B", [b.id])
    return doc, a, b


@requires_occ
def _centre(body):
    from scdm import additive as A

    lo, hi = A.shape_bbox(body.shape)
    return tuple((lo[i] + hi[i]) / 2.0 for i in range(3))


@requires_occ
def test_op_moves_bodies_by_the_counted_vector_and_restores_them():
    from scdm.scripting import OPS

    doc, a, b = _doc_with_two_components()
    before = (_centre(a), _centre(b))
    out, msg = OPS["asm.explode"](doc, {"mode": "axis", "distance_mm": 10.0,
                                        "axis": (1.0, 0.0, 0.0)}, 1000.0)
    assert out is None and "总位移" in msg and "2/2" in msg, msg
    after = (_centre(a), _centre(b))
    # component order: A first -> 10 mm, B second -> 20 mm along +X
    assert after[0][0] - before[0][0] == pytest.approx(0.010, rel=1e-9)
    assert after[1][0] - before[1][0] == pytest.approx(0.020, rel=1e-9)
    assert abs(after[0][1] - before[0][1]) < 1e-12
    out, msg = OPS["asm.explode"](doc, {"restore": True}, 1000.0)
    assert "还原" in msg, msg
    back = (_centre(a), _centre(b))
    for want, got in zip(before, back):
        assert max(abs(want[i] - got[i]) for i in range(3)) < 1e-12


@requires_occ
def test_op_radial_mode_directions_and_replay():
    from scdm.scripting import replay

    doc, a, b = _doc_with_two_components()
    before = (_centre(a), _centre(b))          # 0.01 and 0.11 -> pivot 0.06
    steps = [{"cmd": "asm.explode", "opts": {"mode": "radial",
                                             "distance_mm": 5.0}}]
    msgs = replay(steps, doc, 1000.0)
    assert msgs and msgs[0].startswith("OK asm.explode"), msgs
    ca, cb = _centre(a), _centre(b)
    # A is left of the pivot and B right of it, so radial mode pushes them
    # APART: |xA - pivot| grows, |xB - pivot| grows, and both stay on the axis
    pivot = (before[0][0] + before[1][0]) / 2.0
    assert abs(ca[0] - pivot) > abs(before[0][0] - pivot)
    assert abs(cb[0] - pivot) > abs(before[1][0] - pivot)
    assert ca[0] < before[0][0] < pivot < before[1][0] < cb[0]
    # ... and the y/z components stay untouched (the pivot shares their y/z)
    assert ca[1] == pytest.approx(before[0][1], abs=1e-12)
    assert cb[1] == pytest.approx(before[1][1], abs=1e-12)
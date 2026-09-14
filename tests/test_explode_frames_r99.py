"""R99/P440: the explosion is an animation - every frame is a closed form.

frame_offsets(offsets, i, n) scales each component's final displacement by
t = i/(n-1), so frame 0 is home (all zero vectors), frame n-1 is the full
explosion, and frame n//2 is exactly half.  No intermediate state is stored,
which is why a frame can be replayed and asserted like any other number.
"""
from __future__ import annotations

import importlib.util

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")

CENTRES = {"A": (0.0, 0.0, 0.0), "B": (0.10, 0.0, 0.0), "C": (0.0, 0.10, 0.0)}


def test_frames_interpolate_the_offsets_exactly():
    from scdm import assembly as ASM

    final = ASM.explode_offsets(CENTRES, mode="axis", distance=0.02,
                                order=["A", "B", "C"])
    frames = ASM.explode_frames(final, 3)
    assert len(frames) == 3
    assert all(v == (0.0, 0.0, 0.0) for v in frames[0].values())   # home
    # B is the second component: final (0.04, 0, 0), so frame 1 of 3 is half
    assert frames[1]["B"] == pytest.approx((0.02, 0.0, 0.0), rel=1e-12)
    assert frames[2] == final                                     # full
    # every frame keeps the direction (a scalar multiple of the final vector)
    for f in frames:
        for cid, v in f.items():
            want = final[cid]
            n = sum(c * c for c in want) ** 0.5
            if n < 1e-15:
                assert v == (0.0, 0.0, 0.0)
                continue
            t = sum(v[k] * want[k] for k in range(3)) / (n * n)
            assert v == pytest.approx(tuple(c * t for c in want), rel=1e-12)


def test_frames_are_monotonic_and_bounded():
    from scdm import assembly as ASM

    final = ASM.explode_offsets(CENTRES, mode="radial", distance=0.05,
                                pivot=(0.03, 0.03, 0.0), order=["A", "B", "C"])
    totals = [ASM.total_displacement(f)
              for f in ASM.explode_frames(final, 5)]
    assert totals[0] == 0.0
    assert totals == sorted(totals)
    assert totals[-1] == pytest.approx(ASM.total_displacement(final), rel=1e-12)


def test_bad_frame_requests_are_refused():
    from scdm import assembly as ASM

    final = ASM.explode_offsets(CENTRES, mode="axis", distance=0.01)
    with pytest.raises(ValueError):
        ASM.frame_offsets(final, 0, 1)          # at least two frames
    with pytest.raises(ValueError):
        ASM.frame_offsets(final, 4, 3)          # frame out of range


@requires_occ
def test_the_op_applies_the_requested_frame():
    from scdm import kernel as K
    from scdm.kdoc import KernelDoc
    from scdm.scripting import OPS

    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="A")
    b = doc.add_body(K.make_box(0.02, 0.02, 0.02, origin=(0.10, 0.0, 0.0)),
                     name="B")
    doc.add_component("件 A", [a.id])
    doc.add_component("件 B", [b.id])
    # full explosion: A 10 mm, B 20 mm along +X
    _o, msg = OPS["asm.explode"](doc, {"mode": "axis", "distance_mm": 10.0,
                                        "axis": (1.0, 0.0, 0.0)}, 1000.0)
    x_full = K.bounding_box(a.shape)[0][0] + K.bounding_box(a.shape)[1][0]
    # frame 1 of 3 = half: A 5 mm (the op first restores, then applies)
    _o, msg = OPS["asm.explode"](doc, {"mode": "axis", "distance_mm": 10.0,
                                        "axis": (1.0, 0.0, 0.0),
                                        "frames": 3, "frame": 1}, 1000.0)
    assert "帧 1/2" in msg, msg
    x_half = K.bounding_box(a.shape)[0][0] + K.bounding_box(a.shape)[1][0]
    # frame 0 puts everything back home
    _o, msg = OPS["asm.explode"](doc, {"mode": "axis", "distance_mm": 10.0,
                                        "axis": (1.0, 0.0, 0.0),
                                        "frames": 3, "frame": 0}, 1000.0)
    x_home = K.bounding_box(a.shape)[0][0] + K.bounding_box(a.shape)[1][0]
    assert (x_full - x_half) == pytest.approx(x_half - x_home, rel=1e-9)
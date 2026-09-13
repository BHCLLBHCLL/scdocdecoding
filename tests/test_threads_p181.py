"""P181: symbolic threads - spec validation and annotation-only geometry."""
from __future__ import annotations

import math

import pytest

from scdm import threads as T
from scdm import kernel as K


def test_p181_thread_spec_uses_the_tap_drill_rule():
    s = T.thread_spec(0.006, 0.001)
    assert s["tap_drill"] == pytest.approx(0.005)
    assert s["nominal"] == 0.006 and s["pitch"] == 0.001


def test_p181_thread_spec_rejects_illegal_parameters():
    for nominal, pitch in ((0.006, 0.0), (0.006, -0.001), (0.006, 0.006),
                           (0.006, 0.008)):
        with pytest.raises(K.KernelError):
            T.thread_spec(nominal, pitch)


def test_p181_thread_lines_stay_inside_the_hole_envelope():
    """The profile is annotation: every point is between tap and major radius."""
    origin, axis, nominal, pitch, depth = (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.006, 0.001, 0.01
    segs = T.thread_lines(origin, axis, nominal, pitch, depth)
    assert len(segs) >= 8
    rs, zs = [], []
    for a, b in segs:
        for p in (a, b):
            rs.append(math.hypot(p[0], p[1]))
            zs.append(p[2])
    assert min(rs) >= 0.0025 - 1e-9      # tap drill radius
    assert max(rs) <= 0.003 + 1e-9       # nominal radius
    assert min(zs) >= -1e-9 and max(zs) <= depth + 1e-9


def test_p181_thread_lines_follow_the_axis():
    segs = T.thread_lines((0.01, 0.02, 0.03), (0.0, 1.0, 0.0), 0.008, 0.00125, 0.004)
    zs = [p[1] for s in segs for p in s]
    # origin is the hole START on the axis (+Y here), so the run is 0.02..0.024
    assert min(zs) >= 0.02 - 1e-9 and max(zs) <= 0.024 + 1e-9
    assert all(abs(p[0] - 0.01) < 0.01 for s in segs for p in s)


def test_p181_symbolic_thread_does_not_change_volume():
    """Cutting the tap drill and adding annotation leaves volume to the hole."""
    box = K.make_box(0.02, 0.02, 0.02)
    face = [f for f in K.explore(box, "face")
            if K.face_normal_center(f)[0][2] > 0.99][0]
    holed = K.hole_tapped(box, face, 0.006, 0.001)
    removed = K.volume(box) - K.volume(holed)
    assert removed == pytest.approx(math.pi * 0.0025 ** 2 * 0.02, rel=1e-3)
    # annotation exists but consumed no geometry
    T.thread_lines((0.01, 0.01, 0.0), (0.0, 0.0, 1.0), 0.006, 0.001, 0.02)
    assert K.volume(holed) == pytest.approx(K.volume(holed), rel=0)
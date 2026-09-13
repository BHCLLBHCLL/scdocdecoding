"""P315/R59: close the R58 gap - the U-channel's straight flange makes the bend
pairing (and therefore unfold) work, without teaching the detector about
construction helpers.

The root cause was not the detector: axial_bend never used its `flange`
parameter, so the solid had no tangent flat past the bend and the two bend
cylinders were bounded only by helper planes through the axis.  Giving the
feature its real geometry fixes detection, the developed length and the volume
with one change - and the closed form finally matches the solid.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sheetmetal as SM  # noqa: E402

ANG = math.radians(90.0)
T = 0.002
L, W, FL, R = 0.08, 0.03, 0.01, 0.002


def _u():
    return SM.axial_bend(L, W, T, FL, ANG, R, 0.42)


def test_p315_u_channel_is_detected_as_two_bends():
    u = _u()
    bends = SM.detect_bends(u)
    assert len(bends) == 2, [b["angle_rad"] for b in bends]
    for b in bends:
        assert math.degrees(b["angle_rad"]) == pytest.approx(90.0, rel=1e-9)
        assert b["r_inner"] == pytest.approx(R, rel=1e-9)
        assert b["t"] == pytest.approx(T, rel=1e-9)
        # one bend measures the base, the other the flange (chain order varies)
        assert sorted([b["flat1_len"], b["flat2_len"]]) == pytest.approx(
            sorted([W, FL]), rel=1e-6)
    assert SM.detect_conical(u) == []


def test_p315_unfold_matches_the_hand_closed_form():
    u = _u()
    ba = SM.bend_allowance(ANG, R, 0.42, T)
    hand = W + 2.0 * (FL + ba)
    flat = SM.unfold(u, k=0.42)
    (x0, _y0, _z0), (x1, _y1, _z1) = K._vertex_bbox(flat)
    assert (x1 - x0) == pytest.approx(hand, rel=1e-9)
    pat = SM.flat_pattern(u, k=0.42)
    assert pat["length"] == pytest.approx(hand, rel=1e-9)
    assert len(pat["bend_lines"]) == 2
    # the flat pattern is the blank: area = developed length x width
    assert pat["width"] == pytest.approx(L, rel=1e-9)


def test_p315_u_channel_extremes_still_detect_and_unfold():
    for flange in (0.0005, 0.05):
        u = SM.axial_bend(L, W, T, flange, ANG, R, 0.42)
        assert len(SM.detect_bends(u)) == 2, flange
        ba = SM.bend_allowance(ANG, R, 0.42, T)
        flat = SM.unfold(u, k=0.42)
        (x0, _y0, _z0), (x1, _y1, _z1) = K._vertex_bbox(flat)
        assert (x1 - x0) == pytest.approx(W + 2.0 * (flange + ba), rel=1e-9), flange
    # a shallow bend (30 degrees) is still a bend
    shallow = SM.axial_bend(L, W, T, FL, math.radians(30.0), R, 0.42)
    assert len(SM.detect_bends(shallow)) == 2
    ba = SM.bend_allowance(math.radians(30.0), R, 0.42, T)
    flat = SM.unfold(shallow, k=0.42)
    (x0, _y0, _z0), (x1, _y1, _z1) = K._vertex_bbox(flat)
    assert (x1 - x0) == pytest.approx(W + 2.0 * (FL + ba), rel=1e-9)


def test_p315_existing_cylindrical_parts_are_unchanged():
    # single L-bend: one bend, hand-computed developed length
    part = SM.bend_from_flat(0.02, T, 0.03, 0.02, ANG, 0.002, 0.42)
    bends = SM.detect_bends(part)
    assert len(bends) == 1
    assert math.degrees(bends[0]["angle_rad"]) == pytest.approx(90.0, rel=1e-9)
    hand = 0.03 + 0.02 + SM.bend_allowance(ANG, 0.002, 0.42, T)
    assert SM.flat_pattern(part, k=0.42)["length"] == pytest.approx(hand, rel=1e-9)
    # a plain flat sheet has no bend at all
    assert SM.detect_bends(K.make_box(0.02, 0.02, T)) == []

"""P311/R58: conical bend + axial bend (U-channel).

Closed forms: Pappus for both volumes, neutral-layer arc length for the
developed lengths.  The conical part must NOT be reported as a cylindrical bend
(rule 60/67: a mis-detected cone would silently unfold with the wrong length),
and the existing cylindrical path must be untouched.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sheetmetal as SM  # noqa: E402

ANG = math.radians(90.0)
T = 0.002


def test_p311_conical_bend_volume_and_developed_length():
    h, r1, r2 = 0.03, 0.02, 0.03
    part = SM.conical_bend(ANG, T, h, r1, r2)
    # Pappus: the axis never meets the section, so volume = theta * r_c * A
    want = ANG * ((r1 + r2) / 2.0 + T / 2.0) * T * h
    assert K.volume(part) == pytest.approx(want, rel=1e-9)
    assert len(K.explore(part, "solid")) == 1
    # developed length: the K-factor rule applied on the mid generatrix
    ba = SM.conical_bend_allowance(ANG, r1, r2, 0.42, T)
    assert ba == pytest.approx(ANG * ((r1 + r2) / 2.0 + 0.42 * T), rel=1e-15)
    # a taller cone of the same taper scales the developed length by the angle
    assert SM.conical_bend_allowance(2 * ANG, r1, r2, 0.42, T) == pytest.approx(2 * ba, rel=1e-15)


def test_p311_conical_bend_is_not_a_cylindrical_bend():
    h, r1, r2 = 0.03, 0.02, 0.03
    part = SM.conical_bend(ANG, T, h, r1, r2)
    assert SM.detect_bends(part) == []          # no false cylindrical bend
    cones = SM.detect_conical(part)
    assert len(cones) == 2                      # inner + outer surface
    for c in cones:
        radii = sorted([c["r_at_start"], c["r_at_end"]])
        assert radii == pytest.approx([r1, r1 + T], rel=1e-9) or \
            radii == pytest.approx([r2, r2 + T], rel=1e-9) or \
            radii == pytest.approx([r1, r2], rel=1e-9) or \
            radii == pytest.approx([r1 + T, r2 + T], rel=1e-9)
        assert abs(c["semi_angle_rad"]) == pytest.approx(
            math.atan(abs(r2 - r1) / h), rel=1e-9)
        assert c["height"] == pytest.approx(h, rel=1e-9)
    # cones are surfaces of revolution about z
    assert all(abs(abs(c["axis"][2]) - 1.0) < 1e-9 for c in cones)


def test_p311_conical_bend_rejects_illegal_input():
    with pytest.raises(K.KernelError):
        SM.conical_bend(ANG, 0.0, 0.03, 0.02, 0.03)
    with pytest.raises(K.KernelError):
        SM.conical_bend(ANG, T, -0.03, 0.02, 0.03)
    with pytest.raises(K.KernelError):
        SM.conical_bend(ANG, T, 0.03, 0.0, 0.03)        # axis through the section
    with pytest.raises(K.KernelError):                  # equal radii = cylinder
        SM.conical_bend(ANG, T, 0.03, 0.02, 0.02)
    with pytest.raises(K.KernelError):
        SM.conical_bend(0.0, T, 0.03, 0.02, 0.03)
    with pytest.raises(K.KernelError):
        SM.conical_bend(2.0 * math.pi + 0.1, T, 0.03, 0.02, 0.03)


def test_p311_conical_extremes_are_exact():
    # a long thin cone (slope 1:10) and a steep one (1:1) both stay exact
    for (h, r1, r2) in ((0.10, 0.05, 0.06), (0.02, 0.01, 0.03)):
        part = SM.conical_bend(ANG, T, h, r1, r2)
        want = ANG * ((r1 + r2) / 2.0 + T / 2.0) * T * h
        assert K.volume(part) == pytest.approx(want, rel=1e-9), (h, r1, r2)
    # a full turn is legal (a closed cone ring)
    full = SM.conical_bend(2.0 * math.pi, T, 0.03, 0.02, 0.03)
    want = 2.0 * math.pi * ((0.02 + 0.03) / 2.0 + T / 2.0) * T * 0.03
    assert K.volume(full) == pytest.approx(want, rel=1e-9)


def test_p311_axial_bend_volume_stature_and_developed_length():
    L, w, fl, r = 0.08, 0.03, 0.01, 0.002
    u = SM.axial_bend(L, w, T, fl, ANG, r, 0.42)
    base = L * w * T
    flange = ANG * (r + T / 2.0) * T * L          # Pappus, one flange
    assert K.volume(u) == pytest.approx(base + 2.0 * flange, rel=1e-9)
    assert len(K.explore(u, "solid")) == 1 and len(K.explore(u, "shell")) == 1
    # stature: the flanges rise OUTSIDE the base footprint
    lo, hi = K._vertex_bbox(u)
    assert lo[1] == pytest.approx(-(r + T), abs=1e-9)
    assert hi[1] == pytest.approx(w + r + T, abs=1e-9)
    assert hi[2] == pytest.approx(r + T, abs=1e-9)
    # developed length = base + 2 * (flange + BA), BA = theta*(r + Kt)
    ba = SM.axial_bend_allowance(ANG, r, 0.42, T)
    assert ba == pytest.approx(SM.bend_allowance(ANG, r, 0.42, T), rel=1e-15)
    # hand value: BA = (pi/2)*(0.002 + 0.42*0.002) = 0.00446106,
    # developed = 0.03 + 2*(0.01 + BA) = 0.05892212
    assert w + 2.0 * (fl + ba) == pytest.approx(0.0589221, rel=1e-6)


def test_p311_axial_bend_rejects_illegal_input():
    with pytest.raises(K.KernelError):
        SM.axial_bend(0.0, 0.03, T, 0.01, ANG)
    with pytest.raises(K.KernelError):
        SM.axial_bend(0.08, 0.03, T, -0.01, ANG)
    with pytest.raises(K.KernelError):
        SM.axial_bend(0.08, 0.03, T, 0.01, 0.0)
    with pytest.raises(K.KernelError):
        SM.axial_bend(0.08, 0.03, T, 0.01, math.pi + 0.1)
    with pytest.raises(K.KernelError):
        SM.axial_bend(0.08, 0.03, T, 0.01, ANG, r_inner=-0.001)
    with pytest.raises(K.KernelError):
        SM.axial_bend(0.08, 0.03, T, 0.01, ANG, k=1.5)


def test_p311_existing_cylindrical_parts_are_unchanged():
    """Coexistence: the ordinary L-bend still detects and unfolds as before."""
    part = SM.bend_from_flat(0.02, T, 0.03, 0.02, ANG, 0.002, 0.42)
    bends = SM.detect_bends(part)
    assert len(bends) == 1
    assert math.degrees(bends[0]["angle_rad"]) == pytest.approx(90.0, rel=1e-9)
    assert SM.detect_conical(part) == []
    pat = SM.flat_pattern(part, k=0.42)
    hand = 0.03 + 0.02 + SM.bend_allowance(ANG, 0.002, 0.42, T)
    assert pat["length"] == pytest.approx(hand, rel=1e-9)
    assert len(pat["bend_lines"]) == 1

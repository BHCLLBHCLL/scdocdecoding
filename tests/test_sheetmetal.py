"""H5: sheet-metal kernel — K-factor bend, unfold, rip, corner, jog."""
from __future__ import annotations

import math

import pytest

from scdm import kernel as K
from scdm import sheetmetal as SM

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def test_bend_allowance_formula():
    # BA = theta * (R + K*t)
    assert SM.bend_allowance(math.pi / 2, 0.002, 0.42, 0.001) == \
        pytest.approx(math.pi / 2 * (0.002 + 0.00042))
    assert SM.bend_allowance(math.pi, 0.003, 0.5, 0.002) == \
        pytest.approx(math.pi * 0.004)


def test_bend_from_flat_volume():
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    expected = (0.03 * 0.02 * 0.001                 # flat1
                + (math.pi / 4) * (0.003 ** 2 - 0.002 ** 2) * 0.02  # arc
                + 0.02 * 0.02 * 0.001)             # flat2 (vertical leg)
    assert K.volume(b) == pytest.approx(expected, rel=1e-6)


def test_bend_inner_radius_tangent_top():
    """The bend's inner cylindrical face radius = r_inner and the arc top
    reaches z = t + r_inner."""
    import scdm.additive as A
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(b)
    # arc top reaches t + R; the vertical leg rises to t + R + len2
    assert z1 == pytest.approx(0.001 + 0.002 + 0.02)


def test_detect_bends_single():
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    bends = SM.detect_bends(b)
    assert len(bends) == 1
    x = bends[0]
    assert x["r_inner"] == pytest.approx(0.002)
    assert math.degrees(x["angle_rad"]) == pytest.approx(90.0)
    assert x["flat1_len"] == pytest.approx(0.03)
    assert x["flat2_len"] == pytest.approx(0.02)
    assert x["t"] == pytest.approx(0.001)
    assert x["width"] == pytest.approx(0.02)


def test_unfold_preserves_developed_length():
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    flat = SM.unfold(b, k=0.42)
    import scdm.additive as A
    (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(flat)
    ba = SM.bend_allowance(math.pi / 2, 0.002, 0.42, 0.001)
    assert (x1 - x0) == pytest.approx(0.03 + ba + 0.02)
    assert (y1 - y0) == pytest.approx(0.02)
    assert (z1 - z0) == pytest.approx(0.001)


def test_unfold_k_factor_changes_length():
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    import scdm.additive as A
    lens = []
    for k in (0.2, 0.8):
        flat = SM.unfold(b, k=k)
        (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(flat)
        lens.append(x1 - x0)
    assert lens[1] > lens[0]          # larger K -> larger BA -> longer flat


def test_rip_narrow_slit():
    box = K.make_box(0.01, 0.01, 0.001)
    f = K.explore(box, "face")[0]
    r = SM.rip(box, f, gap=0.0002)
    loss = K.volume(box) - K.volume(r)
    # slit centred on the edge: half the gap cross-section is inside
    assert 0 < loss < 0.0002 * 0.001 * 0.02   # narrow, material-only


def test_corner_relief_removes_material():
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    v0 = K.volume(b)
    cr = SM.corner_relief(b, (0.033, 0, 0.023), 0.002, round_=True)
    assert K.volume(cr) < v0


def test_jog_z_shape():
    j = SM.jog(0.02, 0.001, 0.03, 0.005, 0.02)
    expected = (0.03 * 0.02 * 0.001 + 0.001 * 0.02 * 0.005
                + 0.02 * 0.02 * 0.001)
    assert K.volume(j) == pytest.approx(expected, rel=1e-9)
    import scdm.additive as A
    (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(j)
    assert z1 == pytest.approx(0.005 + 0.001)   # web + flat2 thickness

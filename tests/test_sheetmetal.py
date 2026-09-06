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


# --------------------------------------------------- TODO-2: multi-bend unfold

def _z_profile(w, t, l1, l2, r):
    """Two-bend Z part: flat1 + 90deg bend + vertical web + a second 90deg
    bend at the web's free end (thin top-strip roll, no trailing flat3 —
    the empirical construction that detect_bends reads as two bends)."""
    import math
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    lshape = SM.bend_from_flat(w, t, l1, l2, math.pi / 2, r, 0.42)
    faces = K.explore(lshape, "face")
    top = None
    top_z = -1e18
    for f in faces:
        n, c = K.face_normal_center(f)
        if abs(n[2]) > 0.9 and c[2] > top_z:
            top, top_z = f, c[2]
    if top is None:
        raise RuntimeError("z-profile: no top face")
    o = K._occ()
    ax = o["gp"].gp_Ax1(o["gp"].gp_Pnt(0.032, 0, top_z + r),
                        o["gp"].gp_Dir(0, 1, 0))
    rev = BRepPrimAPI_MakeRevol(top, ax, +math.pi / 2).Shape()
    return K.fuse(lshape, rev)


def test_multi_bend_unfold_counts_each_flat_once():
    """TODO-2: multi-bend unfold invariant — total developed length =
    sum of the three flats (web shared, counted once) + BA per bend."""
    import math
    import scdm.additive as A
    w, t, l1, l2, r = 0.02, 0.001, 0.03, 0.02, 0.002
    z = _z_profile(w, t, l1, l2, r)
    bends = SM.detect_bends(z)
    assert len(bends) == 2, f"expected 2 bends, got {len(bends)}"
    flat = SM.unfold(z, k=0.42)
    (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(flat)
    total = x1 - x0
    # BA per detected bend (the second bend's measured r/t can deviate
    # from the nominal values); flats: bottom 0.03, web 0.02 (shared),
    # top strip 0.001
    ba_sum = sum(SM.bend_allowance(b["angle_rad"], b["r_inner"], 0.42,
                                   b["t"]) for b in bends)
    expected = 0.03 + 0.02 + 0.001 + ba_sum
    assert total == pytest.approx(expected, rel=1e-6)


def test_unfold_chain_order_connects_shared_flats():
    """Both bends must be ordered along the shared-web chain: the
    intermediate flat is identified by midplane signature, not face
    identity (the web's two sides are distinct TShapes)."""
    z = _z_profile(0.02, 0.001, 0.03, 0.02, 0.002)
    bends = SM.detect_bends(z)
    order = SM._chain_order(bends)
    assert len(order) == 2
    b0, b1 = bends[order[0]], bends[order[1]]
    ti = 0.5 * (b0["t"] + b1["t"])
    assert any(SM._same_flat(SM._flat_sig(b0, a), SM._flat_sig(b1, b_), ti)
               for a in (0, 1) for b_ in (0, 1)),         "chained bends share no sheet flat"


def test_single_bend_unfold_unchanged():
    """Regression: single-bend path result is byte-identical to before."""
    import math
    b = SM.bend_from_flat(0.02, 0.001, 0.03, 0.02, math.pi / 2, 0.002, 0.42)
    flat = SM.unfold(b, k=0.42)
    ba = SM.bend_allowance(math.pi / 2, 0.002, 0.42, 0.001)
    total = K.volume(flat) / (0.02 * 0.001)
    assert total == pytest.approx(0.03 + ba + 0.02, rel=1e-9)

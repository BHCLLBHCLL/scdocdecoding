"""P277/R50: knockout - annulus cut held together by radial webs.

Five assertions straight from the R50 plan:
  1. closed form: removed area (and its ratio to the nominal circle)
  2. single connectivity - rule 66, the topology is COUNTED (solids/shells)
  3. illegal web >= diameter (plus the stricter no-slug-left bound)
  4. single-web extreme
  5. unfold compatibility - rule 60, the downstream flow must not silently
     get a wrong developed length
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sheetmetal as SM  # noqa: E402


def _top_face(shape):
    best = None
    for f in K.explore(shape, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[1][2] > best[1][2]):
            best = (f, c)
    return best[0]


def _ring_area(diameter, web):
    R = diameter / 2.0
    r = R - web
    return math.pi * (R * R - r * r)


def _removed_area(diameter, web, web_count):
    """Closed form: the ring minus the area-exact web sectors (each web**2)."""
    return _ring_area(diameter, web) - web_count * web * web


def test_p277_knockout_closed_form_and_removed_area_ratio():
    box = K.make_box(0.02, 0.02, 0.002)          # 20x20x2 mm sheet
    face = _top_face(box)
    D, W, NW, t = 0.010, 0.001, 4, 0.002
    out = K.knockout(box, face, D, W, NW)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(_removed_area(D, W, NW) * t, rel=1e-9)
    # 切除面积占比 (relative to the nominal knockout circle), closed form
    ratio = removed / t / (math.pi * (D / 2.0) ** 2)
    assert ratio == pytest.approx(_removed_area(D, W, NW) / (math.pi * (D / 2.0) ** 2),
                                  rel=1e-9)
    # ... and the webs' share of the ring is exactly web_count*web**2
    assert (removed / t) == pytest.approx(_ring_area(D, W) - NW * W * W, rel=1e-9)
    # the face frame is orientation agnostic: the bottom face behaves the same
    bottom = [f for f in K.explore(box, "face")
              if K.face_normal_center(f)[0][2] < -0.99][0]
    out_b = K.knockout(box, bottom, D, W, NW)
    assert (K.volume(box) - K.volume(out_b)) == pytest.approx(
        _removed_area(D, W, NW) * t, rel=1e-9)


def test_p277_knockout_is_single_connected_counted_not_eyeballed():
    """Rule 66: shells/solids are counted.  The counter has teeth here - the
    same ring cut with no web really does split the body in two."""
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    n, base = K._face_frame(face, None)
    R, r, t = 0.005, 0.004, 0.002
    ring = K.cut(
        K.make_cylinder(R, t + 2e-6, origin=(base[0], base[1], -1e-6), axis=n),
        K.make_cylinder(r, t + 2e-6, origin=(base[0], base[1], -1e-6), axis=n))
    loose = K.cut(box, ring)
    assert len(K.explore(loose, "solid")) == 2, "no-web ring cut must drop the slug"
    assert len(K.explore(loose, "shell")) == 2
    # 1..6 webs all keep one connected body
    for n_web in (1, 2, 3, 4, 6):
        out = K.knockout(box, face, 0.010, 0.001, n_web)
        assert len(K.explore(out, "solid")) == 1, n_web
        assert len(K.explore(out, "shell")) == 1, n_web
    # the webs must not leave slivers/open shell behind (double guard)
    findings = K.check_geometry(out)
    assert not findings["open_shell"]
    assert not findings["self_intersecting"]
    assert not findings["small_faces"] and not findings["short_edges"]


def test_p277_knockout_rejects_illegal_web():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    with pytest.raises(K.KernelError):            # web == diameter
        K.knockout(box, face, 0.010, 0.010, 4)
    with pytest.raises(K.KernelError):            # web > diameter
        K.knockout(box, face, 0.010, 0.012, 4)
    with pytest.raises(K.KernelError):            # web == radius: no slug left
        K.knockout(box, face, 0.010, 0.005, 4)
    with pytest.raises(K.KernelError):
        K.knockout(box, face, 0.010, 0.0, 4)
    with pytest.raises(K.KernelError):
        K.knockout(box, face, 0.010, 0.001, 0)
    with pytest.raises(K.KernelError):
        K.knockout(box, face, 0.0, 0.001, 4)
    with pytest.raises(K.KernelError):            # webs would fill the ring
        K.knockout(box, face, 0.010, 0.004, 6)


def test_p277_single_web_extreme_keeps_the_slug():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    D, W, t = 0.010, 0.001, 0.002
    out = K.knockout(box, face, D, W, 1)
    assert len(K.explore(out, "solid")) == 1
    assert len(K.explore(out, "shell")) == 1
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(_removed_area(D, W, 1) * t, rel=1e-9)
    # one web keeps the least material -> the removed fraction is the largest
    one = removed / t / _ring_area(D, W)
    four = (K.volume(box) - K.volume(K.knockout(box, face, D, W, 4))) / t / _ring_area(D, W)
    assert one > four
    # extreme small knockout: 2 mm slug held by 3 webs of 0.2 mm
    small = K.knockout(box, face, 0.002, 0.0002, 3)
    assert len(K.explore(small, "solid")) == 1
    assert (K.volume(box) - K.volume(small)) == pytest.approx(
        _removed_area(0.002, 0.0002, 3) * t, rel=1e-9)
    # web -> radius: the slug is a hair-thin disc but still attached
    near = K.knockout(box, face, D, 0.0049, 2)
    assert len(K.explore(near, "solid")) == 1
    assert len(K.explore(near, "shell")) == 1
    assert (K.volume(box) - K.volume(near)) == pytest.approx(
        _removed_area(D, 0.0049, 2) * t, rel=1e-9)


def _flat_top_face(part, t):
    """Top face of the FIRST flat of a bent part (the sheet face to form on)."""
    best = None
    for f in K.explore(part, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and c[2] < 2.5 * t:
            if best is None or K.area(f) > best[1]:
                best = (f, K.area(f))
    return best[0]


def test_p277_knockout_is_unfold_compatible():
    """Rule 60: the forming feature must not break unfold/fold analysis - and
    must not make it silently wrong either."""
    w, t, l1, l2, r = 0.02, 0.002, 0.03, 0.02, 0.002
    part = SM.bend_from_flat(w, t, l1, l2, math.pi / 2.0, r, 0.42)
    plain_len = SM.flat_pattern(part)["length"]
    assert len(SM.detect_bends(part)) == 1
    out = K.knockout(part, _flat_top_face(part, t), 0.006, 0.0006, 4)
    # the slug wall must not be read as a second bend (that silently inflated
    # the developed length by ~9% before the R50 fix to detect_bends)
    bends = SM.detect_bends(out)
    assert len(bends) == 1
    assert math.degrees(bends[0]["angle_rad"]) == pytest.approx(90.0, rel=1e-9)
    pat = SM.flat_pattern(out)
    assert pat["length"] == pytest.approx(plain_len, rel=1e-9)
    assert len(pat["bend_lines"]) == 1
    SM.unfold(out)                                # must not raise
    # the formed volume itself stays closed-form
    removed = K.volume(part) - K.volume(out)
    assert removed == pytest.approx(_removed_area(0.006, 0.0006, 4) * t, rel=1e-9)

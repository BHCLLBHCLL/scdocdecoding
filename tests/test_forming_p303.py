"""P303/R56: sheet-metal junction - release / seam / connect.

Closed forms (t = plate thickness along the face normal):
    release  removed = size**2/2 * t      seam  removed = size*width * t
    connect  added   = size*width * t
Placement is pinned too: the feature sits at the face corner (u_min, v_min), so
the difference solid's bbox is the closed-form footprint.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sheetmetal as SM  # noqa: E402

T = 0.002


def _top_face(shape):
    best = None
    for f in K.explore(shape, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1][2]):
            best = (f, c)
    return best[0]


def _bbox(shape):
    lo, hi = K._vertex_bbox(shape)
    return lo, hi


def test_p303_junction_modes_are_closed_form_and_placed_at_the_corner():
    box = K.make_box(0.02, 0.02, T)
    face = _top_face(box)
    v0 = K.volume(box)
    s, w = 0.004, 0.001
    release = K.junction(box, face, s, mode="release")
    seam = K.junction(box, face, s, mode="seam", width=w)
    connect = K.junction(box, face, s, mode="connect", width=w)
    assert v0 - K.volume(release) == pytest.approx(s * s / 2.0 * T, rel=1e-9)
    assert v0 - K.volume(seam) == pytest.approx(s * w * T, rel=1e-9)
    assert K.volume(connect) - v0 == pytest.approx(s * w * T, rel=1e-9)
    for out in (release, seam, connect):
        assert len(K.explore(out, "solid")) == 1
        assert len(K.explore(out, "shell")) == 1
    # placement: the removed (or added) region has the closed-form footprint
    lo, hi = _bbox(K.cut(box, release))          # material the triangle took
    assert hi[0] == pytest.approx(s, abs=1e-9) and hi[1] == pytest.approx(s, abs=1e-9)
    assert lo[0] == pytest.approx(0.0, abs=1e-9) and lo[1] == pytest.approx(0.0, abs=1e-9)
    lo, hi = _bbox(K.cut(seam, box) if False else K.cut(box, seam))
    assert hi[0] == pytest.approx(s, abs=1e-9) and hi[1] == pytest.approx(w, abs=1e-9)
    lo, hi = _bbox(K.cut(connect, box))          # the bridged patch sits on top
    assert lo[2] == pytest.approx(T, abs=1e-9) and hi[2] == pytest.approx(2 * T, abs=1e-9)
    findings = K.check_geometry(connect)
    assert not findings["open_shell"] and not findings["self_intersecting"]
    assert not findings["short_edges"]


def test_p303_junction_works_on_a_reversed_face():
    box = K.make_box(0.02, 0.02, T)
    bottom = [f for f in K.explore(box, "face")
              if K.face_normal_center(f)[0][2] < -0.99][0]
    v0 = K.volume(box)
    out = K.junction(box, bottom, 0.004, mode="release")
    assert v0 - K.volume(out) == pytest.approx(0.004 ** 2 / 2.0 * T, rel=1e-9)
    add = K.junction(box, bottom, 0.004, mode="connect", width=0.001)
    assert K.volume(add) - v0 == pytest.approx(0.004 * 0.001 * T, rel=1e-9)


def test_p303_junction_rejects_illegal_input():
    box = K.make_box(0.02, 0.02, T)
    face = _top_face(box)
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.0)
    with pytest.raises(K.KernelError):
        K.junction(box, face, -0.004)
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.03)                     # longer than the face
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.004, mode="laser")      # unknown mode
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.004, mode="seam")       # width is required
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.004, mode="seam", width=0.0)
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.004, mode="seam", width=0.03)   # wider than face


def test_p303_junction_extremes_are_exact():
    box = K.make_box(0.02, 0.02, T)
    face = _top_face(box)
    v0 = K.volume(box)
    tiny = K.junction(box, face, 0.0005, mode="release")
    assert v0 - K.volume(tiny) == pytest.approx(0.0005 ** 2 / 2.0 * T, rel=1e-9)
    thin = K.junction(box, face, 0.005, mode="seam", width=0.0002)
    assert v0 - K.volume(thin) == pytest.approx(0.005 * 0.0002 * T, rel=1e-9)
    # just inside the face bound is exact ...
    near = K.junction(box, face, 0.019, mode="release")
    assert v0 - K.volume(near) == pytest.approx(0.019 ** 2 / 2.0 * T, rel=1e-9)
    # ... while reaching the opposite edges is refused (the boolean degenerates)
    with pytest.raises(K.KernelError):
        K.junction(box, face, 0.02, mode="release")


def test_p303_junction_is_unfold_compatible():
    w, t, l1, l2, r = 0.02, T, 0.03, 0.02, 0.002
    part = SM.bend_from_flat(w, t, l1, l2, math.pi / 2.0, r, 0.42)
    plain_len = SM.flat_pattern(part)["length"]
    assert len(SM.detect_bends(part)) == 1
    flat_face = None
    best = -1.0
    for f in K.explore(part, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and c[2] < 2.5 * t and K.area(f) > best:
            flat_face, best = f, K.area(f)
    out = K.junction(part, flat_face, 0.003, mode="release")
    bends = SM.detect_bends(out)
    assert len(bends) == 1
    assert math.degrees(bends[0]["angle_rad"]) == pytest.approx(90.0, rel=1e-9)
    pat = SM.flat_pattern(out)
    assert pat["length"] == pytest.approx(plain_len, rel=1e-9)
    assert len(pat["bend_lines"]) == 1
    SM.unfold(out)                                    # must not raise
    removed = K.volume(part) - K.volume(out)
    assert removed == pytest.approx(0.003 ** 2 / 2.0 * t, rel=1e-9)
    assert len(K.explore(out, "shell")) == 1

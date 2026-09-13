"""P295/R54: gusset + tab - closed form, illegal, extreme, single shell and
unfold compatibility (rules 60/67: numbers, not "did not raise")."""
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
        if n[2] > 0.99 and (best is None or c[2] > best[1][2]):
            best = (f, c)
    return best[0]


def test_p295_gusset_and_tab_closed_form():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    v0 = K.volume(box)
    g = K.gusset(box, face, 0.005, 0.003, 0.001)
    assert K.volume(g) - v0 == pytest.approx(0.005 * 0.003 / 2.0 * 0.001,
                                             rel=1e-9)
    t = K.tab(box, face, 0.004, 0.003, 0.001)
    assert K.volume(t) - v0 == pytest.approx(0.004 * 0.003 * 0.001, rel=1e-9)
    # both are single connected shells: added material, no cut to split them
    for out in (g, t):
        assert len(K.explore(out, "solid")) == 1
        assert len(K.explore(out, "shell")) == 1
    findings = K.check_geometry(g)
    assert not findings["open_shell"] and not findings["self_intersecting"]
    assert not findings["short_edges"]


def test_p295_gusset_and_tab_work_on_a_reversed_face():
    """The face frame is orientation agnostic (bottom face of the sheet)."""
    box = K.make_box(0.02, 0.02, 0.002)
    bottom = [f for f in K.explore(box, "face")
              if K.face_normal_center(f)[0][2] < -0.99][0]
    v0 = K.volume(box)
    assert K.volume(K.gusset(box, bottom, 0.005, 0.003, 0.001)) - v0 == \
        pytest.approx(0.005 * 0.003 / 2.0 * 0.001, rel=1e-9)
    assert K.volume(K.tab(box, bottom, 0.004, 0.003, 0.001)) - v0 == \
        pytest.approx(0.004 * 0.003 * 0.001, rel=1e-9)


def test_p295_gusset_and_tab_reject_illegal_and_oversized_input():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    for call in (lambda: K.gusset(box, face, 0.0, 0.003, 0.001),
                 lambda: K.gusset(box, face, 0.005, -0.003, 0.001),
                 lambda: K.gusset(box, face, 0.005, 0.003, 0.0),
                 lambda: K.gusset(box, face, 0.05, 0.003, 0.001),
                 lambda: K.gusset(box, face, 0.005, 0.003, 0.05),
                 lambda: K.tab(box, face, 0.0, 0.003, 0.001),
                 lambda: K.tab(box, face, 0.004, -0.003, 0.001),
                 lambda: K.tab(box, face, 0.004, 0.003, 0.0),
                 lambda: K.tab(box, face, 0.05, 0.003, 0.001),
                 lambda: K.tab(box, face, 0.004, 0.05, 0.001)):
        with pytest.raises(K.KernelError):
            call()


def test_p295_gusset_and_tab_extremes_are_exact():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    v0 = K.volume(box)
    small = K.gusset(box, face, 0.0005, 0.0005, 0.0005)
    assert K.volume(small) - v0 == pytest.approx(0.0005 ** 3 / 2.0, rel=1e-9)
    thin = K.tab(box, face, 0.01, 0.01, 0.0001)
    assert K.volume(thin) - v0 == pytest.approx(0.01 * 0.01 * 0.0001, rel=1e-9)
    # a tab exactly as wide as the face is legal (the bound is the face span)
    full = K.tab(box, face, 0.02, 0.02, 0.0005)
    assert K.volume(full) - v0 == pytest.approx(0.02 * 0.02 * 0.0005, rel=1e-9)


def test_p295_gusset_and_tab_are_unfold_compatible():
    w, t, l1, l2, r = 0.02, 0.002, 0.03, 0.02, 0.002
    part = SM.bend_from_flat(w, t, l1, l2, math.pi / 2.0, r, 0.42)
    plain_len = SM.flat_pattern(part)["length"]
    assert len(SM.detect_bends(part)) == 1
    flat_face = None
    best = -1.0
    for f in K.explore(part, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and c[2] < 2.5 * t and K.area(f) > best:
            flat_face, best = f, K.area(f)
    for name, fn, expect in (
            ("gusset", lambda s: K.gusset(s, flat_face, 0.006, 0.004, 0.001),
             0.006 * 0.004 / 2.0 * 0.001),
            ("tab", lambda s: K.tab(s, flat_face, 0.006, 0.004, 0.001),
             0.006 * 0.004 * 0.001)):
        out = fn(part)
        bends = SM.detect_bends(out)
        assert len(bends) == 1, name
        assert math.degrees(bends[0]["angle_rad"]) == pytest.approx(90.0,
                                                                    rel=1e-9)
        pat = SM.flat_pattern(out)
        assert pat["length"] == pytest.approx(plain_len, rel=1e-9), name
        assert len(pat["bend_lines"]) == 1
        SM.unfold(out)                     # must not raise
        removed = K.volume(out) - K.volume(part)
        assert removed == pytest.approx(expect, rel=1e-9), name
        assert len(K.explore(out, "shell")) == 1, name

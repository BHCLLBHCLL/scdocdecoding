"""P353/R70: sheet-metal cross-break - shallow V and arc grooves.

Closed forms: the V removes a triangular section (w*d/2) and the arc removes a
circular segment whose sagitta is the depth, both times the groove length.  The
arc area has an independent limit check (shallow arcs approach 2*w*d/3).
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sheetmetal as SM  # noqa: E402

T = 0.002
L, W, D = 0.010, 0.002, 0.0003


def _top_face(shape):
    best = None
    for f in K.explore(shape, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1][2]):
            best = (f, c)
    return best[0]


def test_p353_v_and_arc_cross_breaks_are_closed_form():
    box = K.make_box(0.02, 0.02, T)
    face = _top_face(box)
    v0 = K.volume(box)
    v = K.cross_break(box, face, L, W, D, kind="v")
    assert v0 - K.volume(v) == pytest.approx(0.5 * W * D * L, rel=1e-9)
    a = K.cross_break(box, face, L, W, D, kind="arc")
    seg = K.arc_segment_area(W, D)
    assert v0 - K.volume(a) == pytest.approx(seg * L, rel=1e-9)
    assert seg > 0.5 * W * D            # the arc bulges past the V of equal w/d
    for out in (v, a):
        assert len(K.explore(out, "solid")) == 1
        assert len(K.explore(out, "shell")) == 1
    findings = K.check_geometry(a)
    assert not findings["open_shell"] and not findings["self_intersecting"]
    assert not findings["short_edges"]


def test_p353_arc_area_has_the_parabolic_limit():
    """A shallow arc segment approaches 2*w*d/3 (independent of the exact area)."""
    w, d = 0.02, 0.0002                     # d/w = 1%
    seg = K.arc_segment_area(w, d)
    assert seg == pytest.approx(2.0 / 3.0 * w * d, rel=0.02)
    # ... and the exact formula sits just above the parabola
    assert seg > 2.0 / 3.0 * w * d
    R = (w * w / 4.0 + d * d) / (2.0 * d)
    # the exact radius carries the sagitta term: R = w**2/(8d) + d/2
    assert R == pytest.approx(w * w / (8.0 * d) + d / 2.0, rel=1e-12)
    assert R == pytest.approx(0.2501, rel=1e-9)


def test_p353_illegal_and_extreme():
    box = K.make_box(0.02, 0.02, T)
    face = _top_face(box)
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, L, W, T)              # depth == thickness
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, L, W, T * 2)          # deeper than the sheet
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, 0.0, W, D)
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, L, -W, D)
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, L, W, 0.0)
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, L, W, D, kind="laser")
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, 0.05, W, D)           # longer than the face
    with pytest.raises(K.KernelError):
        K.cross_break(box, face, L, 0.05, D)           # wider than the face
    with pytest.raises(K.KernelError):
        K.arc_segment_area(W, 0.0)
    # extreme: a 0.05 mm break is still exact
    v0 = K.volume(box)
    tiny = K.cross_break(box, face, 0.004, 0.001, 0.00005, kind="v")
    assert v0 - K.volume(tiny) == pytest.approx(0.5 * 0.001 * 0.00005 * 0.004,
                                                rel=1e-9)
    arc = K.cross_break(box, face, 0.004, 0.001, 0.00005, kind="arc")
    assert v0 - K.volume(arc) == pytest.approx(
        K.arc_segment_area(0.001, 0.00005) * 0.004, rel=1e-9)


def test_p353_cross_break_is_unfold_compatible():
    w, t, l1, l2, r = 0.02, T, 0.03, 0.02, 0.002
    part = SM.bend_from_flat(w, t, l1, l2, math.pi / 2.0, r, 0.42)
    plain = SM.flat_pattern(part)["length"]
    assert len(SM.detect_bends(part)) == 1
    flat_face = None
    best = -1.0
    for f in K.explore(part, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and c[2] < 2.5 * t and K.area(f) > best:
            flat_face, best = f, K.area(f)
    for kind, expect in (("v", 0.5 * 0.002 * 0.0003 * 0.008),
                         ("arc", K.arc_segment_area(0.002, 0.0003) * 0.008)):
        out = K.cross_break(part, flat_face, 0.008, 0.002, 0.0003, kind=kind)
        bends = SM.detect_bends(out)
        assert len(bends) == 1, kind
        assert math.degrees(bends[0]["angle_rad"]) == pytest.approx(90.0, rel=1e-9)
        pat = SM.flat_pattern(out)
        assert pat["length"] == pytest.approx(plain, rel=1e-9), kind
        SM.unfold(out)                                   # must not raise
        removed = K.volume(part) - K.volume(out)
        assert removed == pytest.approx(expect, rel=1e-9), kind
        assert len(K.explore(out, "shell")) == 1

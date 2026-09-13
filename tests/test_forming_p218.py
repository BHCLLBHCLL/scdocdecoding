"""P218: forming family - round dimple (closed form + illegal + extreme)."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402


def _top_face(shape):
    best = None
    for f in K.explore(shape, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1][2]):
            best = (f, c)
    return best[0] if best else None


def test_p218_dimple_removes_the_closed_form_volume():
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    out = K.dimple_round(box, face, 0.008, 0.002)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(math.pi * 0.004 ** 2 * 0.002, rel=1e-3)


def test_p218_dimple_rejects_illegal_parameters():
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    with pytest.raises(K.KernelError):
        K.dimple_round(box, face, 0.0, 0.002)
    with pytest.raises(K.KernelError):
        K.dimple_round(box, face, -0.008, 0.002)
    with pytest.raises(K.KernelError):
        K.dimple_round(box, face, 0.008, 0.0)
    with pytest.raises(K.KernelError):
        K.dimple_round(box, face, 0.008, -0.001)


def test_p218_dimple_rejects_a_drill_like_depth():
    """Deep than 2 diameters is a hole, not a forming operation."""
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    with pytest.raises(K.KernelError):
        K.dimple_round(box, face, 0.004, 0.009)


def test_p218_extreme_shallow_dimple_still_exact():
    """A 50 um deep dimple is still pi*r^2*depth (extreme-parameter case)."""
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    out = K.dimple_round(box, face, 0.01, 5e-5)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(math.pi * 0.005 ** 2 * 5e-5, rel=5e-3)
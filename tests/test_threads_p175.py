"""P175: tapped-hole family - tap drill diameter, not nominal."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402


def _top_face(shape):
    """The +Z planar face of an axis-aligned box."""
    best = None
    for f in K.explore(shape, "face"):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1][2]):
            best = (f, c)
    return best[0] if best else None


def test_p175_tapped_hole_cuts_the_tap_drill_diameter():
    """A M6x1 tapped hole removes pi*(2.5mm)^2*20mm, not pi*(3mm)^2*20mm."""
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    assert face is not None
    holed = K.hole_tapped(box, face, 0.006, 0.001)
    removed = K.volume(box) - K.volume(holed)
    tap = math.pi * 0.0025 ** 2 * 0.02
    nominal = math.pi * 0.003 ** 2 * 0.02
    assert removed == pytest.approx(tap, rel=1e-3), (removed, tap)
    # guard: using the nominal diameter would be 44% larger
    assert abs(removed - nominal) > 0.1 * nominal


def test_p175_tapped_hole_rejects_illegal_threads():
    """Extreme/illegal parameters must raise, not silently cut."""
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    with pytest.raises(K.KernelError):
        K.hole_tapped(box, face, 0.006, 0.0)
    with pytest.raises(K.KernelError):
        K.hole_tapped(box, face, 0.006, -1.0)
    with pytest.raises(K.KernelError):
        K.hole_tapped(box, face, 0.006, 0.006)


def test_p175_tapped_hole_depth_is_respected():
    """A blind tapped hole removes pi*r_tap^2*depth."""
    box = K.make_box(0.02, 0.02, 0.02)
    face = _top_face(box)
    holed = K.hole_tapped(box, face, 0.008, 0.00125, depth=0.005)
    removed = K.volume(box) - K.volume(holed)
    assert removed == pytest.approx(math.pi * 0.003375 ** 2 * 0.005, rel=2e-3)
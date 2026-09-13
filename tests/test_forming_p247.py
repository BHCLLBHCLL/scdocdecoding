"""P247: louver opening - closed form, illegal, extreme, axis limitation."""
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


def test_p247_louver_slot_removes_length_times_width_times_thickness():
    box = K.make_box(0.02, 0.02, 0.002)          # 20x20x2 mm sheet
    face = _top_face(box)
    out = K.louver(box, face, 0.01, 0.003)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(0.01 * 0.003 * 0.002, rel=1e-3)


def test_p253_bottom_face_louver_uses_the_oriented_prism():
    """R45/P253: the prism route handles either normal direction."""
    box = K.make_box(0.02, 0.02, 0.002)
    bottom = None
    for f in K.explore(box, "face"):
        n, _c = K.face_normal_center(f)
        if n[2] < -0.99:
            bottom = f
    assert bottom is not None
    out = K.louver(box, bottom, 0.008, 0.002)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(0.008 * 0.002 * 0.002, rel=1e-3)


def test_p253_prism_volume_matches_the_swept_area():
    """The cutter is prism(profile, vec): volume = area x swept length."""
    square = K.face_from_polygon([(0.0, 0.0, 0.0), (0.01, 0.0, 0.0),
                                  (0.01, 0.01, 0.0), (0.0, 0.01, 0.0)])
    solid = K.prism(square, (0.0, 0.0, 0.004))
    assert K.volume(solid) == pytest.approx(0.01 * 0.01 * 0.004, rel=1e-6)


def test_p259_slanted_face_louver_end_to_end():
    """R46/P259: a 45-degree face works end to end (closes the R45 gap).

    The sheet is a parallelepiped built by obliquely extruding a rectangle, so
    its two end faces are planar with normal (1,0,1)/sqrt(2) and the slab has a
    UNIFORM thickness along that normal - which is what makes the closed form
    testable: removed = length * width * (extrude . n).
    """
    import math

    s = 1.0 / math.sqrt(2.0)
    n = (s, 0.0, s)
    u = (0.0, 1.0, 0.0)
    v = (n[2], 0.0, -n[0])
    half = 0.02
    pts = [tuple(u[i] * su * half + v[i] * sv * half for i in range(3))
           for (su, sv) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    prof = K.face_from_polygon(pts)
    vec = (0.01, 0.01, 0.0)
    sheet = K.prism(prof, vec)
    thick = abs(sum(vec[i] * n[i] for i in range(3)))
    face = None
    for f in K.explore(sheet, "face"):
        fn, _c = K.face_normal_center(f)
        if abs(fn[0] - s) < 1e-6 and abs(fn[2] - s) < 1e-6:
            face = f
            break
    assert face is not None, "slanted face not found"
    out = K.louver(sheet, face, 0.01, 0.005)
    removed = K.volume(sheet) - K.volume(out)
    assert removed == pytest.approx(0.01 * 0.005 * thick, rel=2e-3)


def test_p247_louver_rejects_illegal_parameters():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    with pytest.raises(K.KernelError):
        K.louver(box, face, 0.0, 0.003)
    with pytest.raises(K.KernelError):
        K.louver(box, face, 0.01, -0.003)
    with pytest.raises(K.KernelError):
        K.louver(box, face, 0.01, 0.003, height=-0.001)



def test_p247_extreme_small_louver_is_exact():
    box = K.make_box(0.02, 0.02, 0.002)
    face = _top_face(box)
    out = K.louver(box, face, 0.0005, 0.0005)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(0.0005 * 0.0005 * 0.002, rel=5e-3)
"""R87/P416: standard profile tables (GB/T 706 nominal dims) for beams.

The tables hold NOMINAL dimensions only: this module builds exact polygons
without the rolling fillets, so its closed-form values differ from a published
handbook table by the fillet area (~1%).  What the tests therefore check is
consistency, not the handbook:

  1. every spec validates through the same _validate() as hand-typed dims;
  2. the closed form matches an INDEPENDENT rectangle decomposition plus the
     parallel-axis theorem (different arithmetic from the subtraction formula);
  3. the built solid's section properties match the closed form - volume =
     area * length and K.section_props on the section face, rel 1e-9;
  4. the series is monotonic (a bigger spec has a bigger area);
  5. the op accepts a spec NAME and labels the body with it.
"""
from __future__ import annotations

import importlib.util
import math

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")


def _i_by_parts(h, b, tw, tf):
    """I-section by three rectangles + parallel axis (independent path)."""
    af = b * tf
    aw = tw * (h - 2.0 * tf)
    yf = (h - tf) / 2.0
    area = 2.0 * af + aw
    ix = 2.0 * (b * tf ** 3 / 12.0 + af * yf ** 2) + tw * (h - 2.0 * tf) ** 3 / 12.0
    iy = 2.0 * (tf * b ** 3 / 12.0) + (h - 2.0 * tf) * tw ** 3 / 12.0
    return area, ix, iy


def _l_by_parts(a, b, t):
    """Equal-leg angle by two rectangles minus the corner overlap.

    Vertical leg a x t (centroid y = a/2), horizontal leg b x t (centroid
    y = t/2), overlap t x t at the corner removed - each term carries its own
    rectangle inertia plus the parallel-axis shift to the section centroid.
    """
    area = t * (a + b - t)
    cy = (a * t * (a / 2.0) + b * t * (t / 2.0) - t * t * (t / 2.0)) / area
    cx = (a * t * (t / 2.0) + b * t * (b / 2.0) - t * t * (t / 2.0)) / area
    ix = (t * a ** 3 / 12.0 + a * t * (a / 2.0 - cy) ** 2
          + b * t ** 3 / 12.0 + b * t * (t / 2.0 - cy) ** 2
          - t * t ** 3 / 12.0 - t * t * (t / 2.0 - cy) ** 2)
    iy = (a * t ** 3 / 12.0 + a * t * (t / 2.0 - cx) ** 2
          + t * b ** 3 / 12.0 + b * t * (b / 2.0 - cx) ** 2
          - t ** 3 * t / 12.0 - t * t * (t / 2.0 - cx) ** 2)
    return area, ix, iy, cx, cy


def test_every_spec_validates_and_matches_an_independent_decomposition():
    from scdm import beams as B

    assert len(B.spec_names()) >= 12
    checked = 0
    for spec in B.spec_names():
        profile, dims = B.spec_dims(spec)
        cf = B.closed_form(profile, **dims)
        assert cf["area"] > 0
        if profile == "i":
            area, ix, iy = _i_by_parts(dims["h"], dims["b"], dims["tw"], dims["tf"])
            assert cf["area"] == pytest.approx(area, rel=1e-12), spec
            assert cf["ix"] == pytest.approx(ix, rel=1e-12), spec
            assert cf["iy"] == pytest.approx(iy, rel=1e-12), spec
        elif profile == "l":
            area, ix, iy, cx, cy = _l_by_parts(dims["a"], dims["b"], dims["t"])
            assert cf["area"] == pytest.approx(area, rel=1e-12), spec
            assert cf["ix"] == pytest.approx(ix, rel=1e-9), spec
            assert cf["iy"] == pytest.approx(iy, rel=1e-9), spec
            assert cf["cx"] == pytest.approx(cx, rel=1e-9), spec
            assert cf["cy"] == pytest.approx(cy, rel=1e-9), spec
        checked += 1
    assert checked >= 12


def test_the_series_is_monotonic():
    from scdm import beams as B

    for profile in ("i", "l", "pipe"):
        areas = [B.closed_form(profile, **B.spec_dims(s)[1])["area"]
                 for s in B.spec_names(profile)]
        assert areas == sorted(areas) and len(set(areas)) == len(areas), profile


def test_unknown_spec_is_refused_with_the_list():
    from scdm import beams as B
    from scdm import kernel as K

    with pytest.raises(K.KernelError) as err:
        B.spec_dims("I999")
    assert "未知型材规格" in str(err.value) and "I16" in str(err.value)


@requires_occ
def test_a_spec_builds_geometry_that_matches_its_closed_form():
    from scdm import beams as B
    from scdm import kernel as K

    for spec in ("I16", "L63x6", "D76x4"):
        profile, mm = B.spec_dims(spec)
        dims = {k: v / 1000.0 for k, v in mm.items()}
        cf = B.closed_form(profile, **dims)
        face = B.section_face(profile, **dims)
        sp = K.section_props(face)
        assert sp["area"] == pytest.approx(cf["area"], rel=1e-9), spec
        assert sp["ix"] == pytest.approx(cf["ix"], rel=1e-9), spec
        solid = B.beam(profile, 0.2, **dims)
        assert K.volume(solid) == pytest.approx(cf["area"] * 0.2, rel=1e-9)


@requires_occ
def test_the_op_accepts_a_spec_name():
    from scdm.kdoc import KernelDoc
    from scdm.scripting import OPS

    doc = KernelDoc()
    body, msg = OPS["create.beam"](doc, {"spec": "I16", "length": 300.0}, 1000.0)
    assert body is not None
    assert "I16" in msg and "GB/T 706" in msg, msg
    assert body.name == msg.replace("已创建", "")
    from scdm import kernel as K

    # an unknown spec name is refused by the table itself (KernelError, the
    # same type the section validation uses)
    with pytest.raises(K.KernelError):
        OPS["create.beam"](KernelDoc(), {"spec": "nope"}, 1000.0)
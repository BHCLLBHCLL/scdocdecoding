"""R92/P426: the channel (C) section - closed form, geometry and standard specs.

The channel is the first ASYMMETRIC rolled shape in this module measured from
the web's outer face: the centroid sits 16.5 mm from it for [10, not at b/2, so
the outline and the closed form have to agree on the same convention.  The
tests check exactly that, twice:

  1. closed form vs an independent rectangle decomposition + parallel axis
     (web + two flanges, all three carried to the section centroid);
  2. the built geometry (K.section_props on the section face, and the prism
     volume) vs the closed form.

Published handbook values for [10 (1274 mm2, Ix 1.98e6 mm4) differ from ours by
the rolling fillets (~1%), which this module does not model - nominal dims only.
"""
from __future__ import annotations

import importlib.util

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")

DIMS = {"h": 100.0, "b": 48.0, "tw": 5.3, "tf": 8.5}      # [10, mm


def _by_parts(h, b, tw, tf):
    """Web + two flanges, each rectangle carried to the section centroid."""
    parts = [((0.0, tw), (0.0, h)),                  # web: x 0..tw
             ((tw, b), (h - tf, h)),                 # top flange
             ((tw, b), (0.0, tf))]                   # bottom flange
    area = sum((x1 - x0) * (y1 - y0) for (x0, x1), (y0, y1) in parts)
    cx = sum((x1 - x0) * (y1 - y0) * (x0 + x1) / 2.0
             for (x0, x1), (y0, y1) in parts) / area
    cy = sum((x1 - x0) * (y1 - y0) * (y0 + y1) / 2.0
             for (x0, x1), (y0, y1) in parts) / area
    ix = sum((x1 - x0) * (y1 - y0) ** 3 / 12.0
             + (x1 - x0) * (y1 - y0) * ((y0 + y1) / 2.0 - cy) ** 2
             for (x0, x1), (y0, y1) in parts)
    iy = sum((y1 - y0) * (x1 - x0) ** 3 / 12.0
             + (x1 - x0) * (y1 - y0) * ((x0 + x1) / 2.0 - cx) ** 2
             for (x0, x1), (y0, y1) in parts)
    return area, cx, cy, ix, iy


def test_closed_form_matches_the_rectangle_decomposition():
    from scdm import beams as B

    cf = B.closed_form("c", **DIMS)
    area, cx, cy, ix, iy = _by_parts(**DIMS)
    assert cf["area"] == pytest.approx(area, rel=1e-12)
    assert cf["cx"] == pytest.approx(cx, rel=1e-12)
    assert cf["cy"] == pytest.approx(cy, rel=1e-12)
    assert cf["ix"] == pytest.approx(ix, rel=1e-12)
    assert cf["iy"] == pytest.approx(iy, rel=1e-12)
    assert cf["j"] == pytest.approx(ix + iy, rel=1e-12)
    # a channel is NOT symmetric about its web centre (that would be an I)
    assert cf["cx"] < DIMS["b"] / 2.0
    assert cf["cy"] == pytest.approx(DIMS["h"] / 2.0, rel=1e-12)


@requires_occ
def test_geometry_matches_the_closed_form():
    from scdm import beams as B
    from scdm import kernel as K

    dims = {k: v / 1000.0 for k, v in DIMS.items()}
    cf = B.closed_form("c", **dims)
    sp = K.section_props(B.section_face("c", **dims))       # centred
    assert sp["area"] == pytest.approx(cf["area"], rel=1e-9)
    assert sp["ix"] == pytest.approx(cf["ix"], rel=1e-9)
    assert sp["iy"] == pytest.approx(cf["iy"], rel=1e-9)
    assert abs(sp["cx"]) < 1e-12 and abs(sp["cy"]) < 1e-12
    solid = B.beam("c", 0.25, **dims)
    assert K.volume(solid) == pytest.approx(cf["area"] * 0.25, rel=1e-9)
    # uncentred: the measured centroid is exactly the closed form's
    raw = K.section_props(B.section_face("c", center=False, **dims))
    assert raw["cx"] == pytest.approx(cf["cx"], rel=1e-9)
    assert raw["cy"] == pytest.approx(cf["cy"], rel=1e-9)


def test_channel_specs_are_in_the_standard_table():
    from scdm import beams as B

    names = B.spec_names("c")
    assert names == ["[10", "[12.6", "[16"]
    areas = []
    for name in names:
        profile, mm = B.spec_dims(name)
        assert profile == "c"
        cf = B.closed_form(profile, **mm)
        assert cf["area"] > 0 and cf["ix"] > cf["iy"]
        areas.append(cf["area"])
        assert "槽钢" in B.named_spec_label(name)
        assert "GB/T 706" in B.named_spec_label(name)
    assert areas == sorted(areas) and len(set(areas)) == len(areas)


@requires_occ
def test_the_op_builds_a_channel_from_a_spec_name():
    from scdm.kdoc import KernelDoc
    from scdm.scripting import OPS

    doc = KernelDoc()
    body, msg = OPS["create.beam"](doc, {"spec": "[12.6", "length": 250.0},
                                   1000.0)
    assert body is not None and "[12.6" in msg and "槽钢" in msg, msg
    with pytest.raises(Exception):
        OPS["create.beam"](KernelDoc(), {"spec": "[999"}, 1000.0)
"""TODO-5: drawing sheet formats — official DrawingFormats dims,
template structure and three-view layout."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import drawing as S
from scdm import kernel as K



# ----------------------------------------------------- TODO-5: sheet formats

def test_sheet_formats_match_official_library():
    """Dims locked from the installed DrawingFormats library."""
    assert S.SHEET_FORMATS["A4"] == (0.210, 0.297)
    assert S.SHEET_FORMATS["A3"] == (0.420, 0.297)
    assert S.SHEET_FORMATS["A0"] == (1.189, 0.841)


def test_sheet_template_structure():
    """Template mirrors the official DrawingSheetDef structure."""
    t = S.sheet_template("A4")
    assert "<width>0.21</width>" in t
    assert "<height>0.297</height>" in t
    assert "<SheetScaleDef" in t
    assert "FractionalScaleFormat" in t
    assert "LineSegment" in t  # border frame curve


def test_layout_fits_three_views_inside_sheet():
    from scdm import kernel as K
    box = K.make_box(0.02, 0.01, 0.015)
    rects = S.layout_three_views(box, "A4")
    assert len(rects) == 3
    w, h = S.SHEET_FORMATS["A4"]
    for name, polys, (x0, y0, x1, y1) in rects:
        assert 0 <= x0 < x1 <= w
        assert 0 <= y0 < y1 <= h
        assert polys, f"{name} has no visible polylines"

"""P307/R57: annotation styles - arrows, text height, datum symbols, composite
tolerance frames.  Every style field must survive the dict round trip and reach
the export as an attribute (layer, arrow, font size)."""
from __future__ import annotations

import os
import tempfile

import pytest

from scdm import drawing as D
from scdm.annotation import (Datum, GdtFrame, Leader, annotation_geometry,
                             annotation_layer, from_dict)


def test_p307_arrow_styles_are_closed_form():
    lead = Leader(view="v", anchor=(0.0, 0.0), text="注", text_height=0.002)
    head = lead.arrow_head()                      # solid triangle at the anchor
    assert head[0] == (0.0, 0.0)
    assert head[1][0] == pytest.approx(2.5 * 0.002, rel=1e-15)
    assert abs(head[1][1]) == pytest.approx(0.8 * 0.002, rel=1e-15)
    assert head[2][1] == pytest.approx(-head[1][1], rel=1e-15)
    # the head follows the leader direction (elbow up-right)
    turned = Leader(view="v", anchor=(0.0, 0.0), text="注", elbow=(0.01, 0.01))
    h2 = turned.arrow_head()
    assert h2[1][0] > 0 and h2[1][1] > 0
    # styles: open = two barbs, none = nothing
    open_head = Leader(view="v", anchor=(0, 0), text="x", arrow="open").arrow_head()
    assert len(open_head) == 3 and open_head[1] == (0.0, 0.0)
    assert Leader(view="v", anchor=(0, 0), text="x", arrow="none").arrow_head() == []
    with pytest.raises(ValueError):
        Leader(view="v", anchor=(0, 0), text="x", arrow="laser").validate()
    with pytest.raises(ValueError):
        Leader(view="v", anchor=(0, 0), text="x", text_height=0.0).validate()


def test_p307_style_fields_round_trip_and_reach_the_geometry():
    lead = Leader(view="v", anchor=(0.001, 0.002), text="注", arrow="open",
                  text_height=0.004, elbow=(0.005, 0.006))
    datum = Datum(view="v", anchor=(0.003, 0.004), label="b", target=True,
                  target_size=0.01)
    frame = GdtFrame(view="v", anchor=(0.0, 0.0), symbol="position", value=0.05,
                     datums=["A"],
                     extra_rows=[{"symbol": "flatness", "value": 0.02},
                                 {"symbol": "perpendicularity", "value": 0.1,
                                  "datums": ["B"]}])
    for a in (lead, datum, frame):
        data = a.to_dict()
        assert from_dict(data).to_dict() == data
        segs, text, _at, style = annotation_geometry(a)
        assert segs and text
        assert style["layer"] == annotation_layer(a)
        assert style["text_height"] > 0
    # datum labels are normalised, and the target mark is a closed triangle
    assert datum.label == "B"
    mark = datum.target_mark()
    assert len(mark) == 3 and mark[0][1] > mark[1][1]
    assert Datum(view="v", anchor=(0, 0), label="A", target=False).target_mark() == []
    # composite frames: one row per entry, dividers per cell
    assert frame.labels() == ["⌖ Ø0.05 A", "⏥ Ø0.02", "⊥ Ø0.1 B"]
    assert len(frame.corners()) == 4
    assert frame.corners()[2][1] == pytest.approx(3 * frame.height, abs=1e-15)
    # 2 row dividers + cell dividers (row1 datum: 2, row2 none: 1, row3 datum: 2)
    assert len(frame.dividers()) == 2 + 2 + 1 + 2
    segs, text, _at, style = annotation_geometry(frame)
    assert style["rows"] == 3 and " / " in text


def test_p307_illegal_styles_and_datum_labels():
    with pytest.raises(ValueError):
        Datum(view="v", anchor=(0, 0), label="").validate()
    with pytest.raises(ValueError):
        Datum(view="v", anchor=(0, 0), label="ABCD").validate()
    with pytest.raises(ValueError):
        Datum(view="v", anchor=(0, 0), label="A B").validate()
    with pytest.raises(ValueError):
        Datum(view="v", anchor=(0, 0), label="A", box=0.0).validate()
    with pytest.raises(ValueError):
        Datum(view="v", anchor=(0, 0), label="A", target_size=-1.0).validate()
    with pytest.raises(ValueError):      # a bad row in a composite frame
        GdtFrame(view="v", anchor=(0, 0),
                 extra_rows=[{"symbol": "laser", "value": 0.02}]).validate()
    with pytest.raises(ValueError):
        GdtFrame(view="v", anchor=(0, 0), extra_rows=[{"value": -0.02}]).validate()
    with pytest.raises(ValueError):
        GdtFrame(view="v", anchor=(0, 0),
                 extra_rows=[{"datums": ["LONG"]}]).validate()


def test_p307_styles_reach_the_export_and_leave_the_model_alone():
    from scdm import kernel as K
    box = K.make_box(0.02, 0.02, 0.02)
    view = D.projected_view(box, (0.0, 0.0, -1.0), label="前视")
    dims = D.dimensions_for([view])
    notes = [Leader(view=view[0], anchor=(0.0, 0.0), text="焊接", arrow="open",
                    text_height=0.004, elbow=(0.005, 0.005)),
             Datum(view=view[0], anchor=(0.01, 0.0), label="A", target=True),
             GdtFrame(view=view[0], anchor=(0.01, 0.01), symbol="position",
                      value=0.05, datums=["A"],
                      extra_rows=[{"symbol": "flatness", "value": 0.02}])]
    before = K.volume(box)
    tmp = tempfile.mkdtemp(prefix="p307_")
    try:
        svg = os.path.join(tmp, "s.svg")
        dxf = os.path.join(tmp, "s.dxf")
        D.svg_sheet([view], svg, dimensions=dims, annotations=notes)
        D.write_dxf([view], dxf, dimensions=dims, annotations=notes)
        svg_text = open(svg, encoding="utf-8").read()
        dxf_text = open(dxf, encoding="utf-8").read()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    # style attributes ride along: layer, arrow style, font size
    assert 'data-layer="NOTE"' in svg_text and 'data-arrow="open"' in svg_text
    assert 'data-layer="GDT"' in svg_text and 'data-layer="DATUM"' in svg_text
    assert 'font-size="4.00"' in svg_text           # 4 mm text height
    assert "DATUM" in dxf_text and "GDT" in dxf_text and "NOTE" in dxf_text
    assert "焊接" in dxf_text and "Ø0.02" in dxf_text
    # an annotation is a drawing object: the model never moves
    assert K.volume(box) == before

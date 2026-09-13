"""P299/R55: drawing annotations - leader + GD&T frame.

Acceptance (R55 plan): the anchor snaps in closed form, annotations never enter
the geometry, the export carries them, and undo/redo round trips.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from scdm import drawing as D
from scdm import snaptools as SNAP
from scdm.annotation import GdtFrame, Leader, annotation_geometry, from_dict

VIEWS = [("前视", [[(0.0, 0.0), (0.02, 0.0), (0.02, 0.02), (0.0, 0.02),
                    (0.0, 0.0)]])]


def test_p299_anchor_snaps_to_the_closed_form_target():
    idx = SNAP.SnapIndex(VIEWS)
    lead = Leader(view="前视", anchor=(0.0, 0.0), text="注", elbow=(0.005, 0.004))
    target = (0.02, 0.0)                      # corner of the view
    (sx, sy), kind = idx.snap((target[0] + 3e-4, target[1] + 3e-4), 1e-3)
    assert kind == "end"
    assert (sx, sy) == target                 # exact, not "near"
    lead.move_to((sx, sy))
    assert lead.anchor == target
    # the elbow keeps its relative position: it moves by the same delta as the
    # anchor (0.005, 0.004) + (0.02, 0.0)
    assert lead.elbow == pytest.approx((0.025, 0.004), abs=1e-15)
    assert lead.points()[0] == target


def test_p299_gdt_frame_label_geometry_and_illegal_input():
    gdt = GdtFrame(view="前视", anchor=(0.01, 0.01), symbol="position",
                   value=0.05, datums=["A", "B"])
    assert gdt.label() == "⌖ Ø0.05 A B"
    c = gdt.corners()
    assert c[0] == (0.01, 0.01)
    assert c[2] == pytest.approx((0.01 + gdt.width, 0.01 + gdt.height), abs=1e-15)
    # segments close the box
    segs, text, _at = annotation_geometry(gdt)
    assert len(segs) == 4 and text == gdt.label()
    with pytest.raises(ValueError):
        GdtFrame(view="前视", anchor=(0, 0), symbol="laser", value=0.05).validate()
    with pytest.raises(ValueError):
        GdtFrame(view="前视", anchor=(0, 0), value=0.0).validate()
    with pytest.raises(ValueError):
        GdtFrame(view="前视", anchor=(0, 0), datums=["ABCD"]).validate()
    with pytest.raises(ValueError):
        Leader(view="前视", anchor=(0, 0), text="  ").validate()
    with pytest.raises(ValueError):
        Leader(view="前视", anchor=(0, 0), text="注", tail=-1.0).validate()


def test_p299_annotations_do_not_enter_the_geometry_and_reach_the_export():
    from scdm import kernel as K
    box = K.make_box(0.02, 0.02, 0.02)
    view = D.projected_view(box, (0.0, 0.0, -1.0), label="前视")
    dims = D.dimensions_for([view])
    lead = Leader(view=view[0], anchor=(0.0, 0.0), text="焊接", elbow=(0.005, 0.005))
    gdt = GdtFrame(view=view[0], anchor=(0.01, 0.01), symbol="position",
                   value=0.05, datums=["A"])
    before = (K.volume(box), K.explore(box, "face").__len__())
    tmp = tempfile.mkdtemp(prefix="p299_")
    try:
        svg = os.path.join(tmp, "s.svg")
        dxf = os.path.join(tmp, "s.dxf")
        D.svg_sheet([view], svg, dimensions=dims, annotations=[lead, gdt])
        D.write_dxf([view], dxf, dimensions=dims, annotations=[lead, gdt])
        svg_text = open(svg, encoding="utf-8").read()
        dxf_text = open(dxf, encoding="utf-8").read()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    # the drawing carries them (a NOTE leader and a GDT frame, both labelled)
    assert 'class="note"' in svg_text
    assert "焊接" in svg_text and "⌖" in svg_text
    assert "NOTE" in dxf_text and "GDT" in dxf_text
    assert "焊接" in dxf_text and "0.05" in dxf_text
    # ... and the model is untouched: an annotation is a drawing object
    assert K.volume(box) == before[0]
    assert len(K.explore(box, "face")) == before[1]
    # the view polylines are the only geometry input of the sheet
    assert len(D.extents(view[1])) == 4


def test_p299_annotation_dict_round_trip():
    lead = Leader(view="前视", anchor=(0.001, 0.002), text="注",
                  elbow=(0.003, 0.004), tail=0.02)
    gdt = GdtFrame(view="前视", anchor=(0.005, 0.006), symbol="perpendicularity",
                   value=0.1, datums=["A"])
    for a in (lead, gdt):
        data = a.to_dict()
        assert from_dict(data).to_dict() == data
    assert from_dict(lead.to_dict()).points() == lead.points()
    assert from_dict(gdt.to_dict()).label() == gdt.label()

"""R102/P0-1: feature parameter edit loop (GUI parameter -> feature -> replay).

The acceptance shape is a box with a through hole: changing the hole diameter
must land on the closed form V = V_box - pi (d/2)^2 t, twice in a row, with the
feature stack unchanged; a refused edit must leave both the parameters and the
geometry exactly as they were; and the history must survive save/load.
"""
from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path

import pytest

from scdm import features as FEAT
from scdm import io_project as IO
from scdm import kernel as K
from scdm import scripting as SCR
from scdm.kdoc import KernelDoc


def _box_with_hole(doc, d_mm=5.0, w_mm=20.0, h_mm=20.0, t_mm=10.0):
    """A box with one through hole on its +Z face, history in effect."""
    body = doc.add_body(K.make_box(w_mm / 1000.0, h_mm / 1000.0, t_mm / 1000.0),
                        name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - t_mm / 1000.0) < 1e-9][0]
    doc.record_feature(body.id, "hole", selector=FEAT.selector_for(body.shape, top),
                       diameter=d_mm, depth=0.0)
    ok, why = doc.replay_body(body.id)
    assert ok, why
    v0 = (w_mm / 1000.0) * (h_mm / 1000.0) * (t_mm / 1000.0)
    return body, v0, t_mm / 1000.0


def _hole_v(v0, d_mm, t_m):
    return v0 - math.pi * (d_mm / 2000.0) ** 2 * t_m


def test_editing_the_hole_diameter_matches_the_closed_form_twice():
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc, 5.0)
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 5.0, t_m), rel=1e-6)

    rep = doc.edit_feature(body.id, 0, "diameter", 8.0)
    assert rep["ok"] is True, rep["reason"]
    assert rep["old"] == 5.0 and rep["value"] == 8.0
    assert rep["volume_before"] == pytest.approx(_hole_v(v0, 5.0, t_m), rel=1e-6)
    assert rep["volume_after"] == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)

    # the history itself is untouched: same ops, same length, new value
    stack = doc.feature_stack(body.id)
    assert stack.ops() == ["hole"] and len(stack) == 1
    assert stack.features[0].params["diameter"] == 8.0

    # a second edit in the other direction lands on the closed form again
    rep2 = doc.edit_feature(body.id, 0, "diameter", 3.0)
    assert rep2["ok"] and K.volume(body.shape) == pytest.approx(
        _hole_v(v0, 3.0, t_m), rel=1e-6)


def test_edit_refusals_do_not_touch_params_or_geometry():
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc, 5.0)
    before = K.volume(body.shape)

    assert "不支持参数" in doc.edit_feature(body.id, 0, "selector", 1)["reason"]
    assert "必须大于" in doc.edit_feature(body.id, 0, "diameter", -1.0)["reason"]
    assert "必须是有限数" in doc.edit_feature(body.id, 0, "diameter", float("nan"))["reason"]
    assert "不是数字" in doc.edit_feature(body.id, 0, "diameter", "abc")["reason"]
    assert "越界" in doc.edit_feature(body.id, 7, "diameter", 4.0)["reason"]
    assert "未知实体" in doc.edit_feature("B99", 0, "diameter", 4.0)["reason"]

    stack = doc.feature_stack(body.id)
    assert stack.features[0].params["diameter"] == 5.0
    assert K.volume(body.shape) == pytest.approx(before, rel=1e-12)


def test_edit_refuses_when_the_body_no_longer_matches_its_history():
    """An unrecorded change makes replay a lie, so it is refused, not guessed."""
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc, 5.0)
    # an extra cut the history does not know about
    side = [f for f in K.explore(body.shape, "face")
            if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    body.shape = K.hole_simple(body.shape, side, 0.001)

    ok, why = doc.can_replay(body.id)
    assert ok is False and "不一致" in why
    rep = doc.edit_feature(body.id, 0, "diameter", 4.0)
    assert rep["ok"] is False and "不一致" in rep["reason"]
    assert doc.feature_stack(body.id).features[0].params["diameter"] == 5.0


def test_a_failed_replay_rolls_back_both_the_parameter_and_the_shape():
    """Shell 1mm wall + fillet 0.25mm; editing the radius to the wall thickness
    must fail (the kernel guard refuses it) and leave everything as it was."""
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="盒")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    doc.record_feature(body.id, "shell",
                       selectors=[FEAT.selector_for(body.shape, top)], thickness=1.0)
    doc.record_feature(body.id, "fillet", radius=0.25)
    ok, why = doc.replay_body(body.id)
    assert ok, why
    v_before = K.volume(body.shape)

    rep = doc.edit_feature(body.id, 1, "radius", 1.0)
    assert rep["ok"] is False, rep
    assert "重放失败" in rep["reason"]
    params = doc.feature_stack(body.id).features[1].params
    assert params["radius"] == 0.25            # parameter rolled back
    assert K.volume(body.shape) == pytest.approx(v_before, rel=1e-12)


def test_an_unrecorded_move_is_detected_as_inconsistent():
    """R104: volume and face count are translation-invariant, so the bounding box
    must be part of the verdict - otherwise the next edit would silently move the
    body back home."""
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc)
    assert doc.can_replay(body.id)[0] is True

    body.shape = K.translate(body.shape, (0.005, 0.0, 0.0))   # no pose recorded
    ok, why = doc.can_replay(body.id)
    assert ok is False and "包围盒" in why, why
    moved = K.cog(body.shape)
    rep = doc.edit_feature(body.id, 0, "diameter", 8.0)
    assert rep["ok"] is False and "包围盒" in rep["reason"]
    assert K.cog(body.shape) == pytest.approx(moved, abs=1e-15)   # no silent jump

    # the recorded path is unchanged: a proper move stays replayable
    doc2 = KernelDoc()
    body2, _v0, _t = _box_with_hole(doc2)
    doc2.translate_body(body2.id, (0.005, 0.0, 0.0))
    assert doc2.can_replay(body2.id)[0] is True

def test_undo_snapshot_carries_the_parameters_and_the_base():
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc, 5.0)
    snap = doc.snapshot()
    assert list(snap["features"]) == [body.id]
    assert list(snap["bases"]) == [body.id]

    assert doc.edit_feature(body.id, 0, "diameter", 8.0)["ok"]
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)

    doc.restore(snap)                          # what edit.undo does
    assert K.volume(doc.bodies[0].shape) == pytest.approx(
        _hole_v(v0, 5.0, t_m), rel=1e-6)
    assert doc.feature_stack(doc.bodies[0].id).features[0].params["diameter"] == 5.0
    assert doc.can_replay(doc.bodies[0].id)[0] is True
    # legacy 5-tuple snapshots (pre-R102) still restore the geometry
    legacy = [(b.id, b.name, K.dumps_brep(b.shape), b.color, b.visible)
              for b in doc.bodies]
    doc.restore(legacy)
    assert len(doc.bodies) == 1 and doc.features == {}


def test_project_round_trip_keeps_the_base_and_the_edit():
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc, 5.0)
    assert doc.edit_feature(body.id, 0, "diameter", 8.0)["ok"]
    d = Path(tempfile.mkdtemp(prefix="r102_"))
    try:
        path = d / "edit.scdm"
        IO.save_scdm(str(path), doc)
        import zipfile
        with zipfile.ZipFile(str(path)) as z:
            names = z.namelist()
        assert "bodies/B1.brep" in names and "bodies/B1.base.brep" in names

        back = IO.load_scdm(str(path))
        assert back.can_replay(back.bodies[0].id)[0] is True
        assert K.volume(back.bodies[0].shape) == pytest.approx(
            _hole_v(v0, 8.0, t_m), rel=1e-6)
        rep = back.edit_feature(back.bodies[0].id, 0, "diameter", 4.0)
        assert rep["ok"] and K.volume(back.bodies[0].shape) == pytest.approx(
            _hole_v(v0, 4.0, t_m), rel=1e-6)

        # a history without a base refuses instead of replaying from the
        # (already featured) stored shape
        back.bodies[0].base_shape = None
        ok, why = back.can_replay(back.bodies[0].id)
        assert ok is False and "基准形状" in why
    finally:
        shutil.rmtree(str(d), ignore_errors=True)


def test_scripted_hole_records_the_history_and_the_edit_replays():
    doc = KernelDoc()
    turns = SCR.replay([
        {"cmd": "insert.box", "opts": {"w": 20.0, "h": 20.0, "d": 10.0}},
        {"cmd": "create.hole", "opts": {"target": "last", "face_i": 1,
                                        "diameter": 5.0, "depth": 0.0}},
    ], doc)
    assert turns == ["OK insert.box", "OK create.hole"], turns
    body = doc.bodies[0]
    assert doc.feature_stack(body.id).ops() == ["hole"]      # R102: script records
    v1 = K.volume(body.shape)
    v0 = 0.02 * 0.02 * 0.01
    # the hole axis is whatever face 1 is; the removed cylinder gives its length
    length = (v0 - v1) / (math.pi * (5.0 / 2000.0) ** 2)

    turns = SCR.replay([{"cmd": "det.params",
                         "opts": {"target": "body", "index": 0, "feature": 0,
                                  "param": "diameter", "value": 8.0}}], doc)
    assert turns == ["OK det.params"], turns
    assert K.volume(body.shape) == pytest.approx(
        v0 - math.pi * (8.0 / 2000.0) ** 2 * length, rel=1e-6)
    # the same edit refuses loudly when it cannot be replayed
    with pytest.raises(ValueError) as e:
        SCR.replay([{"cmd": "det.params",
                     "opts": {"target": "body", "index": 0, "feature": 0,
                              "param": "diameter", "value": -1.0}}], doc)
    assert "参数编辑失败" in str(e.value)
    assert doc.feature_stack(body.id).features[0].params["diameter"] == 8.0


def test_edit_line_grammar():
    ids = ["B1", "B2"]
    edits, errs = FEAT.parse_edit_lines(
        "# 板 B1：孔\n"
        "B1 0 diameter = 8\n"
        "B2 #1 thickness = 1.5\n"
        "// comment\n"
        "\n", ids)
    assert errs == []
    assert [(e["body"], e["index"], e["param"], e["value"]) for e in edits] == [
        ("B1", 0, "diameter", "8"), ("B2", 1, "thickness", "1.5")]

    edits, errs = FEAT.parse_edit_lines("0 diameter = 8", ["B1"])
    assert errs == [] and edits[0]["body"] == "B1"     # single body may be omitted
    _, errs = FEAT.parse_edit_lines("0 diameter = 8", ids)
    assert errs and "缺实体" in errs[0]
    _, errs = FEAT.parse_edit_lines("B1 x diameter = 8", ids)
    assert errs and "不是整数" in errs[0]
    _, errs = FEAT.parse_edit_lines("B1 0 diameter", ids)
    assert errs and "缺 '='" in errs[0]


def test_editable_lists_only_the_whitelisted_parameters():
    doc = KernelDoc()
    body, _v0, _t = _box_with_hole(doc, 5.0)
    rows = {r["param"]: r for r in doc.feature_stack(body.id).editable()}
    assert set(rows) == {"diameter", "depth"}          # selector is not editable
    assert rows["diameter"]["label"] == "直径"
    assert rows["diameter"]["value"] == 5.0
    assert rows["depth"]["unit"] == "mm"
    # every op in the schema has at least one field, and every field is numeric
    for op, fields in FEAT.EDIT_SCHEMA.items():
        assert fields, op
        for f in fields:
            assert f.param and f.label

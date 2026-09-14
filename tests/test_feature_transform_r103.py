"""R103/A-1 + A-2: rigid transforms keep the history replayable, and the
scripted forming ops record the same features the GUI writes.

A-1: moving / rotating / mirroring a body must not break the feature-edit
     invariant — `KBody.base_pose` carries the same rigid pose as the body, so
     `base + stack` still reproduces the live shape.
A-2: dimple / louver / knockout / gusset / tab / junction / cross-break / boss
     now populate the history; the yardstick for an edit is a body built natively
     with the new value (no closed form required, rule 87).
"""
from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("OCC")

from scdm import features as FEAT  # noqa: E402
from scdm import io_project as IO  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


class _Ses:
    """Minimal session stand-in for tools: exposes kdoc + scale."""

    def __init__(self, kdoc, scale=1000.0):
        self.kdoc = kdoc
        self.scale = scale


def _top_face_index(shape):
    best = None
    for i, f in enumerate(K.explore(shape, "face")):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1]):
            best = (i, c[2])
    return best[0] if best else 0


def _box_with_hole(d_mm=5.0, w_mm=20.0, h_mm=20.0, t_mm=10.0):
    doc = KernelDoc()
    body = doc.add_body(K.make_box(w_mm / 1000.0, h_mm / 1000.0, t_mm / 1000.0),
                        name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - t_mm / 1000.0) < 1e-9][0]
    doc.record_feature(body.id, "hole", selector=FEAT.selector_for(body.shape, top),
                       diameter=d_mm, depth=0.0)
    assert doc.replay_body(body.id)[0]
    return doc, body, (w_mm / 1000.0) * (h_mm / 1000.0) * (t_mm / 1000.0), t_mm / 1000.0


def _hole_v(v0, d_mm, t_m):
    return v0 - math.pi * (d_mm / 2000.0) ** 2 * t_m


def _bbox(shape):
    lo, hi = K._vertex_bbox(shape)
    return tuple(lo), tuple(hi)


# --- A-1: rigid transforms --------------------------------------------------

def test_translate_keeps_the_history_replayable():
    doc, body, v0, t_m = _box_with_hole()
    lo0, hi0 = _bbox(body.shape)
    doc.translate_body(body.id, (0.01, 0.0, 0.0))

    assert doc.can_replay(body.id)[0] is True
    lo, hi = _bbox(body.shape)
    for i in range(3):
        shift = 0.01 if i == 0 else 0.0
        assert lo[i] == pytest.approx(lo0[i] + shift, abs=1e-12)
        assert hi[i] == pytest.approx(hi0[i] + shift, abs=1e-12)
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 5.0, t_m), rel=1e-6)

    # and the parameters are still editable after the move
    rep = doc.edit_feature(body.id, 0, "diameter", 8.0)
    assert rep["ok"], rep["reason"]
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)
    lo2, _hi2 = _bbox(body.shape)
    assert lo2[0] == pytest.approx(lo0[0] + 0.01, abs=1e-12)


def test_rotate_keeps_the_history_replayable():
    doc, body, v0, t_m = _box_with_hole()
    lo0, hi0 = _bbox(body.shape)
    doc.rotate_body(body.id, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), math.pi / 2.0)

    assert doc.can_replay(body.id)[0] is True
    # 90 deg about +Z maps (x, y) -> (-y, x): the expected box is pure maths
    exp_lo = (-hi0[1], lo0[0], lo0[2])
    exp_hi = (-lo0[1], hi0[0], hi0[2])
    lo, hi = _bbox(body.shape)
    for i in range(3):
        assert lo[i] == pytest.approx(exp_lo[i], abs=1e-12)
        assert hi[i] == pytest.approx(exp_hi[i], abs=1e-12)
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 5.0, t_m), rel=1e-6)
    assert doc.edit_feature(body.id, 0, "diameter", 6.0)["ok"]


def test_mirror_keeps_the_history_replayable():
    doc, body, v0, t_m = _box_with_hole()
    lo0, hi0 = _bbox(body.shape)
    doc.mirror_body(body.id, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    assert doc.can_replay(body.id)[0] is True
    lo, hi = _bbox(body.shape)
    assert lo[0] == pytest.approx(-hi0[0], abs=1e-12)
    assert hi[0] == pytest.approx(-lo0[0], abs=1e-12)
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 5.0, t_m), rel=1e-6)


def test_undo_snapshot_restores_the_pose():
    doc, body, v0, t_m = _box_with_hole()
    lo0, _hi0 = _bbox(body.shape)
    snap = doc.snapshot()
    assert list(snap["poses"]) == []           # nothing moved yet

    doc.translate_body(body.id, (0.02, 0.0, 0.0))
    assert list(doc.snapshot()["poses"]) == [body.id]

    doc.restore(snap)
    back = doc.bodies[0]
    assert back.base_pose == []
    assert _bbox(back.shape)[0][0] == pytest.approx(lo0[0], abs=1e-12)
    assert doc.can_replay(back.id)[0] is True


def test_project_round_trip_keeps_the_pose():
    doc, body, v0, t_m = _box_with_hole()
    doc.translate_body(body.id, (0.01, 0.0, 0.0))
    doc.edit_feature(body.id, 0, "diameter", 8.0)
    d = Path(tempfile.mkdtemp(prefix="r103_"))
    try:
        path = d / "moved.scdm"
        IO.save_scdm(str(path), doc)
        back = IO.load_scdm(str(path))
        b = back.bodies[0]
        assert b.base_pose and b.base_pose[0][0] == "translate"
        assert back.can_replay(b.id)[0] is True
        assert K.volume(b.shape) == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)
        assert back.edit_feature(b.id, 0, "diameter", 4.0)["ok"]
        assert _bbox(b.shape)[0][0] == pytest.approx(0.01 - 0.0, abs=1e-12)
    finally:
        shutil.rmtree(str(d), ignore_errors=True)


def test_move_tool_and_script_move_keep_the_base():
    # the shared move tool (GUI path)
    doc, body, v0, t_m = _box_with_hole()
    from scdm.tools.direct import get_tool
    msg = get_tool("tool.move").apply(_Ses(doc, 1000.0), {"body_id": body.id},
                                      {"distance": 10.0, "axis": (1.0, 0.0, 0.0)})
    assert "移动" in msg
    assert doc.can_replay(body.id)[0] is True
    assert _bbox(body.shape)[0][0] == pytest.approx(0.01, abs=1e-12)

    # the script op
    doc2 = KernelDoc()
    SCR.replay([{"cmd": "insert.box", "opts": {"w": 20.0, "h": 20.0, "d": 10.0}},
                {"cmd": "create.hole", "opts": {"target": "last", "face_i": 1,
                                                "diameter": 5.0, "depth": 0.0}},
                {"cmd": "tool.move", "opts": {"target": "body", "index": 0,
                                              "distance": 10.0,
                                              "axis": [1.0, 0.0, 0.0]}}], doc2)
    b2 = doc2.bodies[0]
    assert b2.base_pose and b2.base_pose[0][0] == "translate"
    assert doc2.can_replay(b2.id)[0] is True
    assert doc2.edit_feature(b2.id, 0, "diameter", 8.0)["ok"]


# --- A-2: scripted forming ops record features ------------------------------

SHEET = (0.02, 0.02, 0.002)
THIN = (0.02, 0.02, 0.001)
CASES = (
    ("create.dimple", "dimple", {"diameter": 8.0, "depth": 2.0}, (0.02, 0.02, 0.02),
     "diameter", 6.0),
    ("create.louver", "louver", {"length": 10.0, "width": 3.0, "height": 0.0},
     SHEET, "length", 8.0),
    ("create.knockout", "knockout", {"diameter": 10.0, "web": 1.0, "web_count": 4},
     SHEET, "diameter", 8.0),
    ("create.gusset", "gusset", {"length": 5.0, "height": 3.0, "thickness": 1.0},
     SHEET, "height", 2.0),
    ("create.tab", "tab", {"length": 5.0, "width": 3.0, "height": 1.0},
     SHEET, "width", 2.0),
    ("sheet.junction", "junction", {"mode": "release", "size": 4.0}, THIN,
     "size", 3.0),
    ("sheet.cross_break", "cross_break",
     {"length": 10.0, "width": 2.0, "depth": 0.3, "kind": "v"}, SHEET,
     "length", 8.0),
    ("create.boss", "boss", {"diameter": 6.0, "height": 4.0}, (0.02, 0.02, 0.02),
     "height", 3.0),
)


def _run_forming(cmd, opts, box):
    doc = KernelDoc()
    body = doc.add_body(K.make_box(*box), name="B")
    steps = [{"cmd": cmd, "opts": {"target": "last",
                                   "face_i": _top_face_index(body.shape), **opts}}]
    assert SCR.replay(steps, doc) == ["OK %s" % cmd]
    return doc, body


def test_scripted_forming_ops_record_their_features():
    for cmd, op, opts, box, _param, _new in CASES:
        doc, body = _run_forming(cmd, opts, box)
        stack = doc.feature_stack(body.id)
        assert stack.ops() == [op], (cmd, stack.ops())
        assert doc.can_replay(body.id)[0] is True, cmd
        assert stack.features[0].params.get("selector"), cmd
        params = {r["param"] for r in stack.editable()}
        assert params, cmd


def test_editing_a_scripted_forming_feature_matches_a_native_rebuild():
    """The edited body must equal one built natively with the new value."""
    for cmd, _op, opts, box, param, new in CASES:
        doc, body = _run_forming(cmd, opts, box)
        rep = doc.edit_feature(body.id, 0, param, new)
        assert rep["ok"], (cmd, rep["reason"])
        native_doc, native = _run_forming(cmd, {**opts, param: new}, box)
        assert K.volume(body.shape) == pytest.approx(K.volume(native.shape),
                                                     rel=1e-6), cmd
        assert (len(K.explore(body.shape, "face"))
                == len(K.explore(native.shape, "face"))), cmd
        assert rep["volume_after"] == pytest.approx(K.volume(native.shape),
                                                    rel=1e-6), cmd

"""R104/A-1 + P1-1: mates and alignments are replayable poses, and a mate
reports the remaining degrees of freedom from the DOFS table.

A-1: aligning (face-flush / axis-align) or mating must not break the feature-edit
     invariant - the rigid transform is recorded in `KBody.base_pose`.
P1-1: each of the seven kinematic pairs reports `dof == mates.DOFS[type]`, the
     solved transform satisfies that pair's own condition (checked on the mate
     frames, independent of the body), and an over-constrained pair is refused
     with the numbers instead of silently letting the last mate win.
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
from scdm import mates as MATES  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

TYPES = (MATES.RIGID, MATES.REVOLUTE, MATES.CYLINDRICAL, MATES.PLANAR,
         MATES.BALL, MATES.SCREW, MATES.DISTANCE)


def _two_boxes(doc=None):
    """Box A (target) and a smaller box B offset in space (moving)."""
    doc = doc or KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="A")
    b = doc.add_body(K.translate(K.make_box(0.01, 0.01, 0.01),
                                 (0.05, 0.02, 0.03)), name="B")
    fa = [f for f in K.explore(a.shape, "face")
          if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9][0]      # A +Z
    fb = [f for f in K.explore(b.shape, "face")
          if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]      # B +X
    return doc, a, b, fa, fb


def _box_with_hole(doc, name="板"):
    body = doc.add_body(K.make_box(0.02, 0.02, 0.01), name=name)
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.01) < 1e-9][0]
    doc.record_feature(body.id, "hole", selector=FEAT.selector_for(body.shape, top),
                       diameter=5.0, depth=0.0)
    assert doc.replay_body(body.id)[0]
    return body, 0.02 * 0.02 * 0.01, 0.01


def _hole_v(v0, d_mm, t_m):
    return v0 - math.pi * (d_mm / 2000.0) ** 2 * t_m


def _apply(m, p):
    return tuple(sum(m[i][k] * p[k] for k in range(3)) + m[i][3]
                 for i in range(3))


def _rotate(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def _close(a, b, tol=1e-9):
    return max(abs(a[i] - b[i]) for i in range(3)) < tol


def test_every_mate_type_reports_the_dof_table_and_satisfies_its_condition():
    for mtype in TYPES:
        doc, a, b, fa, fb = _two_boxes()
        before = K.cog(b.shape)
        fr_a, fr_b = MATES.frame_of(fa), MATES.frame_of(fb)
        rep = doc.mate_bodies(mtype, a, fa, b, fb, value=0.002)
        assert rep["ok"], (mtype, rep["reason"])
        assert rep["dof"] == MATES.DOFS[mtype], mtype
        assert rep["removes"] == 6 - MATES.DOFS[mtype], mtype
        assert doc.mates[-1]["type"] == mtype
        m = rep["matrix"]
        moved = _apply(m, fr_b.origin)
        if mtype == MATES.DISTANCE:
            want = tuple(fr_a.origin[i] + fr_a.axis[i] * 0.002 for i in range(3))
            assert _close(moved, want), (mtype, moved, want)
        else:
            assert _close(moved, fr_a.origin), (mtype, moved, fr_a.origin)
        axis = _rotate(m, fr_b.axis)
        # which types constrain the orientation: everything but BALL (free) and
        # DISTANCE (the solver only offsets the origins, DOFS says 6 remain)
        if mtype == MATES.PLANAR:
            assert _close(axis, tuple(-c for c in fr_a.axis)), mtype
        elif mtype not in (MATES.BALL, MATES.DISTANCE):
            assert _close(axis, fr_a.axis), (mtype, axis, fr_a.axis)
        assert not _close(K.cog(b.shape), before), mtype      # B actually moved
        assert _close(K.cog(a.shape), K.cog(K.make_box(0.02, 0.02, 0.02))), mtype


def test_over_constraint_is_refused_with_the_numbers():
    doc, a, b, fa, fb = _two_boxes()
    assert doc.mate_bodies(MATES.RIGID, a, fa, b, fb)["ok"]
    after = K.cog(b.shape)
    rep = doc.mate_bodies(MATES.REVOLUTE, a, fa, b, fb)
    assert rep["ok"] is False
    assert "过约束" in rep["reason"] and "已固定 6" in rep["reason"], rep["reason"]
    assert len(doc.mates) == 1                       # the refused one is not kept
    assert _close(K.cog(b.shape), after)             # and nothing moved


def test_align_body_keeps_the_history_replayable():
    """A-1: the aligned body must equal the kernel's own align result, and the
    feature parameters must still be editable afterwards."""
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc)
    target = doc.add_body(K.translate(K.make_box(0.02, 0.02, 0.02),
                                      (0.05, 0.02, 0.03)), name="座")
    doc.translate_body(body.id, (0.01, 0.0, 0.0))
    mf = [f for f in K.explore(body.shape, "face")
          if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9][0]
    tf = [f for f in K.explore(target.shape, "face")
          if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9][0]
    assert doc.align_body(body.id, "faces", mf, tf) is not None

    assert doc.can_replay(body.id)[0] is True
    assert body.base_pose and body.base_pose[-1][0] == "matrix"
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 5.0, t_m), rel=1e-6)

    # independent yardstick: the same transform applied by the kernel alone
    ref_doc = KernelDoc()
    ref, _v0, _t = _box_with_hole(ref_doc)
    ref_doc.translate_body(ref.id, (0.01, 0.0, 0.0))
    ref_mf = [f for f in K.explore(ref.shape, "face")
              if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9][0]
    reference = K.align_faces(ref.shape, ref_mf, tf)
    assert _close(K.cog(body.shape), K.cog(reference), 1e-12)
    assert _close(K._vertex_bbox(body.shape)[0], K._vertex_bbox(reference)[0], 1e-12)

    rep = doc.edit_feature(body.id, 0, "diameter", 8.0)
    assert rep["ok"], rep["reason"]
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)
    assert doc.can_replay(body.id)[0] is True


def test_mate_keeps_the_history_replayable():
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc)
    target = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="座")
    mf = [f for f in K.explore(body.shape, "face")
          if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    tf = [f for f in K.explore(target.shape, "face")
          if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9][0]
    rep = doc.mate_bodies(MATES.RIGID, target, tf, body, mf)
    assert rep["ok"], rep["reason"]
    assert doc.can_replay(body.id)[0] is True
    assert doc.edit_feature(body.id, 0, "diameter", 9.0)["ok"]
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 9.0, t_m), rel=1e-6)


def test_undo_restores_the_pose_and_the_mate_list():
    doc, a, b, fa, fb = _two_boxes()
    snap = doc.snapshot()
    assert doc.mate_bodies(MATES.REVOLUTE, a, fa, b, fb)["ok"]
    assert doc.mates and b.base_pose

    doc.restore(snap)
    back = doc.body_by_id(b.id)
    assert doc.mates == []
    assert back.base_pose == []
    assert _close(K.cog(back.shape), K.cog(K.translate(
        K.make_box(0.01, 0.01, 0.01), (0.05, 0.02, 0.03))))


def test_project_round_trip_keeps_mates_and_poses():
    doc = KernelDoc()
    body, v0, t_m = _box_with_hole(doc)
    target = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="座")
    mf = [f for f in K.explore(body.shape, "face")
          if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    tf = [f for f in K.explore(target.shape, "face")
          if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9][0]
    assert doc.mate_bodies(MATES.RIGID, target, tf, body, mf)["ok"]
    cog = K.cog(body.shape)

    d = Path(tempfile.mkdtemp(prefix="r104_"))
    try:
        path = d / "mate.scdm"
        IO.save_scdm(str(path), doc)
        back = IO.load_scdm(str(path))
        assert [m["type"] for m in back.mates] == [MATES.RIGID]
        b = [x for x in back.bodies if x.name == "板"][0]
        assert b.base_pose and b.base_pose[-1][0] == "matrix"
        assert back.can_replay(b.id)[0] is True
        assert _close(K.cog(b.shape), cog, 1e-12)
        assert back.edit_feature(b.id, 0, "diameter", 7.0)["ok"]
        assert K.volume(b.shape) == pytest.approx(_hole_v(v0, 7.0, t_m), rel=1e-6)
    finally:
        shutil.rmtree(str(d), ignore_errors=True)


def test_scripted_mate_and_align_replay():
    """The eight-layer chain: script op -> pose -> feature edit still works."""
    turns = SCR.replay([
        {"cmd": "insert.box", "opts": {"w": 20.0, "h": 20.0, "d": 20.0}},
        {"cmd": "insert.box", "opts": {"w": 10.0, "h": 10.0, "d": 10.0,
                                       "origin": (50.0, 20.0, 30.0)}},
        {"cmd": "create.hole", "opts": {"target": "body", "index": 1,
                                        "face_i": 0, "diameter": 5.0, "depth": 0.0}},
        {"cmd": "asm.mate", "opts": {"type": "rigid", "target": "body",
                                     "index": 1, "target2": "body", "index2": 0,
                                     "face_a": 4, "face_b": 2}},
    ], KernelDoc())
    doc = KernelDoc()
    SCR.replay([
        {"cmd": "insert.box", "opts": {"w": 20.0, "h": 20.0, "d": 20.0}},
        {"cmd": "insert.box", "opts": {"w": 10.0, "h": 10.0, "d": 10.0,
                                       "origin": (50.0, 20.0, 30.0)}},
        {"cmd": "create.hole", "opts": {"target": "body", "index": 1,
                                        "face_i": 0, "diameter": 5.0, "depth": 0.0}},
        {"cmd": "asm.mate", "opts": {"type": "faces", "target": "body",
                                     "index": 1, "target2": "body", "index2": 0,
                                     "face_a": 4, "face_b": 2}},
    ], doc)
    b = doc.bodies[1]
    assert doc.feature_stack(b.id).ops() == ["hole"]
    assert doc.can_replay(b.id)[0] is True
    assert b.base_pose and b.base_pose[-1][0] == "matrix"
    assert doc.edit_feature(b.id, 0, "diameter", 8.0)["ok"]
    assert doc.can_replay(b.id)[0] is True

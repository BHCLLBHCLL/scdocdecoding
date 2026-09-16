"""R109 A-1 + A-6: welding within the coincidence tolerance, and the sketch
mode travelling with the undo stack.

A-1: R108 welded only vertices that were *exactly* equal.  Real drawings are a
     hair apart, so welding now uses the 0.1 mm coincidence tolerance and snaps
     the later points onto the group leader (the outline is closed immediately,
     not at the next solve).  A gap beyond the tolerance is reported with its
     measured size instead of a generic "no loop".
A-6: entering or leaving sketch mode is a user-visible step, so it is pushed onto
     the undo stack with the document - undo after a 3D command that crossed the
     boundary comes back *into* the sketch, redo leaves it again.
"""
from __future__ import annotations

import math
import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")


def _torn_rect(doc, gap_m=1e-4, w=0.010, h=0.008):
    """A rectangle drawn as four lines whose corners miss by gap_m."""
    sk = doc.add_sketch("xy")
    w2, h2 = w + gap_m, h + gap_m
    segs = [((0.0, 0.0), (w, 0.0)), ((w2, 0.0), (w2, h)),
            ((w2, h2), (0.0, h2)), ((0.0, h), (0.0, 0.0))]
    for a, b in segs:
        sk.curves.append(("line", (a[0], a[1], 0.0), (b[0], b[1], 0.0)))
    return sk


def _mm3(w, h, t):
    return w * h * t * 1e-9


def _drive_constraints(sk, w=0.010, h=0.008):
    """Make the (welded) four-line rectangle a properly constrained sketch."""
    sk.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 2, 3),
        (S.HORIZONTAL, 4, 5), (S.VERTICAL, 6, 7),
        (S.DIST, 0, 1, w), (S.DIST, 2, 3, h),
    ])
    return len(sk.constraints) - 2          # index of the width dimension


# --- A-1: tolerance welding -------------------------------------------------

def test_torn_corners_are_welded_within_the_coincidence_tolerance():
    doc = KernelDoc()
    sk = _torn_rect(doc, 1e-4)               # 0.1 mm gaps
    assert S.sketch_loops(sk.curves) == []   # not a loop yet
    report = {}
    added = S.weld_coincident(sk, tol=1e-4, report=report)
    assert added == 4 and report["moved"] == 3
    assert len(S.sketch_loops(sk.curves)) == 1
    # the welded corners are now *identical*, so the loop survives a solve
    pts, _segs, kinds = S.read_points(sk, with_kinds=True)
    gap = min(math.dist(pts[i][:2], pts[j][:2])
              for i in range(len(pts)) for j in range(i + 1, len(pts))
              if kinds[i] == kinds[j] == "vertex" and
              frozenset((i, j)) in {frozenset((0, 7)), frozenset((1, 2)),
                                    frozenset((3, 4)), frozenset((5, 6))})
    assert gap == 0.0


def test_the_tolerance_is_parameterisable():
    doc = KernelDoc()
    sk = _torn_rect(doc, 1e-4)
    # three corners miss by 0.1mm, the fourth one (0,0) was drawn exactly
    assert S.weld_coincident(sk, tol=1e-6) == 1        # only the exact corner
    assert S.weld_coincident(sk, tol=1e-3) == 3        # now the torn ones too


def test_extrude_welds_before_extracting_loops():
    doc = KernelDoc()
    sk = _torn_rect(doc, 1e-4)
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert rep["welded"] == 4 and rep["welded_moved"] == 3
    assert len(rep["bodies"]) == 1
    assert len(S.sketch_loops(sk.curves)) == 1
    # as drawn (corners taken from the group leader) -> within the welded offsets
    assert K.volume(rep["bodies"][0].shape) == pytest.approx(
        _mm3(10, 8, 5), rel=2e-2)


def test_a_gap_beyond_the_tolerance_is_reported_with_its_size():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.010, 0.0, 0.0)))
    sk.curves.append(("line", (0.0105, 0.0, 0.0), (0.0105, 0.008, 0.0)))
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep["ok"] is False
    assert "未重合" in rep["reason"] and "0.5mm" in rep["reason"], rep["reason"]
    assert rep["welded"] == 0


def test_a_torn_sketch_can_still_be_driven_to_the_closed_form():
    doc = KernelDoc()
    sk = _torn_rect(doc, 1e-4)
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    body = rep["bodies"][0]
    idx = _drive_constraints(sk)
    drive = SKM.set_dimension(doc, sk.id, idx, 20.0, 1000.0)
    assert drive["ok"], drive["reason"]
    assert drive["dof"] == 0
    assert len(S.sketch_loops(sk.curves)) == 1
    assert SKM.sync_sketch_bodies(doc, sk.id, 1000.0)["updated"] == [body.id]
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)
    assert doc.can_replay(body.id)[0] is True


# --- A-6: the mode travels with the undo stack ------------------------------

_APP = None          # keep the QApplication alive across tests (see below)


def _viewer():
    """A viewer for one test.

    The QApplication is held in a module global: a local reference is collected
    between tests, and destroying the app destroys every widget with it - the next
    test then fails with "wrapped C/C++ object has been deleted".
    """
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui
    return scdm_gui.ScdmViewer(path=_BOX)


def test_undo_after_a_3d_command_comes_back_into_the_sketch():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sid = v._sketch_session.sketch_id
        assert v._mode() == SKM.MODE_SKETCH

        v.on_command("asm.mate")             # a 3D command crosses the boundary
        assert v._mode() == SKM.MODE_SOLID

        v.on_command("edit.undo")            # ... and undo takes the mode back
        assert v._mode() == SKM.MODE_SKETCH
        assert v._sketch_session is not None
        assert v._sketch_session.sketch_id == sid
        assert v.session().show_grid is True

        v.on_command("edit.redo")            # redo leaves it again
        assert v._mode() == SKM.MODE_SOLID
        assert v._sketch_session is None
        assert v.session().show_grid is False
    finally:
        # the window may already be gone under pytest's GC (the smoke test
        # leaves its viewers to the collector as well) - the assertions above
        # are what this test is about
        try:
            v.hide()
        except RuntimeError:
            pass


def test_entering_sketch_mode_is_itself_an_undo_step():
    v = _viewer()
    try:
        assert v._mode() == SKM.MODE_SOLID
        v.on_command("mode.sketch")
        assert v._mode() == SKM.MODE_SKETCH
        v.on_command("edit.undo")            # undoing the entry leaves 3D
        assert v._mode() == SKM.MODE_SOLID
        v.on_command("edit.redo")
        assert v._mode() == SKM.MODE_SKETCH
    finally:
        # the window may already be gone under pytest's GC (the smoke test
        # leaves its viewers to the collector as well) - the assertions above
        # are what this test is about
        try:
            v.hide()
        except RuntimeError:
            pass

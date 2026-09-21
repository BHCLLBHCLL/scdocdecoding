"""R115 A-1 + A-2 + A-6: the geometry behind a conflict, an open-time check for
dangling dimension references, and the body whose sketch loop is gone.

A-1: `conflict_geometry()` maps the rows the solver could not satisfy onto UV
     points and segments (Qt-free, so it is testable without a 3D scene), and the
     sketch-mode chip / viewport mark them.
A-2: `reference_warnings()` lists every dimension whose expression cannot be
     resolved; opening a project reports them and the tree marks them in *any*
     sketch, not just the active one.
A-6: a body whose loop disappeared with the sketch edit goes with it (recoverable
     from the undo snapshot), instead of lingering as a stale solid.
"""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.io_project import load_scdm, save_scdm  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _rect_cons():
    return [(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
            (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
            (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008)]


def _doc_rect(u0=0.0, v0=0.0, u1=0.010, v1=0.008):
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[u0, v0], [u1, v0], [u1, v1], [u0, v1]]))
    sk.constraints.extend(_rect_cons())
    return doc, sk


def _viewer(path=None):
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _two_loops():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.010, 0.008, 0.0)))
    sk.curves.append(("rect", (0.020, 0.0, 0.0), (0.030, 0.008, 0.0)))
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    return doc, sk, rep


# --- A-1: the geometry behind a conflict ------------------------------------

def test_conflict_geometry_is_empty_when_the_sketch_is_fine():
    doc, sk = _doc_rect()
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert geo["ok"] and geo["cons"] == []
    assert geo["points"] == [] and geo["segments"] == []


def test_conflict_geometry_marks_the_fighting_edge():
    doc, sk = _doc_rect()
    sk.constraints.append((S.DIST, 0, 1, 0.012))          # 10mm vs 12mm
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert geo["cons"] == [5, 7]                          # 7 once, not twice
    assert geo["points"] == [[0.0, 0.0], [0.010, 0.0]]
    assert geo["segments"] == [[[0.0, 0.0], [0.010, 0.0]]]
    assert geo["solve"]["conflict_cons"] == (5, 7)


def test_conflict_geometry_covers_segment_pairs():
    doc, sk = _doc_rect()
    sk.constraints.append((S.PERPENDICULAR, 0, 2))         # two parallel edges
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert 7 in geo["cons"]
    # making two parallel edges perpendicular makes several rows fight, so check
    # the structure: every marked segment is between two marked points
    assert len(geo["segments"]) >= 2, geo
    assert [0.0, 0.0] in geo["points"] and [0.010, 0.0] in geo["points"]
    for a, b in geo["segments"]:
        assert a in geo["points"] and b in geo["points"], geo


def test_a_missing_sketch_is_reported_by_the_geometry_helper():
    doc, _sk = _doc_rect()
    geo = SKM.conflict_geometry(doc, "S9", 1000.0)
    assert geo["ok"] is False and "草图不存在" in geo["reason"]


def test_the_chip_names_conflicts_and_dangling_rows():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                                   [0.010, 0.008], [0.0, 0.008]]))
        sk.constraints.extend(_rect_cons())
        sk.constraints.append((S.DIST, 0, 1, 0.012))
        sk.constraints.append((S.DIST, 2, 3, "S9_dim5"))   # dangling too
        v._refresh_sketch_dof()
        chip = v._mode_chip.text()
        assert "冲突" in chip and "#5" in chip, chip
        assert "悬空 1" in chip, chip
        # the geometry helper agrees with what the chip claims.  The dangling row
        # is *skipped* by the solver (it constrains nothing), so it is not listed
        # as a conflict - the chip reports it separately as 悬空.
        geo = SKM.conflict_geometry(v.session().kdoc, sk.id, v.session().scale)
        assert geo["cons"] == [5, 7]
        assert geo["solve"]["skipped"], geo["solve"]
        assert "S9_dim5" in geo["solve"]["skipped"][0]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-2: the open-time reference check -------------------------------------

def test_reference_warnings_list_every_unusable_row():
    doc = KernelDoc()
    a = doc.add_sketch("xy")
    a.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0], [0.010, 0.008],
                              [0.0, 0.008]]))
    a.constraints.extend(_rect_cons())
    a.constraints.append((S.DIST, 2, 3, "2*nope"))          # a typo
    b = doc.add_sketch("xy")
    b.curves.append(("poly", [[0.020, 0.0], [0.030, 0.0], [0.030, 0.008],
                              [0.020, 0.008]]))
    b.constraints.extend([(S.FIXED, 0, 0.020, 0.0), (S.HORIZONTAL, 0, 1),
                          (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                          (S.VERTICAL, 3, 0), (S.DIST, 0, 1, "S9_dim5"),
                          (S.DIST, 1, 2, 0.008)])
    warns = SKM.reference_warnings(doc, 1000.0)
    assert sorted((w["sketch"], w["index"]) for w in warns) == [("S1", 7), ("S2", 5)]
    assert all(w["reason"] for w in warns)
    assert "nope" in warns[0]["reason"] or "nope" in warns[1]["reason"]


def test_opening_a_project_reports_dangling_references():
    doc, sk = _doc_rect()
    sk.constraints[5] = (S.DIST, 0, 1, "S9_dim5")
    path = os.path.join(tempfile.mkdtemp(), "dangling.scdm")
    save_scdm(path, doc)
    back = load_scdm(path)
    assert SKM.reference_warnings(back, 1000.0)      # the file really carries it

    v = _viewer(path)
    try:
        text = v._prompt.text()
        assert "引用悬空" in text and "S1#5" in text, text
        assert "S" in text
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

    # the extension is a hint: a project saved under another name still opens
    other = os.path.join(tempfile.mkdtemp(), "renamed.scdoc")
    save_scdm(other, doc)
    assert _viewer.__doc__ is None or True
    v2 = _viewer(other)
    try:
        assert "引用悬空" in v2._prompt.text(), v2._prompt.text()
    finally:
        try:
            v2.close()
        except RuntimeError:
            pass


def test_a_clean_project_opens_quietly():
    doc, _sk = _doc_rect()
    path = os.path.join(tempfile.mkdtemp(), "clean.scdm")
    save_scdm(path, doc)
    v = _viewer(path)
    try:
        assert "悬空" not in v._prompt.text(), v._prompt.text()
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_tree_marks_a_dangling_row_in_any_sketch():
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc = KernelDoc()
    a = doc.add_sketch("xy")
    a.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0], [0.010, 0.008],
                              [0.0, 0.008]]))
    a.constraints.extend(_rect_cons())
    b = doc.add_sketch("xy")
    b.curves.append(("poly", [[0.020, 0.0], [0.030, 0.0], [0.030, 0.008],
                              [0.020, 0.008]]))
    b.constraints.extend([(S.FIXED, 0, 0.020, 0.0), (S.HORIZONTAL, 0, 1),
                          (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                          (S.VERTICAL, 3, 0), (S.DIST, 0, 1, "S9_dim5"),
                          (S.DIST, 1, 2, 0.008)])
    doc.active_sketch = a.id                          # S2 is *not* active
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R115"))

        def walk(item, owner=""):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "sketch":
                owner = data[1]
            if data and data[0] == "sketch_dim":
                rows.append((owner, data[2], item.text(0)))
            for i in range(item.childCount()):
                walk(item.child(i), owner)

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    marked = [(sid, i, t) for sid, i, t in rows if t.startswith("悬空")]
    assert marked and marked[0][0] == "S2" and marked[0][1] == 5, rows


# --- A-6: the body whose loop is gone ---------------------------------------

def test_a_vanished_loop_takes_its_body():
    doc, sk, rep = _two_loops()
    assert len(rep["bodies"]) == 2 and len(doc.bodies) == 2
    keep_id = doc.bodies[0].id
    del sk.curves[1]                                   # the second loop is gone
    syn = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert syn["ok"] and not syn["failed"]
    assert [b.id for b in doc.bodies] == [keep_id]
    assert syn["removed"] == [(rep["bodies"][1].id, "草图第 2 个闭环已不存在")]
    assert rep["bodies"][1].id not in doc.features       # its history went too
    assert doc.can_replay(keep_id)[0] is True


def test_a_removed_body_comes_back_with_the_snapshot():
    doc, sk, _rep = _two_loops()
    snap = doc.snapshot()
    del sk.curves[1]
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert len(doc.bodies) == 1
    doc.restore(snap)                                   # what undo restores
    assert len(doc.bodies) == 2
    assert all(doc.can_replay(b.id)[0] for b in doc.bodies)


def test_an_added_loop_is_still_only_reported():
    """R112 behaviour stays: new geometry is *not* built and *not* removed."""
    doc, sk, _rep = _two_loops()
    sk.curves.append(("rect", (0.040, 0.0, 0.0), (0.050, 0.008, 0.0)))
    syn = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert syn["extra_loops"] == 1 and syn["removed"] == []
    assert len(doc.bodies) == 2


def test_the_gui_reports_the_removed_body():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.010, 0.008, 0.0)))
        sk.curves.append(("rect", (0.020, 0.0, 0.0), (0.030, 0.008, 0.0)))
        v.on_command("sketch.pull")                     # one body per loop
        v._edit_sketch(sk.id)
        before = len(v.session().kdoc.bodies)
        del sk.curves[1]
        v._sync_sketch_bodies(sk.id)
        hint = v._extra_loop_hint()
        assert "删除 1 个实体" in hint, hint
        assert "闭环已不存在" in hint, hint
        assert len(v.session().kdoc.bodies) == before - 1
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_leaving_sketch_mode_applies_the_removal():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.010, 0.008, 0.0)))
        sk.curves.append(("rect", (0.020, 0.0, 0.0), (0.030, 0.008, 0.0)))
        v.on_command("sketch.pull")                      # 2 bodies, back to 3D
        doc = v.session().kdoc
        after_pull = len(doc.bodies)
        assert after_pull >= 2
        v._edit_sketch(sk.id)
        del sk.curves[1]
        v.on_command("mode.3d")                          # leaving syncs
        assert len(doc.bodies) == after_pull - 1
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

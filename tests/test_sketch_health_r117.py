"""R117 A-1 + A-2 + A-6: redundancy attribution, a persistent health report in the
structure tree, and keeping a solid instead of deleting it.

A-1: a repeated row says *which earlier row* it repeats (the original: a triple
     duplicate points at the first one, not at the second copy).
A-2: `report_text()` is the copyable form, and the tree carries the report as a
     node whose rows can be double-clicked to go to the offending sketch/object.
A-6: `sync_sketch_bodies(..., detach=True)` keeps the solid as a plain shape
     while the default still removes it (both are reported).
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import health as HEALTH  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketch_solver as SS  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets
_PTS = [[0.0, 0.0], [0.010, 0.0], [0.010, 0.008], [0.0, 0.008]]
_SEGS = [(0, 1), (1, 2), (2, 3), (3, 0)]


def _rect_cons(width=0.010):
    return [(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
            (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
            (S.DIST, 0, 1, width), (S.DIST, 1, 2, 0.008)]


def _doc_rect(width=0.010):
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0], [0.010, 0.008],
                               [0.0, 0.008]]))
    sk.constraints.extend(_rect_cons(width))
    return doc, sk


def _solve(extra):
    return SS.solve_report([list(p) for p in _PTS], _rect_cons() + extra,
                           segments=list(_SEGS))


def _two_loops():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.010, 0.008, 0.0)))
    sk.curves.append(("rect", (0.020, 0.0, 0.0), (0.030, 0.008, 0.0)))
    SKM.extrude_active(doc, 5.0, 1000.0)
    return doc, sk


def _ensure_app():
    """Hold the QApplication in a module global (a local one is collected and
    takes every widget with it - and Qt aborts outright when a widget is built
    with no application at all)."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    return _APP


def _viewer(path=None):
    _ensure_app()
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


# --- A-1: which row does a redundant one repeat? ----------------------------

def test_a_duplicate_names_the_row_it_repeats():
    rep = _solve([(S.DIST, 0, 1, 0.010)])
    assert rep.redundant_cons == (7,)
    assert rep.duplicate_of == ((7, 5),)


def test_a_triple_duplicate_points_at_the_original():
    rep = _solve([(S.DIST, 0, 1, 0.010), (S.DIST, 0, 1, 0.010)])
    assert rep.redundant_cons == (7, 8)
    assert rep.duplicate_of == ((7, 5), (8, 5))


def test_a_fight_is_not_called_a_duplicate():
    rep = _solve([])
    assert rep.duplicate_of == ()


def test_the_marks_and_labels_carry_the_attribution():
    doc, sk = _doc_rect()
    sk.constraints.append((S.DIST, 0, 1, 0.010))
    sk.constraints.append((S.DIST, 0, 1, 0.010))
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert [(m["index"], m["state"], m["duplicate_of"]) for m in geo["marks"]] == [
        (7, "redundant", 5), (8, "redundant", 5)]
    assert SKM.conflict_labels(doc, sk.id, 1000.0) == [
        "尺寸#7 冗余（重复 #5）", "尺寸#8 冗余（重复 #5）"]
    assert geo["solve"]["duplicate_of"] == ((7, 5), (8, 5))


def test_a_conflicting_row_reports_no_attribution():
    doc, sk = _doc_rect()
    sk.constraints.append((S.DIST, 0, 1, 0.012))          # a fight, not a copy
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert all(m["state"] == "conflict" and m["duplicate_of"] is None
               for m in geo["marks"])


# --- A-2: the health report -------------------------------------------------

def test_report_text_is_one_line_per_warning():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.named.append({"name": "面组", "items": [("face", "%s:0" % body.id)]})
    doc.remove(body.id)
    warns = HEALTH.document_warnings(doc, 1000.0)
    text = HEALTH.report_text(warns)
    lines = text.splitlines()
    assert lines[0].startswith("引用体检：")
    assert len(lines) == len(warns) + 1
    assert "命名选择" in lines[1]
    assert HEALTH.report_text([]) == ""


def test_the_tree_shows_the_health_report():
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.named.append({"name": "面组", "items": [("face", "%s:0" % body.id)]})
    doc.remove(body.id)
    _ensure_app()
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R117"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health":
                rows.append((data, item.text(0)))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    assert rows, "no health node in the tree"
    head = [t for d, t in rows if len(d) == 2][0]
    assert head.startswith("引用体检：1 条"), head
    assert "命名选择" in rows[-1][1]


def test_a_clean_document_has_no_health_node():
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc, _sk = _doc_rect()
    _ensure_app()
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R117"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health":
                rows.append((data, item.text(0)))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    assert rows == []


def test_double_clicking_a_health_row_locates_it():
    _ensure_app()
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel
    import scdm_gui

    v = _viewer()
    sk = None
    panel = None
    try:
        doc = v.session().kdoc
        sk = doc.add_sketch("xy")
        sk.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0], [0.020, 0.008],
                                   [0.0, 0.008]]))
        sk.constraints.extend(_rect_cons("S9_dim5"))    # dangling reference
        doc.active_sketch = sk.id
        panel = LeftPanel()
        found = []
        panel.populate_tree(Session(kdoc=doc, name="R117"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health" and len(data) > 2:
                found.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
        assert found, "no health row"
        v._on_tree_double_click(found[0])
        assert v._mode() == SKM.MODE_SKETCH, v._prompt.text()
        assert v._sketch_session.sketch_id == sk.id
    finally:
        for w in (panel,):
            if w is not None:
                try:
                    w.hide()
                except RuntimeError:
                    pass
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-6: keep the solid instead of deleting it -----------------------------

def test_detach_keeps_the_solid_but_drops_the_feature():
    doc, sk = _two_loops()
    ids = [b.id for b in doc.bodies]
    del sk.curves[1]
    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0, detach=True)
    assert rep["detached"] == [(ids[1], "草图第 2 个闭环已不存在")]
    assert rep["removed"] == [] and rep["updated"] == [ids[0]]
    body = doc.body_by_id(ids[1])
    assert body is not None
    assert K.volume(body.shape) == pytest.approx(10 * 8 * 5 * 1e-9, rel=1e-9)
    assert len(doc.feature_stack(ids[1])) == 0
    assert doc.can_replay(ids[1])[0] is False        # nothing left to replay


def test_detach_is_opt_in():
    doc, sk = _two_loops()
    del sk.curves[1]
    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert rep["removed"] and rep["detached"] == []
    assert len(doc.bodies) == 1


def test_a_detached_body_still_survives_a_reload():
    import tempfile
    from scdm.io_project import load_scdm, save_scdm

    doc, sk = _two_loops()
    ids = [b.id for b in doc.bodies]
    del sk.curves[1]
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0, detach=True)
    path = os.path.join(tempfile.mkdtemp(), "detached.scdm")
    save_scdm(path, doc)
    back = load_scdm(path)
    assert [b.id for b in back.bodies] == ids
    assert K.volume(back.body_by_id(ids[1]).shape) == pytest.approx(
        10 * 8 * 5 * 1e-9, rel=1e-9)


def test_the_gui_reports_a_detached_body():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.010, 0.008, 0.0)))
        sk.curves.append(("rect", (0.020, 0.0, 0.0), (0.030, 0.008, 0.0)))
        v.on_command("sketch.pull")
        v._edit_sketch(sk.id)
        before = len(v.session().kdoc.bodies)
        v.left.show_options("mode.sketch")
        v.left.set_checked("mode.sketch", 2, True)      # 闭环消失时保留实体
        del sk.curves[1]
        v._sync_sketch_bodies(sk.id)
        hint = v._extra_loop_hint()
        assert "保留 1 个实体" in hint and "已断开参数" in hint, hint
        assert len(v.session().kdoc.bodies) == before   # nothing was deleted
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

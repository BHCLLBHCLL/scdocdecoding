"""R121 A-1 + A-3 + A-6: untick rows in the preview, retarget from the sketch
picked in the tree, and an along-curve anchor.

A-1: `repair_selected(..., exclude=ids)` is the other way round from `ids` -
     "fix everything except these", which is what unticking a preview row means;
     asking for both at once is refused.
A-3: the retarget target is the sketch row picked in the tree when there is one,
     and the typed index otherwise.
A-6: `pattern_curves(..., anchor=(u, v))` makes a chosen point of the geometry
     follow the path, instead of assuming the geometry sits at the path start.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import health as HEALTH  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _ensure_app():
    """Hold the QApplication in a module global (Qt aborts without one)."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    return _APP


def _viewer(path=None):
    _ensure_app()
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _rect(doc, u0, w, width):
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[u0, 0.0], [u0 + w, 0.0], [u0 + w, 0.008],
                               [u0, 0.008]]))
    sk.constraints.extend([(S.FIXED, 0, u0, 0.0), (S.HORIZONTAL, 0, 1),
                           (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                           (S.VERTICAL, 3, 0), (S.DIST, 0, 1, width),
                           (S.DIST, 1, 2, 0.008)])
    return sk


def _three_dangling():
    doc = KernelDoc()
    a = _rect(doc, 0.0, 0.020, "S9_dim5")
    b = _rect(doc, 0.040, 0.020, "S9_dim5")
    c = _rect(doc, 0.080, 0.020, "S9_dim5")
    return doc, a, b, c


# --- A-1: untick rows in the preview ----------------------------------------

def test_exclude_repairs_everything_but_the_unticked_rows():
    doc, a, b, c = _three_dangling()
    rep = HEALTH.repair_selected(doc, None, 1000.0, exclude=["S2#5"])
    assert len(rep["fixed"]) == 2 and rep["skipped"] == [], rep
    assert isinstance(a.constraints[5][3], float)
    assert isinstance(c.constraints[5][3], float)
    assert b.constraints[5][3] == "S9_dim5"          # the unticked one
    assert [w["id"] for w in HEALTH.document_warnings(doc, 1000.0)] == ["S2#5"]


def test_ids_and_exclude_together_are_refused():
    doc, a, _b, _c = _three_dangling()
    rep = HEALTH.repair_selected(doc, ["S1#5"], 1000.0, exclude=["S2#5"])
    assert rep["ok"] is False and "不能同时" in rep["reason"], rep
    assert a.constraints[5][3] == "S9_dim5"          # nothing happened


def test_the_plan_honours_exclude():
    doc, _a, _b, _c = _three_dangling()
    plan = HEALTH.repair_plan(doc, 1000.0, exclude=["S2#5"])
    assert [p["id"] for p in plan] == ["S1#5", "S3#5"]
    assert len(HEALTH.repair_plan(doc, 1000.0, ids=["S1#5"])) == 1


def test_the_plan_and_the_repair_agree_under_exclude():
    doc, _a, _b, _c = _three_dangling()
    ids = [p["id"] for p in HEALTH.repair_plan(doc, 1000.0,
                                               exclude=["S3#5"])]
    rep = HEALTH.repair_selected(doc, ids, 1000.0)
    assert len(rep["fixed"]) == len(ids)
    assert [w["id"] for w in HEALTH.document_warnings(doc, 1000.0)] == ["S3#5"]


def test_the_command_can_skip_the_selected_rows():
    _ensure_app()
    from scdm.document import Session

    v = _viewer()
    try:
        doc = v.session().kdoc
        a = _rect(doc, 0.0, 0.020, "S9_dim5")
        b = _rect(doc, 0.040, 0.020, "S9_dim5")
        rows = []
        v.left.populate_tree(Session(kdoc=doc, name="R121"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health" and len(data) > 3:
                rows.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(v.left.tree.topLevelItemCount()):
            walk(v.left.tree.topLevelItem(i))
        v.left.show_options("repair.refs")
        v.left.set_checked("repair.refs", 2, True)       # 跳过选中的
        v.left.tree.clearSelection()
        rows[1].setSelected(True)                        # untick the second
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "跳过选中的 1 条，修好 1 条" in text, text
        assert isinstance(a.constraints[5][3], float)
        assert b.constraints[5][3] == "S9_dim5"
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-3: pick the retarget target in the tree ------------------------------

def test_the_command_retargets_to_the_sketch_picked_in_the_tree():
    _ensure_app()
    from scdm.document import Session

    v = _viewer()
    try:
        doc = v.session().kdoc
        a = _rect(doc, 0.0, 0.020, "S9_dim5")
        target = _rect(doc, 0.040, 0.017, 0.017)         # S2, 17mm
        v.left.populate_tree(Session(kdoc=doc, name="R121"))
        v.left.show_options("repair.refs")
        v.left.set_checked("repair.refs", 1, True)       # 改指向
        v.left.tree.clearSelection()
        picked = None

        def walk(item):
            nonlocal picked
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "sketch" and data[1] == target.id:
                picked = item
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(v.left.tree.topLevelItemCount()):
            walk(v.left.tree.topLevelItem(i))
        assert picked is not None, "the target sketch is not in the tree"
        picked.setSelected(True)
        assert v._selected_sketch_id() == target.id
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "修好 1 条" in text, text
        assert a.constraints[5][3] == "%s_dim5" % target.id
        assert SKM.dimensions(doc, a.id, 1000.0)[0]["value_mm"] == \
            pytest.approx(17.0)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_without_a_picked_sketch_the_typed_index_is_used():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        a = _rect(doc, 0.0, 0.020, "S9_dim5")
        _rect(doc, 0.040, 0.014, 0.014)                  # S2
        v.left.show_options("repair.refs")
        v.left.set_checked("repair.refs", 1, True)
        v.left.tree.clearSelection()
        assert v._selected_sketch_id() is None
        page = v.left._opt_pages["repair.refs"]
        page[2][0].setValue(2.0)
        v.on_command("repair.refs")
        assert a.constraints[5][3] == "S2_dim5"
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-6: the along-curve anchor --------------------------------------------

def test_an_explicit_anchor_follows_the_path():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.005, 0.001, 0.0), (0.007, 0.004, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="along", path=[(0.0, 0.0), (0.020, 0.0)],
                           anchor=(0.005, 0.001))
    assert rep["ok"] and rep["anchor"] == [0.005, 0.001]
    copies = [c for c in sk.curves if c[0] == "poly"]
    anchors = [(round(float(c[1][0][0]), 9), round(float(c[1][0][1]), 9))
               for c in copies]
    assert anchors == [(0.010, 0.0), (0.020, 0.0)], anchors
    # the geometry keeps its shape and its offset from the anchor: the rect
    # (5,1)-(7,4)mm becomes (10,0)-(12,3)mm, corner for corner
    pts = [(round(float(p[0]) * 1000, 9), round(float(p[1]) * 1000, 9))
           for p in copies[0][1]]
    assert pts == [(10.0, 0.0), (12.0, 0.0), (12.0, 3.0), (10.0, 3.0)], pts


def test_the_default_anchor_is_still_the_path_start():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.003, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="along", path=[(0.0, 0.0), (0.020, 0.0)])
    assert rep["anchor"] == [0.0, 0.0]
    copies = [c for c in sk.curves if c[0] == "poly"]
    xs = sorted(float(c[1][0][0]) for c in copies)
    assert xs == [pytest.approx(0.010, abs=1e-12), pytest.approx(0.020, abs=1e-12)]


def test_a_bad_anchor_is_refused():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.003, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="along", path=[(0.0, 0.0), (0.020, 0.0)],
                           anchor=5)
    assert rep["ok"] is False and "锚点无效" in rep["reason"], rep
    assert len(sk.curves) == 1


def test_the_op_takes_the_anchor_in_millimetres():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
    sk.curves.append(("rect", (0.005, 0.001, 0.0), (0.007, 0.004, 0.0)))
    _b, msg = SCR.OPS["sketch.pattern"](doc, {"count": 3, "mode": "along",
                                              "path_index": 0,
                                              "anchor_mm": [5.0, 1.0]}, 1000.0)
    assert "沿曲线" in msg, msg
    copies = [c for c in sk.curves if c[0] == "poly"]
    anchors = sorted(round(float(c[1][0][0]), 9) for c in copies)
    assert anchors == [0.010, 0.020], anchors

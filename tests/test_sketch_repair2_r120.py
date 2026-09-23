"""R120 A-1 + A-2 + A-3: repair only the rows you picked, batch-retarget with a
target map, and treat imported structures as read-only.

A-1: `repair_selected(kdoc, ids)` touches exactly the named warnings - the rest
     of the document is left as it was - and the tree can select several rows.
A-2: the action may be a `{scope: action}` map and `to` may be one target or a
     `{warning id: target}` map, so a batch retarget is one call.
A-3: a warning from an imported group is flagged read-only, refused by a repair,
     skipped by `repair_all` and shown as "只读（导入），跳过" in the plan.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import health as HEALTH  # noqa: E402
from scdm import kernel as K  # noqa: E402
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


def _two_dangling():
    """S1 and S2 both pointing at a deleted S9, plus S3 as a target."""
    doc = KernelDoc()
    a = _rect(doc, 0.0, 0.020, "S9_dim5")
    b = _rect(doc, 0.040, 0.020, "S9_dim5")
    c = _rect(doc, 0.080, 0.012, 0.012)
    return doc, a, b, c


# --- A-1: repair exactly what was picked ------------------------------------

def test_repair_selected_touches_only_the_named_rows():
    doc, a, b, _c = _two_dangling()
    assert [w["id"] for w in HEALTH.document_warnings(doc, 1000.0)] == ["S1#5",
                                                                       "S2#5"]
    other_before = list(b.constraints)
    rep = HEALTH.repair_selected(doc, ["S1#5"], 1000.0)
    assert rep["fixed"] == [("S1#5", "已冻结为 20mm")] and rep["skipped"] == []
    assert isinstance(a.constraints[5][3], float)
    assert b.constraints == other_before                 # untouched
    assert [w["id"] for w in HEALTH.document_warnings(doc, 1000.0)] == ["S2#5"]


def test_repair_selected_without_ids_is_everything():
    doc, a, b, _c = _two_dangling()
    rep = HEALTH.repair_selected(doc, None, 1000.0)
    assert len(rep["fixed"]) == 2 and rep["skipped"] == []
    assert isinstance(a.constraints[5][3], float)
    assert isinstance(b.constraints[5][3], float)
    assert HEALTH.document_warnings(doc, 1000.0) == []


def test_the_plan_filters_by_ids():
    doc, _a, _b, _c = _two_dangling()
    plan = HEALTH.repair_plan(doc, 1000.0, ids=["S2#5"])
    assert [p["id"] for p in plan] == ["S2#5"]
    assert len(HEALTH.repair_plan(doc, 1000.0)) == 2


def test_the_tree_allows_multi_selection():
    _ensure_app()
    from PyQt5.QtWidgets import QAbstractItemView
    v = _viewer()
    try:
        assert v.left.tree.selectionMode() == QAbstractItemView.ExtendedSelection
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_command_repairs_the_selected_rows_only():
    _ensure_app()
    from scdm.gui.left_panel import LeftPanel

    v = _viewer()
    panel = None
    try:
        doc = v.session().kdoc
        a = _rect(doc, 0.0, 0.020, "S9_dim5")
        b = _rect(doc, 0.040, 0.020, "S9_dim5")
        from scdm.document import Session
        rows = []
        v.left.populate_tree(Session(kdoc=doc, name="R120"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health" and len(data) > 3:
                rows.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(v.left.tree.topLevelItemCount()):
            walk(v.left.tree.topLevelItem(i))
        assert len(rows) == 2
        v.left.tree.clearSelection()
        rows[1].setSelected(True)                    # only the second one
        assert v._selected_health_ids() == ["S2#5"]
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "选中 1 条，修好 1 条" in text, text
        assert isinstance(b.constraints[5][3], float)
        assert a.constraints[5][3] == "S9_dim5"      # the other one is untouched
    finally:
        if panel is not None:
            try:
                panel.hide()
            except RuntimeError:
                pass
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-2: batch retarget ----------------------------------------------------

def test_a_batch_retarget_points_every_dimension_at_one_sketch():
    doc, a, b, c = _two_dangling()
    rep = HEALTH.repair_selected(doc, None, 1000.0,
                                 action={"dimension": "retarget"}, to="S3")
    assert len(rep["fixed"]) == 2 and rep["skipped"] == [], rep
    assert a.constraints[5][3] == "S3_dim5"
    assert b.constraints[5][3] == "S3_dim5"
    assert HEALTH.document_warnings(doc, 1000.0) == []
    widths = [SKM.dimensions(doc, sk.id, 1000.0)[0]["value_mm"]
              for sk in (a, b)]
    assert widths == [pytest.approx(12.0, rel=1e-9)] * 2
    assert SKM.dimensions(doc, c.id, 1000.0)[0]["value_mm"] == pytest.approx(12.0)


def test_a_target_map_gives_each_row_its_own_target():
    doc = KernelDoc()
    a = _rect(doc, 0.0, 0.020, "S9_dim5")
    b = _rect(doc, 0.040, 0.020, "S9_dim5")
    t1 = _rect(doc, 0.080, 0.011, 0.011)
    t2 = _rect(doc, 0.120, 0.013, 0.013)
    rep = HEALTH.repair_selected(doc, None, 1000.0, action="retarget",
                                 to={"S1#5": ("S3", 5), "S2#5": "S4"})
    assert len(rep["fixed"]) == 2 and rep["skipped"] == [], rep
    assert a.constraints[5][3] == "S3_dim5"
    assert b.constraints[5][3] == "S4_dim5"
    assert SKM.dimensions(doc, a.id, 1000.0)[0]["value_mm"] == pytest.approx(11.0)
    assert SKM.dimensions(doc, b.id, 1000.0)[0]["value_mm"] == pytest.approx(13.0)


def test_the_command_can_batch_retarget():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        a = _rect(doc, 0.0, 0.020, "S9_dim5")
        _rect(doc, 0.040, 0.020, "S9_dim5")
        _rect(doc, 0.080, 0.014, 0.014)                 # S3, the target
        v.left.show_options("repair.refs")
        v.left.set_checked("repair.refs", 1, True)      # 尺寸改指向草图序号
        page = v.left._opt_pages["repair.refs"]
        page[2][0].setValue(3.0)
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "修好 2 条" in text, text
        assert a.constraints[5][3] == "S3_dim5"
        assert SKM.dimensions(doc, a.id, 1000.0)[0]["value_mm"] == pytest.approx(14.0)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-3: imported structures are read-only ---------------------------------

def test_an_imported_structure_is_read_only():
    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.groups.append({"name": "导入层", "items": [("body", "B9")],
                       "imported": True})
    doc.named.append({"name": "用户组", "items": [("body", "B9")]})
    warns = {w["scope"]: w for w in HEALTH.document_warnings(doc, 1000.0)}
    assert warns["group"].get("readonly") is True
    assert "导入，只读" in warns["group"]["reason"]
    assert not warns["named"].get("readonly")
    rep = HEALTH.repair_warning(doc, warns["group"], "auto", 1000.0)
    assert rep["ok"] is False and rep["options"] == []
    assert "导入结构" in rep["reason"], rep
    assert len(doc.groups[0]["items"]) == 1              # the group is untouched


def test_repair_all_skips_read_only_and_still_fixes_the_rest():
    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.groups.append({"name": "导入层", "items": [("body", "B9")],
                       "imported": True})
    _rect(doc, 0.0, 0.020, "S9_dim5")
    rep = HEALTH.repair_all(doc, 1000.0)
    assert len(rep["fixed"]) == 1 and len(rep["skipped"]) == 1, rep
    assert "只读" in rep["skipped"][0][1]
    assert len(doc.groups[0]["items"]) == 1
    assert [w["scope"] for w in HEALTH.document_warnings(doc, 1000.0)] == ["group"]


def test_the_plan_says_a_read_only_row_will_be_skipped():
    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.groups.append({"name": "导入层", "items": [("body", "B9")],
                       "imported": True})
    plan = HEALTH.repair_plan(doc, 1000.0)
    assert plan[0]["action"] == "" and plan[0]["text"] == "只读（导入），跳过"
    assert "只读" in HEALTH.plan_text(plan)


def test_the_tree_says_the_row_is_imported_and_read_only():
    _ensure_app()
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.groups.append({"name": "导入层", "items": [("body", "B9")],
                       "imported": True})
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R120"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health":
                rows.append(item.text(0))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    assert any("导入，只读" in t for t in rows), rows

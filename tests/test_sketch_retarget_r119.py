"""R119 A-1 + A-2 + A-3: retarget a dangling reference, review the repair plan
before it runs, and locate the surviving members of a named selection or group.

A-1: `repair_warning(action="retarget", to="S2")` keeps a dimension's intent -
     the row keeps its expression form, only the sketch it names changes, and the
     geometry re-solves against the new target.
A-2: `repair_plan()` says what a repair would do without touching anything, and
     the command can run it as a dry run first.
A-3: a named-selection or group health row selects the members that still exist.
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


def _two_sketches():
    """S1 whose width points at a deleted S9, and S2 with a 15mm width."""
    doc = KernelDoc()
    a = _rect(doc, 0.0, 0.020, "S9_dim5")
    b = _rect(doc, 0.040, 0.015, 0.015)
    return doc, a, b


# --- A-1: retarget instead of freeze ---------------------------------------

def test_retargeting_keeps_the_intent():
    doc, a, b = _two_sketches()
    warns = HEALTH.document_warnings(doc, 1000.0)
    assert len(warns) == 1 and warns[0]["ref"] == ("S1", 5)
    rep = HEALTH.repair_warning(doc, warns[0], "retarget", 1000.0, to="S2")
    assert rep["ok"] and "改指向 S2_dim5" in rep["reason"], rep
    assert rep["options"] == ["freeze", "retarget"]
    assert a.constraints[5][3] == "S2_dim5"          # the expression form stays
    assert HEALTH.document_warnings(doc, 1000.0) == []
    rows = {d["index"]: d for d in SKM.dimensions(doc, a.id, 1000.0)}
    assert rows[5]["value_mm"] == pytest.approx(15.0, rel=1e-9)


def test_a_retargeted_dimension_follows_its_new_target():
    doc, a, b = _two_sketches()
    warns = HEALTH.document_warnings(doc, 1000.0)
    assert HEALTH.repair_warning(doc, warns[0], "retarget", 1000.0,
                                 to="S2")["ok"]
    out = SKM.extrude_active(doc, 5.0, 1000.0,
                             SKM.SketchSession(sketch_id=a.id, plane="xy"))
    body = out["bodies"][0]
    assert K.volume(body.shape) == pytest.approx(15 * 8 * 5 * 1e-9, rel=1e-6)
    assert SKM.set_dimension(doc, b.id, 5, 25.0, 1000.0)["ok"]
    SKM.redrive_expressions(doc, 1000.0)
    SKM.sync_sketch_bodies(doc, a.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(25 * 8 * 5 * 1e-9, rel=1e-6)


def test_a_bad_retarget_target_is_refused():
    doc, a, _b = _two_sketches()
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    missing = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="S8")
    assert missing["ok"] is False and "目标草图 S8 已不存在" in missing["reason"]
    not_dim = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="S2",
                                    to_index=3)
    assert not_dim["ok"] is False and "没有尺寸 #3" in not_dim["reason"]
    no_to = HEALTH.repair_warning(doc, warn, "retarget", 1000.0)
    # R122 widened the message: a target may be a sketch or a parameter
    assert no_to["ok"] is False and "需要给出目标" in no_to["reason"]
    assert "param:" in no_to["reason"]
    assert a.constraints[5][3] == "S9_dim5"          # nothing was changed


def test_the_auto_action_still_freezes():
    doc, a, _b = _two_sketches()
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "auto", 1000.0)
    assert rep["action"] == "freeze" and rep["ok"]
    assert isinstance(a.constraints[5][3], float)


# --- A-2: review the plan first --------------------------------------------

def test_the_plan_says_what_would_happen_without_doing_it():
    doc, a, _b = _two_sketches()
    b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    b2 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    c1 = doc.add_component("C1", [b1.id])
    c2 = doc.add_component("C2", [b2.id])
    mate, _why = doc.add_mate("rigid", c1.id, c2.id)
    assert mate is not None
    doc.components = [c for c in doc.components if c.id != c2.id]
    plan = HEALTH.repair_plan(doc, 1000.0)
    assert len(plan) == len(HEALTH.document_warnings(doc, 1000.0)) == 2
    by_id = {p["id"]: p for p in plan}
    assert by_id["S1#5"]["action"] == "freeze"
    assert by_id["S1#5"]["text"] == "冻结为当前值"
    assert any(p["action"] == "drop" for p in plan)
    # nothing happened yet
    assert a.constraints[5][3] == "S9_dim5" and doc.mates
    text = HEALTH.plan_text(plan)
    assert len(text.splitlines()) == len(plan) + 1
    assert HEALTH.plan_text([]) == ""


def test_the_plan_matches_what_repair_all_then_does():
    doc, _a, _b = _two_sketches()
    plan = HEALTH.repair_plan(doc, 1000.0)
    rep = HEALTH.repair_all(doc, 1000.0)
    assert len(rep["fixed"]) == len(plan) and rep["skipped"] == []
    assert HEALTH.repair_plan(doc, 1000.0) == []


def test_the_command_can_dry_run_first():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        a = _rect(doc, 0.0, 0.020, "S9_dim5")
        v.left.show_options("repair.refs")
        v.left.set_checked("repair.refs", 0, True)      # 先预览
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "引用修复预览：1 条" in text, text
        assert "S1#5 → 冻结为当前值" in text, text
        assert v.repair_plan and v.repair_plan[0]["action"] == "freeze"
        assert a.constraints[5][3] == "S9_dim5"          # untouched

        v.left.set_checked("repair.refs", 0, False)
        v.on_command("repair.refs")
        assert "修好 1 条" in v._prompt.text(), v._prompt.text()
        assert isinstance(a.constraints[5][3], float)
        assert v.repair_plan == []
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-3: named selections and groups locate their survivors ----------------

def _health_rows(panel, doc):
    from scdm.document import Session
    rows = []
    panel.populate_tree(Session(kdoc=doc, name="R119"))

    def walk(item):
        data = item.data(0, Qt.UserRole)
        if data and data[0] == "health" and len(data) > 3:
            rows.append(item)
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(panel.tree.topLevelItemCount()):
        walk(panel.tree.topLevelItem(i))
    return rows


def test_a_named_selection_row_selects_its_surviving_members():
    _ensure_app()
    from scdm.gui.left_panel import LeftPanel

    v = _viewer()
    panel = None
    try:
        doc = v.session().kdoc
        gone = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        live = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
        doc.named.append({"name": "面组",
                          "items": [("face", "%s:0" % gone.id),
                                    ("face", "%s:0" % live.id)]})
        doc.remove(gone.id)
        panel = LeftPanel()
        rows = _health_rows(panel, doc)
        named = [r for r in rows if r.data(0, Qt.UserRole)[1] == "named"]
        assert named, "no named-selection row"
        v._on_tree_double_click(named[0])
        assert ("body", live.id) in v.sel.items, (v.sel.items, live.id)
        assert ("body", gone.id) not in v.sel.items
        assert "仍然存在的成员" in v._prompt.text(), v._prompt.text()
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


def test_a_group_row_with_no_survivors_says_so():
    _ensure_app()
    from scdm.gui.left_panel import LeftPanel

    v = _viewer()
    panel = None
    try:
        doc = v.session().kdoc
        gone = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        doc.groups.append({"name": "组1", "items": [("body", gone.id)]})
        doc.remove(gone.id)
        panel = LeftPanel()
        rows = _health_rows(panel, doc)
        group = [r for r in rows if r.data(0, Qt.UserRole)[1] == "group"]
        assert group, "no group row"
        before = list(v.sel.items)
        v._on_tree_double_click(group[0])
        # nothing to select, and nothing selected by accident
        assert v.sel.items == before, v.sel.items
        assert ("body", gone.id) not in v.sel.items
        assert "都已不存在" in v._prompt.text(), v._prompt.text()
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

"""R118 A-1 + A-2 + A-3: the redundancy link drawn, one-click repair of dangling
references, and health rows that locate mates and configurations.

A-1: `conflict_geometry()[\"links\"]` pairs a repeated row with the original it
     repeats, and the viewport draws that pair (violet connector).
A-2: `repair_warning()` freezes an unresolvable dimension at the value the
     geometry has now (the only safe fix for a row other expressions address),
     drops the other scopes by value, and refuses the rest *listing the options*.
A-3: double-clicking a health row opens the sketch, selects a component\'s bodies,
     or switches to the configuration it names.
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
    """Hold the QApplication in a module global (see R117: Qt aborts without one)."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    return _APP


def _viewer(path=None):
    _ensure_app()
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _rect_sk(doc, width=0.010):
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0], [0.020, 0.008],
                               [0.0, 0.008]]))
    sk.constraints.extend([(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1),
                           (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                           (S.VERTICAL, 3, 0), (S.DIST, 0, 1, width),
                           (S.DIST, 1, 2, 0.008)])
    return sk


def _dangling_doc():
    doc = KernelDoc()
    sk = _rect_sk(doc, "S9_dim5")
    return doc, sk


def _component_doc():
    doc = KernelDoc()
    b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    b2 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    c1 = doc.add_component("C1", [b1.id])
    c2 = doc.add_component("C2", [b2.id])
    mate, why = doc.add_mate("rigid", c1.id, c2.id)
    assert mate is not None and why == ""
    doc.components = [c for c in doc.components if c.id != c2.id]
    return doc, c1, c2, b1, b2


# --- A-1: the redundancy link -----------------------------------------------

def test_links_pair_a_repeated_row_with_its_original():
    doc = KernelDoc()
    sk = _rect_sk(doc)
    sk.constraints.append((S.DIST, 0, 1, 0.010))
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert geo["links"] == [(5, 7)]
    sk.constraints.append((S.DIST, 0, 1, 0.010))
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert geo["links"] == [(5, 7), (5, 8)]          # both point at the original


def test_a_clean_or_conflicting_sketch_has_no_links():
    doc = KernelDoc()
    sk = _rect_sk(doc)
    assert SKM.conflict_geometry(doc, sk.id, 1000.0)["links"] == []
    sk.constraints.append((S.DIST, 0, 1, 0.012))     # a fight, not a copy
    assert SKM.conflict_geometry(doc, sk.id, 1000.0)["links"] == []


def test_the_link_agrees_with_the_marks_and_labels():
    doc = KernelDoc()
    sk = _rect_sk(doc)
    sk.constraints.append((S.DIST, 0, 1, 0.010))
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    redundant = {m["index"]: m for m in geo["marks"] if m["state"] == "redundant"}
    for src, dep in geo["links"]:
        assert redundant[dep]["duplicate_of"] == src
        assert ("重复 #%d" % src) in "".join(
            SKM.conflict_labels(doc, sk.id, 1000.0))


# --- A-2: one-click repair --------------------------------------------------

def test_freezing_keeps_the_geometry_and_clears_the_warning():
    doc, sk = _dangling_doc()
    pts_before = [tuple(p) for p in S.read_points(sk)[0]]
    warns = HEALTH.document_warnings(doc, 1000.0)
    assert len(warns) == 1 and warns[0]["scope"] == "dimension"
    rep = HEALTH.repair_warning(doc, warns[0], "auto", 1000.0)
    assert rep["ok"] and "冻结" in rep["reason"], rep
    assert rep["options"] == ["freeze"]
    assert isinstance(sk.constraints[5][3], float)
    assert sk.constraints[5][3] == pytest.approx(0.020, rel=1e-6)   # as drawn
    assert [tuple(p) for p in S.read_points(sk)[0]] == pts_before
    assert HEALTH.document_warnings(doc, 1000.0) == []


def test_dropping_a_dimension_is_refused_with_the_options():
    doc, _sk = _dangling_doc()
    warns = HEALTH.document_warnings(doc, 1000.0)
    rep = HEALTH.repair_warning(doc, warns[0], "drop", 1000.0)
    assert rep["ok"] is False
    assert rep["options"] == ["freeze"] and "可用" in rep["reason"], rep
    assert HEALTH.document_warnings(doc, 1000.0)           # nothing changed


def test_a_mate_warning_is_repaired_by_dropping_it():
    doc, _c1, c2, _b1, _b2 = _component_doc()
    warns = HEALTH.document_warnings(doc, 1000.0)
    assert [w["scope"] for w in warns] == ["mate"]
    rep = HEALTH.repair_warning(doc, warns[0], "auto", 1000.0)
    assert rep["ok"] and "删除" in rep["reason"], rep
    assert doc.mates == []
    assert HEALTH.document_warnings(doc, 1000.0) == []


def test_a_named_selection_keeps_its_other_items():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.named.append({"name": "面组",
                      "items": [("face", "%s:0" % body.id), ("face", "B9:0")]})
    warns = HEALTH.document_warnings(doc, 1000.0)
    assert len(warns) == 1 and warns[0]["scope"] == "named"
    assert HEALTH.repair_warning(doc, warns[0], "auto", 1000.0)["ok"]
    assert doc.named[0]["items"] == [("face", "%s:0" % body.id)]
    assert HEALTH.document_warnings(doc, 1000.0) == []


def test_configuration_and_instance_warnings_are_repaired():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    cfg = doc.add_configuration("默认")
    cfg.suppressed_bodies = [body.id, "B9"]
    cfg.transforms = {"B9": ((1.0, 0, 0, 0), (0, 1.0, 0, 0), (0, 0, 1.0, 0),
                             (0, 0, 0, 1.0))}
    doc.instances.append({"id": "I1", "body_id": "B9", "source": body.id})
    scopes = sorted(w["scope"] for w in HEALTH.document_warnings(doc, 1000.0))
    assert scopes == ["config", "config", "instance"]
    rep = HEALTH.repair_all(doc, 1000.0)
    assert len(rep["fixed"]) == 3 and rep["skipped"] == [], rep
    assert cfg.suppressed_bodies == [body.id]
    assert cfg.transforms == {}
    assert doc.instances == []
    assert HEALTH.document_warnings(doc, 1000.0) == []


def test_repair_all_clears_the_document_and_is_idempotent():
    doc, _c1, _c2, _b1, _b2 = _component_doc()
    sk = _rect_sk(doc, "S9_dim5")
    assert len(HEALTH.document_warnings(doc, 1000.0)) == 2
    rep = HEALTH.repair_all(doc, 1000.0)
    assert len(rep["fixed"]) == 2 and rep["skipped"] == [], rep
    assert HEALTH.document_warnings(doc, 1000.0) == []
    again = HEALTH.repair_all(doc, 1000.0)
    assert again["fixed"] == [] and again["skipped"] == []
    assert isinstance(sk.constraints[5][3], float)


def test_the_repair_command_fixes_the_selected_row():
    _ensure_app()
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    v = _viewer()
    panel = None
    try:
        doc = v.session().kdoc
        sk = _rect_sk(doc, "S9_dim5")
        doc.active_sketch = sk.id
        panel = LeftPanel()
        rows = []
        panel.populate_tree(Session(kdoc=doc, name="R118"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "health" and len(data) > 3:
                rows.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
        assert rows, "no health row"
        v.left.tree.setCurrentItem(rows[0])
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "引用修复" in text and "冻结" in text, text
        assert isinstance(sk.constraints[5][3], float)
        assert HEALTH.document_warnings(doc, 1000.0) == []

        # nothing left to fix
        v.on_command("repair.refs")
        assert "没有悬空引用" in v._prompt.text(), v._prompt.text()
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


def test_the_repair_command_without_a_selection_fixes_everything():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        b2 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
        c1 = doc.add_component("C1", [b1.id])
        c2 = doc.add_component("C2", [b2.id])
        mate, _why = doc.add_mate("rigid", c1.id, c2.id)
        assert mate is not None
        doc.components = [c for c in doc.components if c.id != c2.id]
        _rect_sk(doc, "S9_dim5")
        assert len(HEALTH.document_warnings(doc, 1000.0)) == 2
        v.on_command("repair.refs")
        text = v._prompt.text()
        assert "修好 2 条" in text, text
        assert HEALTH.document_warnings(doc, 1000.0) == []
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-3: health rows locate mates and configurations -----------------------

def _health_rows(v, panel, doc):
    from scdm.document import Session
    rows = []
    panel.populate_tree(Session(kdoc=doc, name="R118"))

    def walk(item):
        data = item.data(0, Qt.UserRole)
        if data and data[0] == "health" and len(data) > 3:
            rows.append(item)
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(panel.tree.topLevelItemCount()):
        walk(panel.tree.topLevelItem(i))
    return rows


def test_double_clicking_a_mate_row_selects_the_component_bodies():
    _ensure_app()
    from scdm.gui.left_panel import LeftPanel

    v = _viewer()
    panel = None
    try:
        doc = v.session().kdoc
        b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        b2 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
        c1 = doc.add_component("C1", [b1.id])
        c2 = doc.add_component("C2", [b2.id])
        doc.add_mate("rigid", c1.id, c2.id)
        doc.components = [c for c in doc.components if c.id != c2.id]
        panel = LeftPanel()
        rows = _health_rows(v, panel, doc)
        assert rows and rows[0].data(0, Qt.UserRole)[1] == "mate"
        v._on_tree_double_click(rows[0])
        # the dangling end is gone, so the mate's *other* end is selected
        assert ("body", b1.id) in v.sel.items, (v.sel.items, b1.id)
        assert "已选中组件" in v._prompt.text(), v._prompt.text()
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


def test_double_clicking_a_config_row_switches_configuration():
    _ensure_app()
    from scdm.gui.left_panel import LeftPanel

    v = _viewer()
    panel = None
    try:
        doc = v.session().kdoc
        body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
        cfg = doc.add_configuration("默认")
        cfg.suppressed_bodies = [body.id, "B9"]
        panel = LeftPanel()
        rows = _health_rows(v, panel, doc)
        config_rows = [r for r in rows
                       if r.data(0, Qt.UserRole)[1] == "config"]
        assert config_rows, "no config row"
        v._on_tree_double_click(config_rows[0])
        assert doc.active_configuration == cfg.id, doc.active_configuration
        assert "配置" in v._prompt.text(), v._prompt.text()
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

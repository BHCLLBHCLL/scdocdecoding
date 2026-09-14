"""R103/A-3 + A-4: the parameter dialog logic and the feature-tree edit entry.

A-3: the two-editor dialog and its Qt-free logic (`feature_lines` /
     `parse_table_lines` / `apply_param_text`) - the dialog is driven
     offscreen, the effects are checked against the closed-form volume.
A-4: the structure tree lists one row per editable feature parameter, and a body
     whose history no longer reproduces its shape gets a tooltip with the
     measured reason instead of editable rows.
"""
from __future__ import annotations

import math
import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import features as FEAT  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm.document import Session  # noqa: E402
from scdm.gui import params as PG  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _doc_with_hole(d_mm=5.0):
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.01), name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.01) < 1e-9][0]
    doc.record_feature(body.id, "hole", selector=FEAT.selector_for(body.shape, top),
                       diameter=d_mm, depth=0.0)
    assert doc.replay_body(body.id)[0]
    return doc, body, 0.02 * 0.02 * 0.01, 0.01


def _hole_v(v0, d_mm, t_m):
    return v0 - math.pi * (d_mm / 2000.0) ** 2 * t_m


def test_feature_lines_lists_rows_and_reason_comments():
    doc, body, _v0, _t = _doc_with_hole()
    lines = PG.feature_lines(doc, 1000.0)
    assert lines[0].startswith("# B1 板：hole")
    assert "B1 0 diameter = 5" in lines and "B1 0 depth = 0" in lines

    # a body whose history no longer matches gets a comment, never a row
    side = [f for f in K.explore(body.shape, "face")
            if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    body.shape = K.hole_simple(body.shape, side, 0.001)
    lines = PG.feature_lines(doc, 1000.0)
    assert any("不可重放" in ln and "不一致" in ln for ln in lines), lines
    assert not any(ln.startswith("B1 0 ") for ln in lines)


def test_param_dialog_round_trips_both_blocks(app):
    from PyQt5.QtTest import QTest
    doc, _body, _v0, _t = _doc_with_hole()
    dlg = PG.ParamDialog(None, "w = 20", PG.feature_lines(doc, 1000.0))
    dlg.set_texts("w = 30", "B1 0 diameter = 8")
    ok_button = dlg.buttons.button(dlg.buttons.Ok)
    QTest.mouseClick(ok_button, Qt.LeftButton)
    assert dlg.result() == dlg.Accepted
    table_text, feat_text = dlg.texts()
    assert table_text == "w = 30" and feat_text == "B1 0 diameter = 8"


def test_apply_param_text_edits_the_feature_to_the_closed_form():
    doc, body, v0, t_m = _doc_with_hole()
    lines = PG.feature_lines(doc, 1000.0)
    feat = [ln.replace("diameter = 5", "diameter = 8") for ln in lines]
    rep = PG.apply_param_text(doc, "width = 20", chr(10).join(feat), 1000.0)
    # every editable row is applied (diameter changed, depth re-applied as-is)
    assert rep["errors"] == [] and len(rep["done"]) == 2 and not rep["failed"]
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 8.0, t_m), rel=1e-6)
    assert "width" in rep["table"].names()
    assert rep["reports"][0]["old"] == 5.0


def test_apply_param_text_rejects_bad_input_without_touching_the_doc():
    doc, body, v0, t_m = _doc_with_hole()
    before = K.volume(body.shape)

    rep = PG.apply_param_text(doc, "width = ", "B1 0 diameter = 8", 1000.0)
    assert rep["errors"] and "参数表" in rep["errors"][0]
    assert K.volume(body.shape) == pytest.approx(before, rel=1e-12)
    assert doc.feature_stack(body.id).features[0].params["diameter"] == 5.0

    rep = PG.apply_param_text(doc, "width = 20", "B1 0 diameter", 1000.0)
    assert rep["errors"] and "缺 '='" in rep["errors"][0]
    assert K.volume(body.shape) == pytest.approx(before, rel=1e-12)
    assert doc.feature_stack(body.id).features[0].params["diameter"] == 5.0


def test_apply_single_edit_matches_the_closed_form():
    doc, body, v0, t_m = _doc_with_hole()
    rep = PG.apply_single_edit(doc, body.id, 0, "diameter", 6.5, 1000.0)
    assert rep["ok"], rep["reason"]
    assert K.volume(body.shape) == pytest.approx(_hole_v(v0, 6.5, t_m), rel=1e-6)


def _payloads(tree):
    out = []

    def walk(item):
        data = item.data(0, Qt.UserRole)
        if data:
            out.append((data, item.toolTip(0)))
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(i))
    return out


def test_replay_verdict_is_memoised_but_never_stale(monkeypatch):
    """R103: the tree asks for the verdict on every rebuild, so `can_replay`
    memoises it - a changed parameter or a changed shape must recompute."""
    import scdm.kdoc as KD
    doc, body, _v0, _t = _doc_with_hole()
    calls = {"n": 0}
    real = FEAT.replay_mismatch

    def counting(a, b):
        calls["n"] += 1
        return real(a, b)

    monkeypatch.setattr(KD, "replay_mismatch", counting)
    assert doc.can_replay(body.id)[0] is True
    assert calls["n"] == 1
    for _ in range(5):
        assert doc.can_replay(body.id)[0] is True
    assert calls["n"] == 1                       # served from the memo

    assert doc.edit_feature(body.id, 0, "diameter", 8.0)["ok"]
    calls["n"] = 0
    assert doc.can_replay(body.id)[0] is True
    assert calls["n"] == 1                       # parameters changed -> recompute

    side = [f for f in K.explore(body.shape, "face")
            if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    body.shape = K.hole_simple(body.shape, side, 0.001)
    calls["n"] = 0
    ok, why = doc.can_replay(body.id)
    assert ok is False and "不一致" in why
    assert calls["n"] == 1                       # shape changed -> recompute

def test_tree_lists_feature_parameters_and_marks_unreplayable_bodies(app):
    from scdm.gui.left_panel import LeftPanel
    doc, body, _v0, _t = _doc_with_hole()
    panel = LeftPanel()
    panel.populate_tree(Session(kdoc=doc, name="T"))
    rows = [d for d, _tip in _payloads(panel.tree) if d and d[0] == "feature_param"]
    assert rows == [("feature_param", "B1", 0, "diameter"),
                    ("feature_param", "B1", 0, "depth")], rows
    feat_rows = [x for x in _payloads(panel.tree) if x[0] and x[0][0] == "feature_param"]
    assert feat_rows and "双击修改" in feat_rows[0][1]

    # break the history: the feature node explains why, and offers no rows
    side = [f for f in K.explore(body.shape, "face")
            if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    body.shape = K.hole_simple(body.shape, side, 0.001)
    panel.populate_tree(Session(kdoc=doc, name="T"))
    items = _payloads(panel.tree)
    assert not [d for d, _tip in items if d and d[0] == "feature_param"]
    feat = [x for x in items if x[0] and x[0][0] == "feature"]
    assert feat and "不可重放" in feat[0][1] and "不一致" in feat[0][1]

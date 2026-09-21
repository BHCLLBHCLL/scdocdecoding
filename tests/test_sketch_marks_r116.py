"""R116 A-1 + A-2 + A-5: typed conflict marks, a whole-document reference check,
and an along-curve pattern that takes several curves and a start offset.

A-1: every mark says *what kind* of constraint it is and whether it is violated
     (conflict) or merely repeated (redundant), so the viewport can colour the two
     apart and the text can say "尺寸 #5" instead of "#5".
A-2: `document_warnings()` walks dimensions, mates, named selections, groups,
     configurations and placed instances and reports every id that no longer
     exists; opening a project summarises them.
A-5: `path_points()` chains several sketch curves into one path (in any order)
     and `pattern_curves(..., offset=)` starts the pattern further along it.
"""
from __future__ import annotations

import math
import os
import tempfile

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import health as HEALTH  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.io_project import save_scdm  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _rect_cons():
    return [(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
            (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
            (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008)]


def _doc_rect():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0], [0.010, 0.008],
                               [0.0, 0.008]]))
    sk.constraints.extend(_rect_cons())
    return doc, sk


def _viewer(path=None):
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _corner_path():
    """Two lines meeting at a right angle: (0,0)->(10,0)->(10,10)mm, out of order."""
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.010, 0.0, 0.0), (0.010, 0.010, 0.0)))
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.010, 0.0, 0.0)))
    return doc, sk


# --- A-1: typed marks -------------------------------------------------------

def test_marks_carry_kind_and_state():
    doc, sk = _doc_rect()
    sk.constraints.append((S.DIST, 0, 1, 0.012))          # 10mm vs 12mm
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert [m["index"] for m in geo["marks"]] == [5, 7]
    assert {m["kind"] for m in geo["marks"]} == {"dist"}
    assert {m["state"] for m in geo["marks"]} == {"conflict"}
    assert {m["label"] for m in geo["marks"]} == {"尺寸"}
    assert SKM.conflict_labels(doc, sk.id, 1000.0) == ["尺寸#5 冲突",
                                                       "尺寸#7 冲突"]


def test_a_repeated_row_is_marked_redundant():
    doc, sk = _doc_rect()
    sk.constraints.append((S.DIST, 0, 1, 0.010))          # the same again
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    assert [m["index"] for m in geo["marks"]] == [7]
    assert geo["marks"][0]["state"] == "redundant"
    assert SKM.conflict_labels(doc, sk.id, 1000.0) == ["尺寸#7 冗余"]


def test_marks_name_each_constraint_kind():
    doc, sk = _doc_rect()
    sk.constraints.append((S.VERTICAL, 0, 1))             # h + v on one edge
    labels = SKM.conflict_labels(doc, sk.id, 1000.0)
    assert any(x.startswith("水平#1") for x in labels), labels
    assert any(x.startswith("竖直#7") for x in labels), labels
    assert any(x.startswith("尺寸#5") for x in labels), labels


def test_each_mark_carries_its_own_geometry():
    doc, sk = _doc_rect()
    sk.constraints.append((S.DIST, 0, 1, 0.012))
    geo = SKM.conflict_geometry(doc, sk.id, 1000.0)
    for m in geo["marks"]:
        assert m["points"] == [[0.0, 0.0], [0.010, 0.0]]
        assert m["segments"] == [[[0.0, 0.0], [0.010, 0.0]]]
    # the aggregate is exactly the union of the marks
    assert geo["points"] == [[0.0, 0.0], [0.010, 0.0]]
    assert geo["segments"] == [[[0.0, 0.0], [0.010, 0.0]]]
    assert geo["cons"] == [m["index"] for m in geo["marks"]]


def test_the_chip_and_the_labels_agree():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                                   [0.010, 0.008], [0.0, 0.008]]))
        sk.constraints.extend(_rect_cons())
        sk.constraints.append((S.DIST, 0, 1, 0.012))
        v._refresh_sketch_dof()
        chip = v._mode_chip.text()
        labels = SKM.conflict_labels(v.session().kdoc, sk.id, v.session().scale)
        assert "#5" in chip and "#7" in chip, chip
        assert all(("#%d" % m) in chip for m in (5, 7)), (chip, labels)
        assert labels == ["尺寸#5 冲突", "尺寸#7 冲突"], labels
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-2: the whole-document reference check --------------------------------

def test_a_clean_document_has_no_warnings():
    doc, _sk = _doc_rect()
    assert HEALTH.document_warnings(doc, 1000.0) == []
    assert HEALTH.warning_summary([]) == ""


def test_a_mate_to_a_deleted_component_is_reported():
    doc = KernelDoc()
    b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    b2 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    c1 = doc.add_component("C1", [b1.id])
    c2 = doc.add_component("C2", [b2.id])
    mate, why = doc.add_mate("rigid", c1.id, c2.id)
    assert mate is not None and why == ""
    # while both components exist the mate is fine ...
    assert [w for w in HEALTH.document_warnings(doc, 1000.0)
            if w["scope"] == "mate"] == []
    doc.components = [c for c in doc.components if c.id != c2.id]
    warns = HEALTH.document_warnings(doc, 1000.0)
    mate = [w for w in warns if w["scope"] == "mate"]
    assert mate and c2.id in mate[0]["reason"], warns


def test_a_named_selection_on_a_deleted_body_is_reported():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.named.append({"name": "上表面", "items": [("face", "%s:0" % body.id)]})
    doc.groups.append({"name": "组1", "items": [("body", body.id)]})
    assert HEALTH.document_warnings(doc, 1000.0) == []
    doc.remove(body.id)
    warns = HEALTH.document_warnings(doc, 1000.0)
    scopes = {w["scope"] for w in warns}
    assert scopes == {"named", "group"}, warns
    assert all("上表面" in w["reason"] or "组1" in w["reason"] for w in warns)


def test_a_configuration_pointer_is_reported():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    comp = doc.add_component("C1", [body.id])
    cfg = doc.add_configuration("默认")
    cfg.hidden_components = [comp.id]
    cfg.suppressed_bodies = [body.id]
    cfg.transforms = {comp.id: ((1.0, 0, 0, 0), (0, 1.0, 0, 0),
                                (0, 0, 1.0, 0), (0, 0, 0, 1.0))}
    cfg.properties = {body.id: {"material": "钢"}}
    assert [w for w in HEALTH.document_warnings(doc, 1000.0)
            if w["scope"] == "config"] == []
    doc.remove(body.id)
    doc.components = []
    warns = [w for w in HEALTH.document_warnings(doc, 1000.0)
             if w["scope"] == "config"]
    assert len(warns) == 4, warns
    assert {w["extra"] for w in warns} == {"hidden", "suppressed", "transform",
                                           "properties"}


def test_the_summary_names_the_scopes():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    doc.named.append({"name": "面组", "items": [("face", "%s:0" % body.id)]})
    doc.remove(body.id)
    text = HEALTH.warning_summary(HEALTH.document_warnings(doc, 1000.0))
    assert "引用悬空" in text and "命名选择" in text, text


def test_opening_a_project_with_a_mate_warning_reports_it():
    doc = KernelDoc()
    b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="A")
    b2 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    c1 = doc.add_component("C1", [b1.id])
    c2 = doc.add_component("C2", [b2.id])
    mate, _why = doc.add_mate("rigid", c1.id, c2.id)
    assert mate is not None
    doc.components = [c for c in doc.components if c.id != c2.id]
    path = os.path.join(tempfile.mkdtemp(), "mate.scdm")
    save_scdm(path, doc)
    v = _viewer(path)
    try:
        text = v._prompt.text()
        assert "引用悬空" in text and "配合" in text, text
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-5: multi-curve paths and the start offset ----------------------------

def test_a_multi_segment_path_is_chained_in_any_order():
    doc, sk = _corner_path()
    chain, why = S.path_points(sk, [0, 1])
    assert chain is not None, why
    assert len(chain) == 3
    assert {tuple(round(v, 6) for v in p) for p in chain} == {
        (0.0, 0.0), (0.010, 0.0), (0.010, 0.010)}
    single, _why = S.path_points(sk, 1)
    assert single == [(0.0, 0.0), (0.010, 0.0)]


def test_a_gap_in_the_path_is_refused():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.010, 0.0, 0.0)))
    sk.curves.append(("line", (0.020, 0.0, 0.0), (0.030, 0.0, 0.0)))
    chain, why = S.path_points(sk, [0, 1])
    assert chain is None and "不连续" in why, why
    assert S.path_points(sk, [0, 9])[1].startswith("路径曲线序号无效")


def test_instances_follow_a_corner():
    doc, sk = _corner_path()
    # selecting the curve that starts at the origin first fixes the direction
    chain, why = S.path_points(sk, [1, 0])
    assert chain[0] == (0.0, 0.0), (chain, why)
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.002, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="along", path=chain)
    assert rep["ok"] and rep["path_length"] == pytest.approx(0.020, rel=1e-12)
    copies = [c for c in sk.curves if c[0] == "poly"]
    assert len(copies) == 2
    # The rect sits at the path start and the chain starts there too (the first
    # selected curve is listed first), so the copies land on the corner (10,0) and
    # on the far end (10,10) - and the 90-degree turn shows up as two directions.
    anchors = {(round(float(c[1][0][0]), 9), round(float(c[1][0][1]), 9))
               for c in copies}
    assert anchors == {(0.010, 0.0), (0.010, 0.010)}, anchors
    angles = set()
    for c in copies:
        a0, a1 = c[1][0], c[1][1]
        angles.add(round(math.degrees(math.atan2(float(a1[1]) - float(a0[1]),
                                                 float(a1[0]) - float(a0[0]))),
                         6) % 180.0)
    assert sorted(angles) == [0.0, 90.0], angles


def test_the_start_offset_moves_the_instances():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.003, 0.0)))
    rep = S.pattern_curves(sk, 3, mode="along",
                           path=[(0.0, 0.0), (0.020, 0.0)], offset=0.005)
    assert rep["ok"] and rep["offset"] == pytest.approx(0.005)
    assert rep["step"] == pytest.approx(0.0075, rel=1e-12)
    xs = sorted(float(c[1][0][0]) for c in sk.curves if c[0] == "poly")
    assert xs == [pytest.approx(0.0125, abs=1e-12), pytest.approx(0.020, abs=1e-12)]
    assert S.pattern_curves(sk, 3, mode="along", path=[(0.0, 0.0), (0.020, 0.0)],
                            offset=-1.0)["reason"] == "起点偏移不能为负"
    bad = S.pattern_curves(sk, 3, mode="along", path=[(0.0, 0.0), (0.020, 0.0)],
                           offset=0.020)
    assert bad["ok"] is False and "超出路径长度" in bad["reason"]


def test_the_op_takes_a_path_list_and_an_offset():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.010, 0.0, 0.0), (0.010, 0.010, 0.0)))
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.010, 0.0, 0.0)))
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.002, 0.0)))
    _b, msg = SCR.OPS["sketch.pattern"](doc, {"count": 3, "mode": "along",
                                              "path_index": [0, 1],
                                              "offset_mm": 5.0}, 1000.0)
    assert "沿曲线" in msg and "×3" in msg, msg
    with pytest.raises(ValueError) as err:
        SCR.OPS["sketch.pattern"](doc, {"count": 3, "mode": "along",
                                        "path_index": [0, 2]}, 1000.0)
    assert "不连续" in str(err.value) or "序号无效" in str(err.value)


def test_the_gui_patterns_along_several_selected_curves():
    v = _viewer()
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("line", (0.030, 0.0, 0.0), (0.040, 0.0, 0.0)))
        sk.curves.append(("line", (0.040, 0.0, 0.0), (0.040, 0.010, 0.0)))
        sk.curves.append(("rect", (0.030, 0.0, 0.0), (0.032, 0.002, 0.0)))
        v.left.show_options("sketch.pattern")
        v.left.set_checked("sketch.pattern", 1, True)
        page = v.left._opt_pages["sketch.pattern"]
        page[3][0].setValue(3)
        page[2][5].setValue(2.0)                     # 起点偏移 2mm
        assert v._select_sketch_entity([0.035, 0.0002]) is not None
        v._select_sketch_entity([0.0402, 0.005], add=True)
        assert len(v.sketch_selection) == 2
        v.on_command("sketch.pattern")
        text = v._prompt.text()
        assert "沿曲线" in text, text
        assert "+" in text                                   # both curves named
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

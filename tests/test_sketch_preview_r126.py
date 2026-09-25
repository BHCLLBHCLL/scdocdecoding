"""R126 A-4 + A-11: a dimension change is previewed before it is committed, and a
retarget target can be picked from the document (one per selected row).

A-4:  `preview_dimension` solves a *copy* of the sketch and builds the prospective
      solid with the same feature code a replay uses, so the preview cannot drift
      from the real drive - and cancelling is "do nothing", which is why the
      status can promise the volume has not moved.
A-11: `target_options` lists what this document can be pointed at (a sketch, one
      of its dimensions, a parameter), the option page lists them in a picker that
      writes the radio group and the field, and ";" gives one target per selected
      row in selection order.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import health as HEALTH  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.params import ParamTable  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BOX = os.path.join(_ROOT, "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _ensure_app():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    return _APP


def _viewer(path=None):
    _ensure_app()
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _mm3(w, h, t):
    return w * h * t * 1e-9


def _rect(sk, u0=0.0, width=0.020, height=0.008, width_dim=None):
    sk.curves.append(("poly", [[u0, 0.0], [u0 + width, 0.0],
                               [u0 + width, height], [u0, height]]))
    sk.constraints.extend([
        (S.FIXED, 0, u0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, width_dim if width_dim is not None else width),
        (S.DIST, 1, 2, height)])


def _document(t_mm=5.0):
    """A 20x8mm plate plus a second sketch, and a parameter table."""
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = doc.add_sketch("xy")
    _rect(sk, 0.0, 0.020, 0.008)
    rep = SKM.extrude_active(doc, t_mm, 1000.0)     # one sketch: no ambiguity
    assert rep["ok"], rep["reason"]
    other = doc.add_sketch("xy")
    _rect(other, 0.040, 0.010, 0.008)
    return doc, sk, other, rep["bodies"][0]


def _dangling_document():
    """Two dangling rows on S1 (the width and the height) and a live S2."""
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = doc.add_sketch("xy")
    _rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")
    sk.constraints[6] = (S.DIST, 1, 2, "S9_dim6")          # height dangling too
    other = doc.add_sketch("xy")
    _rect(other, 0.040, 0.010, 0.008)
    return doc, sk, other


# --- A-4: the preview --------------------------------------------------------

def test_the_preview_does_not_touch_the_document():
    doc, sk, _other, body = _document()
    before = K.volume(body.shape)
    rep = SKM.preview_dimension(doc, sk.id, 5, 10.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert rep["before"] == pytest.approx(before)
    assert rep["after"] == pytest.approx(_mm3(10, 8, 5), rel=1e-6)
    assert len(rep["bodies"]) == 1 and rep["bodies"][0]["body"] == body.id
    # the copy is what was solved: the document is exactly where it was
    assert K.volume(body.shape) == pytest.approx(before)
    assert sk.constraints[5][3] == 0.020


def test_a_bad_value_is_refused_before_anything_moves():
    doc, sk, _other, body = _document()
    before = K.volume(body.shape)
    rep = SKM.preview_dimension(doc, sk.id, 5, "2*nope", 1000.0)
    assert rep["ok"] is False and "未知参数" in rep["reason"], rep
    assert rep["bodies"] == [] and rep["after"] == 0.0      # no shape on refusal
    assert K.volume(body.shape) == pytest.approx(before)
    assert sk.constraints[5][3] == 0.020


def test_the_preview_is_what_the_commit_produces():
    doc, sk, _other, body = _document()
    rep = SKM.preview_dimension(doc, sk.id, 5, 10.0, 1000.0)
    assert rep["ok"] and rep["value_mm"] == pytest.approx(10.0)
    assert SKM.set_dimension(doc, sk.id, 5, 10.0, 1000.0)["ok"]
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(rep["after"], rel=1e-6)


def test_a_vanished_loop_is_refused_in_the_preview():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    _rect(sk, 0.0, 0.020, 0.008)                     # loop 1, fully constrained
    sk.curves.append(("poly", [[0.040, 0.0], [0.050, 0.0],   # loop 2, no rows
                               [0.050, 0.008], [0.040, 0.008]]))
    rep0 = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep0["ok"] and len(rep0["bodies"]) == 2, rep0
    sk.curves = [c for c in sk.curves                 # the second loop is gone
                 if c[0] != "poly" or c[1][0][0] < 0.02]
    rep = SKM.preview_dimension(doc, sk.id, 5, 10.0, 1000.0)
    assert rep["ok"] is False and "闭环已不存在" in rep["reason"], rep


# --- A-4: the command --------------------------------------------------------

def test_the_gui_previews_then_cancels():
    v = _viewer()
    try:
        doc = v.session().kdoc
        sk = doc.add_sketch("xy")
        _rect(sk, 0.0, 0.020, 0.008)
        rep = SKM.extrude_active(doc, 5.0, 1000.0)
        body = rep["bodies"][0]
        before = K.volume(body.shape)
        got = v.preview_sketch_dimension(sk.id, 5, 10.0)
        assert got["ok"], got["reason"]
        assert v.dim_preview is not None
        assert "预览" in v._prompt.text() and "未提交" in v._prompt.text()
        assert K.volume(body.shape) == pytest.approx(before)
        v.cancel_sketch_dimension()
        assert v.dim_preview is None and "已取消" in v._prompt.text()
        assert K.volume(body.shape) == pytest.approx(before)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_committing_the_preview_moves_the_body():
    v = _viewer()
    try:
        doc = v.session().kdoc
        sk = doc.add_sketch("xy")
        _rect(sk, 0.0, 0.020, 0.008)
        rep = SKM.extrude_active(doc, 5.0, 1000.0)
        body = rep["bodies"][0]
        v.preview_sketch_dimension(sk.id, 5, 10.0)
        out = v.commit_sketch_dimension()
        assert out["ok"], out["reason"]
        assert v.dim_preview is None
        assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-6)
        assert "尺寸 10mm" in v._prompt.text() and "重建 1 个实体" in v._prompt.text()
        assert sk.constraints[5][3] == pytest.approx(0.010)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_drive_dialog_commits_only_when_confirmed():
    v = _viewer()
    try:
        doc = v.session().kdoc
        sk = doc.add_sketch("xy")
        _rect(sk, 0.0, 0.020, 0.008)
        rep = SKM.extrude_active(doc, 5.0, 1000.0)
        body = rep["bodies"][0]
        before = K.volume(body.shape)
        asked = {"n": 0}
        v._ask_text = lambda *a, **k: "10"
        v._confirm = lambda *a, **k: (asked.__setitem__("n", asked["n"] + 1)
                                      and False)
        v._edit_sketch_dimension(sk.id, 5)
        assert asked["n"] == 1, "the dialog did not ask before committing"
        assert K.volume(body.shape) == pytest.approx(before)
        v._confirm = lambda *a, **k: True
        v._edit_sketch_dimension(sk.id, 5)
        assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-6)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-11: picking the target from the document -----------------------------

def test_the_document_lists_the_targets_it_offers():
    doc, sk, other, _body = _document()
    got = SKM.target_options(doc, 1000.0)
    tos = [e["to"] for e in got]
    assert sk.id in tos and other.id in tos
    assert "param:d" in tos
    assert "%s_dim5" % other.id in tos
    by_to = {e["to"]: e for e in got}
    assert by_to["param:d"]["radio"] == 1 and by_to["param:d"]["text"] == "d"
    assert by_to["%s_dim5" % other.id]["radio"] == 0
    assert "10mm" in by_to["%s_dim5" % other.id]["label"]
    assert "5mm" in by_to["param:d"]["label"]


def test_a_dimension_name_and_a_pair_are_targets():
    doc, _sk, other = _dangling_document()
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    assert warn["id"].endswith("#5"), warn
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0,
                                to="%s_dim5" % other.id)
    assert rep["ok"], rep["reason"]
    assert doc.sketches[0].constraints[5][3] == "%s_dim5" % other.id

    doc2, _sk2, other2 = _dangling_document()
    warn2 = HEALTH.document_warnings(doc2, 1000.0)[0]
    rep2 = HEALTH.repair_warning(doc2, warn2, "retarget", 1000.0,
                                 to=(other2.id, 5))
    assert rep2["ok"], rep2["reason"]
    assert doc2.sketches[0].constraints[5][3] == "%s_dim5" % other2.id


def test_the_picker_writes_the_choice_and_the_field():
    v = _viewer()
    try:
        doc = v.session().kdoc
        _rect(doc.add_sketch("xy"), 0.0, 0.020, 0.008)
        v._sync_repair_targets()
        n = v.left.target_count("repair.refs", 0)
        assert n == v.repair_targets and n >= 2, (n, v.repair_targets)
        assert v.left.target_label("repair.refs", 0).startswith("（")
        v.left.set_target_index("repair.refs", 0, 1)         # first real entry
        assert v.left.choice_value("repair.refs", 0) == 0
        assert v.left.text_value("repair.refs", 0) == "S1"
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_picker_is_what_the_repair_uses():
    v = _viewer()
    try:
        doc = v.session().kdoc
        sk = doc.add_sketch("xy")
        _rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")     # dangling
        _rect(doc.add_sketch("xy"), 0.040, 0.010, 0.008)      # S2: 10mm
        v._sync_repair_targets()
        # pick "S2_dim5" out of the document's own list
        entries = SKM.target_options(doc, v.session().scale)
        which = [i for i, e in enumerate(entries) if e["to"] == "S2_dim5"][0]
        v.left.set_target_index("repair.refs", 0, which + 1)
        assert v.left.text_value("repair.refs", 0) == "S2_dim5"
        v.left.set_checked("repair.refs", 1, True)            # 尺寸改指向
        v.on_command("repair.refs")
        assert sk.constraints[5][3] == "S2_dim5", sk.constraints[5]
        assert HEALTH.document_warnings(doc, v.session().scale) == []
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_row_by_row_targets_follow_the_selection():
    v = _viewer()
    try:
        doc = v.session().kdoc
        doc.param_table = ParamTable()
        doc.param_table.set("d", "5")
        sk = doc.add_sketch("xy")
        _rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")
        sk.constraints[6] = (S.DIST, 1, 2, "S9_dim6")
        _rect(doc.add_sketch("xy"), 0.040, 0.010, 0.008)
        v._refresh_sketch_dof()
        v._rebuild()
        rows = [it for it in _iter_items(v.left.tree)
                if _health_payload(it) is not None]
        assert len(rows) == 2, [it.text(0) for it in rows]
        for it in rows:
            it.setSelected(True)
        ids = v._selected_health_ids()
        assert len(ids) == 2, ids
        v.left.set_checked("repair.refs", 1, True)
        v.left.set_text("repair.refs", 0, "S2_dim5; param:d")
        v.on_command("repair.refs")
        first, second = rows[0], rows[1]
        assert sk.constraints[5][3] == "S2_dim5", sk.constraints[5]
        assert sk.constraints[6][3] == "d", sk.constraints[6]
        assert "逐行" in v._prompt.text(), v._prompt.text()
        assert first is not second
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_row_by_row_targets_refuse_a_mismatch():
    v = _viewer()
    try:
        doc = v.session().kdoc
        doc.param_table = ParamTable()
        doc.param_table.set("d", "5")
        sk = doc.add_sketch("xy")
        _rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")
        _rect(doc.add_sketch("xy"), 0.040, 0.010, 0.008)
        v.left.set_checked("repair.refs", 1, True)
        v.left.set_text("repair.refs", 0, "S2_dim5; param:d")   # two targets
        v.on_command("repair.refs")                              # nothing selected
        assert "逐行目标需要与选中条目一一对应" in v._prompt.text(), v._prompt.text()
        assert sk.constraints[5][3] == "S9_dim5"
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def _iter_items(tree):
    """Every item in the structure tree, depth first."""
    def walk(item):
        yield item
        for i in range(item.childCount()):
            yield from walk(item.child(i))
    for i in range(tree.topLevelItemCount()):
        yield from walk(tree.topLevelItem(i))


def _health_payload(item):
    """A health *row* (the parent node carries a payload too, without a warning)."""
    data = item.data(0, Qt.UserRole)
    if data and data[0] == "health" and len(data) > 3 \
            and isinstance(data[3], dict) and data[3].get("scope"):
        return data
    return None

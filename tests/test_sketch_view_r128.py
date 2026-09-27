"""R128 A-16 + A-17 + A-18: the point size is a remembered view setting, one row
gets one picker, and redo comes back after an undo.

A-16: the sketch page's 点大小 is stored with the view (QSettings), applied to the
      scene the moment it moves, and read back when the window is built again.
A-17: the per-row pickers appear for *any* selection, one row included, so
      "which row does this target belong to" never depends on the count.
A-18: undo goes back to the preview's "before" and redo returns to the committed
      state; a pending preview is dropped by either (it describes a state we left).
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.params import ParamTable  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402
QSettings = pytest.importorskip("PyQt5.QtCore").QSettings  # noqa: E402

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


def _plate(v):
    doc = v.session().kdoc
    sk = doc.add_sketch("xy")
    _rect(sk, 0.0, 0.020, 0.008)
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep["ok"], rep["reason"]
    return doc, sk, rep["bodies"][0]


def _one_dangling_row(v):
    doc = v.session().kdoc
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = doc.add_sketch("xy")
    _rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")
    other = doc.add_sketch("xy")
    _rect(other, 0.040, 0.010, 0.008)
    v._refresh_sketch_dof()
    v._rebuild()
    rows = []
    for it in _items(v.left.tree):
        data = it.data(0, Qt.UserRole)
        if data and data[0] == "health" and len(data) > 3 \
                and isinstance(data[3], dict) and data[3].get("scope"):
            rows.append(it)
    assert len(rows) == 1, [r.text(0) for r in rows]
    rows[0].setSelected(True)
    v.left.show_options("repair.refs")
    return doc, sk, other, rows[0]


def _items(tree):
    def walk(item):
        yield item
        for i in range(item.childCount()):
            yield from walk(item.child(i))
    for i in range(tree.topLevelItemCount()):
        yield from walk(tree.topLevelItem(i))


# --- A-16: the point size is remembered --------------------------------------

def test_moving_the_point_size_is_announced_and_stored():
    v = _viewer()
    settings = QSettings("scdocdecoding", "scdm")
    old = settings.value("view/point_scale", None)
    try:
        seen = []
        v.left.option_changed.connect(lambda c, i: seen.append((c, i)))
        v.left.show_options("mode.sketch")
        v.left._opt_pages["mode.sketch"][2][0].setValue(2.5)
        assert ("mode.sketch", 0) in seen, seen
        assert float(settings.value("view/point_scale")) == 2.5
        assert v._apply_point_scale() == 2.5
    finally:
        if old is None:
            settings.remove("view/point_scale")
        else:
            settings.setValue("view/point_scale", old)
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_point_size_comes_back_with_the_window():
    settings = QSettings("scdocdecoding", "scdm")
    old = settings.value("view/point_scale", None)
    settings.setValue("view/point_scale", 3.0)
    try:
        v = _viewer()
        try:
            assert v.left.spin_value("mode.sketch", 0) == 3.0
        finally:
            try:
                v.close()
            except RuntimeError:
                pass
    finally:
        if old is None:
            settings.remove("view/point_scale")
        else:
            settings.setValue("view/point_scale", old)


# --- A-17: one row, one picker ----------------------------------------------

def test_a_single_selected_row_gets_its_own_picker():
    v = _viewer()
    try:
        _doc, sk, other, _row = _one_dangling_row(v)
        v._sync_repair_targets()
        assert len(v.left.row_target_boxes("repair.refs", 0)) == 1
        entries = SKM.target_options(v.session().kdoc, v.session().scale)
        which = [i for i, e in enumerate(entries)
                 if e["to"] == "%s_dim5" % other.id][0]
        v.left.set_row_target_index("repair.refs", 0, 0, which + 1)
        assert v.left.row_targets("repair.refs", 0) == ["%s_dim5" % other.id]
        v.left.set_checked("repair.refs", 1, True)
        v.on_command("repair.refs")
        assert sk.constraints[5][3] == "%s_dim5" % other.id, sk.constraints[5]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-18: undo, then redo ---------------------------------------------------

def test_undo_then_redo_lands_on_both_sides_of_the_commit():
    v = _viewer()
    try:
        doc, sk, body = _plate(v)
        before = K.volume(body.shape)
        rep = v.preview_sketch_dimension(sk.id, 5, 10.0)
        assert rep["ok"], rep["reason"]
        assert v.commit_sketch_dimension()["ok"]
        after = K.volume(body.shape)
        assert after == pytest.approx(_mm3(10, 8, 5), rel=1e-6)
        # a restore replaces the body objects, so read through the document
        def volume():
            return K.volume(doc.body_by_id(body.id).shape)

        v.on_command("edit.undo")
        assert "已撤销" in v._prompt.text(), v._prompt.text()
        assert volume() == pytest.approx(before, rel=1e-9)
        assert v.dim_preview is None
        v.on_command("edit.redo")
        assert "已重做" in v._prompt.text(), v._prompt.text()
        assert volume() == pytest.approx(after, rel=1e-9)
        assert v.dim_preview is None
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_an_undo_drops_a_pending_preview():
    v = _viewer()
    try:
        doc, sk, body = _plate(v)
        before = K.volume(body.shape)
        assert v.preview_sketch_dimension(sk.id, 5, 10.0)["ok"]
        assert v.dim_preview is not None
        v._push_undo()                       # something to undo to
        v.on_command("edit.undo")
        assert v.dim_preview is None, "预览跟着旧状态留下来了"
        assert "已撤销" in v._prompt.text()
        assert before > 0 and body.id
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

"""R127 A-13 + A-15 + A-8 + A-14: the preview shows every body and can be taken
back, the point markers have one size table, and a per-row target is picked.

A-13/A-15: a dimension change can move several bodies; every one of them is
      previewed (one translucent actor each) and the status names the count, and
      the commit puts the pre-drive state on the history so one undo lands back
      exactly on the "before" the preview promised.
A-8:  the pixel size of a point marker lives in one table (Scene.POINT_SIZES) and
      is scaled by the sketch page's 点大小, so a marker cannot be 16 here and 8
      there for no reason.
A-14: with several health rows selected each row gets its own picker; a row left
      on 「跟随上面的目标」 keeps the single target.
"""
from __future__ import annotations

import os
import re

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.params import ParamTable  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BOX = os.path.join(_ROOT, "box.scdoc")
_SCENE = os.path.join(_ROOT, "scdm", "gui", "scene.py")
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


def _constrained_rect(sk, u0=0.0, width=0.020, height=0.008, width_dim=None):
    """A fully constrained rectangle - the first loop of a sketch."""
    sk.curves.append(("poly", [[u0, 0.0], [u0 + width, 0.0],
                               [u0 + width, height], [u0, height]]))
    sk.constraints.extend([
        (S.FIXED, 0, u0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, width_dim if width_dim is not None else width),
        (S.DIST, 1, 2, height)])


def _free_rect(sk, u0, width, height=0.008):
    """A second profile with no rows of its own (a body without constraints)."""
    sk.curves.append(("poly", [[u0, 0.0], [u0 + width, 0.0],
                               [u0 + width, height], [u0, height]]))


def _two_loop_document(v, t_mm=5.0):
    doc = v.session().kdoc
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = doc.add_sketch("xy")
    _constrained_rect(sk, 0.0, 0.020, 0.008)
    _free_rect(sk, 0.040, 0.010)
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"] and len(rep["bodies"]) == 2, rep
    return doc, sk, rep["bodies"]


def _items(tree):
    def walk(item):
        yield item
        for i in range(item.childCount()):
            yield from walk(item.child(i))
    for i in range(tree.topLevelItemCount()):
        yield from walk(tree.topLevelItem(i))


def _health_rows(tree):
    out = []
    for it in _items(tree):
        data = it.data(0, Qt.UserRole)
        if data and data[0] == "health" and len(data) > 3 \
                and isinstance(data[3], dict) and data[3].get("scope"):
            out.append(it)
    return out


class _NoWindow:
    """render() only needs something to call Render() on."""

    def Render(self):
        return None


class _FakeRenderer:
    def __init__(self):
        self.actors = []

    def AddActor(self, a):
        self.actors.append(a)

    def RemoveActor(self, a):
        self.actors.remove(a)

    def GetRenderWindow(self):
        return _NoWindow()


def _bare_scene():
    """A Scene without a GL context: the marker paths do not need one."""
    from scdm.gui.scene import Scene
    sc = Scene.__new__(Scene)
    sc.renderer = _FakeRenderer()
    sc._anchor_actors = []
    sc._preview_actors = []
    sc._preview_actor = None
    sc._preview_hidden = []
    sc._point_scale = 1.0
    sc._origin_actor = None
    sc._grid_actor = None
    return sc


# --- A-13 + A-15: every body, and one step back ------------------------------

def test_the_preview_covers_every_body_the_sketch_builds():
    v = _viewer()
    try:
        doc, sk, bodies = _two_loop_document(v)
        before = sum(K.volume(b.shape) for b in bodies)
        rep = v.preview_sketch_dimension(sk.id, 5, 10.0)
        assert rep["ok"], rep["reason"]
        assert len(rep["bodies"]) == 2, rep["bodies"]
        assert [b["body"] for b in rep["bodies"]] == [b.id for b in bodies]
        # the driven loop shrinks, the free one does not: the total is the sum
        assert rep["after"] == pytest.approx(_mm3(10, 8, 5) + _mm3(10, 8, 5),
                                             rel=1e-6)
        assert rep["before"] == pytest.approx(before, rel=1e-6)
        assert "2 个实体" in v._prompt.text(), v._prompt.text()
        assert sum(K.volume(b.shape) for b in bodies) == pytest.approx(before)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_scene_draws_one_actor_per_previewed_body():
    doc_sk = None
    from scdm.kernel import make_box
    sc = _bare_scene()
    n = sc.show_previews([make_box(0.01, 0.01, 0.01),
                          make_box(0.02, 0.02, 0.02)])
    assert n == 2, n
    assert len(sc._preview_actors) == 2
    assert doc_sk is None
    sc.clear_preview()
    assert sc._preview_actors == [] and sc.renderer.actors == []


def test_one_undo_goes_back_to_what_the_preview_promised():
    v = _viewer()
    try:
        doc, sk, bodies = _two_loop_document(v)
        before = [K.volume(b.shape) for b in bodies]
        rep = v.preview_sketch_dimension(sk.id, 5, 10.0)
        assert rep["ok"]
        assert v.commit_sketch_dimension()["ok"]
        after = [K.volume(b.shape) for b in bodies]
        assert after != before, "the commit did not move anything"
        v.on_command("edit.undo")
        assert "已撤销" in v._prompt.text(), v._prompt.text()
        back = [K.volume(b.shape) for b in doc.bodies if b.id in
                [x.id for x in bodies]]
        assert back == pytest.approx(before, rel=1e-9)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-8: one size table -----------------------------------------------------

def test_the_point_sizes_live_in_one_table():
    from scdm.gui.scene import Scene
    assert set(Scene.POINT_SIZES) >= {"vertex", "sketch", "select",
                                      "conflict", "anchor"}
    with open(_SCENE, encoding="utf-8") as fh:
        src = fh.read()
    # no call site may hard-code a size again: the table is the one answer
    literals = re.findall(r"_points_actor\([^)]*,\s*(\d+)\s*\)", src)
    assert literals == [], "point sizes outside the table: %s" % literals


def test_a_point_size_can_be_scaled_and_is_clamped():
    sc = _bare_scene()
    assert sc._point_size("anchor") == sc.POINT_SIZES["anchor"]
    assert sc.set_point_scale(2.0) == 2.0
    assert sc._point_size("anchor") == sc.POINT_SIZES["anchor"] * 2
    assert sc.set_point_scale(0.0) == 1.0          # a zero scale is no scale
    assert sc.set_point_scale(99.0) == 6.0         # and it is clamped
    assert sc.set_point_scale("nonsense") == 1.0


def test_the_sketch_page_carries_the_point_size():
    v = _viewer()
    try:
        v.left.show_options("mode.sketch")
        assert v.left.spin_value("mode.sketch", 0) == 1.0
        assert v.left.is_checked("mode.sketch", 0) is True     # 草图网格
        assert v.left.is_checked("mode.sketch", 2) is False    # 保留实体
        v.left._opt_pages["mode.sketch"][2][0].setValue(2.0)
        assert v._apply_point_scale() == 2.0
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_anchor_marker_uses_the_table():
    doc_sk = None
    from scdm.kdoc import KernelDoc
    sc = _bare_scene()
    doc_sk = KernelDoc()
    sk = doc_sk.add_sketch("xy")
    sc.set_point_scale(2.0)
    sc.set_anchor_marker(sk, [0.005, 0.001])
    assert len(sc._anchor_actors) == 1
    act = sc._anchor_actors[0]
    assert act.GetProperty().GetPointSize() == sc._point_size("anchor")
    assert act.GetProperty().GetPointSize() == 32
    assert act.GetMapper().GetInput().GetNumberOfCells() == 1


# --- A-14: one target per row ------------------------------------------------

def _two_dangling_rows(v):
    doc = v.session().kdoc
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = doc.add_sketch("xy")
    _constrained_rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")
    sk.constraints[6] = (S.DIST, 1, 2, "S9_dim6")
    other = doc.add_sketch("xy")
    _constrained_rect(other, 0.040, 0.010, 0.008)
    v._refresh_sketch_dof()
    v._rebuild()
    rows = _health_rows(v.left.tree)
    assert len(rows) == 2, [r.text(0) for r in rows]
    for it in rows:
        it.setSelected(True)
    v.left.show_options("repair.refs")
    return doc, sk, other, rows


def test_each_selected_row_gets_its_own_picker():
    v = _viewer()
    try:
        _doc, sk, other, _rows = _two_dangling_rows(v)
        v._sync_repair_targets()
        assert len(v.left.row_target_boxes("repair.refs", 0)) == 2
        assert v.left.row_targets("repair.refs", 0) == [None, None]
        entries = SKM.target_options(v.session().kdoc, v.session().scale)
        want = ["%s_dim5" % other.id, "param:d"]
        for i, to in enumerate(want):
            which = [k for k, e in enumerate(entries) if e["to"] == to][0]
            v.left.set_row_target_index("repair.refs", 0, i, which + 1)
        assert v.left.row_targets("repair.refs", 0) == want
        v.left.set_checked("repair.refs", 1, True)
        v.on_command("repair.refs")
        assert sk.constraints[5][3] == "%s_dim5" % other.id, sk.constraints[5]
        assert sk.constraints[6][3] == "d", sk.constraints[6]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_a_row_left_alone_follows_the_single_target():
    v = _viewer()
    try:
        _doc, sk, other, _rows = _two_dangling_rows(v)
        v._sync_repair_targets()
        entries = SKM.target_options(v.session().kdoc, v.session().scale)
        which = [k for k, e in enumerate(entries)
                 if e["to"] == "param:d"][0]
        v.left.set_row_target_index("repair.refs", 0, 1, which + 1)   # row 6 only
        v.left.set_text("repair.refs", 0, "%s_dim5" % other.id)       # the rest
        assert v.left.row_targets("repair.refs", 0)[0] is None
        v.left.set_checked("repair.refs", 1, True)
        v.on_command("repair.refs")
        assert sk.constraints[5][3] == "%s_dim5" % other.id, sk.constraints[5]
        assert sk.constraints[6][3] == "d", sk.constraints[6]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_row_pickers_survive_a_refresh():
    v = _viewer()
    try:
        _doc, _sk, other, _rows = _two_dangling_rows(v)
        v._sync_repair_targets()
        entries = SKM.target_options(v.session().kdoc, v.session().scale)
        which = [k for k, e in enumerate(entries)
                 if e["to"] == "%s_dim5" % other.id][0]
        v.left.set_row_target_index("repair.refs", 0, 0, which + 1)
        v._sync_repair_targets()          # the same selection: do not rebuild
        assert v.left.row_targets("repair.refs", 0)[0] == "%s_dim5" % other.id
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

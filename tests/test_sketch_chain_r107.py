"""R107 A group: multi-loop extrusion, exact circle sections, driven dimensions.

* A-1: every closed loop of a sketch becomes its own body, with its own
  self-contained `sketch` feature - so editing one loop rebuilds only its body.
* A-2: a circle loop extrudes to a real cylinder (@pi r^2 h@), not a polygon.
* A-3: a sketch dimension is *driven*: setting its value re-solves the sketch
  (LM solver) and rebuilds the bodies, so a number moves geometry.
"""
from __future__ import annotations

import math
import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _extrude(doc, curves, t_mm=5.0, plane="xy"):
    sk = doc.add_sketch(plane)
    sk.curves.extend(curves)
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"], rep["reason"]
    return sk, rep["bodies"]


def _rect(w_mm, h_mm, x0=0.0, y0=0.0):
    return ("rect", (x0, y0), (x0 + w_mm / 1000.0, y0 + h_mm / 1000.0))


def _mm3(w, h, t):
    return w * h * t * 1e-9


# --- A-1: one body per loop -------------------------------------------------

def test_every_loop_becomes_its_own_body():
    doc = KernelDoc()
    sk, bodies = _extrude(doc, [_rect(10, 8), _rect(5, 4, x0=0.02)], 5.0)
    assert len(bodies) == 2
    assert [round(K.volume(b.shape), 12) for b in bodies] == [
        pytest.approx(_mm3(10, 8, 5), rel=1e-9),
        pytest.approx(_mm3(5, 4, 5), rel=1e-9)]
    for i, b in enumerate(bodies):
        stack = doc.feature_stack(b.id)
        assert stack.ops() == ["sketch"]
        assert stack.features[0].params["loop"] == i
        assert doc.can_replay(b.id)[0] is True
        assert [r["param"] for r in stack.editable()] == ["height"]


def test_each_body_follows_its_own_loop():
    doc = KernelDoc()
    sk, bodies = _extrude(doc, [_rect(10, 8), _rect(5, 4, x0=0.02)], 5.0)
    sk.curves[1] = _rect(10, 4, x0=0.02)          # widen the second loop only
    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert rep["ok"] and sorted(rep["updated"]) == sorted(b.id for b in bodies)
    assert K.volume(bodies[0].shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-9)
    assert K.volume(bodies[1].shape) == pytest.approx(_mm3(10, 4, 5), rel=1e-9)


def test_a_removed_loop_takes_its_body_and_leaves_the_other_alone():
    """R115/A-6 changed this from "reported and kept" to "reported and removed":
    a body whose loop no longer exists has no defining geometry left, so it goes
    with the loop while the other loop keeps following the sketch."""
    doc = KernelDoc()
    sk, bodies = _extrude(doc, [_rect(10, 8), _rect(5, 4, x0=0.02)], 5.0)
    keep_id, gone_id = bodies[0].id, bodies[1].id
    del sk.curves[1]
    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert rep["ok"] and not rep["failed"]
    assert [b for b, _why in rep["removed"]] == [gone_id]
    assert "第 2 个闭环已不存在" in rep["removed"][0][1]
    assert doc.body_by_id(gone_id) is None
    assert [b.id for b in doc.bodies] == [keep_id]
    assert K.volume(doc.body_by_id(keep_id).shape) == pytest.approx(
        _mm3(10, 8, 5), rel=1e-9)


# --- A-2: exact circular sections ------------------------------------------

def test_circle_extrusion_is_exact():
    doc = KernelDoc()
    _sk, bodies = _extrude(doc, [("circle", (0.0, 0.0), 0.002)], 10.0)
    assert len(bodies) == 1
    v = K.volume(bodies[0].shape)
    assert v == pytest.approx(math.pi * 0.002 ** 2 * 0.010, rel=1e-6)
    assert len(K.explore(bodies[0].shape, "face")) == 3      # a real cylinder

    # the polygon path the old extrude used was 0.16% off - pin the difference
    polygon = K.volume(S.extrude_sketch([("circle", (0.0, 0.0), 0.002)], 0.010))
    assert abs(polygon - v) / v > 1e-3


def test_circle_and_polygon_loops_together():
    doc = KernelDoc()
    _sk, bodies = _extrude(doc, [("circle", (0.0, 0.0), 0.002), _rect(10, 8, x0=0.02)],
                           5.0)
    assert len(bodies) == 2
    assert K.volume(bodies[0].shape) == pytest.approx(
        math.pi * 0.002 ** 2 * 0.005, rel=1e-6)
    assert K.volume(bodies[1].shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-9)


# --- A-3: driven dimensions -------------------------------------------------

def _driven_rect(doc, w_mm=10.0, h_mm=8.0, t_mm=5.0):
    """A rectangle as one polyline + H/V + two dimensions + a pin."""
    sk = doc.add_sketch("xy")
    w, h = w_mm / 1000.0, h_mm / 1000.0
    sk.curves.append(("poly", [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]]))
    sk.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, w), (S.DIST, 1, 2, h),
    ])
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"], rep["reason"]
    return sk, rep["bodies"][0]


def _size(sk):
    pts, _segs = S.read_points(sk)
    return (math.dist(pts[0][:2], pts[1][:2]), math.dist(pts[1][:2], pts[2][:2]))


def test_driving_a_dimension_moves_the_body():
    doc = KernelDoc()
    sk, body = _driven_rect(doc)
    assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-9)
    dims = SKM.dimensions(doc, sk.id)
    assert [round(d["value_mm"], 6) for d in dims] == [10.0, 8.0]
    assert dims[0]["label"] == "距离 10mm"

    rep = SKM.set_dimension(doc, sk.id, dims[0]["index"], 20.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert rep["old_mm"] == pytest.approx(10.0, rel=1e-9)
    assert rep["dof"] == 0 and rep["residual"] < 1e-8
    w, h = _size(sk)
    assert w == pytest.approx(0.020, rel=1e-9) and h == pytest.approx(0.008, rel=1e-9)

    assert SKM.sync_sketch_bodies(doc, sk.id, 1000.0)["updated"] == [body.id]
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)
    assert doc.can_replay(body.id)[0] is True

    # the second dimension drives independently, and the DOF count is unchanged
    rep2 = SKM.set_dimension(doc, sk.id, dims[1]["index"], 4.0, 1000.0)
    assert rep2["ok"] and rep2["dof"] == rep["dof"]
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 4, 5), rel=1e-6)


def test_a_failed_drive_rolls_back_the_sketch():
    doc = KernelDoc()
    sk, body = _driven_rect(doc)
    before_vol = K.volume(body.shape)

    # an impossible target: a second, conflicting dimension on the same pair
    sk.constraints.append((S.DIST, 0, 1, 0.030))
    bad_index = len(sk.constraints) - 1
    before_curves = list(sk.curves)
    before_cons = list(sk.constraints)          # the state a failed drive restores
    rep = SKM.set_dimension(doc, sk.id, bad_index, 0.040, 1000.0)
    assert rep["ok"] is False and "未落到目标尺寸" in rep["reason"]
    assert list(sk.curves) == before_curves
    assert list(sk.constraints) == before_cons
    assert K.volume(body.shape) == pytest.approx(before_vol, rel=1e-12)

    # ... and a refusal that never reaches the solver
    sk.constraints.pop()
    assert SKM.set_dimension(doc, sk.id, 5, -1.0, 1000.0)["ok"] is False
    assert K.volume(body.shape) == pytest.approx(before_vol, rel=1e-12)


def test_scripted_drive_replays():
    doc = KernelDoc()
    _sk, body = _driven_rect(doc)
    turns = SCR.replay([{"cmd": "sketch.drive",
                         "opts": {"sketch": 0, "index": 5, "value_mm": 15.0}}], doc)
    assert turns == ["OK sketch.drive"], turns
    assert K.volume(body.shape) == pytest.approx(_mm3(15, 8, 5), rel=1e-6)


# --- the tree + GUI hooks ---------------------------------------------------

def test_tree_lists_dimensions_as_editable_rows():
    from PyQt5.QtWidgets import QApplication, QTreeWidgetItem
    Qt = pytest.importorskip("PyQt5.QtCore").Qt
    app = QApplication.instance() or QApplication([])
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel
    doc = KernelDoc()
    sk, _body = _driven_rect(doc)
    panel = LeftPanel()
    panel.populate_tree(Session(kdoc=doc, name="T"))
    found = []

    def walk(item):
        data = item.data(0, Qt.UserRole)
        if data:
            found.append(data)
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(panel.tree.topLevelItemCount()):
        walk(panel.tree.topLevelItem(i))
    dims = [d for d in found if d and d[0] == "sketch_dim"]
    assert dims == [("sketch_dim", sk.id, 5), ("sketch_dim", sk.id, 6)], dims


def test_gui_rebuilds_bodies_after_a_library_drive():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import scdm_gui
    box = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "box.scdoc")
    v = scdm_gui.ScdmViewer(path=box)
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                                   [0.010, 0.008], [0.0, 0.008]]))
        sk.constraints.extend([
            (S.FIXED, 0, 0.0, 0.0),
            (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
            (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
            (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008),
        ])
        v.on_command("sketch.pull")
        body = v.session().kdoc.bodies[-1]
        assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-9)

        dims = SKM.dimensions(v.session().kdoc, sk.id, v.session().scale)
        assert SKM.set_dimension(v.session().kdoc, sk.id, dims[0]["index"],
                                 20.0, v.session().scale)["ok"]
        assert v._sync_sketch_bodies(sk.id) == 1
        assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)
    finally:
        v.close()

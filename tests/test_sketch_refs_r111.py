"""R111 A-1 + A-2 + A-6: dimensions that reference dimensions, Pull to a face in
the library, and a read-only degrees-of-freedom report.

A-1: an expression may name another dimension (`dimN`, N = the constraint index),
     chains settle in one redrive, and a cycle is refused with the two indices.
A-2: `extrude_active(..., to_face=<face>)` measures the plane distance and picks
     the direction; a face that is not parallel to the sketch is refused.
A-6: `dof_report()` solves a *copy* of the sketch (rule 85: a measurement must
     not change the workload) and reports DOF / redundancy / conflict.
"""
from __future__ import annotations

import math
import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")
_APP = None          # keep the QApplication alive across tests


def _mm3(w, h, t):
    return w * h * t * 1e-9


def _referenced_rect(doc, width_expr="2*dim6", height=8.0, t_mm=5.0):
    """A fully constrained rectangle whose width is an expression."""
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0],
                               [0.020, height / 1000.0], [0.0, height / 1000.0]]))
    sk.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, width_expr), (S.DIST, 1, 2, height / 1000.0),
    ])
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"], rep["reason"]
    return sk, rep["bodies"][0]


# --- A-1: dimensions that reference dimensions ------------------------------

def test_a_dimension_can_reference_another_dimension():
    doc = KernelDoc()
    sk, body = _referenced_rect(doc)                 # width = 2*dim6, dim6 = 8mm
    rows = {d["index"]: d for d in SKM.dimensions(doc, sk.id, 1000.0)}
    assert rows[5]["expr"] == "2*dim6" and rows[5]["value_mm"] == pytest.approx(16.0)

    drive = SKM.set_dimension(doc, sk.id, 6, 4.0, 1000.0)
    assert drive["ok"], drive["reason"]
    redrive = SKM.redrive_expressions(doc, 1000.0)
    assert redrive["ok"] and redrive["redriven"] >= 1
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(8, 4, 5), rel=1e-6)

def test_a_chain_of_dimensions_settles():
    # Three rectangles in one sketch, each contributing one width, so the chain
    # (#15 -> #17 -> #19) is the only coupling.  A multi-loop sketch yields one
    # body per loop (R107/A-1), hence the summed volume.
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                               [0.010, 0.003], [0.0, 0.003]]))
    for x0 in (0.020, 0.040):
        sk.curves.append(("poly", [[x0, 0.0], [x0 + 0.005, 0.0],
                                   [x0 + 0.005, 0.004], [x0, 0.004]]))
    for b, x in ((0, 0.0), (4, 0.020), (8, 0.040)):
        sk.constraints.extend([(S.FIXED, b, x, 0.0), (S.HORIZONTAL, b, b + 1),
                               (S.VERTICAL, b + 1, b + 2),
                               (S.HORIZONTAL, b + 2, b + 3),
                               (S.VERTICAL, b + 3, b)])
    sk.constraints.extend([
        (S.DIST, 0, 1, "2*dim17"),   # 15: A width  = 2 * B width
        (S.DIST, 1, 2, "5"),         # 16: A height = 5mm
        (S.DIST, 4, 5, "dim19+2"),   # 17: B width  = C width + 2
        (S.DIST, 5, 6, "3"),         # 18: B height = 3mm
        (S.DIST, 8, 9, "4"),         # 19: C width  = 4mm (the leaf)
        (S.DIST, 9, 10, "2"),        # 20: C height = 2mm
    ])
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert len(rep["bodies"]) == 3
    redrive = SKM.redrive_expressions(doc, 1000.0)
    assert redrive["ok"], redrive["reason"]
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    # dim19 = 4 -> dim17 = 6 -> dim15 = 12
    vol = sum(K.volume(b.shape) for b in doc.bodies)
    assert vol == pytest.approx(_mm3(12 * 5 + 6 * 3 + 4 * 2, 1, 5), rel=1e-6)

    widened = SKM.set_dimension(doc, sk.id, 19, 8.0, 1000.0)      # drive the leaf
    assert widened["ok"], widened["reason"]
    SKM.redrive_expressions(doc, 1000.0)
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    # dim19 = 8 -> dim17 = 10 -> dim15 = 20
    vol2 = sum(K.volume(b.shape) for b in doc.bodies)
    assert vol2 == pytest.approx(_mm3(20 * 5 + 10 * 3 + 8 * 2, 1, 5), rel=1e-6)


def test_a_reference_must_name_a_dimension():
    """`dimN` binds to the constraint index, so the refusal has to name them."""
    doc = KernelDoc()
    sk, body = _referenced_rect(doc)
    before = K.volume(body.shape)

    outside = SKM.set_dimension(doc, sk.id, 5, "2*dim77", 1000.0)
    assert outside["ok"] is False
    assert "越界" in outside["reason"] and "dim77" in outside["reason"]
    assert "可引用的尺寸" in outside["reason"]

    geometric = SKM.set_dimension(doc, sk.id, 5, "2*dim3", 1000.0)
    assert geometric["ok"] is False
    assert "不是尺寸" in geometric["reason"] and "#3" in geometric["reason"]
    assert K.volume(body.shape) == pytest.approx(before, rel=1e-12)


def test_a_broken_dimension_stays_visible_and_numbered():
    """A row that cannot be resolved must not vanish from the tree (its index
    is the only handle a user has for fixing the reference)."""
    doc = KernelDoc()
    sk, _body = _referenced_rect(doc)
    sk.constraints.append((S.DIST, 2, 3, "2*nope"))
    rows = {d["index"]: d for d in SKM.dimensions(doc, sk.id, 1000.0)}
    assert 7 in rows, "the broken row disappeared"
    assert rows[7]["value_mm"] is None
    assert "无法求值" in rows[7]["label"] and rows[7]["reason"]


def test_the_pull_sees_the_sketch_its_dimensions_describe():
    """R111 pinned "the pull extrudes the sketch as drawn"; R124/A-5 changed it,
    because a label saying 16mm over a body of 20mm is simply a lie.  The pull now
    redrives the expression rows first (idempotent when they already agree)."""
    doc = KernelDoc()
    sk, body = _referenced_rect(doc)          # drawn 20x8, width = "2*dim6" = 16
    assert K.volume(body.shape) == pytest.approx(_mm3(16, 8, 5), rel=1e-6)
    # driving it further still moves the sketch, and the table still re-solves
    assert SKM.set_dimension(doc, sk.id, 6, 5.0, 1000.0)["ok"]      # height 5mm
    assert SKM.redrive_expressions(doc, 1000.0)["ok"]
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(10, 5, 5), rel=1e-6)


def test_a_cyclic_reference_is_refused_with_both_indices():
    doc = KernelDoc()
    sk, body = _referenced_rect(doc)
    before = K.volume(body.shape)
    saved = list(sk.constraints)

    rep = SKM.set_dimension(doc, sk.id, 5, "2*dim5", 1000.0)     # self reference
    assert rep["ok"] is False and "循环" in rep["reason"]
    assert "#5" in rep["reason"]
    assert list(sk.constraints) == saved
    assert K.volume(body.shape) == pytest.approx(before, rel=1e-12)

    # a two-step cycle: 5 -> 6 then 6 -> 5
    plain = KernelDoc()
    sk2 = plain.add_sketch("xy")
    sk2.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                                [0.010, 0.008], [0.0, 0.008]]))
    sk2.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008),
    ])
    assert SKM.set_dimension(plain, sk2.id, 5, "2*dim6", 1000.0)["ok"]
    rep2 = SKM.set_dimension(plain, sk2.id, 6, "dim5/2", 1000.0)
    assert rep2["ok"] is False and "循环" in rep2["reason"]
    assert "#6" in rep2["reason"] and "#5" in rep2["reason"]
    assert sk2.constraints[6][3] == 0.008       # the refused value was rolled back


# --- A-2: Pull to a face ----------------------------------------------------

def _plate(doc, t_mm=12.0):
    body = doc.add_body(K.make_box(0.02, 0.02, t_mm / 1000.0), name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - t_mm / 1000.0) < 1e-9][0]
    return body, top


def test_extrude_to_a_face_measures_the_plane_distance():
    doc = KernelDoc()
    plate, top = _plate(doc, 12.0)
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
    rep = SKM.extrude_active(doc, 99.0, 1000.0, to_face=top)   # the 99 is ignored
    assert rep["ok"], rep["reason"]
    assert rep["to_face_mm"] == pytest.approx(12.0, rel=1e-9)
    body = rep["bodies"][0]
    assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 12), rel=1e-9)
    feature = doc.feature_stack(body.id).features[0]
    assert feature.params["height"] == pytest.approx(12.0)
    assert feature.params.get("mode", "one") == "one"
    assert doc.can_replay(body.id)[0] is True      # replay needs no face


def test_extrude_to_a_face_below_the_sketch_goes_reverse():
    doc = KernelDoc()
    plate = doc.add_body(K.translate(K.make_box(0.02, 0.02, 0.006),
                                     (0.0, 0.0, -0.006)))
    bottom = [f for f in K.explore(plate.shape, "face")
              if abs(K.face_normal_center(f)[1][2] + 0.006) < 1e-9][0]
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
    rep = SKM.extrude_active(doc, 1.0, 1000.0, to_face=bottom)
    assert rep["ok"], rep["reason"]
    body = rep["bodies"][0]
    assert doc.feature_stack(body.id).features[0].params.get("mode") == "reverse"
    lo, hi = K._vertex_bbox(body.shape)
    assert (lo[2], hi[2]) == (pytest.approx(-0.006, abs=1e-12), 0.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 6), rel=1e-9)


def test_to_face_refuses_a_non_parallel_face():
    doc = KernelDoc()
    plate, _top = _plate(doc, 12.0)
    side = [f for f in K.explore(plate.shape, "face")
            if abs(K.face_normal_center(f)[0][0] - 1.0) < 1e-9][0]
    sk = doc.add_sketch("xy")
    sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
    rep = SKM.extrude_active(doc, 5.0, 1000.0, to_face=side)
    assert rep["ok"] is False and "平行" in rep["reason"]
    assert len(doc.bodies) == 1                    # nothing was created


# --- A-6: the DOF report ----------------------------------------------------

def test_dof_report_counts_and_never_touches_the_sketch():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                               [0.010, 0.008], [0.0, 0.008]]))
    before = S.read_points(sk)[0]
    bare = SKM.dof_report(doc, sk.id, 1000.0)
    assert bare["ok"] and bare["dof"] == 8         # 4 free points
    assert S.read_points(sk)[0] == before          # read-only

    sk.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, 0.010), (S.DIST, 1, 2, 0.008),
    ])
    fixed = SKM.dof_report(doc, sk.id, 1000.0)
    assert fixed["ok"] and fixed["dof"] == 0 and fixed["converged"] is True
    assert S.read_points(sk)[0] == before

    sk.constraints.append((S.DIST, 0, 1, 0.010))   # a duplicate row
    redundant = SKM.dof_report(doc, sk.id, 1000.0)
    assert redundant["redundant"] >= 1


def test_the_mode_chip_shows_the_remaining_dof():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui
    v = scdm_gui.ScdmViewer(path=_BOX)
    v.on_command("mode.sketch")
    assert v._mode() == SKM.MODE_SKETCH
    chip = v._mode_chip.text()
    assert "自由度" in chip, chip
    assert "自由度 0" in chip                       # an empty sketch has no variables
    assert "自由度 0" in chip                       # an empty sketch has no variables


def test_the_tree_shows_the_index_a_reference_needs():
    """An expression names a dimension as `dimN`, so the tree must show N - and
    a row that cannot be resolved must stay listed instead of disappearing."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    from scdm.document import Session
    from scdm.gui.left_panel import LeftPanel

    doc = KernelDoc()
    sk, _body = _referenced_rect(doc)
    sk.constraints.append((S.DIST, 2, 3, "2*nope"))
    panel = LeftPanel()
    rows = []
    try:
        panel.populate_tree(Session(kdoc=doc, name="R111"))

        def walk(item):
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "sketch_dim":
                rows.append((data[2], item.text(0), item.toolTip(0)))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
    finally:
        try:
            panel.hide()
        except RuntimeError:
            pass
    assert {r[0] for r in rows} == {5, 6, 7}
    by_index = {r[0]: r for r in rows}
    assert by_index[5][1].startswith("#5 "), by_index[5][1]
    assert "dim5" in by_index[5][2]              # the tooltip names the reference
    assert "无法求值" in by_index[7][1]           # the broken row is still there


def test_gui_pull_to_the_selected_face():
    """The ribbon 到面 hands the *face* to the library, so the GUI keeps no second
    distance calculation of its own (one source of truth for the height)."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    import scdm_gui

    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        doc = v.session().kdoc
        plate = doc.add_body(K.make_box(0.02, 0.02, 0.012), name="板")
        v.on_command("mode.sketch")
        sk = doc.sketches[-1]
        sk.curves.append(("rect", (0.030, 0.030), (0.040, 0.038)))
        faces = K.explore(plate.shape, "face")
        top_i = [i for i, f in enumerate(faces)
                 if abs(K.face_normal_center(f)[1][2] - 0.012) < 1e-9][0]
        v.left.show_options("tool.pull")
        v.left.set_checked("tool.pull", 2, True)              # 到面
        v.sel.items = [("face", "%s:%d" % (plate.id, top_i))]
        v.on_command("sketch.pull")

        body = doc.bodies[-1]
        assert doc.feature_stack(body.id).features[0].params["height"] == \
            pytest.approx(12.0)
        assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 12), rel=1e-9)
        assert v._mode() == SKM.MODE_SOLID
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


"""R105: the sketch / solid mode boundary.

The complaint this answers: "there is no boundary between sketching and 3D, so
you cannot switch smoothly like in SpaceClaim".  The boundary is now explicit and
testable:

* `sketchmode.plan()` is the policy table (which commands belong to the sketch
  side, which are neutral, and what a solid command does while sketching);
* `SketchSession` owns the active sketch, its plane source and the staleness
  check (drawing on a plane that moved is worse than refusing);
* the GUI shows the boundary (Edit Sketch tab + status chip), crosses it in one
  place (`_exit_sketch`) and crosses it automatically when a 3D command is
  used, and Pull turns the sketch into a body and returns to 3D.
"""
from __future__ import annotations

import math
import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import scripting as SCR  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _rect_sketch(doc, w_mm=10.0, h_mm=8.0, plane="xy"):
    sk = doc.add_sketch(plane)
    sk.curves.append(("rect", (0.0, 0.0), (w_mm / 1000.0, h_mm / 1000.0)))
    return sk


# --- the policy table -------------------------------------------------------

def test_plan_is_the_boundary_table():
    for cmd in ("sketch.line", "sketch.rect", "con.dim", "sketch.finish",
                "sketch.pull", "tool.pull", "view.fit", "show.edges",
                "style.wire", "edit.undo", "measure.dist", "mode.3d",
                "mode.sketch", "tools.script"):
        assert SKM.plan(cmd, SKM.MODE_SKETCH).kind == "run", cmd
    for cmd in ("asm.mate", "create.hole", "tool.combine", "sheet.bend",
                "surface.thicken", "repair.check", "prep.share", "mesh.volume",
                "det.view", "create.beam"):
        p = SKM.plan(cmd, SKM.MODE_SKETCH)
        assert p.kind == "exit_then_run", cmd
        assert p.exits and cmd in p.reason
    # in solid mode nothing changes
    for cmd in ("sketch.line", "asm.mate", "create.hole"):
        assert SKM.plan(cmd, SKM.MODE_SOLID).kind == "run", cmd
    assert SKM.plan("", SKM.MODE_SKETCH).kind == "run"


# --- the session ------------------------------------------------------------

def test_datum_sketch_never_goes_stale():
    doc = KernelDoc()
    sk = _rect_sketch(doc)
    ses = SKM.SketchSession(sketch_id=sk.id, plane="xy", source="datum")
    assert ses.stale(doc) is None
    assert ses.label() == "XY"


def test_face_sketch_goes_stale_when_the_body_moves_or_disappears():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.01), name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.01) < 1e-9][0]
    n, c = K.face_normal_center(top)
    sk = doc.add_sketch("custom")
    sk.origin, sk.normal = tuple(c), tuple(n)
    ses = SKM.SketchSession(sketch_id=sk.id, plane="custom", source="face",
                            source_body=body.id, source_normal=tuple(n),
                            source_point=tuple(c))
    assert ses.stale(doc) is None            # the face is still there

    # a move *inside* the plane keeps the sketch valid (the check is geometric,
    # not tied to a face index) ...
    doc.translate_body(body.id, (0.05, 0.0, 0.0))
    assert ses.stale(doc) is None
    doc.translate_body(body.id, (-0.05, 0.0, 0.0))

    # ... a move along the normal does not
    doc.translate_body(body.id, (0.0, 0.0, 0.05))
    assert "平面已改变" in ses.stale(doc)

    doc.translate_body(body.id, (0.0, 0.0, -0.05))
    assert ses.stale(doc) is None            # back home -> fine again
    doc.bodies.remove(body)
    assert "实体已不存在" in ses.stale(doc)


def test_resolve_active_prefers_the_session_sketch():
    doc = KernelDoc()
    first = _rect_sketch(doc)
    second = _rect_sketch(doc)
    ses = SKM.SketchSession(sketch_id=first.id, plane="xy")
    sk, why = SKM.resolve_active(doc, ses)
    assert sk is first and why == ""

    # no session and two sketches: ask the user instead of guessing
    sk2, why2 = SKM.resolve_active(doc, None)
    assert sk2 is None and "双击" in why2
    doc.sketches.remove(second)
    assert SKM.resolve_active(doc, None)[0] is first

    empty = KernelDoc()
    none, why3 = SKM.resolve_active(empty, None)
    assert none is None and "没有草图" in why3


# --- the bridge -------------------------------------------------------------

def test_extrude_active_is_the_closed_form_bridge():
    doc = KernelDoc()
    _rect_sketch(doc, 10.0, 8.0)
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert len(rep["bodies"]) == 1 and len(doc.bodies) == 1
    assert rep["volume"] == pytest.approx(10.0 * 8.0 * 5.0 * 1e-9, rel=1e-9)

    # a circle-only sketch still works (polygonal approximation in the prism)
    doc2 = KernelDoc()
    sk = doc2.add_sketch("xy")
    sk.curves.append(("circle", (0.0, 0.0), 0.002))
    rep2 = SKM.extrude_active(doc2, 10.0, 1000.0)
    assert rep2["ok"], rep2["reason"]
    assert rep2["volume"] == pytest.approx(math.pi * 0.002 ** 2 * 0.010,
                                           rel=2e-3)

    # and the reasons are explicit
    doc3 = KernelDoc()
    assert "没有草图" in SKM.extrude_active(doc3, 5.0)["reason"]
    doc4 = KernelDoc()
    _rect_sketch(doc4)
    assert "高度" in SKM.extrude_active(doc4, 0.0)["reason"]


def test_extrude_refuses_a_stale_session():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.01), name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.01) < 1e-9][0]
    n, c = K.face_normal_center(top)
    sk = doc.add_sketch("custom")
    sk.origin, sk.normal = tuple(c), tuple(n)
    sk.curves.append(("rect", (0.0, 0.0), (0.01, 0.008)))
    ses = SKM.SketchSession(sketch_id=sk.id, plane="custom", source="face",
                            source_body=body.id, source_normal=tuple(n),
                            source_point=tuple(c))
    doc.translate_body(body.id, (0.0, 0.0, 0.05))   # the plane itself moves
    rep = SKM.extrude_active(doc, 5.0, 1000.0, ses)
    assert rep["ok"] is False and "平面已改变" in rep["reason"]
    assert len(doc.bodies) == 1              # nothing was created


# --- wiring -----------------------------------------------------------------

def test_mode_commands_are_wired():
    from scdm.catalog import M3_LIVE, all_commands
    ids = {c.id for c in all_commands()}
    assert {"sketch.finish", "sketch.pull"} <= ids
    assert {"sketch.finish", "sketch.pull"} <= M3_LIVE
    assert "sketch.pull" in SCR.OPS
    src = (os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scdm_gui.py"))
    text = open(src, encoding="utf-8").read()
    for handler in ("_do_sketch_finish", "_do_sketch_pull", "_exit_sketch"):
        assert "def %s" % handler in text, handler
    msg = SCR.OPS["sketch.pull"](_doc_with_rect(), {"distance": 5.0}, 1000.0)[1]
    assert "草图拉伸" in msg


def _doc_with_rect():
    doc = KernelDoc()
    _rect_sketch(doc)
    return doc


# --- the GUI boundary -------------------------------------------------------

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")


@pytest.fixture()
def viewer():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import scdm_gui
    v = scdm_gui.ScdmViewer(path=_BOX)
    yield v
    v.close()


def test_gui_switches_between_sketch_and_solid_in_one_click(viewer):
    v = viewer
    assert v._mode() == SKM.MODE_SOLID
    v.on_command("mode.sketch")
    assert v._mode() == SKM.MODE_SKETCH
    assert v.session().show_grid is True
    assert v.ribbon._tab_ids[v.ribbon.tabs.currentIndex()] == "sketchmode"
    assert v._mode_chip.text().startswith("草图模式") and not v._mode_chip.isHidden()
    assert v._sketch_session is not None and v._sketch_session.sketch_id

    # a neutral command keeps the mode (view commands do not cross the boundary)
    v.on_command("view.fit")
    assert v._mode() == SKM.MODE_SKETCH

    # a solid command crosses it and then runs - one click, no dead state
    # (asm.mate with no selection only writes a status line: no modal dialog,
    # so this stays headless-safe)
    v.on_command("asm.mate")
    assert v._mode() == SKM.MODE_SOLID
    assert v.session().show_grid is False
    assert v._sketch_session is None and v._sketch_tool is None
    assert v.ribbon._tab_ids[v.ribbon.tabs.currentIndex()] == "design"
    assert v._mode_chip.isHidden()

    # ... and back in, then out through the explicit command
    v.on_command("mode.sketch")
    assert v._mode() == SKM.MODE_SKETCH
    v.on_command("sketch.finish")
    assert v._mode() == SKM.MODE_SOLID and v._mode_chip.isHidden()


def test_gui_pull_sketch_extrudes_and_returns_to_3d(viewer):
    v = viewer
    v.on_command("mode.sketch")
    sk = v.session().kdoc.sketches[-1]
    sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
    before = len(v.session().kdoc.bodies)
    v.on_command("sketch.pull")
    assert v._mode() == SKM.MODE_SOLID           # the pull ends the mode
    assert len(v.session().kdoc.bodies) == before + 1
    made = v.session().kdoc.bodies[-1]
    # the GUI takes the height from the Pull option page (its default is 5mm;
    # the library/script default of 10mm is covered in the library test above)
    assert K.volume(made.shape) == pytest.approx(0.010 * 0.008 * 0.005, rel=1e-9)
    assert v.session().show_grid is False

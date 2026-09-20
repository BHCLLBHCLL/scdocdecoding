"""R106/B-1: the sketch is a feature - editing it rebuilds the extruded body.

Acceptance from the plan:
* changing a rectangle in sketch mode -> the body's volume is `w·h·t` again;
* the body's history contains the `sketch` op.

The feature carries the sketch definition (plane + curves + height) so a reloaded
project replays the same body, and `sketch_id` keeps the live link so an edited
outline rebuilds its bodies.
"""
from __future__ import annotations

import math
import os
import shutil
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import io_project as IO  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _rect_doc(w_mm=10.0, h_mm=8.0, t_mm=5.0, plane="xy"):
    doc = KernelDoc()
    sk = doc.add_sketch(plane)
    sk.curves.append(("rect", (0.0, 0.0), (w_mm / 1000.0, h_mm / 1000.0)))
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"], rep["reason"]
    return doc, sk, rep["bodies"][0]


def _vol(w_mm, h_mm, t_mm):
    return w_mm * h_mm * t_mm * 1e-9


def test_extrude_records_a_sketch_feature():
    doc, sk, body = _rect_doc()
    stack = doc.feature_stack(body.id)
    assert stack.ops() == ["sketch"]
    assert doc.can_replay(body.id)[0] is True
    assert K.volume(body.shape) == pytest.approx(_vol(10, 8, 5), rel=1e-9)

    f = stack.features[0]
    assert f.params["sketch_id"] == sk.id
    assert f.params["height"] == 5.0 and f.params["plane"] == "xy"
    assert len(f.params["curves"]) == 1
    assert f.label() == "草图拉伸 5mm"
    # the outline itself is not a text-dialog parameter - only the height is
    assert [r["param"] for r in stack.editable()] == ["height"]


def test_editing_the_height_rebuilds_the_body():
    doc, _sk, body = _rect_doc()
    rep = doc.edit_feature(body.id, 0, "height", 8.0)
    assert rep["ok"], rep["reason"]
    assert rep["old"] == 5.0 and rep["value"] == 8.0
    assert K.volume(body.shape) == pytest.approx(_vol(10, 8, 8), rel=1e-9)
    assert doc.can_replay(body.id)[0] is True


def test_editing_the_sketch_outline_rebuilds_the_body():
    doc, sk, body = _rect_doc()
    sk.curves[0] = ("rect", (0.0, 0.0), (0.020, 0.008))     # 10mm -> 20mm
    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert rep["ok"] and rep["updated"] == [body.id], rep
    assert K.volume(body.shape) == pytest.approx(_vol(20, 8, 5), rel=1e-9)
    assert doc.can_replay(body.id)[0] is True

    # the height is untouched by an outline edit, and both can be combined
    assert doc.edit_feature(body.id, 0, "height", 4.0)["ok"]
    assert K.volume(body.shape) == pytest.approx(_vol(20, 8, 4), rel=1e-9)
    # ... and a second outline edit still lands on the closed form
    sk.curves[0] = ("rect", (0.0, 0.0), (0.030, 0.010))
    assert SKM.sync_sketch_bodies(doc, sk.id, 1000.0)["updated"] == [body.id]
    assert K.volume(body.shape) == pytest.approx(_vol(30, 10, 4), rel=1e-9)


def test_sketch_feature_survives_the_project_round_trip():
    doc, sk, body = _rect_doc()
    d = Path(tempfile.mkdtemp(prefix="r106_"))
    try:
        path = d / "sketch.scdm"
        IO.save_scdm(str(path), doc)
        back = IO.load_scdm(str(path))
        b = back.bodies[0]
        assert back.feature_stack(b.id).ops() == ["sketch"]
        assert back.can_replay(b.id)[0] is True
        assert K.volume(b.shape) == pytest.approx(_vol(10, 8, 5), rel=1e-9)

        # the sketch itself came back too, so the live link works after reload
        assert [s.id for s in back.sketches] == [sk.id]
        back.sketches[0].curves[0] = ("rect", (0.0, 0.0), (0.020, 0.008))
        assert SKM.sync_sketch_bodies(back, back.sketches[0].id, 1000.0)["updated"] \
            == [b.id]
        assert K.volume(b.shape) == pytest.approx(_vol(20, 8, 5), rel=1e-9)
        assert back.edit_feature(b.id, 0, "height", 6.0)["ok"]
        assert K.volume(b.shape) == pytest.approx(_vol(20, 8, 6), rel=1e-9)
    finally:
        shutil.rmtree(str(d), ignore_errors=True)


def test_the_feature_definition_is_independent_of_the_live_sketch():
    """The curves travel with the feature, so deleting the sketch does not break
    replay - it only breaks the live link, and that is reported, not ignored."""
    doc, sk, body = _rect_doc()
    doc.sketches.remove(sk)
    assert doc.can_replay(body.id)[0] is True          # still self-contained
    assert doc.edit_feature(body.id, 0, "height", 9.0)["ok"]
    assert K.volume(body.shape) == pytest.approx(_vol(10, 8, 9), rel=1e-9)

    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert rep["ok"] is False and "草图已不存在" in rep["reason"]


def test_an_open_outline_takes_its_body_away():
    """R115/A-6: with no loop left the body has no defining geometry, so the sync
    removes it (and says which one) instead of leaving a stale solid behind."""
    doc, sk, body = _rect_doc()
    # replace the closed rectangle with a single line (no loop at all)
    sk.curves = [("line", (0.0, 0.0), (0.010, 0.0))]
    rep = SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert rep["ok"] and not rep["failed"]
    assert rep["removed"] and rep["removed"][0][0] == body.id
    assert "第 1 个闭环已不存在" in rep["removed"][0][1]
    assert doc.body_by_id(body.id) is None
    assert doc.features.get(body.id) is None
    # and a snapshot taken before the edit still describes the whole document
    assert doc.can_replay(body.id)[0] is False


# --- the GUI hook -----------------------------------------------------------

_BOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "box.scdoc")


def test_gui_sketch_bodies_follow_an_edited_sketch():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import scdm_gui
    v = scdm_gui.ScdmViewer(path=_BOX)
    try:
        v.on_command("mode.sketch")
        sk = v.session().kdoc.sketches[-1]
        sk.curves.append(("rect", (0.0, 0.0), (0.010, 0.008)))
        v.on_command("sketch.pull")
        body = v.session().kdoc.bodies[-1]
        assert v.session().kdoc.feature_stack(body.id).ops() == ["sketch"]
        assert K.volume(body.shape) == pytest.approx(_vol(10, 8, 5), rel=1e-9)

        # edit the outline and use the same hook every drawing path calls
        sk.curves[0] = ("rect", (0.0, 0.0), (0.020, 0.008))
        n = v._sync_sketch_bodies(sk.id)
        assert n == 1
        assert K.volume(body.shape) == pytest.approx(_vol(20, 8, 5), rel=1e-9)
    finally:
        v.close()

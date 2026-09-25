"""R123 A-1 + A-2 + A-7: expression targets, the anchor marker, and screenshot demos.

A-2: `to="expr:2*d"` turns a dangling dimension into an expression that keeps
     following the parameter table; a self reference reads as a cycle.
A-1: the GUI remembers the anchor a pattern used (`viewer.anchor_marker`), draws
     it, and drops it as soon as the selection changes.
A-7: the screenshot tool gained `conflict` and `mate` scenarios (the reference
     images under docs/screenshots are generated with them).
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import health as HEALTH  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.params import ParamTable  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BOX = os.path.join(_ROOT, "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets


def _ensure_app():
    """Hold the QApplication in a module global (Qt aborts without one)."""
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    return _APP


def _viewer(path=None):
    _ensure_app()
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _rect(doc, u0, w, width):
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[u0, 0.0], [u0 + w, 0.0], [u0 + w, 0.008],
                               [u0, 0.008]]))
    sk.constraints.extend([(S.FIXED, 0, u0, 0.0), (S.HORIZONTAL, 0, 1),
                           (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                           (S.VERTICAL, 3, 0), (S.DIST, 0, 1, width),
                           (S.DIST, 1, 2, 0.008)])
    return sk


def _with_param(value="5"):
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("d", value)
    return doc, _rect(doc, 0.0, 0.020, "S9_dim5")


# --- A-2: expression targets -------------------------------------------------

def test_a_dimension_can_be_retargeted_at_an_expression():
    doc, sk = _with_param("5")
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="expr:2*d")
    assert rep["ok"] and "已改指向算式 2*d" in rep["reason"], rep
    assert sk.constraints[5][3] == "2*d"
    assert HEALTH.document_warnings(doc, 1000.0) == []
    assert SKM.dimensions(doc, sk.id, 1000.0)[0]["value_mm"] == pytest.approx(10.0)


def test_an_expression_target_follows_the_parameter():
    doc, sk = _with_param("5")
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    assert HEALTH.repair_warning(doc, warn, "retarget", 1000.0,
                                 to="expr:2*d")["ok"]
    doc.param_table.set("d", "8")
    assert SKM.redrive_expressions(doc, 1000.0)["ok"]
    assert SKM.dimensions(doc, sk.id, 1000.0)[0]["value_mm"] == pytest.approx(16.0)


def test_an_empty_expression_is_refused():
    doc, sk = _with_param()
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="expr:  ")
    assert rep["ok"] is False and "算式目标为空" in rep["reason"], rep
    assert sk.constraints[5][3] == "S9_dim5"


def test_a_self_reference_reads_as_a_cycle():
    doc, sk = _with_param()
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="expr:2*dim5")
    assert rep["ok"] is False
    assert "循环" in rep["reason"] and "#5" in rep["reason"], rep
    assert sk.constraints[5][3] == "S9_dim5"


def test_a_self_reference_is_refused_by_the_driver_too():
    doc, sk = _with_param()
    rep = SKM.set_dimension(doc, sk.id, 5, "2*dim5", 1000.0)
    assert rep["ok"] is False and "循环" in rep["reason"], rep
    assert sk.constraints[5][3] == "S9_dim5"


def test_the_missing_target_message_lists_the_forms():
    doc, _sk = _with_param()
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0)
    assert "S2" in rep["reason"] and "param:" in rep["reason"] and \
        "expr:" in rep["reason"], rep


# --- A-1: the anchor marker --------------------------------------------------

def _along_setup(v):
    """A sketch with a path line and a rect, ready for an along pattern."""
    doc = v.session().kdoc
    v.on_command("mode.sketch")
    sk = doc.sketches[-1]
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
    sk.curves.append(("rect", (0.005, 0.001, 0.0), (0.007, 0.004, 0.0)))
    v.left.show_options("sketch.pattern")
    v.left.set_checked("sketch.pattern", 1, True)
    page = v.left._opt_pages["sketch.pattern"]
    page[3][0].setValue(3)
    return sk, page


def test_the_gui_remembers_the_anchor_it_used():
    _ensure_app()
    v = _viewer()
    try:
        sk, page = _along_setup(v)
        v.left.set_checked("sketch.pattern", 2, False)
        page[2][6].setValue(5.0)
        page[2][7].setValue(1.0)
        assert v._select_sketch_entity([0.010, 0.0002]) is not None
        assert v.anchor_marker is None            # nothing ran yet
        v.on_command("sketch.pattern")
        assert v.anchor_marker == (pytest.approx(0.005), pytest.approx(0.001))
        assert "锚点 5, 1mm" in v._prompt.text(), v._prompt.text()
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_marker_comes_from_the_picked_point():
    _ensure_app()
    v = _viewer()
    try:
        sk, page = _along_setup(v)
        v.left.set_checked("sketch.pattern", 2, True)
        page[2][6].setValue(99.0)                 # would be wrong
        assert v._select_sketch_entity([0.0051, 0.0011]) is not None
        assert v.sketch_selection[0][0] == "point"
        assert v._select_sketch_entity([0.010, 0.0002], add=True) is not None
        v.on_command("sketch.pattern")
        assert v.anchor_marker == (pytest.approx(0.005), pytest.approx(0.001))
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_no_anchor_means_no_marker_and_a_new_selection_clears_it():
    _ensure_app()
    v = _viewer()
    try:
        sk, page = _along_setup(v)
        v.left.set_checked("sketch.pattern", 2, False)
        assert v._select_sketch_entity([0.010, 0.0002]) is not None
        v.on_command("sketch.pattern")
        assert v.anchor_marker is None            # the path start was used
        assert "锚点" not in v._prompt.text()

        page[2][6].setValue(5.0)
        page[2][7].setValue(1.0)
        v.on_command("sketch.pattern")
        assert v.anchor_marker is not None
        v._select_sketch_entity([0.010, 0.0002])  # a new pick drops the marker
        assert v.anchor_marker is None
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_scene_can_draw_the_anchor():
    from scdm.gui.scene import Scene
    assert hasattr(Scene, "set_anchor_marker")
    assert hasattr(Scene, "clear_anchor_marker")
    assert Scene.ANCHOR_COLOR != Scene.CONFLICT_COLOR


# --- A-7: the screenshot demos ----------------------------------------------

@pytest.mark.parametrize("demo,needle", [("conflict", "冲突"), ("mate", "health=2")])
def test_the_screenshot_demos_run(demo, needle):
    out = os.path.join("_tmp", "shot_%s_test.png" % demo)
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable,
                           os.path.join(_ROOT, "tools", "gui_screenshot.py"),
                           "--out", out, "--demo", demo, "--size", "600x400"],
                          cwd=_ROOT, env=env, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, (proc.stdout, proc.stderr[-800:])
    assert "saved" in proc.stdout, proc.stdout
    assert needle in proc.stdout, proc.stdout
    assert os.path.exists(out)

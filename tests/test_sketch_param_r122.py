"""R122 A-2 + A-3 + A-6 + C: the along-curve anchor in the GUI, retargeting at a
parameter, picking the anchor from the sketch selection, and the screenshot tool.

A-3: `repair_warning(..., to="param:d")` points a dangling dimension at a
     parameter-table entry; the number then follows the table like any expression.
A-2/A-6: the pattern option page carries anchor U/V, and a selected sketch point
     wins over them (the R114 selection set).
C: `tools/gui_screenshot.py` renders the window and paints the GL viewport in,
   so one PNG shows the whole application.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


# --- A-3: retarget at a parameter -------------------------------------------

def test_a_dimension_can_be_retargeted_at_a_parameter():
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = _rect(doc, 0.0, 0.020, "S9_dim5")
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="param:d")
    assert rep["ok"] and "已改指向参数 d" in rep["reason"], rep
    assert sk.constraints[5][3] == "d"
    assert HEALTH.document_warnings(doc, 1000.0) == []
    assert SKM.dimensions(doc, sk.id, 1000.0)[0]["value_mm"] == pytest.approx(5.0)


def test_a_parameter_target_follows_the_table():
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = _rect(doc, 0.0, 0.020, "S9_dim5")
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    assert HEALTH.repair_warning(doc, warn, "retarget", 1000.0,
                                 to="param:d")["ok"]
    doc.param_table.set("d", "12")
    assert SKM.redrive_expressions(doc, 1000.0)["ok"]
    assert SKM.dimensions(doc, sk.id, 1000.0)[0]["value_mm"] == pytest.approx(12.0)


def test_an_unknown_parameter_is_refused():
    doc = KernelDoc()
    doc.param_table = ParamTable()
    sk = _rect(doc, 0.0, 0.020, "S9_dim5")
    warn = HEALTH.document_warnings(doc, 1000.0)[0]
    rep = HEALTH.repair_warning(doc, warn, "retarget", 1000.0, to="param:nope")
    assert rep["ok"] is False and "参数表里没有 nope" in rep["reason"], rep
    assert sk.constraints[5][3] == "S9_dim5"
    no_table = KernelDoc()
    sk2 = _rect(no_table, 0.0, 0.020, "S9_dim5")
    w2 = HEALTH.document_warnings(no_table, 1000.0)[0]
    rep2 = HEALTH.repair_warning(no_table, w2, "retarget", 1000.0, to="param:d")
    assert rep2["ok"] is False and "参数表里没有" in rep2["reason"]
    assert sk2.constraints[5][3] == "S9_dim5"


def test_the_batch_retarget_accepts_a_parameter_target():
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("w", "7")
    a = _rect(doc, 0.0, 0.020, "S9_dim5")
    b = _rect(doc, 0.040, 0.020, "S9_dim5")
    rep = HEALTH.repair_selected(doc, None, 1000.0, action="retarget",
                                 to="param:w")
    assert len(rep["fixed"]) == 2 and rep["skipped"] == [], rep
    assert a.constraints[5][3] == "w" and b.constraints[5][3] == "w"
    assert SKM.dimensions(doc, a.id, 1000.0)[0]["value_mm"] == pytest.approx(7.0)


# --- A-2 + A-6: the anchor in the GUI ---------------------------------------

def _pattern_along(v, doc, sk, count=3):
    """Select the path curve and run the GUI pattern command."""
    v.left.show_options("sketch.pattern")
    v.left.set_checked("sketch.pattern", 1, True)          # 沿曲线阵列
    page = v.left._opt_pages["sketch.pattern"]
    page[3][0].setValue(count)
    assert v._select_sketch_entity([0.010, 0.0002]) is not None
    v.on_command("sketch.pattern")
    return v._prompt.text()


def test_the_anchor_spins_place_the_geometry_on_the_path():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        v.on_command("mode.sketch")
        sk = doc.sketches[-1]
        sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
        sk.curves.append(("rect", (0.005, 0.001, 0.0), (0.007, 0.004, 0.0)))
        v.left.show_options("sketch.pattern")
        v.left.set_checked("sketch.pattern", 2, False)     # 不用选中点
        page = v.left._opt_pages["sketch.pattern"]
        page[2][6].setValue(5.0)                           # 锚点 U=5mm
        page[2][7].setValue(1.0)                           # 锚点 V=1mm
        text = _pattern_along(v, doc, sk)
        assert "沿曲线" in text and "锚点" in text, text
        copies = [c for c in sk.curves if c[0] == "poly"]
        anchors = sorted(round(float(c[1][0][0]), 9) for c in copies)
        assert anchors == [0.010, 0.020], anchors
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_a_selected_sketch_point_wins_over_the_spins():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        v.on_command("mode.sketch")
        sk = doc.sketches[-1]
        sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
        sk.curves.append(("rect", (0.005, 0.001, 0.0), (0.007, 0.004, 0.0)))
        # pick the rect's (5,1)mm corner, then the path line, with Shift
        assert v._select_sketch_entity([0.0051, 0.0011]) is not None
        picked = v.sketch_selection[0]
        assert picked[0] == "point", picked
        assert v._select_sketch_entity([0.010, 0.0002], add=True) is not None
        v.left.show_options("sketch.pattern")
        v.left.set_checked("sketch.pattern", 1, True)
        v.left.set_checked("sketch.pattern", 2, True)       # 锚点用选中草图点
        page = v.left._opt_pages["sketch.pattern"]
        page[3][0].setValue(3)
        page[2][6].setValue(99.0)                          # would be wrong
        v.on_command("sketch.pattern")
        text = v._prompt.text()
        assert "锚点 5, 1mm" in text, text
        copies = [c for c in sk.curves if c[0] == "poly"]
        anchors = sorted(round(float(c[1][0][0]), 9) for c in copies)
        assert anchors == [0.010, 0.020], anchors
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_without_an_anchor_the_path_start_is_used():
    _ensure_app()
    v = _viewer()
    try:
        doc = v.session().kdoc
        v.on_command("mode.sketch")
        sk = doc.sketches[-1]
        sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
        sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.003, 0.0)))
        v.left.show_options("sketch.pattern")
        v.left.set_checked("sketch.pattern", 2, False)
        text = _pattern_along(v, doc, sk)
        assert "锚点" not in text, text
        copies = [c for c in sk.curves if c[0] == "poly"]
        xs = sorted(round(float(c[1][0][0]), 9) for c in copies)
        assert xs == [0.010, 0.020], xs
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- C: the screenshot tool --------------------------------------------------

def test_the_screenshot_tool_writes_a_png():
    from PyQt5.QtGui import QImage
    out = os.path.join("_tmp", "shot_tool_test.png")
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable,
                           os.path.join(_ROOT, "tools", "gui_screenshot.py"),
                           "--out", out, "--demo", "sketch", "--size", "600x400"],
                          cwd=_ROOT, env=env, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, (proc.stdout, proc.stderr[-800:])
    assert "saved" in proc.stdout and "chip=" in proc.stdout, proc.stdout
    assert os.path.exists(out)
    img = QImage(out)
    assert not img.isNull() and img.width() > 200 and img.height() > 200
    assert "自由度" in proc.stdout          # the demo really built the sketch

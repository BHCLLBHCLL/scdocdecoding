"""R124 A-2 + A-3 + A-5: every instance's anchor, the recorded screenshots, and
the pull that sees the sketch its dimensions describe.

A-5: `extrude_active` re-drives the expression rows before it pulls, so the label
     and the body finally agree (a label saying 16mm over a 20mm body is a lie);
     a broken expression is reported instead of silently ignored.
A-2: `pattern_curves(mode="along")` reports where each instance's anchor landed,
     and the window marks them all - then forgets them on the next pick.
A-3: `tools/gui_screenshot.py --check` re-renders the recorded images and fails
     when one no longer shows what its sidecar says it shows.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BOX = os.path.join(_ROOT, "box.scdoc")
_TOOL = os.path.join(_ROOT, "tools", "gui_screenshot.py")
_SHOTS = os.path.join(_ROOT, "docs", "screenshots")
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


def _mm3(w, h, t):
    return w * h * t * 1e-9


def _rect(doc, width="0.020", height=8.0, t_mm=5.0):
    """A 20x8 mm rectangle whose width is a number or an expression."""
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0],
                               [0.020, height / 1000.0], [0.0, height / 1000.0]]))
    sk.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, width), (S.DIST, 1, 2, height / 1000.0),
    ])
    return sk


def _run_tool(*args, timeout=600):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, _TOOL] + list(args), cwd=_ROOT,
                          env=env, capture_output=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


# --- A-5: the pull sees the sketch its dimensions describe -------------------

def test_a_clean_sketch_reports_that_nothing_needed_redriving():
    doc = KernelDoc()
    _rect(doc, 0.020)                       # a plain number, nothing to re-drive
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert rep["redrive"] == {"ok": True, "redriven": 0, "reason": ""}
    assert K.volume(rep["bodies"][0].shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)


def test_a_broken_expression_still_pulls_the_drawn_loop():
    doc = KernelDoc()
    _rect(doc, "2*nope")                    # no such parameter: the row is broken
    rep = SKM.extrude_active(doc, 5.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert rep["redrive"]["ok"] is False and rep["redrive"]["reason"], rep["redrive"]
    # the drawn geometry is still what gets pulled - the refusal is not a crash
    assert K.volume(rep["bodies"][0].shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)


# --- A-2: one anchor per instance -------------------------------------------

def test_the_along_pattern_reports_one_anchor_per_instance():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.030, 0.0, 0.0)))
    sk.curves.append(("rect", (0.0, 0.0, 0.0), (0.002, 0.003, 0.0)))
    path, why = S.path_points(sk, [0])
    assert path, why
    rep = S.pattern_curves(sk, 4, mode="along", path=path)
    assert rep["ok"], rep["reason"]
    assert len(rep["anchors"]) == 4, rep["anchors"]
    xs = [round(float(a[0]), 9) for a in rep["anchors"]]
    assert xs == [0.0, 0.010, 0.020, 0.030], xs      # evenly spaced along the path
    assert rep["step"] == pytest.approx(0.010)


def test_the_first_anchor_is_the_one_the_caller_chose():
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("line", (0.0, 0.0, 0.0), (0.030, 0.0, 0.0)))
    sk.curves.append(("rect", (0.010, 0.001, 0.0), (0.012, 0.004, 0.0)))
    path, why = S.path_points(sk, [0])
    assert path, why
    rep = S.pattern_curves(sk, 3, mode="along", path=path, offset=0.005,
                           anchor=(0.010, 0.001))
    assert rep["ok"], rep["reason"]
    assert rep["anchor"] == [pytest.approx(0.010), pytest.approx(0.001)]
    got = [(round(float(a[0]), 9), round(float(a[1]), 9)) for a in rep["anchors"]]
    assert got == [(0.010, 0.001), (0.0175, 0.0), (0.030, 0.0)], got
    # the geometry follows its anchor: the original keeps the chosen point and
    # every copy lands on the path, exactly where the report said it would
    boxes = sorted((round(float(c[1][0][0]), 9), round(float(c[1][0][1]), 9))
                   for c in sk.curves if c[0] == "poly")
    assert boxes == got[1:], (boxes, got)


def test_the_window_marks_every_instance_and_forgets_them_on_a_new_pick():
    v = _viewer()
    try:
        doc = v.session().kdoc
        v.on_command("mode.sketch")
        sk = doc.sketches[-1]
        sk.curves.append(("line", (0.0, 0.0, 0.0), (0.020, 0.0, 0.0)))
        sk.curves.append(("rect", (0.005, 0.001, 0.0), (0.007, 0.004, 0.0)))
        v.left.show_options("sketch.pattern")
        v.left.set_checked("sketch.pattern", 1, True)      # 沿曲线阵列
        v.left.set_checked("sketch.pattern", 2, False)     # 不用选中点
        page = v.left._opt_pages["sketch.pattern"]
        page[3][0].setValue(3)
        page[2][6].setValue(5.0)                           # 锚点 U=5mm
        page[2][7].setValue(1.0)                           # 锚点 V=1mm
        assert v._select_sketch_entity([0.010, 0.0002]) is not None
        v.on_command("sketch.pattern")
        text = v._prompt.text()
        assert "沿曲线" in text and "锚点" in text, text
        assert len(v.anchor_markers) == 3, v.anchor_markers
        assert v.anchor_markers[0] == (pytest.approx(0.005), pytest.approx(0.001))
        assert v.anchor_markers[-1] == (pytest.approx(0.020), pytest.approx(0.0))
        assert v.anchor_marker == (pytest.approx(0.005), pytest.approx(0.001))
        # a new selection belongs to a different pattern, so the marks go away
        assert v._select_sketch_entity([0.012, 0.0002]) is not None
        assert v.anchor_markers == [] and v.anchor_marker is None
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_scene_draws_one_marker_or_a_whole_list_of_them():
    """The viewport side of A-2, without a GL window (offscreen has no scene)."""
    from scdm.gui.scene import Scene

    class _Fake:
        def __init__(self):
            self.actors = []

        def AddActor(self, a):
            self.actors.append(a)

        def RemoveActor(self, a):
            self.actors.remove(a)

    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sc = Scene.__new__(Scene)                 # no GL context: only the marker path
    sc.renderer = _Fake()
    sc._anchor_actors = []
    sc.set_anchor_marker(sk, [0.005, 0.001])
    assert len(sc._anchor_actors) == 1 and len(sc.renderer.actors) == 1
    sc.set_anchor_marker(sk, [[0.005, 0.001], [0.010, 0.0], [0.020, 0.0]])
    assert len(sc._anchor_actors) == 1, "one actor draws every anchor"
    assert len(sc.renderer.actors) == 1
    sc.clear_anchor_marker()
    assert sc._anchor_actors == [] and sc.renderer.actors == []


def test_a_point_marker_is_actually_drawable():
    """R124: a polydata that holds points and no cells renders **nothing**.

    The marker was in the renderer and invisible on screen, which is worse than
    no marker: the code says it drew one.  Vertex cells make it a primitive.
    """
    import vtk
    from vtkmodules.util import numpy_support
    from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter
    from scdm.gui.scene import _points_actor

    act = _points_actor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], (1.0, 0.0, 0.0), 14)
    pd = act.GetMapper().GetInput()
    assert pd.GetNumberOfPoints() == 2
    assert pd.GetNumberOfCells() == 2, "points without cells are never drawn"
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.0, 0.0, 0.0)
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.AddRenderer(ren)
    rw.SetSize(120, 120)
    ren.AddActor(act)
    ren.ResetCamera()
    rw.Render()
    w2i = vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    img = w2i.GetOutput()
    w, h, _ = img.GetDimensions()
    px = numpy_support.vtk_to_numpy(img.GetPointData().GetScalars())
    assert int((px.reshape(h, w, -1)[:, :, 0] > 120).sum()) > 0, "no pixels drawn"


# --- A-3: the recorded screenshots ------------------------------------------

def test_the_committed_screenshots_still_show_what_they_claim():
    """`--check` re-renders each recorded image and compares its sidecar.

    Pixels are not compared (they differ per platform); what is compared is the
    scenario, the mode chip and the health count, so a stale image is caught and
    a different font is not.
    """
    proc = _run_tool("--check", "--dir", _SHOTS)
    assert proc.returncode == 0, (proc.stdout, proc.stderr[-800:])
    assert "0 stale" in proc.stdout, proc.stdout
    assert "ok    " in proc.stdout, proc.stdout


def test_a_drifted_screenshot_is_caught():
    room = os.path.join(_ROOT, "_tmp", "shots_r124")
    os.makedirs(room, exist_ok=True)
    with open(os.path.join(room, "drifted.json"), "w", encoding="utf-8") as fh:
        json.dump({"file": "drifted.png", "demo": "solid", "model": "box.scdoc",
                   "size_arg": "600x400", "size": [600, 400], "3d": False,
                   "chip": "不是这个", "health": 0}, fh, ensure_ascii=False)
    proc = _run_tool("--check", "--dir", room)
    assert proc.returncode == 1, (proc.stdout, proc.stderr[-800:])
    assert "stale" in proc.stdout and "1 stale" in proc.stdout, proc.stdout

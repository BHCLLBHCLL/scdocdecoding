"""R110: circle radii and expression dimensions, plus the document's active sketch.

A-1: a circle is driven through its handle distance *or* a RADIUS constraint - the
     solved radius is written back into the curve (before this, driving a circle
     moved the handle but left the stored radius alone, so it never grew).
A-2: a dimension may be an expression ("2*d"), stored as written and resolved
     against the parameter table, in millimetres; changing the table re-drives it.
A-5: the document remembers the sketch being edited, so it survives save/load.
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
from scdm import sketch as S  # noqa: E402
from scdm import sketchmode as SKM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.params import ParamTable  # noqa: E402
from scdm.sketch_solver import RADIUS  # noqa: E402


def _circle_doc(r_mm=2.0, t_mm=10.0, constraint=None):
    doc = KernelDoc()
    sk = doc.add_sketch("xy")
    sk.curves.append(("circle", (0.0, 0.0), r_mm / 1000.0))
    if constraint == "radius":
        sk.constraints.append((RADIUS, 0, r_mm / 1000.0))
    elif constraint == "dist":
        sk.constraints.append((S.DIST, 0, 1, r_mm / 1000.0))
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"], rep["reason"]
    return doc, sk, rep["bodies"][0]


def _cyl_volume(r_mm, t_mm):
    return math.pi * (r_mm / 1000.0) ** 2 * (t_mm / 1000.0)


def _rect_doc(t_mm=5.0, expr="2*d", d=5.0):
    doc = KernelDoc()
    doc.param_table = ParamTable()
    doc.param_table.set("d", str(d))
    sk = doc.add_sketch("xy")
    sk.curves.append(("poly", [[0.0, 0.0], [0.010, 0.0],
                               [0.010, 0.008], [0.0, 0.008]]))
    sk.constraints.extend([
        (S.FIXED, 0, 0.0, 0.0),
        (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, expr), (S.DIST, 1, 2, 0.008),
    ])
    rep = SKM.extrude_active(doc, t_mm, 1000.0)
    assert rep["ok"], rep["reason"]
    return doc, sk, rep["bodies"][0]


def _mm3(w, h, t):
    return w * h * t * 1e-9


# --- A-1: circle radii ------------------------------------------------------

def test_a_circle_is_driven_through_its_handle_distance():
    doc, sk, body = _circle_doc(2.0, constraint="dist")
    assert SKM.dimensions(doc, sk.id, 1000.0)[0]["value_mm"] == pytest.approx(2.0)

    rep = SKM.set_dimension(doc, sk.id, 0, 3.0, 1000.0)
    assert rep["ok"], rep["reason"]
    assert sk.curves[0][2] == pytest.approx(0.003, rel=1e-6)   # the radius moved
    assert SKM.sync_sketch_bodies(doc, sk.id, 1000.0)["updated"] == [body.id]
    assert K.volume(body.shape) == pytest.approx(_cyl_volume(3.0, 10.0), rel=1e-6)


def test_a_radius_constraint_is_listed_and_driven():
    doc, sk, body = _circle_doc(2.0, constraint="radius")
    dims = SKM.dimensions(doc, sk.id, 1000.0)
    assert [(d["kind"], round(d["value_mm"], 6)) for d in dims] == [("radius", 2.0)]
    assert dims[0]["label"] == "半径 2mm"

    rep = SKM.set_dimension(doc, sk.id, 0, 3.5, 1000.0)
    assert rep["ok"], rep["reason"]
    assert sk.curves[0][2] == pytest.approx(0.0035, rel=1e-9)
    assert SKM.sync_sketch_bodies(doc, sk.id, 1000.0)["updated"] == [body.id]
    assert K.volume(body.shape) == pytest.approx(_cyl_volume(3.5, 10.0), rel=1e-6)


def test_numeric_dimensions_are_reported_in_millimetres():
    """The stored number is metres; the reported value must be millimetres."""
    doc, sk, _body = _circle_doc(2.0, constraint="radius")
    sk.constraints.append((S.DIST, 0, 1, 0.002))          # 2 mm, stored in metres
    rows = {d["index"]: d for d in SKM.dimensions(doc, sk.id, 1000.0)}
    assert rows[1]["value_mm"] == pytest.approx(2.0)
    assert rows[1]["expr"] is None


# --- A-2: expression dimensions --------------------------------------------

def test_an_expression_dimension_drives_and_re_resolves():
    doc, sk, body = _rect_doc(d=5.0)                      # 2*d = 10 mm
    rows = {d["index"]: d for d in SKM.dimensions(doc, sk.id, 1000.0)}
    assert rows[5]["expr"] == "2*d" and rows[5]["value_mm"] == pytest.approx(10.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(10, 8, 5), rel=1e-6)

    # a parameter change re-drives every expression dimension (R110/A-2)
    doc.param_table.set("d", "10")
    redrive = SKM.redrive_expressions(doc, 1000.0)
    assert redrive["ok"] and redrive["redriven"] == 1
    SKM.sync_sketch_bodies(doc, sk.id, 1000.0)
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)
    # the stored row still carries the expression, not its resolution
    assert sk.constraints[5][3] == "2*d"


def test_a_bad_expression_is_refused_and_rolled_back():
    doc, sk, body = _rect_doc(d=5.0)
    before = K.volume(body.shape)
    saved = list(sk.constraints)
    rep = SKM.set_dimension(doc, sk.id, 5, "2*nope", 1000.0)
    assert rep["ok"] is False and "表达式无法求值" in rep["reason"]
    assert list(sk.constraints) == saved
    assert K.volume(body.shape) == pytest.approx(before, rel=1e-12)


# --- A-5: the active sketch survives a reload -------------------------------

def test_the_active_sketch_survives_the_project_round_trip():
    doc, sk, body = _circle_doc(2.0, constraint="dist")
    assert doc.active_sketch == sk.id
    d = Path(tempfile.mkdtemp(prefix="r110_"))
    try:
        path = d / "active.scdm"
        IO.save_scdm(str(path), doc)
        back = IO.load_scdm(str(path))
        assert back.active_sketch == sk.id
        active, why = SKM.resolve_active(back, None)      # no GUI session at all
        assert active is not None and active.id == sk.id, why
        # and the reloaded document can still drive it
        rep = SKM.set_dimension(back, sk.id, 0, 4.0, 1000.0)
        assert rep["ok"], rep["reason"]
        assert SKM.sync_sketch_bodies(back, sk.id, 1000.0)["updated"] == [body.id]
        assert K.volume(back.bodies[0].shape) == pytest.approx(
            _cyl_volume(4.0, 10.0), rel=1e-6)
    finally:
        shutil.rmtree(str(d), ignore_errors=True)


def test_resolve_active_prefers_the_session_then_the_document():
    doc = KernelDoc()
    first = doc.add_sketch("xy")
    second = doc.add_sketch("xy")
    doc.active_sketch = second.id
    assert SKM.resolve_active(doc, None)[0] is second
    ses = SKM.SketchSession(sketch_id=first.id, plane="xy")
    assert SKM.resolve_active(doc, ses)[0] is first


# --- the GUI hook -----------------------------------------------------------

def test_the_parameter_dialog_re_drives_sketches():
    """apply_param_text must re-solve expression dimensions after a table change."""
    from scdm.gui import params as PG
    doc, sk, body = _rect_doc(d=5.0)
    rep = PG.apply_param_text(doc, "d = 10", "", 1000.0)
    assert rep["errors"] == []
    assert (rep.get("redrive") or {}).get("redriven") == 1
    assert K.volume(body.shape) == pytest.approx(_mm3(20, 8, 5), rel=1e-6)

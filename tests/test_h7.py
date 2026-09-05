"""H7: parameter-driven expressions + SpaceClaim-style script API."""
from __future__ import annotations

import math

import pytest

from scdm import kernel as K
from scdm.params import ParamTable, eval_expr, param_box

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


# -- expression engine ------------------------------------------------------
def test_eval_expr_arithmetic():
    assert eval_expr("2 + 3 * 4", {}) == 14
    assert eval_expr("(2 + 3) * 4", {}) == 20


def test_paramtable_dependency_resolution():
    t = ParamTable()
    t.set("width", 20.0)
    t.set("height", "width * 2")
    t.set("depth", "height / 4 + pi")
    r = t.resolve()
    assert r["height"] == 40.0
    assert r["depth"] == pytest.approx(10.0 + math.pi)


def test_paramtable_propagation():
    t = ParamTable()
    t.set("w", 20.0)
    t.set("h", "w * 1.5")
    t.set("w", 40.0)
    assert t.resolve()["h"] == pytest.approx(60.0)


def test_paramtable_rejects_unknown_ref():
    t = ParamTable()
    t.set("x", "nope + 1")
    with pytest.raises(ValueError):
        t.resolve()


def test_paramtable_rejects_cycles():
    t = ParamTable()
    t.set("a", "b + 1")
    t.set("b", "a + 1")
    with pytest.raises(ValueError):
        t.resolve()


def test_paramtable_rejects_injection():
    t = ParamTable()
    t.set("x", "__import__('os').system('echo pwn')")
    with pytest.raises(ValueError):
        t.resolve()


# -- parametric body driven by global table ---------------------------------
def test_parametric_expression_rebuild():
    t = ParamTable()
    t.set("w", 20.0)
    t.set("h", "w * 1.5")
    p = param_box("P", w=20.0, h=30.0, d=10.0)
    p.table = t
    p.set(W="w", H="h")
    assert p.resolve_params()["W"] == 20.0
    v0 = K.volume(p.build(1000.0))
    t.set("w", 40.0)
    v1 = K.volume(p.build(1000.0))
    assert v1 == pytest.approx(v0 * 4, rel=1e-9)   # 2x width, 2x height


# -- script API facade -------------------------------------------------------
def test_script_api_end_to_end():
    from scdm.kdoc import KernelDoc
    from scdm.script_api import ScriptSession

    doc = KernelDoc()
    s = ScriptSession(doc)
    part = s.GetRootPart()
    box = s.AddBox(20, 20, 20, name="Base")
    s.SetParameter("width", 20.0)
    s.SetParameter("height", "width / 2")
    boss = s.AddCylinder(5, s.GetParameter("height"), name="Boss")
    s.CombineUnite(box, boss)
    assert [b.Name for b in part.GetBodies()] == ["Base", "Boss"]
    s.SetParameter("width", 40.0)
    assert s.GetParameter("height") == pytest.approx(20.0)
    assert s.GetBodyByName("Base") is not None


def test_script_api_move_and_fillet():
    from scdm.kdoc import KernelDoc
    from scdm.script_api import ScriptSession

    doc = KernelDoc()
    s = ScriptSession(doc)
    b = s.AddBox(10, 10, 10, name="B")
    s.MoveBody(b, 5, 0, 0)
    faces = b.GetFaces()
    assert len(faces) == 6
    s.FilletEdges(b, 1.0, edge_indices=[0])
    assert b.Volume < 10 ** 3 / 1000 ** 3   # fillet removes material


# -- scripting OPS coverage ---------------------------------------------------
def test_scripting_new_ops_replay():
    from scdm.kdoc import KernelDoc
    from scdm.scripting import OPS, replay

    for cmd in ("insert.box", "sheet.bend", "sheet.unfold",
                "surface.thicken", "surface.offset", "surface.untrim",
                "repair.check"):
        assert cmd in OPS, cmd
    doc = KernelDoc()
    msgs = replay([
        {"cmd": "insert.box", "opts": {"w": 20, "h": 20, "d": 20,
                                       "name": "Base"}},
        {"cmd": "sheet.bend", "opts": {"create": True, "width": 20,
                                       "thickness": 1, "flat1": 30,
                                       "flat2": 20}},
        {"cmd": "sheet.unfold", "opts": {"k": 0.42}},
        {"cmd": "surface.thicken", "opts": {"thickness": 0.5, "face": 0}},
    ], doc, scale=1000.0)
    assert all(m.startswith("OK") for m in msgs), msgs

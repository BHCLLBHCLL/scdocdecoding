"""P311/R58: conical/axial bend wiring - ops, catalog+live, replay, GUI path."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sheetmetal as SM  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402

ANG = math.radians(90.0)
T = 0.002


def _conical():
    return {"angle": 90.0, "thickness": 1.0, "height": 30.0, "r1": 20.0,
            "r2": 30.0, "k": 0.42}


def _axial():
    return {"length": 80.0, "width": 30.0, "thickness": 1.0, "flange": 10.0,
            "angle": 90.0, "r_inner": 2.0, "k": 0.42}


def test_p311_conical_and_axial_are_registered_and_live():
    assert "sheet.conical" in OPS and "sheet.axial" in OPS
    from scdm.catalog import M5_LIVE, all_commands
    ids = {c.id for c in all_commands()}
    assert {"sheet.conical", "sheet.axial"} <= ids
    assert {"sheet.conical", "sheet.axial"} <= M5_LIVE


def test_p311_op_volumes_are_closed_form():
    # the ops take mm: 1.0 mm thickness -> t = 0.001 m
    t = 0.001
    kdoc = KernelDoc()
    body, msg = OPS["sheet.conical"](kdoc, _conical(), 1000.0)
    want = ANG * ((0.02 + 0.03) / 2.0 + t / 2.0) * t * 0.03
    assert K.volume(body.shape) == pytest.approx(want, rel=1e-9)
    assert "圆锥折弯" in msg and kdoc.bodies[0] is body
    doc2 = KernelDoc()
    ub, msg2 = OPS["sheet.axial"](doc2, _axial(), 1000.0)
    base = 0.08 * 0.03 * t
    flange = ANG * (0.002 + t / 2.0) * t * 0.08
    assert K.volume(ub.shape) == pytest.approx(base + 2.0 * flange, rel=1e-9)
    assert "轴向折弯" in msg2


def test_p311_replay_is_reproducible():
    steps = [{"cmd": "sheet.conical", "opts": _conical()},
             {"cmd": "sheet.axial", "opts": _axial()}]
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        replay(steps, doc, 1000.0)
        vols.append(tuple(K.volume(b.shape) for b in doc.bodies))
    t = 0.001
    want = (ANG * ((0.02 + 0.03) / 2.0 + t / 2.0) * t * 0.03,
            0.08 * 0.03 * t + 2.0 * ANG * (0.002 + t / 2.0) * t * 0.08)
    for got, exp in zip(vols[0], want):
        assert got == pytest.approx(exp, rel=1e-9)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)

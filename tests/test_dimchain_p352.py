"""P352/R69: dimension chains and tolerance stack-up.

Closed forms: the chain sum equals the span from the first start to the last end,
worst-case stacking is the sum of the limits and statistical stacking is the RSS.
Breaks and axis violations are a countable verdict, and the total dimension's
label comes from the same dim_text() the canvas and both exports use (rule 84).
"""
from __future__ import annotations

import math
import os
import tempfile

import pytest

from scdm import dimchain as DC
from scdm import drawing as D

MM = 1000.0


def mk(x0, x1, value, tol=0.0, axis="h", y=0.0):
    d = D.Dimension("前视", axis, value, (x0, y), (x1, y), 0.01)
    d.tol = tol
    return d


def _chain():
    return [mk(0.0, 0.02, 20.0, 0.1), mk(0.02, 0.05, 30.0, 0.2),
            mk(0.05, 0.10, 50.0, 0.3)]


def test_p352_chain_sum_is_closed_form():
    v = DC.check_chain(_chain())
    assert v["ok"] is True and v["count"] == 3
    assert v["order"] == [0, 1, 2]
    assert v["sum"] == pytest.approx(100.0, rel=1e-12)
    assert v["span"] == pytest.approx(100.0, rel=1e-12)     # 0.10 m in mm
    assert v["mismatch"] == pytest.approx(0.0, abs=1e-12)
    assert v["breaks"] == [] and v["violations"] == []
    # a shuffled input still chains (order is derived, not assumed)
    shuffled = DC.check_chain([_chain()[2], _chain()[0], _chain()[1]])
    assert shuffled["ok"] is True and shuffled["order"] == [1, 2, 0]
    assert shuffled["sum"] == pytest.approx(100.0, rel=1e-12)


def test_p352_stack_up_worst_and_rss_are_closed_form():
    worst = DC.stack_up(_chain(), "worst")
    rss = DC.stack_up(_chain(), "rss")
    assert worst["tol"] == pytest.approx(0.6, rel=1e-15)          # 0.1+0.2+0.3
    assert rss["tol"] == pytest.approx(math.sqrt(0.14), rel=1e-15)
    assert worst["sum"] == rss["sum"] == pytest.approx(100.0, rel=1e-15)
    assert worst["count"] == 3 and worst["max_tol"] == 0.3
    assert worst["mode"] == "worst" and rss["mode"] == "rss"
    # the Chinese aliases are accepted, and the total dimension carries the stack
    assert DC.stack_up(_chain(), "极值")["tol"] == pytest.approx(0.6, rel=1e-15)
    assert DC.stack_up(_chain(), "统计")["tol"] == pytest.approx(math.sqrt(0.14),
                                                                 rel=1e-15)
    total = DC.chain_dimension(_chain())
    assert total.value_mm == pytest.approx(100.0, rel=1e-12)
    assert total.tol == pytest.approx(0.6, rel=1e-15)
    assert total.a == (0.0, 0.0) and total.b == (0.10, 0.0)
    assert D.dim_text(total) == "100.0 ±0.6"
    assert DC.chain_dimension(_chain(), mode="rss").tol == pytest.approx(
        math.sqrt(0.14), rel=1e-15)


def test_p352_breaks_and_axis_violations_are_countable():
    broken = DC.check_chain([mk(0.0, 0.02, 20.0), mk(0.03, 0.05, 20.0)])
    assert broken["ok"] is False
    assert len(broken["breaks"]) == 1
    b = broken["breaks"][0]
    assert b["after"] == 0 and b["at"] == 1
    assert b["gap"] == pytest.approx(10.0, rel=1e-12)     # mm, comparable
    assert broken["mismatch"] == pytest.approx(10.0, rel=1e-12)
    mixed = DC.check_chain([mk(0.0, 0.02, 20.0), mk(0.02, 0.05, 30.0, axis="v")])
    assert mixed["ok"] is False
    assert [x["reason"] for x in mixed["violations"]] == ["axis"]
    # a broken run cannot be annotated as a total
    with pytest.raises(ValueError):
        DC.chain_dimension([mk(0.0, 0.02, 20.0), mk(0.03, 0.05, 20.0)])
    assert "断口 1 处" in DC.describe(broken)
    assert "3 段" in DC.describe(DC.check_chain(_chain()))


def test_p352_illegal_inputs():
    with pytest.raises(ValueError):
        DC.check_chain([])
    with pytest.raises(ValueError):
        DC.stack_up([])
    with pytest.raises(ValueError):
        DC.check_chain([mk(0.0, 0.02, -1.0)])
    with pytest.raises(ValueError):
        DC.check_chain([mk(0.0, 0.02, 20.0, tol=-0.1)])
    with pytest.raises(ValueError):
        DC.stack_up(_chain(), "monte-carlo")
    with pytest.raises(ValueError):
        DC.check_chain(_chain(), axis="x")


def test_p352_chain_labels_reach_both_exports():
    view = ("前视", [[(0.0, 0.0), (0.10, 0.0), (0.10, 0.02), (0.0, 0.02),
                     (0.0, 0.0)]])
    dims = _chain() + [DC.chain_dimension(_chain())]
    tmp = tempfile.mkdtemp(prefix="p352_")
    try:
        svg = os.path.join(tmp, "s.svg")
        dxf = os.path.join(tmp, "s.dxf")
        D.svg_sheet([view], svg, dimensions=dims)
        D.write_dxf([view], dxf, dimensions=dims)
        svg_text = open(svg, encoding="utf-8").read()
        dxf_text = open(dxf, encoding="utf-8").read()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    # the total label (value + stacked tolerance) is in BOTH exports, once
    assert "100.0 ±0.6" in svg_text
    assert "100.0 ±0.6" in dxf_text
    assert "30.0 ±0.2" in svg_text and "30.0 ±0.2" in dxf_text

"""P283/R51: beam wiring - op, feature label/dispatch, catalog+live, replay."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import beams as BEAMS  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm.features import Feature, FeatureStack  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402


def test_p283_beam_is_registered_labelled_and_live():
    assert "create.beam" in OPS
    f = Feature(op="beam", params={"profile": "i", "length": 200.0,
                                   "spec": "工字钢 I 100×50×5×7"})
    assert f.label() == "梁 工字钢 I 100×50×5×7"
    from scdm.catalog import M4_LIVE, all_commands, live_commands
    ids = {c.id for c in all_commands()}
    assert "create.beam" in ids
    assert "create.beam" in M4_LIVE
    # the weldment half of the domain is an explicit, non-live placeholder
    assert "weld.symbol" in ids
    assert "weld.symbol" not in live_commands()


def test_p283_beam_op_creates_the_closed_form_solid():
    kdoc = KernelDoc()
    body, msg = OPS["create.beam"](kdoc, {"profile": "pipe", "d": 60.0,
                                          "t": 3.0, "length": 200.0}, 1000.0)
    cf = BEAMS.closed_form("pipe", d=0.06, t=0.003)
    assert K.volume(body.shape) == pytest.approx(cf["area"] * 0.2, rel=1e-9)
    assert "圆管" in body.name and "圆管" in msg
    assert kdoc.bodies and kdoc.bodies[0] is body


def test_p283_beam_feature_dispatch_rebuilds_the_same_solid():
    stack = FeatureStack()
    stack.add("beam", profile="l", a=50.0, b=40.0, t=5.0, length=120.0,
              spec="角钢 50×40×5")
    out = stack.apply(K.make_box(0.001, 0.001, 0.001))
    cf = BEAMS.closed_form("l", a=0.05, b=0.04, t=0.005)
    assert K.volume(out) == pytest.approx(cf["area"] * 0.12, rel=1e-9)


def test_p283_beam_replay_is_reproducible():
    steps = [{"cmd": "create.beam",
              "opts": {"profile": "i", "h": 100.0, "b": 50.0, "tw": 5.0,
                       "tf": 7.0, "length": 200.0}}]
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        replay(steps, doc, 1000.0)
        vols.append(K.volume(doc.bodies[0].shape))
    cf = BEAMS.closed_form("i", h=0.1, b=0.05, tw=0.005, tf=0.007)
    assert vols[0] == pytest.approx(cf["area"] * 0.2, rel=1e-9)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)
    assert len(K.explore(doc.bodies[0].shape, "solid")) == 1

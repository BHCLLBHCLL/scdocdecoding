"""P291/R53: polyline beam wiring - op, feature label/dispatch, catalog, replay."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import beams as BEAMS  # noqa: E402
from scdm import kernel as K  # noqa: E402
from scdm.features import Feature, FeatureStack  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402

PTS_MM = [[0.0, 0.0, 0.0], [120.0, 0.0, 0.0], [120.0, 90.0, 0.0]]
I_MM = {"h": 100.0, "b": 50.0, "tw": 5.0, "tf": 7.0}
TOTAL_M = 0.21


def _area():
    return BEAMS.closed_form("i", **{k: v / 1000.0 for k, v in I_MM.items()})["area"]


def _opts():
    return {"profile": "i", "points": PTS_MM, **I_MM}


def test_p291_polyline_beam_is_registered_labelled_and_live():
    assert "create.beam_polyline" in OPS
    f = Feature(op="beam_polyline",
                params={"spec": "工字钢 I 100×50×5×7", "index": 2, "count": 2})
    assert f.label() == "折线梁 工字钢 I 100×50×5×7 段2/2"
    from scdm.catalog import M4_LIVE, all_commands
    assert "create.beam_polyline" in {c.id for c in all_commands()}
    assert "create.beam_polyline" in M4_LIVE


def test_p291_op_creates_one_body_per_member_and_records_the_group():
    kdoc = KernelDoc()
    body, msg = OPS["create.beam_polyline"](kdoc, _opts(), 1000.0)
    assert len(kdoc.bodies) == 2
    assert len(kdoc.weldments) == 1
    weld = kdoc.weldments[0]
    assert weld.total_length() == pytest.approx(TOTAL_M, rel=1e-12)
    assert sum(K.volume(b.shape) for b in kdoc.bodies) == pytest.approx(
        _area() * TOTAL_M, rel=1e-9)
    assert body is kdoc.bodies[0] and "折线梁" in msg
    params = kdoc.feature_stack(body.id).as_dict()[-1]
    assert params["op"] == "beam_polyline"
    assert params["params"]["count"] == 2
    assert params["params"]["index"] == 1


def test_p291_member_feature_dispatch_rebuilds_the_member():
    stack = FeatureStack()
    # feature params are mm, exactly as op_beam_polyline records them
    stack.add("beam_polyline", profile="i", p0=[0.0, 0.0, 0.0],
              p1=[120.0, 0.0, 0.0], spec="工字钢 I 100×50×5×7", index=1, count=2,
              **I_MM)
    out = stack.apply(K.make_box(0.001, 0.001, 0.001))
    assert K.volume(out) == pytest.approx(_area() * 0.12, rel=1e-9)


def test_p291_polyline_replay_is_reproducible():
    steps = [{"cmd": "create.beam_polyline", "opts": _opts()}]
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        replay(steps, doc, 1000.0)
        vols.append(sum(K.volume(b.shape) for b in doc.bodies))
        assert len(doc.weldments) == 1
    assert vols[0] == pytest.approx(_area() * TOTAL_M, rel=1e-9)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)

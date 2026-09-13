"""P278/R50: knockout wiring - op, feature label/dispatch, catalog+live, replay."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.features import Feature  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402


def _top_face_index(shape):
    best = None
    for i, f in enumerate(K.explore(shape, "face")):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1]):
            best = (i, c[2])
    return best[0] if best else 0


def _removed_volume(diameter_mm, web_mm, web_count, t=0.002):
    R = diameter_mm / 2000.0
    r = R - web_mm / 1000.0
    return (math.pi * (R * R - r * r) - web_count * (web_mm / 1000.0) ** 2) * t


def test_p278_knockout_is_registered_labelled_and_live():
    assert "create.knockout" in OPS
    f = Feature(op="knockout", params={"diameter": 10.0, "web": 1.0,
                                       "web_count": 4})
    assert "敲落" in f.label()
    from scdm.catalog import M4_LIVE, all_commands
    assert "create.knockout" in {c.id for c in all_commands()}
    # rule 55: implementation + catalog + live set - miss one and it is
    # unreachable from the ribbon
    assert "create.knockout" in M4_LIVE


def test_p278_knockout_feature_dispatch_rebuilds_the_same_volume():
    box = K.make_box(0.02, 0.02, 0.002)
    stack_face = _top_face_index(box)
    from scdm.features import FeatureStack
    from scdm.features import selector_for
    faces = K.explore(box, "face")
    sel = selector_for(box, faces[stack_face])
    stack = FeatureStack()
    stack.add("knockout", selector=sel, diameter=10.0, web=1.0, web_count=4)
    out = stack.apply(box)
    removed = K.volume(box) - K.volume(out)
    assert removed == pytest.approx(_removed_volume(10.0, 1.0, 4), rel=1e-9)


def test_p278_knockout_op_closed_form():
    kdoc = KernelDoc()
    body = kdoc.add_body(K.make_box(0.02, 0.02, 0.002), name="B")
    v0 = K.volume(body.shape)
    OPS["create.knockout"](kdoc, {"target": "last",
                                  "face_i": _top_face_index(body.shape),
                                  "diameter": 10.0, "web": 1.0,
                                  "web_count": 4}, 1000.0)
    removed = v0 - K.volume(body.shape)
    assert removed == pytest.approx(_removed_volume(10.0, 1.0, 4), rel=1e-9)


def test_p278_knockout_replay_is_reproducible():
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, 0.002), name="B")
        v0 = K.volume(body.shape)
        replay([{"cmd": "create.knockout",
                 "opts": {"target": "last",
                          "face_i": _top_face_index(body.shape),
                          "diameter": 10.0, "web": 1.0, "web_count": 4}}],
               doc, 1000.0)
        vols.append(v0 - K.volume(body.shape))
    assert vols[0] == pytest.approx(_removed_volume(10.0, 1.0, 4), rel=1e-9)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)

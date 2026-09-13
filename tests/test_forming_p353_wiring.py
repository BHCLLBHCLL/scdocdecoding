"""P353/R70: cross-break wiring - op, feature label/dispatch, catalog, replay."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.features import Feature, FeatureStack, selector_for  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402

T = 0.002


def _top_face_index(shape):
    best = None
    for i, f in enumerate(K.explore(shape, "face")):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1]):
            best = (i, c[2])
    return best[0] if best else 0


def test_p353_cross_break_is_registered_labelled_and_live():
    assert "sheet.cross_break" in OPS
    f = Feature(op="cross_break", params={"kind": "v", "length": 10.0,
                                          "width": 2.0, "depth": 0.3})
    assert f.label() == "压筋 v 10×2×0.3"
    from scdm.catalog import M5_LIVE, all_commands
    assert "sheet.cross_break" in {c.id for c in all_commands()}
    assert "sheet.cross_break" in M5_LIVE


def test_p353_op_and_feature_dispatch_are_closed_form():
    for kind, expect in (("v", 0.5 * 0.002 * 0.0003 * 0.010),
                         ("arc", K.arc_segment_area(0.002, 0.0003) * 0.010)):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, T), name="B")
        v0 = K.volume(body.shape)
        OPS["sheet.cross_break"](doc, {"target": "last",
                                       "face_i": _top_face_index(body.shape),
                                       "kind": kind, "length": 10.0,
                                       "width": 2.0, "depth": 0.3}, 1000.0)
        assert (v0 - K.volume(body.shape)) == pytest.approx(expect, rel=1e-9), kind
        box = K.make_box(0.02, 0.02, T)
        sel = selector_for(box, K.explore(box, "face")[_top_face_index(box)])
        stack = FeatureStack()
        stack.add("cross_break", selector=sel, kind=kind, length=10.0,
                  width=2.0, depth=0.3)
        out = stack.apply(box)
        assert (K.volume(box) - K.volume(out)) == pytest.approx(expect,
                                                                rel=1e-9), kind


def test_p353_replay_is_reproducible():
    steps = [{"cmd": "sheet.cross_break",
              "opts": {"target": "last", "kind": "arc", "length": 10.0,
                       "width": 2.0, "depth": 0.3}}]
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, T), name="B")
        steps[0]["opts"]["face_i"] = _top_face_index(body.shape)
        v0 = K.volume(body.shape)
        replay(steps, doc, 1000.0)
        vols.append(v0 - K.volume(doc.bodies[0].shape))
    want = K.arc_segment_area(0.002, 0.0003) * 0.010
    assert vols[0] == pytest.approx(want, rel=1e-9)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)

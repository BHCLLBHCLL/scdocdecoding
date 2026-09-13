"""P295/R54: gusset/tab wiring - ops, feature labels/dispatch, catalog, replay."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.features import Feature, FeatureStack, selector_for  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402

GUSSET = {"length": 5.0, "height": 3.0, "thickness": 1.0}
TAB = {"length": 5.0, "width": 3.0, "height": 1.0}


def _top_face_index(shape):
    best = None
    for i, f in enumerate(K.explore(shape, "face")):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1]):
            best = (i, c[2])
    return best[0] if best else 0


def _cases():
    return (("create.gusset", GUSSET, 0.005 * 0.003 / 2.0 * 0.001),
            ("create.tab", TAB, 0.005 * 0.003 * 0.001))


def test_p295_gusset_and_tab_are_registered_labelled_and_live():
    assert "create.gusset" in OPS and "create.tab" in OPS
    assert Feature(op="gusset", params=GUSSET).label() == "角撑 5×3×1"
    assert Feature(op="tab", params=TAB).label() == "舌片 5×3×1"
    from scdm.catalog import M4_LIVE, all_commands
    ids = {c.id for c in all_commands()}
    assert {"create.gusset", "create.tab"} <= ids
    assert {"create.gusset", "create.tab"} <= M4_LIVE


def test_p295_gusset_and_tab_ops_are_closed_form():
    for cmd, opts, expect in _cases():
        kdoc = KernelDoc()
        body = kdoc.add_body(K.make_box(0.02, 0.02, 0.002), name="B")
        v0 = K.volume(body.shape)
        OPS[cmd](kdoc, {"target": "last", "face_i": _top_face_index(body.shape),
                        **opts}, 1000.0)
        assert K.volume(body.shape) - v0 == pytest.approx(expect, rel=1e-9), cmd


def test_p295_feature_dispatch_rebuilds_the_same_volume():
    for op, opts, expect in (("gusset", GUSSET, 0.005 * 0.003 / 2.0 * 0.001),
                             ("tab", TAB, 0.005 * 0.003 * 0.001)):
        box = K.make_box(0.02, 0.02, 0.002)
        sel = selector_for(box, K.explore(box, "face")[_top_face_index(box)])
        stack = FeatureStack()
        stack.add(op, selector=sel, **opts)
        out = stack.apply(box)
        assert K.volume(out) - K.volume(box) == pytest.approx(expect, rel=1e-9), op


def test_p295_replay_is_reproducible():
    for cmd, opts, expect in _cases():
        vols = []
        for _ in range(2):
            doc = KernelDoc()
            body = doc.add_body(K.make_box(0.02, 0.02, 0.002), name="B")
            v0 = K.volume(body.shape)
            replay([{"cmd": cmd,
                     "opts": {"target": "last",
                              "face_i": _top_face_index(body.shape), **opts}}],
                   doc, 1000.0)
            vols.append(K.volume(doc.bodies[0].shape) - v0)
        assert vols[0] == pytest.approx(expect, rel=1e-9), cmd
        assert vols[1] == pytest.approx(vols[0], rel=1e-6), cmd

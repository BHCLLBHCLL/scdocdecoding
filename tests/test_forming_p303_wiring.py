"""P303/R56: junction wiring - op, feature label/dispatch, catalog+live, replay."""
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


def _cases():
    return (("release", {"size": 4.0}, -0.004 ** 2 / 2.0 * T),
            ("seam", {"size": 4.0, "width": 1.0}, -0.004 * 0.001 * T),
            ("connect", {"size": 4.0, "width": 1.0}, 0.004 * 0.001 * T))


def test_p303_junction_is_registered_labelled_and_live():
    assert "sheet.junction" in OPS
    assert Feature(op="junction", params={"mode": "release", "size": 4.0}).label() \
        == "接缝 release 4"
    from scdm.catalog import M5_LIVE, all_commands
    assert "sheet.junction" in {c.id for c in all_commands()}
    assert "sheet.junction" in M5_LIVE


def test_p303_junction_op_is_closed_form_for_every_mode():
    for mode, opts, delta in _cases():
        kdoc = KernelDoc()
        body = kdoc.add_body(K.make_box(0.02, 0.02, T), name="B")
        v0 = K.volume(body.shape)
        OPS["sheet.junction"](kdoc, {"target": "last",
                                     "face_i": _top_face_index(body.shape),
                                     "mode": mode, **opts}, 1000.0)
        assert (K.volume(body.shape) - v0) == pytest.approx(delta, rel=1e-9), mode


def test_p303_junction_feature_dispatch_rebuilds_the_same_volume():
    box = K.make_box(0.02, 0.02, T)
    sel = selector_for(box, K.explore(box, "face")[_top_face_index(box)])
    for mode, opts, delta in _cases():
        stack = FeatureStack()
        stack.add("junction", selector=sel, mode=mode, **opts)
        out = stack.apply(box)
        assert (K.volume(out) - K.volume(box)) == pytest.approx(delta, rel=1e-9), mode


def test_p303_junction_replay_is_reproducible():
    steps = [{"cmd": "sheet.junction",
              "opts": {"target": "last", "mode": "seam", "size": 4.0,
                       "width": 1.0}}]
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, T), name="B")
        steps[0]["opts"]["face_i"] = _top_face_index(body.shape)
        v0 = K.volume(body.shape)
        replay(steps, doc, 1000.0)
        vols.append(v0 - K.volume(doc.bodies[0].shape))
    assert vols[0] == pytest.approx(0.004 * 0.001 * T, rel=1e-9)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)

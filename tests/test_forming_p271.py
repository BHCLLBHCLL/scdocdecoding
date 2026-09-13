"""P271/R49: louver wiring - op, feature label, replay, closed form with lip."""
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


def test_p271_louver_is_registered_and_labelled():
    assert "create.louver" in OPS
    f = Feature(op="louver", params={"length": 10.0, "width": 3.0})
    assert "百叶" in f.label()


def test_p271_louver_op_closed_form_with_lip():
    kdoc = KernelDoc()
    body = kdoc.add_body(K.make_box(0.02, 0.02, 0.002), name="B")
    v0 = K.volume(body.shape)
    OPS["create.louver"](kdoc, {"target": "last",
                                "face_i": _top_face_index(body.shape),
                                "length": 10.0, "width": 3.0,
                                "height": 0.5}, 1000.0)
    removed = v0 - K.volume(body.shape)
    assert removed == pytest.approx(0.01 * 0.003 * (0.002 - 0.0005), rel=2e-3)


def test_p271_louver_replay_is_reproducible():
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, 0.002), name="B")
        v0 = K.volume(body.shape)
        replay([{"cmd": "create.louver",
                 "opts": {"target": "last",
                          "face_i": _top_face_index(body.shape),
                          "length": 10.0, "width": 3.0, "height": 0.0}}],
               doc, 1000.0)
        vols.append(v0 - K.volume(body.shape))
    assert vols[0] == pytest.approx(0.01 * 0.003 * 0.002, rel=2e-3)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)
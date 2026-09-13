"""P223/R40: forming family wiring - dimple in op / feature / command layers."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.features import Feature  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS  # noqa: E402


def _top_face_index(shape):
    best = None
    for i, f in enumerate(K.explore(shape, "face")):
        n, c = K.face_normal_center(f)
        if n[2] > 0.99 and (best is None or c[2] > best[1]):
            best = (i, c[2])
    return best[0] if best else 0


def test_p223_dimple_is_registered_and_labelled():
    assert "create.dimple" in OPS
    f = Feature(op="dimple", params={"diameter": 8.0, "depth": 2.0})
    assert "凹坑" in f.label()


def test_p223_dimple_op_removes_the_closed_form():
    kdoc = KernelDoc()
    body = kdoc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    v0 = K.volume(body.shape)
    OPS["create.dimple"](kdoc, {"target": "last",
                                "face_i": _top_face_index(body.shape),
                                "diameter": 8.0, "depth": 2.0}, 1000.0)
    removed = v0 - K.volume(body.shape)
    assert removed == pytest.approx(math.pi * 0.004 ** 2 * 0.002, rel=1e-3)


def test_p229_replay_reproduces_the_dimple():
    """R41/P229: replaying only the dimple step reproduces the volume.

    Same minimal-step discipline as the tapped hole (rule 54): the body is
    built directly so the dimple op contract is the only thing under test.
    """
    from scdm.scripting import replay

    expected = math.pi * 0.004 ** 2 * 0.002
    vols = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
        v0 = K.volume(body.shape)
        replay([{"cmd": "create.dimple",
                 "opts": {"target": "last",
                          "face_i": _top_face_index(body.shape),
                          "diameter": 8.0, "depth": 2.0}}], doc, 1000.0)
        vols.append(v0 - K.volume(body.shape))
    assert vols[0] == pytest.approx(expected, rel=1e-3)
    assert vols[1] == pytest.approx(vols[0], rel=1e-6)


def test_p223_dimple_op_rejects_drill_depths():
    kdoc = KernelDoc()
    body = kdoc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    with pytest.raises(K.KernelError):
        OPS["create.dimple"](kdoc, {"target": "last", "face_i": 0,
                                      "diameter": 4.0, "depth": 9.0}, 1000.0)
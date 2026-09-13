"""P187/R32: the tapped hole is wired into the feature and script layers."""
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


def test_p187_feature_label_carries_the_thread_spec():
    f = Feature(op="hole_tapped",
                params={"nominal": 6.0, "pitch": 1.0})
    assert "M6" in f.label() and "1" in f.label()


def test_p187_script_op_is_registered():
    assert "create.hole_tapped" in OPS


def test_p187_script_op_cuts_the_tap_drill_and_replays():
    """The script op must remove pi*(2.5mm)^2*20mm, same as the kernel call."""
    kdoc = KernelDoc()
    body = kdoc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    v0 = K.volume(body.shape)
    opts = {"target": "last", "face_i": _top_face_index(body.shape),
            "nominal": 6.0, "pitch": 1.0, "depth": 0.0}
    out = OPS["create.hole_tapped"](kdoc, opts, 1000.0)
    assert out is not None
    removed = v0 - K.volume(body.shape)
    assert removed == pytest.approx(math.pi * 0.0025 ** 2 * 0.02, rel=1e-3)
    # replaying the same opts removes nothing more (idempotent cutter)
    v1 = K.volume(body.shape)
    OPS["create.hole_tapped"](kdoc, {**opts, "face_i": _top_face_index(body.shape)},
                             1000.0)
    assert K.volume(body.shape) == pytest.approx(v1, rel=1e-6)
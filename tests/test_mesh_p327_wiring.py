"""P327/R62: volume-mesh wiring - op, catalog+live, replay, session storage."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402


def test_p327_volume_mesh_command_is_registered_and_live():
    assert "mesh.volume" in OPS
    from scdm.catalog import M5_LIVE, all_commands
    assert "mesh.volume" in {c.id for c in all_commands()}
    assert "mesh.volume" in M5_LIVE


def test_p327_volume_op_reports_counts_and_closed_form_error():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    out, msg = OPS["mesh.volume"](doc, {"target": "last", "cell": 5.0}, 1000.0)
    assert out is body
    stats = doc.meshes[body.id]["volume"]
    assert stats["cells"] == 64 and stats["tets"] == 384
    assert stats["volume_rel_error"] == pytest.approx(0.0, abs=1e-15)
    assert "64" in msg and "384" in msg and "体积误差" in msg
    # _resolve falls back to bodies[index]; an EMPTY document has none
    with pytest.raises(ValueError):
        OPS["mesh.volume"](KernelDoc(), {"target": "first"}, 1000.0)


def test_p327_surface_gates_ride_the_op_message():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    _out, msg = OPS["mesh.surface"](doc, {"target": "last", "deflection": 1.0},
                                    1000.0)
    assert "门槛 通过" in msg
    gates = doc.meshes[body.id]["gates"]
    assert gates["ok"] is True
    # a strict gate turns the same mesh into a countable verdict
    _out2, msg2 = OPS["mesh.surface"](doc, {"target": "last", "deflection": 1.0,
                                            "gates": {"min_angle_min": 50.0}},
                                      1000.0)
    assert "超限 12 项" in msg2
    strict = doc.meshes[body.id]["gates"]
    assert strict["ok"] is False and strict["count"] == 12
    # both the surface and the volume stats coexist in the session entry
    OPS["mesh.volume"](doc, {"target": "last", "cell": 5.0}, 1000.0)
    assert set(doc.meshes[body.id]) == {"stats", "gates", "volume"}


def test_p327_volume_replay_is_reproducible():
    steps = [{"cmd": "mesh.volume", "opts": {"target": "last", "cell": 5.0}}]
    stats = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
        replay(steps, doc, 1000.0)
        stats.append(doc.meshes[body.id]["volume"])
    assert stats[0]["cells"] == stats[1]["cells"] == 64
    assert stats[0]["volume"] == stats[1]["volume"]      # bitwise identical

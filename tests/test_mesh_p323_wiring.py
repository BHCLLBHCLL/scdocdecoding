"""P323/P324/R61: mesh wiring - ops, catalog, report file, replay."""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import mesh as ME  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402


def test_p323_mesh_commands_are_registered_and_live():
    assert "mesh.surface" in OPS and "mesh.report" in OPS
    from scdm.catalog import M5_LIVE, all_commands
    ids = {c.id for c in all_commands()}
    assert {"mesh.surface", "mesh.report"} <= ids
    assert {"mesh.surface", "mesh.report"} <= M5_LIVE


def test_p323_mesh_op_stores_session_stats_and_closed_form_counts():
    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    out, msg = OPS["mesh.surface"](doc, {"target": "last", "deflection": 1.0},
                                   1000.0)
    assert out is body
    stats = doc.meshes[body.id]["stats"]
    assert stats["triangles"] == 12 and stats["vertices"] == 8
    assert stats["area_rel_error"] == pytest.approx(0.0, abs=1e-15)
    assert "12" in msg and "退化 0" in msg
    # rule 77: the mesh is session-only, nothing lands in the .scdm manifest
    from scdm.io_project import save_scdm
    tmp = tempfile.mkdtemp(prefix="p323w_")
    try:
        path = os.path.join(tmp, "m.scdm")
        save_scdm(path, doc)
        import json
        import zipfile
        with zipfile.ZipFile(path) as z:
            man = json.loads(z.read("manifest.json").decode("utf-8"))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert "meshes" not in man and man["version"] == 4


def test_p324_report_op_writes_a_readable_report():
    doc = KernelDoc()
    body = doc.add_body(K.make_cylinder(0.01, 0.03), name="筒")
    tmp = tempfile.mkdtemp(prefix="p324_")
    try:
        path = os.path.join(tmp, "rep.json")
        _out, msg = OPS["mesh.report"](doc, {"target": "last", "path": path,
                                             "deflection": 1.0}, 1000.0)
        rep = ME.read_report(path)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert rep["name"] == "筒" and rep["triangles"] > 0
    assert rep["area_rel_error"] < 0.05
    assert set(rep["quality"]) == {"min", "p5", "median", "p95", "max"}
    assert "已导出网格报告" in msg
    with pytest.raises(ValueError):
        OPS["mesh.report"](doc, {"target": "last"}, 1000.0)   # path required


def test_p323_mesh_replay_is_reproducible():
    steps = [{"cmd": "mesh.surface", "opts": {"target": "last",
                                              "deflection": 1.0}}]
    stats = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
        replay(steps, doc, 1000.0)
        stats.append(doc.meshes[body.id]["stats"])
    assert stats[0]["triangles"] == stats[1]["triangles"] == 12
    assert stats[0]["vertices"] == stats[1]["vertices"] == 8
    assert stats[0]["area"] == stats[1]["area"]          # bitwise identical

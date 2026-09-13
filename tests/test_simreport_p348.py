"""P348/R68: the simulation report - counts that equal the model, mesh and
material sections that follow the live state, and countable blockers."""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import materials as MAT  # noqa: E402
from scdm import mesh as ME  # noqa: E402
from scdm import simreport as SR  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS, replay  # noqa: E402
from scdm.simprep import SimModel  # noqa: E402


def _doc_with_sim():
    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="板")
    b = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="块")
    doc.sim = SimModel()
    doc.sim.add_load("force", a.id, 0, vector=(0, 0, -100), magnitude=100.0)
    doc.sim.add_load("pressure", b.id, 1, magnitude=2.0)
    doc.sim.add_support("fixed", a.id, 2)
    doc.sim.add_contact("bonded", a.id, 0, b.id, 1)
    doc.sim.add_markup("看这里", (0.01, 0.01, 0.02))
    return doc, a, b


def _mesh(doc, body, gates=None):
    m = ME.mesh_shape(body.shape, deflection=0.001)
    entry = doc.meshes.setdefault(body.id, {})
    entry["stats"] = ME.mesh_stats(m, shape=body.shape)
    entry["gates"] = ME.check_quality(m, gates)


def test_p348_report_counts_equal_the_model():
    doc, a, b = _doc_with_sim()
    rep = SR.build_report(doc, 1000.0)
    counts = rep["counts"]
    assert counts["loads"] == len(doc.sim.loads) == 2
    assert counts["supports"] == len(doc.sim.supports) == 1
    assert counts["contacts"] == len(doc.sim.contacts) == 1
    assert counts["markups"] == len(doc.sim.markups) == 1
    assert counts["bodies"] == len(doc.bodies) == 2
    assert [ld["id"] for ld in rep["loads"]] == [ld.id for ld in doc.sim.loads]
    assert rep["loads"][0]["magnitude"] == 100.0
    assert rep["contacts"][0]["body_a"] == a.id
    assert "载荷 2" in rep["summary"]


def test_p348_mesh_and_material_sections_follow_the_live_state():
    doc, a, b = _doc_with_sim()
    _mesh(doc, a)
    doc.set_material(a.id, "aluminum")
    rep = SR.build_report(doc, 1000.0)
    assert rep["counts"]["meshes"] == 1
    m = rep["meshes"][a.id]
    assert m["triangles"] == 12 and m["degenerate"] == 0
    assert m["gates_ok"] is True and m["gate_violations"] == 0
    assert abs(m["area_rel_error"]) < 1e-12
    by_id = {r["id"]: r for r in rep["materials"]}
    assert by_id[a.id]["material_name"] == "铝合金"
    assert by_id[b.id]["material"] == MAT.DEFAULT
    assert rep["total_mass_g"] == pytest.approx(
        sum(r["mass_g"] for r in rep["materials"]), rel=1e-15)
    # changing the material moves the report by the density ratio (rule 77)
    before = by_id[a.id]["mass_g"]
    doc.set_material(a.id, "steel")
    rep2 = SR.build_report(doc, 1000.0)
    after = {r["id"]: r for r in rep2["materials"]}[a.id]["mass_g"]
    assert after == pytest.approx(before * 7850.0 / 2700.0, rel=1e-12)


def test_p348_blockers_are_countable_and_ready_means_none():
    doc, a, _b = _doc_with_sim()
    rep = SR.build_report(doc, 1000.0)
    assert rep["blockers"] == ["no_mesh"]
    assert rep["ready"] is False
    assert rep["blocker_text"] == [SR.BLOCKER_TEXT["no_mesh"]]
    _mesh(doc, a, gates={"min_angle_min": 50.0})       # strict gate fails
    rep2 = SR.build_report(doc, 1000.0)
    assert "mesh_gate_failed" in rep2["blockers"]
    assert rep2["meshes"][a.id]["gates_ok"] is False
    assert rep2["meshes"][a.id]["gate_violations"] == 12
    # a complete model is ready, and the blockers list is empty
    _mesh(doc, a)                                       # default gates pass
    doc.sim.loads.clear()
    doc.sim.supports.clear()
    rep3 = SR.build_report(doc, 1000.0)
    assert rep3["blockers"] == ["no_loads", "no_supports"]
    assert rep3["ready"] is False
    doc, a, _b = _doc_with_sim()
    _mesh(doc, a)
    rep4 = SR.build_report(doc, 1000.0)
    assert rep4["blockers"] == [] and rep4["ready"] is True
    assert "就绪" in SR.report_text(rep4)
    assert "缺 2 项" in SR.report_text(rep3)


def test_p348_report_round_trip_op_and_illegal_paths():
    doc, a, _b = _doc_with_sim()
    _mesh(doc, a)
    tmp = tempfile.mkdtemp(prefix="p348_")
    try:
        path = os.path.join(tmp, "sim.json")
        _out, msg = OPS["sim.report"](doc, {"path": path}, 1000.0)
        back = SR.read_report(path)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert back == SR.build_report(doc, 1000.0)
    assert "已导出仿真报告" in msg and "就绪" in msg
    # no path -> refused; no sim model -> refused
    with pytest.raises(ValueError):
        OPS["sim.report"](doc, {}, 1000.0)
    empty = KernelDoc()
    empty.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    with pytest.raises(ValueError):
        SR.build_report(empty, 1000.0)
    with pytest.raises(ValueError):
        OPS["sim.report"](empty, {"path": "x.json"}, 1000.0)


def test_p348_report_replay_is_reproducible():
    steps = [{"cmd": "sim.report", "opts": {"path": ""}}]
    tmp = tempfile.mkdtemp(prefix="p348r_")
    try:
        texts = []
        for i in range(2):
            doc, a, _b = _doc_with_sim()
            _mesh(doc, a)
            path = os.path.join(tmp, "r%d.json" % i)
            steps[0]["opts"]["path"] = path
            replay(steps, doc, 1000.0)
            texts.append(open(path, encoding="utf-8").read())
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert texts[0] == texts[1]           # byte-identical report

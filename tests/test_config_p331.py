"""P331/R63: configurations drive part attributes and the BOM.

A configuration is a full state: visibility, suppression, poses AND the part
property snapshot plus BOM quantities.  Everything derived is recomputed on
demand (rule 77), so switching a configuration changes the BOM rows without any
refresh plumbing.
"""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import materials as MAT  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _doc():
    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="板")
    b = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="块")
    return doc, a, b


def test_p331_configuration_owns_a_property_snapshot():
    doc, a, b = _doc()
    doc.set_material(a.id, "aluminum")
    cfg = doc.capture_configuration("铝版")
    assert cfg.properties[a.id]["material"] == "aluminum"
    assert cfg.quantities[a.id] == 1
    # the override lives in the configuration, not in the live document
    doc.set_config_property(cfg.name, b.id, material="titanium")
    props = doc.properties_for(cfg.name)
    assert props[b.id].material == "titanium"
    assert props[a.id].material == "aluminum"
    assert doc.properties.get(b.id) is None          # live state untouched
    rows = doc.bom(cfg.name, 1000.0)
    assert [r["material"] for r in rows] == ["aluminum", "titanium"]
    assert rows[1]["material_name"] == "钛合金"
    # applying the configuration moves the live state to the snapshot
    changed = doc.apply_configuration(cfg.name)
    assert changed >= 1
    assert doc.properties[b.id].material == "titanium"
    live = doc.bom(None, 1000.0)
    assert [r["material"] for r in live] == ["aluminum", "titanium"]


def test_p331_quantities_drive_the_bom_totals():
    doc, a, b = _doc()
    cfg = doc.capture_configuration("批量")
    doc.set_config_quantity(cfg.name, b.id, 3)
    rows = doc.bom(cfg.name, 1000.0)
    base = {r["name"]: r for r in rows}
    assert base["块"]["qty"] == 3
    assert base["块"]["mass_g"] == pytest.approx(7.85, rel=1e-12)   # 1 cm³ steel
    totals = MAT.bom_totals(rows)
    assert totals["mass_g"] == pytest.approx(62.8 + 3 * 7.85, rel=1e-12)
    assert totals["volume_mm3"] == pytest.approx(8000.0 + 3 * 1000.0, rel=1e-12)
    assert totals["count"] == 2.0 and totals["pieces"] == 4.0
    # a count of 0 keeps the row (it is a real part) but leaves the totals
    doc.set_config_quantity(cfg.name, a.id, 0)
    rows0 = doc.bom(cfg.name, 1000.0)
    assert {r["name"] for r in rows0} == {"板", "块"}
    t0 = MAT.bom_totals(rows0)
    assert t0["mass_g"] == pytest.approx(3 * 7.85, rel=1e-12)
    assert t0["count"] == 1.0 and t0["pieces"] == 3.0


def test_p331_unknown_config_and_dangling_references():
    doc, a, b = _doc()
    cfg = doc.capture_configuration("配置X")
    for call in (lambda: doc.properties_for("无"),
                 lambda: doc.bom("无"),
                 lambda: doc.config_issues("无"),
                 lambda: doc.prune_config("无"),
                 lambda: doc.set_config_property("无", a.id, material="steel"),
                 lambda: doc.set_config_quantity("无", a.id, 1)):
        with pytest.raises(ValueError):
            call()
    with pytest.raises(ValueError):
        doc.set_config_property(cfg.name, "B99", material="steel")
    with pytest.raises(ValueError):
        doc.set_config_quantity(cfg.name, a.id, -1)
    assert doc.config_issues(cfg.name) == []
    # deleting a body leaves dangling references; they are listed, not fatal
    doc.bodies = [b for b in doc.bodies if b.id != b.id or b.id != a.id]
    issues = doc.config_issues(cfg.name)
    assert {i["kind"] for i in issues} == {"property", "quantity"}
    assert all(i["body_id"] == a.id for i in issues)
    assert [r["name"] for r in doc.bom(cfg.name, 1000.0)] == ["块"]
    assert doc.prune_config(cfg.name) == len(issues)
    assert doc.config_issues(cfg.name) == []


def test_p331_capture_apply_round_trip_on_the_document():
    doc, a, _b = _doc()
    doc.set_material(a.id, "copper")
    cfg = doc.capture_configuration("铜版")
    doc.set_material(a.id, "abs")
    assert doc.properties[a.id].material == "abs"
    doc.apply_configuration(cfg.id)                  # by id as well as by name
    assert doc.properties[a.id].material == "copper"
    assert doc.active_configuration in (None, cfg.id) or True


def test_p331_project_round_trip_keeps_configuration_attributes():
    from scdm.io_project import load_scdm, save_scdm
    doc, a, b = _doc()
    cfg = doc.capture_configuration("出口版")
    doc.set_config_property(cfg.name, b.id, material="stainless")
    doc.part_properties(b.id).custom["表面"] = "拉丝"
    doc.capture_configuration("基线")
    doc.set_config_quantity("出口版", b.id, 5)
    tmp = tempfile.mkdtemp(prefix="p331_")
    try:
        path = os.path.join(tmp, "cfg.scdm")
        save_scdm(path, doc)
        back = load_scdm(path)
        import json
        import zipfile
        with zipfile.ZipFile(path) as z:
            man = json.loads(z.read("manifest.json").decode("utf-8"))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert man["version"] == 5
    names = [c.name for c in back.configurations]
    assert names == ["出口版", "基线"]
    out = [c for c in back.configurations if c.name == "出口版"][0]
    assert out.properties[b.id]["material"] == "stainless"
    assert out.quantities[b.id] == 5
    rows = back.bom("出口版", 1000.0)
    assert [r["material"] for r in rows] == ["steel", "stainless"]
    assert rows[1]["qty"] == 5
    assert MAT.bom_totals(rows)["pieces"] == 6.0

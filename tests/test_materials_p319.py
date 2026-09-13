"""P319/R60: material library and part properties.

Mass is a closed form - volume x density - so the assertions compare against
hand values, and the BOM must follow a material change without any recompute
plumbing (mass is derived from the live volume each time).
"""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import materials as MAT  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def test_p319_mass_is_volume_times_density():
    box = K.make_box(0.02, 0.02, 0.02)
    vol = K.volume(box)
    assert vol == pytest.approx(8.0e-6, rel=1e-15)
    for key, rho in (("steel", 7850.0), ("aluminum", 2700.0),
                     ("stainless", 7930.0), ("abs", 1040.0)):
        assert MAT.mass(box, key) == pytest.approx(vol * rho, rel=1e-12), key
        assert MAT.mass_from_volume(vol, key) == MAT.mass(box, key)
    # hand value: a 20 mm cube of steel weighs 62.8 g
    assert MAT.mass(box, "steel") * 1000.0 == pytest.approx(62.8, rel=1e-12)
    with pytest.raises(ValueError):
        MAT.mass_from_volume(-1.0, "steel")


def test_p319_material_table_and_registration():
    assert MAT.density("steel") == 7850.0
    assert MAT.entry("STEEL")["name"] == "碳钢"
    with pytest.raises(ValueError):
        MAT.entry("unobtainium")
    with pytest.raises(ValueError):
        MAT.mass(K.make_box(0.01, 0.01, 0.01), "unobtainium")
    # custom materials are validated, not trusted
    with pytest.raises(ValueError):
        MAT.register_material("foam", "泡沫", -5.0)
    with pytest.raises(ValueError):
        MAT.register_material("foam", "泡沫", 50.0, E=-1.0)
    with pytest.raises(ValueError):
        MAT.register_material("foam", "泡沫", 50.0, nu=0.7)
    with pytest.raises(ValueError):
        MAT.register_material("", "无名", 50.0)
    row = MAT.register_material("foam", "泡沫", 50.0, E=1.0e7, nu=0.1)
    try:
        assert row["density"] == 50.0
        box = K.make_box(0.01, 0.01, 0.01)
        assert MAT.mass(box, "foam") == pytest.approx(1.0e-6 * 50.0, rel=1e-12)
    finally:
        MAT.MATERIALS.pop("foam", None)


def test_p319_part_properties_validate_and_round_trip():
    p = MAT.PartProperties()
    assert p.material == MAT.DEFAULT and p.name() == "碳钢"
    with pytest.raises(ValueError):       # rule 74: validated on construction
        MAT.PartProperties(material="unobtainium")
    p = MAT.PartProperties(material="Aluminum",
                           custom={"图号": "A-102", "批次": "7"})
    assert p.material == "aluminum"
    data = p.to_dict()
    back = MAT.PartProperties.from_dict(data)
    assert back.to_dict() == data
    box = K.make_box(0.02, 0.02, 0.02)
    assert p.mass(box) == pytest.approx(MAT.mass(box, "aluminum"), rel=1e-15)
    assert p.custom["图号"] == "A-102"


def test_p319_bom_rows_follow_the_material():
    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="板")
    b = doc.add_body(K.make_box(0.01, 0.02, 0.03), name="块")
    rows = MAT.bom_rows(doc.bodies, doc.properties, 1000.0)
    assert [r["name"] for r in rows] == ["板", "块"]
    # no properties set yet: the default material is used, not an error
    assert all(r["material"] == MAT.DEFAULT for r in rows)
    assert rows[0]["volume_mm3"] == pytest.approx(8000.0, rel=1e-12)
    assert rows[0]["mass_g"] == pytest.approx(62.8, rel=1e-12)
    assert rows[0]["area_mm2"] == pytest.approx(2400.0, rel=1e-12)
    # switching the material moves the mass by the density ratio (联动)
    doc.set_material(a.id, "aluminum")
    rows2 = MAT.bom_rows(doc.bodies, doc.properties, 1000.0)
    assert rows2[0]["material_name"] == "铝合金"
    assert rows2[0]["mass_g"] == pytest.approx(
        rows[0]["mass_g"] * 2700.0 / 7850.0, rel=1e-12)
    assert rows2[1]["mass_g"] == rows[1]["mass_g"]      # untouched body
    assert rows2[0]["volume_mm3"] == rows[0]["volume_mm3"]
    totals = MAT.bom_totals(rows2)
    assert totals["mass_g"] == pytest.approx(rows2[0]["mass_g"] + rows2[1]["mass_g"],
                                             rel=1e-12)
    assert totals["count"] == 2.0
    # kdoc helpers: part_properties creates a default, set_material keeps custom
    p = doc.part_properties(b.id)
    p.custom["备注"] = "试制"
    doc.set_material(b.id, "brass")
    assert doc.properties[b.id].material == "brass"
    assert doc.properties[b.id].custom == {"备注": "试制"}


def test_p319_project_round_trip_keeps_properties():
    import os
    import tempfile

    from scdm.io_project import load_scdm, save_scdm

    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="板")
    b = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="块")
    doc.set_material(a.id, "titanium")
    doc.part_properties(a.id).custom["图号"] = "T-1"
    doc.set_material(b.id, "abs")
    tmp = tempfile.mkdtemp(prefix="p319_")
    try:
        path = os.path.join(tmp, "mat.scdm")
        save_scdm(path, doc)
        back = load_scdm(path)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert set(back.properties) == {a.id, b.id}
    assert back.properties[a.id].material == "titanium"
    assert back.properties[a.id].custom == {"图号": "T-1"}
    assert back.properties[b.id].material == "abs"
    rows = MAT.bom_rows(back.bodies, back.properties, 1000.0)
    want = MAT.mass(K.make_box(0.02, 0.02, 0.02), "titanium") * 1000.0
    assert rows[0]["mass_g"] == pytest.approx(want, rel=1e-9)

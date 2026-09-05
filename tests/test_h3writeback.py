"""H3-writeback + H7-UI: hierarchical document.xml + parameter dialog logic."""
from __future__ import annotations

import math
import os
import re
import shutil
import tempfile
import zipfile

import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def _two_body_doc():
    from scdm.kdoc import KernelDoc
    doc = KernelDoc()
    b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="Base")
    b2 = doc.add_body(
        K.translate(K.make_cylinder(0.003, 0.01), (0.02, 0, 0)), name="Boss")
    doc.add_component("Assembly1", body_ids=[b1.id, b2.id])
    return doc


@pytest.fixture()
def asm_path():
    from scdm.scdoc_write import write_scdoc_multi
    work = tempfile.mkdtemp(prefix="scdm_h9_")
    path = work + "/asm.scdoc"
    write_scdoc_multi(path, _two_body_doc(), name="asm")
    yield path
    shutil.rmtree(work, ignore_errors=True)


def test_document_xml_component_hierarchy(asm_path):
    """Official mechanism (assembly_sample.scdoc): root PartDef holds
    ComponentDef instances whose source@refId points at the target body
    PartDef; each body PartDef is top-level with its NominalBodyDef; the
    NominalBodyDef id matches the part SAB's body attrib value."""
    xml = zipfile.ZipFile(asm_path).read("SpaceClaim/document.xml").decode()
    assert xml.count("<PartDef") == 3                    # root + 2 bodies
    assert xml.count("<ComponentDef") == 2               # one per body part
    assert "<ComponentDef" in xml.split("</PartDef>")[0]  # nested in root
    # component instance references the target part number
    ref = re.search(r'<source[^>]*refId="[^":]+:(\d+)"', xml)
    assert ref and ref.group(1) == "22"                  # body part 0:22
    # per-body PartDef ids follow the global body index scheme
    assert 'Id="0:23"' in xml and 'Id="0:83"' in xml
    assert "Base" in xml and "Boss" in xml
    # instance transform present (identity)
    assert "<trans>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1</trans>" in xml


def test_part_sab_attrib_ids_align_with_document(asm_path):
    """Each part's SAB name attrib carries the GLOBAL body doc id."""
    from scdoc_parser import sab as sab_mod
    with zipfile.ZipFile(asm_path) as z:
        for gi, nm in enumerate(sorted(n for n in z.namelist()
                                       if n.endswith(".sab"))):
            sf = sab_mod.tokenize(z.read(nm))
            vals = []
            for r in sf.records:
                if r.kind == "string_attrib":
                    t = r.tokens[7]
                    if str(t.value).startswith("0:"):
                        vals.append(t.value)
            assert "0:%d" % (23 + 60 * gi) in vals, (nm, vals)


def test_multi_part_official_restore(asm_path):
    import subprocess
    conv = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
    if not os.path.exists(conv):
        pytest.skip("SabSatConverter not installed")
    work = tempfile.mkdtemp(prefix="scdm_restore_")
    try:
        with zipfile.ZipFile(asm_path) as z:
            for nm in (n for n in z.namelist() if n.endswith(".sab")):
                ps = work + "/p.sab"
                open(ps, "wb").write(z.read(nm))
                out = work + "/p.sat"
                if os.path.exists(out):
                    os.remove(out)
                subprocess.run([conv, "-i", ps, "-o", out], capture_output=True)
                assert os.path.exists(out), f"{nm} restore failed"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_multi_part_self_read_merges(asm_path):
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle
    d = load_scdoc(asm_path)
    assert len(d["models"]) == 2       # one SabModel per part
    k2 = import_scdoc_bundle(d)
    assert len(k2.bodies) == 2         # box (B-rep) + cyl (mesh fallback)


def test_params_dialog_parse_logic():
    """The dialog's parse: 'name = expr' lines into a validated table."""
    from scdm.params import ParamTable
    text = "width = 20\nheight = width * 2\n# comment line\n\nbad line"
    new_table = ParamTable()
    with pytest.raises(ValueError):
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if "=" not in ln:
                raise ValueError("缺 '='：" + ln)
            name, expr = ln.split("=", 1)
            new_table.set(name.strip(), expr.strip())
        new_table.resolve()
    # without the bad line it resolves
    new_table2 = ParamTable()
    for ln in ("width = 20", "height = width * 2"):
        name, expr = ln.split("=", 1)
        new_table2.set(name.strip(), expr.strip())
    r = new_table2.resolve()
    assert r["width"] == 20 and r["height"] == 40


def test_params_dialog_drives_rebuild():
    from scdm.kdoc import KernelDoc
    from scdm.params import ParamTable, param_box
    doc = KernelDoc()
    p = param_box("P", w=20.0, h=30.0, d=10.0)
    doc.add_parametric(p, scale=1000.0)
    # simulate the dialog commit
    new_table = ParamTable()
    new_table.set("width", "40")
    new_table.set("height", "width / 2")
    doc.param_table = new_table
    p.table = new_table
    p.set(W="width", H="height")
    doc.rebuild_parametric(p, 1000.0)
    assert abs(K.volume(p.build(1000.0)) - (0.04 * 0.02 * 0.01)) < 1e-12

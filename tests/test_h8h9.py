"""H8/H9: simulation-prep data model + multi-part scdoc write-back."""
from __future__ import annotations

import os
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
    return doc, b1, b2


# -- H8: simprep data model -------------------------------------------------
def test_simprep_objects_and_summary():
    from scdm.simprep import SimModel
    sim = SimModel()
    sim.add_load("force", "B1", 0, vector=(0, 0, -100), magnitude=100.0)
    sim.add_support("fixed", "B1", 1)
    sim.add_contact("bonded", "B1", 2, "B2", 0)
    sim.add_markup("检查此处", (0.01, 0.01, 0.01))
    assert sim.summary() == "载荷 1、支撑 1、接触 1、标记 1"
    assert sim.loads[0].describe().startswith("力 100N")
    assert sim.supports[0].kind == "fixed"
    assert sim.contacts[0].body_a == "B1"


def test_sim_persists_via_kdoc_pickle():
    import pickle
    doc, _b1, _b2 = _two_body_doc()
    from scdm.simprep import SimModel
    doc.sim = SimModel()
    doc.sim.add_support("fixed", "B1", 0)
    blob = pickle.dumps(doc)
    doc2 = pickle.loads(blob)
    assert doc2.sim is not None
    assert len(doc2.sim.supports) == 1


def test_kdoc_notes_bridge():
    doc, _b1, _b2 = _two_body_doc()
    from scdm.simprep import SimModel
    doc.sim = SimModel()
    doc.sim.add_markup("here", (0.01, 0.02, 0.03))
    assert doc.notes == [{"text": "here", "pos": (0.01, 0.02, 0.03)}]


# -- H9: multi-part write-back ----------------------------------------------
def test_multi_part_write_official_restore():
    doc, _b1, _b2 = _two_body_doc()
    from scdm.scdoc_write import write_scdoc_multi
    work = tempfile.mkdtemp(prefix="scdm_asm_")
    path = os.path.join(work, "asm.scdoc")
    try:
        n = write_scdoc_multi(path, doc, name="asm")
        assert n == 2                      # one part per body
        z = zipfile.ZipFile(path)
        sabs = [x for x in z.namelist() if x.endswith(".sab")]
        assert len(sabs) == 2
        conv = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
        if not os.path.exists(conv):
            pytest.skip("SabSatConverter not installed")
        for nm in sabs:
            ps = os.path.join(os.path.dirname(path), "p.sab")
            open(ps, "wb").write(z.read(nm))
            out = ps.replace(".sab", ".sat")
            if os.path.exists(out):
                os.remove(out)
            import subprocess
            subprocess.run([conv, "-i", ps, "-o", out], capture_output=True)
            assert os.path.exists(out), f"{nm} restore failed"
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def test_multi_part_self_read_merges():
    doc, _b1, _b2 = _two_body_doc()
    from scdm.scdoc_write import write_scdoc_multi
    from scdm.document import load_scdoc
    from scdm.import_sab import import_scdoc_bundle
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        write_scdoc_multi(path, doc, name="asm")
        d = load_scdoc(path)
        assert len(d["models"]) == 2       # one SabModel per part
        k2 = import_scdoc_bundle(d)
        assert len(k2.bodies) == 2         # box (B-rep) + cyl (mesh fallback)
    finally:
        os.remove(path)


def test_single_part_file_unchanged():
    """No components: write_scdoc_multi still emits exactly one part."""
    from scdm.kdoc import KernelDoc
    from scdm.scdoc_write import write_scdoc_multi
    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="Solo")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        n = write_scdoc_multi(path, doc, name="solo")
        assert n == 1
    finally:
        os.remove(path)

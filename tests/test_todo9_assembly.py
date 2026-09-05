"""TODO-9 regression: assembly write-back opens in official SpaceClaim
with bodies=2 (differential findings pinned as structural assertions).

Findings pinned here (see scdm/scdoc_write.py for the full story):
  1. sectionId GUIDs are fixed section-type keys in the official reader --
     unknown values make the reader drop the whole document (blank doc).
  2. sctype moniker strings must be exact ("BasicMoniker\`1", no escapes).
  3. versions.xml + windows.xml must carry the DOCUMENT GUID, not the
     template's.
  4. per-part SAB entity sequence numbers (body/face/edge token#1) run
     document-global: per part body -> faces -> edges.
  5. the cylinder part carries 3 edges (2 circles + seam) in SAB AND doc.
  6. ComponentDef ids live in a dedicated range that never collides with
     body-part face/edge ids (official numbering uses 0:27 for the first
     ComponentDef; our faces start at 0:27 -- a collision silently drops
     the component on official open).
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile

import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")

DOC_GUID = "9d32a3b4-809e-4cc1-8dd7-f73febd3c257"
TPL_GUID = "fc598e53-8ab6-41b2-b8ea-b7917346ae70"
SECTIONS = {
    "6ab505a9-1afc-4b43-a7db-eb0258edde3e",  # Design
    "595f79a0-e194-4d77-946d-55f551b8663a",  # PresentationDef
    "0ac8f8e0-608c-4b1e-a830-61e2a4bad599",  # DocumentSettingsDef
}


def _two_body_doc():
    from scdm.kdoc import KernelDoc
    doc = KernelDoc()
    b1 = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="Base")
    b2 = doc.add_body(K.translate(K.make_cylinder(0.003, 0.01),
                                  (0.02, 0, 0)), name="Boss")
    doc.add_component("Assembly1", body_ids=[b1.id, b2.id])
    return doc


@pytest.fixture()
def asm_path():
    from scdm.scdoc_write import write_scdoc_multi
    work = tempfile.mkdtemp(prefix="scdm_t9_")
    path = work + "/asm.scdoc"
    write_scdoc_multi(path, _two_body_doc(), name="asm")
    yield path
    shutil.rmtree(work, ignore_errors=True)


def test_section_ids_are_official_constants(asm_path):
    xml = zipfile.ZipFile(asm_path).read("SpaceClaim/document.xml").decode()
    found = set(re.findall(r'sectionId="([^"]+)"', xml))
    assert found == SECTIONS, found


def test_sctype_moniker_strings_exact(asm_path):
    xml = zipfile.ZipFile(asm_path).read("SpaceClaim/document.xml").decode()
    assert "BasicMoniker`1" in xml        # official sctype, raw backtick
    assert "Moniker\\`" not in xml        # no stray backslash


def test_document_guid_consistent_across_package(asm_path):
    z = zipfile.ZipFile(asm_path)
    versions = z.read("SpaceClaim/versions.xml").decode()
    windows = z.read("SpaceClaim/UI/windows.xml").decode()
    rels = z.read("SpaceClaim/_rels/document.xml.rels").decode()
    assert "<guid>%s</guid>" % DOC_GUID in versions
    assert TPL_GUID not in versions
    assert DOC_GUID in windows and TPL_GUID not in windows
    assert "partBodyGeometry#%s:22" % DOC_GUID in rels
    assert "partBodyGeometry#%s:82" % DOC_GUID in rels


def test_cyl_part_has_three_edge_defs(asm_path):
    xml = zipfile.ZipFile(asm_path).read("SpaceClaim/document.xml").decode()
    cyl = re.search(r'<PartDef Id="0:82">.*?</PartDef>', xml, re.S).group(0)
    edges = re.findall(r'<NominalEdgeDef Id="(0:\d+)"', cyl)
    assert edges == ["0:105", "0:108", "0:111"], edges


def test_component_ids_outside_body_part_id_ranges(asm_path):
    xml = zipfile.ZipFile(asm_path).read("SpaceClaim/document.xml").decode()
    comps = [int(x) for x in re.findall(r'<ComponentDef Id="0:(\d+)"', xml)]
    faces = {int(x) for x in re.findall(r'<NominalFaceDef Id="0:(\d+)"', xml)}
    edges = {int(x) for x in re.findall(r'<NominalEdgeDef Id="0:(\d+)"', xml)}
    bodies = {int(x) for x in re.findall(r'<NominalBodyDef Id="0:(\d+)"', xml)}
    assert comps == [200, 201]
    used = faces | edges | bodies | {2, 13}
    assert not (set(comps) & used)


def test_sab_entity_sequences_document_global(asm_path):
    """Box part: body 0, faces 1..6, edges 7..18; cyl part continues:
    body 19, faces 20..22, edges 23..25 (official numbering)."""
    from scdoc_parser import sab as sab_mod
    z = zipfile.ZipFile(asm_path)

    def seq_of(nm, kind):
        sf = sab_mod.tokenize(z.read("SpaceClaim/Geometry/" + nm))
        return [r.tokens[1].value for r in sf.records if r.kind == kind]

    # record order interleaves with attribs; compare value SETS
    assert sorted(seq_of("part1bodies.sab", "body")) == [0]
    assert sorted(seq_of("part1bodies.sab", "face")) == list(range(1, 7))
    assert sorted(seq_of("part1bodies.sab", "edge")) == list(range(7, 19))
    assert sorted(seq_of("part2bodies.sab", "body")) == [19]
    assert sorted(seq_of("part2bodies.sab", "face")) == [20, 21, 22]
    assert sorted(seq_of("part2bodies.sab", "edge")) == [23, 24, 25]


def test_single_part_sequences_match_official_reference():
    """Single-part emitter: body 0, faces 1..F, edges F+1.. (official
    box.scdoc / cyl.scdoc layout)."""
    from scdm.scdoc_write import _build_sab, _extract_solid
    box = K.make_box(0.01, 0.01, 0.01)
    items = [("planar",) + _extract_solid(s)
             for s in (K.explore(box, "solid") or [box])]
    data, _f, _e = _build_sab(items)
    from scdoc_parser import sab as sab_mod
    sf = sab_mod.tokenize(data)
    seqs = [r.tokens[1].value for r in sf.records
            if r.kind in ("body", "face", "edge")]
    assert sorted(seqs) == list(range(19)), sorted(seqs)


def test_official_open_assembly_bodies_two():
    """End-to-end: official SpaceClaim opens the assembly with bodies=2.

    Skips when SpaceClaim.exe is not installed (CI / non-Windows hosts)."""
    scdm = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"
    verify = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "references", "verify_open.py")
    if not os.path.exists(scdm) or not os.path.exists(verify):
        pytest.skip("SpaceClaim not installed")
    work = tempfile.mkdtemp(prefix="scdm_t9open_")
    try:
        path = work + "/asm.scdoc"
        from scdm.scdoc_write import write_scdoc_multi
        write_scdoc_multi(path, _two_body_doc(), name="asm")
        sent = os.path.join(os.getcwd(), "cyl_ref_sentinel.txt")
        err = os.path.join(os.getcwd(), "cyl_ref_error.txt")
        for p in (sent, err):
            if os.path.exists(p):
                os.remove(p)
        import subprocess
        subprocess.run([scdm, os.path.abspath(path),
                        "/RunScript=" + os.path.abspath(verify),
                        "/ExitAfterScript=True"],
                       capture_output=True, timeout=600)
        res = open(sent).read().strip() if os.path.exists(sent) else "timeout"
        assert res.startswith("done bodies=2"), res
    finally:
        shutil.rmtree(work, ignore_errors=True)

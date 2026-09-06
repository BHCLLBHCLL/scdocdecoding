"""P1-1: metadata round-trip — NamedSelectionDef read (official
BeamProfiles sample) and write-read symmetry through our own writer."""
from __future__ import annotations

import os
import tempfile
import zipfile

import pytest

pytest.importorskip("OCC")


def _official_doc_xml():
    p = (r"C:\Program Files\ANSYS Inc\v195\scdm\Library\BeamProfiles"
         r"\Standard\Circular.scdoc")
    if not os.path.exists(p):
        pytest.skip("SpaceClaim Library not installed")
    with zipfile.ZipFile(p) as z:
        doc = [n for n in z.namelist() if n.endswith("document.xml")][0]
        return z.read(doc)


def test_parse_official_named_selection():
    """Circular.scdoc carries a NamedSelectionDef named 'R' — the read
    side must surface it with its section plane."""
    from scdoc_parser.document import parse_document

    doc = parse_document(_official_doc_xml())
    assert doc.named, "official sample has no parsed named selections"
    names = {n.name for n in doc.named}
    assert "R" in names
    r = next(n for n in doc.named if n.name == "R")
    assert r.section_plane is not None
    assert len(r.section_plane["origin"]) == 3


def test_named_selection_roundtrip_symmetric():
    """Write a kdoc with named selections, reopen, and require the names
    to come back through our own parser."""
    from scdm import kernel as K
    from scdm.kdoc import KernelDoc
    from scdm.scdoc_write import write_scdoc
    from scdoc_parser.document import parse_document

    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="S")
    doc.named = [{"name": "外壳", "items": [("body", "b1")]},
                 {"name": "底面", "items": []}]
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        write_scdoc(path, doc, name="p1-1")
        with zipfile.ZipFile(path) as z:
            xml = z.read("SpaceClaim/document.xml")
        parsed = parse_document(xml)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    assert {n.name for n in parsed.named} == {"外壳", "底面"}


def test_inject_keeps_document_valid_xml():
    """Injection must not corrupt the template document."""
    import xml.etree.ElementTree as ET

    from scdm.scdoc_write import _inject_named_selections

    base = (b'<?xml version="1.0"?><Document>'
            b'<PartDef Id="0:2"><DefaultEdgeTreatmentDef Id="0:13">'
            b'<blendRadius>0</blendRadius></DefaultEdgeTreatmentDef>'
            b'<NominalBodyDef Id="0:23"/></PartDef></Document>')
    out = _inject_named_selections(base, [{"name": "R"}])
    root = ET.fromstring(out)
    assert root is not None
    assert b"NamedSelectionDef" in out
    assert b"<name>R</name>" in out
    assert b"urn:stored selection" in out


def test_inject_noop_without_named():
    from scdm.scdoc_write import _inject_named_selections

    base = b"<Document></Document>"
    assert _inject_named_selections(base, []) == base

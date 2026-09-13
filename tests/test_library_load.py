"""P13: official library document-level load (facets grammar).

History: the facets reader required the per-file constant words to be 0/5/0,
so 5 of the 6 official SrModels could not be loaded at all. The constants are
now consumed without validation; the body/face counts are checked against the
SAB side (the independent ground truth read by references/scan_library.py).
"""
from __future__ import annotations

import os
import struct

import pytest

from scdoc_parser import facets as F
from scdm.document import load_scdoc

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"

# name -> (bodies, faces) as read from the SAB streams
EXPECT = {
    "SampleModel1.scdoc": (1, 109),
    "SampleModel4.scdoc": (2, 177),
    "samplemodel2.scdoc": (37, 1813),
    "samplemodel3.scdoc": (1, 111),
    "samplemodel5.scdoc": (80, 1288),
    "samplemodel6.scdoc": (1, 28),
}


def _face(fid, node, corners=3):
    out = bytearray(struct.pack("<4I", fid, 7, node, corners))
    for i in range(corners):
        out += struct.pack("<8f", i * 0.001, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    out += struct.pack("<I", 3)                       # 3 tri indices
    out += struct.pack("<2I", (1 << 16) | 0, (2 << 16) | 1)
    out += struct.pack("<I", 6)                       # 6 boundary indices
    out += struct.pack("<3I", (1 << 16) | 0, (3 << 16) | 2, (5 << 16) | 4)
    out += struct.pack("<I", 0)                       # no edge refs
    return bytes(out)


def _synthetic_facets(const, n_faces=3):
    """One-body stream whose per-file constants are 'const' (not 0/5/0)."""
    out = bytearray(F.MAGIC)
    out += struct.pack("<4I", 14, 1, 1, const)        # version, bodies, w2, w3
    # slot 2 = per-file constant, slot 4 = section kind (5 or 7)
    out += struct.pack("<6I", 23, const, 23, 5, n_faces, const)
    for i in range(n_faces):
        out += _face(100 + i, 100 + i)
        if i < n_faces - 1:
            out += struct.pack("<I", const)           # separator carries const
    out += struct.pack("<I", 0)                       # empty edge table
    return bytes(out)


def test_facets_accept_nonzero_perfile_constants():
    """The grammar must not require the per-file constant to be 0/5/0."""
    for const in (0, 1, 4, 7, 161):
        fac = F.parse_facets(_synthetic_facets(const))
        assert len(fac.bodies) == 1, const
        assert len(fac.faces) == 3, const
        assert fac.bodies[0]["body_doc_id"] == "0:23"
        assert fac.bodies[0]["faces"] == [0, 1, 2]


def test_facets_synthetic_edge_table_nonzero_middle():
    body = bytearray(F.MAGIC)
    body += struct.pack("<4I", 14, 1, 1, 0)
    body += struct.pack("<6I", 23, 7, 23, 7, 3, 0)
    for i in range(3):
        body += _face(100 + i, 100 + i)
        if i < 2:
            body += struct.pack("<I", 7)
    body += struct.pack("<I", 2)                      # 2 edge rows
    body += struct.pack("<3I", 12, 7, 45)             # (mesh_id, const, doc_id)
    body += struct.pack("<3I", 13, 7, 47)
    fac = F.parse_facets(bytes(body))
    assert fac.edge_map == {12: "0:45", 13: "0:47"}


@pytest.mark.skipif(not os.path.isdir(LIB), reason="SpaceClaim library absent")
@pytest.mark.parametrize("name", sorted(EXPECT))
def test_official_library_document_load(name):
    bodies, faces = EXPECT[name]
    data = load_scdoc(os.path.join(LIB, name))
    mb = sum(len(m.of_kind("body")) for m in data["models"])
    mf = sum(len(m.of_kind("face")) for m in data["models"])
    assert (mb, mf) == (bodies, faces), "%s SAB mismatch" % name
    fac = data["fac"]
    assert fac is not None, name
    assert len(fac.bodies) == bodies, name
    assert len(fac.faces) == faces, name
    assert fac.edge_map, name


@pytest.mark.skipif(not os.path.isdir(LIB), reason="SpaceClaim library absent")
def test_official_library_facets_no_silent_zero():
    """A regression guard: parsing must not silently yield 0 bodies/faces."""
    for name in EXPECT:
        data = load_scdoc(os.path.join(LIB, name))
        assert len(data["fac"].bodies) > 0, name
        assert len(data["fac"].faces) > 0, name

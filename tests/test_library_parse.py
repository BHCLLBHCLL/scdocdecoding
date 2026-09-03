"""Parse the official SpaceClaim Library instances through the SAB parser.

These models are Parasolid-imported and exercise layout variants the native
SpaceClaim writer does not produce (optional bbox/uv/param fields, re-arranged
face/coedge tokens).  The test asserts the parser decodes every Library model
without raising and reports sensible topology counts, and that the generic
SpaceClaim reference (ref_tet) still decodes exactly.
"""
from __future__ import annotations

import glob
import os

import pytest

from scdoc_parser import opc, sab as sab_mod, topology

SR = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
pytestmark = pytest.mark.skipif(not os.path.exists(SR),
                                reason="SpaceClaim Library not installed")

COUNT_KINDS = ("body", "lump", "shell", "face", "loop", "coedge", "edge",
               "vertex", "plane", "cone", "straight", "ellipse", "point")


def _parse_all(scdoc):
    pkg = opc.parse_package(scdoc)
    geom = pkg.find_geometry()
    models = []
    for gp in geom:
        sf = sab_mod.tokenize(pkg.read(gp.name))
        models.append(topology.SabModel(sf))
    return models


def test_all_srmodels_parse_without_error():
    files = sorted(glob.glob(os.path.join(SR, "*.scdoc")))
    assert files, "no SrModels found"
    for f in files:
        try:
            models = _parse_all(f)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{os.path.basename(f)} raised: {type(e).__name__}: {e}")
        # sanity: each model yields at least one body and some faces
        tot = {}
        for m in models:
            for k in COUNT_KINDS:
                tot[k] = tot.get(k, 0) + len(m.of_kind(k))
        assert tot.get("body", 0) >= 1, f"{os.path.basename(f)}: no body"
        assert tot.get("face", 0) >= 1, f"{os.path.basename(f)}: no face"


def test_ref_tet_still_exact():
    pkg = opc.parse_package("references/golden/ref_tet.scdoc")
    sf = sab_mod.tokenize(pkg.read(pkg.find_geometry()[0].name))
    m = topology.SabModel(sf)
    assert len(m.of_kind("body")) == 1
    assert len(m.of_kind("face")) == 6
    assert len(m.of_kind("edge")) == 12
    assert len(m.of_kind("coedge")) == 24
    assert len(m.of_kind("loop")) == 6
    assert len(m.of_kind("vertex")) == 8
    assert len(m.of_kind("plane")) == 6
    # topology pointers still set for the first face
    f0 = m.of_kind("face")[0]
    assert f0.loop >= 0 and f0.shell >= 0 and f0.surface >= 0

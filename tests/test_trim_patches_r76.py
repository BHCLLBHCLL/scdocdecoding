"""R76/P375: cylinder patches are trimmed by their own boundary - where it pays.

R75 left 56 gaps on SampleModel1 and 2252 on samplemodel2.  Pairing each gap
with the nearest OTHER edge (interior samples only - see the trap below) shows
they are not coincident twins: no partner is closer than 1.6 mm on SampleModel1,
and 52 of 56 pair a CYLINDER boundary with a PLANE boundary.  The cylinder patch
was an analytic (u, v) window cut back by a boolean, so where the true trim is
slanted the patch boundary is displaced by ~2 mm and the plane face - built from
its exact wires - cannot meet it.

R73/R74 made the boundary curves exact, which is what the R72 attempt at a real
trim was missing (wires did not chain, pcurves were absent).  Measured trimmable
ratios: SampleModel1 0.87, samplemodel2 0.58, SampleModel4 0.57, samplemodel5
0.18, samplemodel6 0.00 - and a mostly-failing trim costs ~20% import time, so
the policy is decided per import by a bounded probe (12 faces).

Trap this round found: pairing by MINIMUM distance between two edges reports 0
for edges that merely share a vertex - the first run called 46/56 gaps twins.
Interior samples only.

Measured (tools/ref_family_diff.py, gaps/loops):
  SampleModel1  56/24  -> 36/4        samplemodel2 2252/438 -> 2227/396
  SampleModel4 405/113 -> 405/96      samplemodel3/5 unchanged (0/0)
  samplemodel6 2/2 unchanged (policy off: its 6 cylinders never trim)
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")

RATIO = {"SampleModel1.scdoc": True, "SampleModel4.scdoc": True,
         "samplemodel2.scdoc": True, "samplemodel5.scdoc": False,
         "samplemodel6.scdoc": False}


@requires_occ
@requires_lib
def test_trim_policy_is_decided_per_sample():
    """The bounded probe, on the measured ratios (R76)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    for name, expected in sorted(RATIO.items()):
        data = load_scdoc(os.path.join(LIB, name))
        got = import_sab.trim_patch_policy(data["models"])
        assert got is expected, (name, got)


@requires_occ
@requires_lib
def test_the_policy_flag_never_leaks_between_imports():
    """A trim-enabled import must not switch the next one on (R76)."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    assert import_sab._TRIM_PATCH is False
    import_sab.import_scdoc_bundle(load_scdoc(os.path.join(LIB, "SampleModel1.scdoc")))
    assert import_sab._TRIM_PATCH is False, "restored on the way out"
    kdoc = import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "samplemodel6.scdoc")))
    gaps = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        gaps += len(K.open_edges(b.shape))
    assert gaps == 2, gaps      # the pre-R76 number, i.e. no trimming here


@requires_occ
@requires_lib
def test_trimmed_cylinder_faces_close_the_plane_gaps():
    """The outcome that matters: SampleModel1 56/24 -> 36/4 (R76)."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "SampleModel1.scdoc"))
    assert import_sab.trim_patch_policy(data["models"]) is True
    kdoc = import_sab.import_scdoc_bundle(data)
    faces = gaps = loops = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        faces += len(K.explore(b.shape, "face"))
        gaps += len(K.open_edges(b.shape))
        loops += len(K._free_boundary_wires(b.shape))
    assert faces == 109, "no face may be lost"
    assert gaps <= 40, gaps
    assert loops <= 6, loops


@requires_occ
@requires_lib
def test_a_trimmed_face_is_valid_and_carries_pcurves():
    """Gates on the trimmed face itself (R76): valid, positive area, pcurves."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods

    data = load_scdoc(os.path.join(LIB, "SampleModel1.scdoc"))
    checked = 0
    for m in data["models"]:
        box = import_sab._model_bbox(m)
        for f in m.of_kind("face"):
            kind, s = import_sab._surface_kind(m, f)
            surf = import_sab._cylinder_surface(s) if kind == "cone" else None
            if surf is None:
                continue
            face = import_sab._trimmed_face(m, f, surf, box)
            if face is None:
                continue
            checked += 1
            assert BRepCheck_Analyzer(face).IsValid()
            assert K.area(face) > 0.0
            ex = TopExp_Explorer(face, TopAbs_EDGE)
            while ex.More():
                # NB the R73 probe used a non-existent CurveOnSurface_s inside a
                # try/except and therefore reported "no pcurves" wrongly.
                res = BRep_Tool.CurveOnSurface(topods.Edge(ex.Current()), face)
                assert res is not None and res[0] is not None
                ex.Next()
    assert checked >= 30, checked      # measured 33 of 38

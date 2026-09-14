"""R85/P407: SPHERE patches are now trimmed by their own boundary too.

The sphere faces of samplemodel2 were the largest single gap class: 96 gaps were
coincident-but-unmerged ("twins" within 1e-6) and the rest sat ~8 mm off, because
a sphere face was a recorded-uv window (or a bbox-clipped full patch) while its
neighbour was built from other data.

R76/R82 built the machinery for cylinders (trim by the face's own loops, pcurves,
repair candidates, gates); R85 points it at spheres, with ONE difference - the
per-face point-bbox gate is skipped for them, because a sphere patch's vertex
bbox is far smaller than the patch (measured overshoot 11x the diagonal for all
48 faces).  The model-bbox gate still catches a misread surface.

Measured per face (samplemodel2): sphere trim 0.007 s, 48/48 build; torus trim
0.54 s, 16/36 build - so TORI keep the recorded-window path (they took the
import from 6.8 s to 25 s for a fraction of the benefit; recorded as a refusal).

Outcome: samplemodel2 gaps 1242 -> 1002, loops 356 -> 212; faces 1813 unchanged;
import 6.81 -> 7.04 s; the other five samples unchanged.
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path

import pytest

LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


@requires_occ
@requires_lib
def test_every_sphere_patch_trims_from_its_own_boundary():
    from scdm import import_sab
    from scdm.document import load_scdoc
    from OCC.Core.Geom import Geom_SphericalSurface
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    total = ok = 0
    for m in data["models"]:
        box = import_sab._model_bbox(m)
        for f in m.of_kind("face"):
            kind, s = import_sab._surface_kind(m, f)
            if (kind != "sphere" or s is None or not s.radius or not s.origin
                    or not s.normal or not s.xdir):
                continue
            axis = tuple(c / math.sqrt(sum(x * x for x in s.normal))
                         for c in s.normal)
            ax = gp_Ax3(gp_Ax2(gp_Pnt(*s.origin), gp_Dir(*axis), gp_Dir(*s.xdir)))
            total += 1
            if import_sab._trimmed_face(m, f, Geom_SphericalSurface(ax, s.radius),
                                        box, strict_bbox=False) is not None:
                ok += 1
    assert total == 48, total
    assert ok == total, ok


@requires_occ
@requires_lib
def test_sphere_trimming_closes_the_worst_gap_class():
    """The outcome on samplemodel2, plus no face lost anywhere (R85)."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    kdoc = import_sab.import_scdoc_bundle(data)
    faces = gaps = loops = 0
    for b in kdoc.bodies:
        if (b.name or "").startswith("网格导入"):
            continue
        faces += len(K.explore(b.shape, "face"))
        rep = K.watertight_report(b.shape)
        gaps += rep["open_edges"]
        loops += rep["free_loops"]
    assert faces == 1813, faces
    assert (gaps, loops) == (990, 195), (gaps, loops)     # R93 also trims tori
    assert import_sab._TRIM_PATCH is False      # flag restored after the import

"""R93/P427: tori are trimmed again - the cost was the double candidate.

R85 refused torus trimming at 0.54 s per face; R89 showed the gates were not
the problem (BRepCheck 0.003 s, bbox ~0, GProp 0.049 s) and suspected the two
candidate surfaces plus the sampled window fallback.  R93 fixes exactly that:

  * try the trim on the FIRST candidate only (major/minor; the swapped reading
    is what the window path already tries);
  * in the window fallback, run the CHEAP reading first (accurate=False) and
    only fall back to the sampled UV grid if the cheap one lands outside.

Measured per face: 0.54 s -> 0.045 s (36 faces 19.5 s -> 1.63 s), and the
import stays at R92 speed (samplemodel2 7.2-7.6 s).

Outcome: samplemodel2 gaps 1002 -> 990, loops 212 -> 195 (faces 1813 exact);
SampleModel4 gaps 347 -> 335, loops 76 -> 72 with FOUR FEWER faces (149 -> 145).
The face count drop is surplus splits, not lost material: the total face area
GROWS from 0.181274 to 0.188455 m2 (+3.96%) - the window patches were short.
"""
from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import pytest

LIB = r"C:\\Program Files\\ANSYS Inc\\v195\\scdm\\Library\\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


@requires_occ
def test_tori_are_allowed_and_the_guard_still_refuses_cones():
    from scdm.import_sab import _trim_surface_allowed
    from OCC.Core.Geom import (Geom_ConicalSurface, Geom_CylindricalSurface,
                               Geom_SphericalSurface, Geom_ToroidalSurface)
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    ax = gp_Ax3(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0),
                       gp_Dir(1.0, 0.0, 0.0)))
    assert _trim_surface_allowed(Geom_ToroidalSurface(ax, 0.02, 0.005))
    assert _trim_surface_allowed(Geom_CylindricalSurface(ax, 0.01))
    assert _trim_surface_allowed(Geom_SphericalSurface(ax, 0.01))
    assert not _trim_surface_allowed(Geom_ConicalSurface(ax, 0.5, 0.01))


@requires_occ
@requires_lib
def test_torus_trimming_is_cheap_now():
    """The R85 refusal was 0.54 s per face; the R93 path is under 0.1 s."""
    from scdm import import_sab
    from scdm.document import load_scdoc
    from OCC.Core.Geom import Geom_ToroidalSurface
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    total = ok = 0
    started = time.time()
    for m in data["models"]:
        box = import_sab._model_bbox(m)
        for f in m.of_kind("face"):
            kind, s = import_sab._surface_kind(m, f)
            if (kind != "torus" or s is None or not s.major or not s.minor
                    or not s.origin or not s.normal or not s.xdir):
                continue
            axis = tuple(c / (sum(x * x for x in s.normal) ** 0.5)
                         for c in s.normal)
            ax = gp_Ax3(gp_Ax2(gp_Pnt(*s.origin), gp_Dir(*axis),
                               gp_Dir(*s.xdir)))
            total += 1
            if import_sab._trimmed_face(m, f, Geom_ToroidalSurface(ax, s.major,
                                                               s.minor),
                                        box, strict_bbox=False) is not None:
                ok += 1
    per_face = (time.time() - started) / max(1, total)
    assert total >= 30, total
    assert ok >= 14, ok                      # measured 14 of 36 (V2/V3 candidates)
    assert per_face < 0.1, per_face          # measured 0.045 (was 0.54)


@requires_occ
@requires_lib
def test_the_outcome_and_the_area_evidence():
    """Gaps/loops down; the four fewer faces carry MORE surface area (R93)."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "SampleModel4.scdoc"))
    areas = []
    faces = []
    gaps = []
    for flag in (True, False):                      # trimmed, then window
        import_sab._TRIM_PATCH = flag
        kdoc = import_sab._import_scdoc_bundle(data)
        n = 0
        area = 0.0
        for b in kdoc.bodies:
            if (b.name or "").startswith("网格导入"):
                continue
            rep = K.watertight_report(b.shape)
            gaps.append(rep["open_edges"])
            for f in K.explore(b.shape, "face"):
                n += 1
                area += K.area(f)
        faces.append(n)
        areas.append(area)
    import_sab._TRIM_PATCH = False
    assert faces == [145, 149], faces
    assert areas[0] > areas[1] * 1.03, areas       # +3.96% measured
    assert sum(gaps[:2]) < sum(gaps[2:]), gaps     # fewer gaps when trimmed
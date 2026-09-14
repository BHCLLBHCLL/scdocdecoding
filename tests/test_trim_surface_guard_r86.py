"""R86/P411: cones and tori are REFUSED by the trim path - one of them crashes.

Measured this round:

  * torus: 0.54 s per face, 16/36 build (BndLib + GProp on a trimmed torus
    dominate the gates) - 36 faces cost 19.4 s and the samplemodel2 import went
    6.8 s -> 25 s, so tori keep the recorded-window path;
  * cone: the PROCESS DIES inside OpenCASCADE on samplemodel2 face 270
    (semi = -30 deg, r = 0.246): the surface builds fine, then the trim kills the
    interpreter - a native crash that no try/except can catch.

_trim_surface_allowed() is the guard: cylinders and spheres only.  The second
test below is the regression - it calls the trim on that exact cone face and
passes only if the guard turned the crash into a clean None.
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
def test_only_cylinders_and_spheres_may_be_trimmed():
    from scdm.import_sab import _trim_surface_allowed
    from OCC.Core.Geom import (Geom_ConicalSurface, Geom_CylindricalSurface,
                               Geom_SphericalSurface, Geom_ToroidalSurface)
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    ax = gp_Ax3(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0),
                       gp_Dir(1.0, 0.0, 0.0)))
    assert _trim_surface_allowed(Geom_CylindricalSurface(ax, 0.01))
    assert _trim_surface_allowed(Geom_SphericalSurface(ax, 0.01))
    assert not _trim_surface_allowed(Geom_ConicalSurface(ax, 0.5, 0.01))
    # R93: tori became cheap enough to allow (single candidate + cheap fallback)
    assert _trim_surface_allowed(Geom_ToroidalSurface(ax, 0.02, 0.005))


@requires_occ
@requires_lib
def test_the_cone_that_crashed_is_refused_instead_of_crashing():
    """samplemodel2 face 270: semi -30 deg, r 0.246 - the native-crash case."""
    from scdm import import_sab
    from scdm.document import load_scdoc
    from OCC.Core.Geom import Geom_ConicalSurface
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    data = load_scdoc(os.path.join(LIB, "samplemodel2.scdoc"))
    # the face is identified by its RECORD, not by an index: face indices are
    # per model and entity 270 exists in several of them
    target = None
    for m in data["models"]:
        for f in m.of_kind("face"):
            kind, s = import_sab._surface_kind(m, f)
            if (kind != "cone" or s is None or s.semangle is None
                    or not s.radius):
                continue
            if (abs(s.semangle + 0.5235987755982988) < 1e-9      # -30 deg
                    and abs(s.radius - 0.2462136) < 1e-4):
                target = (m, f, s)
                break
        if target:
            break
    assert target is not None, "the crashing cone record was not found"
    m, f, s = target
    axis = tuple(c / math.sqrt(sum(x * x for x in s.normal)) for c in s.normal)
    ax = gp_Ax3(gp_Ax2(gp_Pnt(*s.origin), gp_Dir(*axis), gp_Dir(*s.xdir)))
    surf = Geom_ConicalSurface(ax, s.semangle, s.radius)
    box = import_sab._model_bbox(m)
    # the guard must refuse BEFORE anything expensive (or crashing) runs
    assert import_sab._trimmed_face(m, f, surf, box) is None

"""R75/P371: free edges are counted as GAPS, not as seams.

The R74 numbers (SampleModel1 56, SampleModel4 423, samplemodel2 2325) mixed two
very different things: real gaps in the shell and the SEAM of a periodic face (a
cylinder patch stores its seam as one edge used twice by the same face, so the
ancestor map reports a single face).  Measured seams: 0 / 18 / 73.

The classification (tools/free_edge_report.py) also records curve type, owner
surface type, length and how each end continues:

  sample        free  seams  gaps   curve mix                    median length
  SampleModel1    56      0    56   ellipse 42, circle 10, line 4      4.9 mm
  SampleModel4   423     18   405   line 192, circle 109, spline 87    5.6 mm
  samplemodel2  2325     73  2252   line 774, circle 729, ellipse 712 68.7 mm
  samplemodel3/5   0      0     0   -                                  -
  samplemodel6     2      0     2   circle 1, ellipse 1               313 mm

R75 also fixed a lifetime bug this exposed: pythonocc's FindFromIndex returns a
VIEW into the C++ ancestor map, so returning those lists from a helper produced
dangling handles that read as size 0 - every seam then classified as "not a
seam".  edge_face_counts() now materialises everything while the map is alive.
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

# free / seams / gaps - re-measured after R76's cylinder trim policy
MEASURED = {
    "SampleModel1.scdoc": (36, 0, 36),
    "SampleModel4.scdoc": (386, 18, 368),
    "samplemodel2.scdoc": (1494, 34, 1460),
    "samplemodel6.scdoc": (2, 0, 2),
}


@requires_occ
def test_a_full_wrap_cylinder_patch_keeps_its_seam_out_of_the_count():
    """Semantics on a case we build ourselves (R75).

    A full-wrap cylindrical patch has three interesting edges: the SEAM (the
    vertical line, used TWICE by the same face - so the ancestor map already
    counts it twice and it never looks free) and the two rim circles, which
    really are open boundary.  free == open == 2 for this patch.
    """
    from scdm import kernel as K
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.Geom import Geom_CylindricalSurface
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt

    ax = gp_Ax3(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0),
                       gp_Dir(1.0, 0.0, 0.0)))
    surf = Geom_CylindricalSurface(ax, 0.01)
    face = BRepBuilderAPI_MakeFace(surf, 0.0, 6.283185307179586,
                                   0.0, 0.02, 1e-6).Face()
    pairs = K.edge_face_counts(face)
    # the seam is used TWICE by the same face, so the map already counts it
    # twice and it never shows up as free; the two rims are the real boundary
    assert max(n for (_e, n, _f) in pairs) == 2
    free = [(e, f) for (e, n, f) in pairs if n < 2]
    assert len(free) == 2, "the two rim circles"
    assert not any(K.is_seam_edge(e, f) for (e, f) in free)
    assert len(K.free_edges(face)) == 2
    assert len(K.open_edges(face)) == 2


@requires_occ
@requires_lib
def test_free_seam_and_gap_counts_per_sample():
    """Counts are per sample and the seam split is exact (R75)."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc

    for name, (free, seams, gaps) in sorted(MEASURED.items()):
        data = load_scdoc(os.path.join(LIB, name))
        kdoc = import_sab.import_scdoc_bundle(data)
        got_free = got_gaps = 0
        for b in kdoc.bodies:
            if (b.name or "").startswith("网格导入"):
                continue
            got_free += len(K.free_edges(b.shape))
            got_gaps += len(K.open_edges(b.shape))
        assert (got_free, got_free - got_gaps, got_gaps) == (free, seams, gaps), name


@requires_occ
@requires_lib
def test_edge_face_counts_survive_the_call():
    """R75 lifetime bug: views into the ancestor map read 0 once it dies."""
    from scdm import import_sab
    from scdm import kernel as K
    from scdm.document import load_scdoc
    from collections import Counter

    data = load_scdoc(os.path.join(LIB, "SampleModel1.scdoc"))
    kdoc = import_sab.import_scdoc_bundle(data)
    body = [b for b in kdoc.bodies
            if not (b.name or "").startswith("网格导入")][0]
    hist = Counter(n for (_e, n, _f) in K.edge_face_counts(body.shape))
    # R76 trimmed 20 of the 56 free edges away; a dangling view would give {}
    assert hist == {1: 36, 2: 294}, hist

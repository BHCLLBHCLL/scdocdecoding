"""P0-2: geometry-coverage regressions — filleted / holed / conical
solids must write native .scdoc end-to-end (ConvertToBSpline +
_approx_bsurface fallback path)."""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.scdoc_write import write_scdoc  # noqa: E402


def _kdoc(shape, name="p02"):
    body = type("B", (), {"shape": shape, "color": None})()
    doc = type("D", (), {"shape": shape, "bodies": [body],
                         "name": name, "components": None})()
    return doc


def _write_ok(shape) -> bool:
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        write_scdoc(path, _kdoc(shape))
        return os.path.getsize(path) > 1000
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_filleted_box_writes_scdoc():
    """Rounded box (analytic torus/cylinder faces from the round) must
    survive the fallback path."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE
    box = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
    ex = TopExp_Explorer(box, TopAbs_EDGE)
    ex.Next()
    f = BRepFilletAPI_MakeFillet(box)
    f.Add(1.0, ex.Current())
    assert _write_ok(f.Shape())


def test_holed_box_writes_scdoc():
    """Box with a cylindrical bore — non-B-spline faces from the cut."""
    from OCC.Core.BRepPrimAPI import (BRepPrimAPI_MakeBox,
                                      BRepPrimAPI_MakeCylinder)
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    cut = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(20, 20, 20).Shape(),
                          BRepPrimAPI_MakeCylinder(3.0, 40.0).Shape())
    assert _write_ok(cut.Shape())


def test_cone_frustum_writes_scdoc():
    """Conical solid (analytic cone faces) must write."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
    cone = BRepPrimAPI_MakeCone(8.0, 3.0, 30.0).Shape()
    assert _write_ok(cone)


def test_convert_to_bspline_no_deprecation_warning():
    """Regression: static-method call, not the deprecated instance
    accessor."""
    import warnings
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    ex = TopExp_Explorer(box, TopAbs_EDGE)
    ex.Next()
    f = BRepFilletAPI_MakeFillet(box)
    f.Add(0.5, ex.Current())
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any DeprecationWarning -> fail
        _write_ok(f.Shape())


# --------------------------------------------------------------------------
# structural regressions (P0-2 general path: loop rings, exact ellipse
# edges, spline-surface clusters, worklist record-index alignment)
# --------------------------------------------------------------------------

def _decode(path):
    from scdm.document import load_scdoc
    return load_scdoc(path)["model"]


def _write_temp(shape) -> str:
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    write_scdoc(path, _kdoc(shape))
    return path


def test_coedge_pointers_align_with_records():
    """Worklist indices are record units: a spline-surface cluster emits 4
    records (spline+exactsur+nurbs+both), so any entity queued after it
    must shift by 3.  Drift made coedge->edge pointers resolve to
    non-edge records (P0-2 root cause)."""
    from OCC.Core.BRepPrimAPI import (BRepPrimAPI_MakeBox,
                                      BRepPrimAPI_MakeCylinder)
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    cut = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(20, 20, 20).Shape(),
                          BRepPrimAPI_MakeCylinder(3.0, 40.0).Shape())
    path = _write_temp(cut.Shape())
    try:
        model = _decode(path)
        coedges = model.of_kind("coedge")
        assert coedges, "no coedges decoded"
        for ce in coedges:
            tgt = model.e(ce.edge) if ce.edge >= 0 else None
            assert tgt is not None and tgt.kind in ("edge", "tedge"), (
                "coedge %d edge ptr %s -> %s" %
                (ce.idx, ce.edge, tgt.kind if tgt else None))
    finally:
        os.unlink(path)


def test_holed_box_loop_structure():
    """Through-hole box: caps carry outer rect + inner circle loops
    (4 + 1 coedges), wall is the 4-coedge slit ring (seam twice + two
    closed circle edges)."""
    from OCC.Core.BRepPrimAPI import (BRepPrimAPI_MakeBox,
                                      BRepPrimAPI_MakeCylinder)
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.gp import gp_Ax2, gp_Pnt, gp_Dir
    cut = BRepAlgoAPI_Cut(
        BRepPrimAPI_MakeBox(20, 20, 20).Shape(),
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(10, 10, -10), gp_Dir(0, 0, 1)), 3.0, 40.0).Shape())
    path = _write_temp(cut.Shape())
    try:
        model = _decode(path)
        assert len(model.of_kind("face")) == 7
        # exact circle edges -> official ellipse records
        assert len(model.of_kind("ellipse")) == 2
        # one B-spline surface cluster: spline head (entity) + 3 inner
        # payload records (exactsur/nurbs/both)
        assert len(model.of_kind("spline")) == 1
        for kind in ("exactsur", "nurbs", "both"):
            n = sum(1 for e in model.inner if e.kind == kind)
            assert n == 1, (kind, n)
        loop_shapes = sorted(
            tuple(sorted(len(model.coedges_of_loop(lp))
                         for lp in model.loops_of_face(f)))
            for f in model.of_kind("face"))
        assert sorted([(4,)] * 5 + [(1, 4)] * 2) == loop_shapes
    finally:
        os.unlink(path)


def test_cone_cap_single_closed_edge_ring():
    """Cone caps are single-closed-edge loops (1 coedge), side face the
    4-coedge ring; 3 faces total."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
    path = _write_temp(BRepPrimAPI_MakeCone(8.0, 3.0, 30.0).Shape())
    try:
        model = _decode(path)
        faces = model.of_kind("face")
        assert len(faces) == 3
        ces = sorted(len(model.coedges_of_loop(lp))
                     for f in faces for lp in model.loops_of_face(f))
        assert ces == [1, 1, 4]
        assert len(model.of_kind("ellipse")) == 2
    finally:
        os.unlink(path)


def test_filleted_box_vocabulary_and_rings():
    """Rounded box: quarter-cylinder faces as spline clusters, arc edges
    as exact ellipse records, every loop 4 coedges."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE
    box = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
    ex = TopExp_Explorer(box, TopAbs_EDGE)
    f = BRepFilletAPI_MakeFillet(box)
    for _ in range(4):          # one planar face's four edges -> 10 faces
        f.Add(1.0, ex.Current())
        ex.Next()
    path = _write_temp(f.Shape())
    try:
        model = _decode(path)
        assert len(model.of_kind("face")) == 10
        assert len(model.of_kind("spline")) == 4
        assert len(model.of_kind("ellipse")) == 4
        for ce in model.of_kind("coedge"):
            tgt = model.e(ce.edge) if ce.edge >= 0 else None
            assert tgt is not None and tgt.kind in ("edge", "tedge")
    finally:
        os.unlink(path)


def test_plain_box_planar_fast_path_intact():
    """Pure-plane bodies keep the byte-validated path: official record
    vocabulary only, 6 faces / 12 edges / all pointers resolve."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    path = _write_temp(BRepPrimAPI_MakeBox(10, 10, 10).Shape())
    try:
        model = _decode(path)
        assert len(model.of_kind("face")) == 6
        assert len(model.of_kind("edge")) == 12
        # no cluster vocabulary leaked into the planar path
        assert not model.of_kind("spline")
        assert not model.of_kind("ellipse")
        for ce in model.of_kind("coedge"):
            tgt = model.e(ce.edge) if ce.edge >= 0 else None
            assert tgt is not None and tgt.kind in ("edge", "tedge")
    finally:
        os.unlink(path)


def test_lofted_solid_bcur_edges():
    """Smooth loft between rectangles: spline side faces (general path)
    plus corner edges; the stream must decode with aligned pointers."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCC.Core.gp import gp_Pnt
    w1 = BRepBuilderAPI_MakePolygon(
        gp_Pnt(0, 0, 0), gp_Pnt(10, 0, 0), gp_Pnt(10, 10, 0),
        gp_Pnt(0, 10, 0), True).Wire()
    w2 = BRepBuilderAPI_MakePolygon(
        gp_Pnt(5, 5, 25), gp_Pnt(15, 5, 25), gp_Pnt(15, 15, 25),
        gp_Pnt(5, 15, 25), True).Wire()
    loft = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    loft.AddWire(w1)
    loft.AddWire(w2)
    shape = loft.Shape()
    path = _write_temp(shape)
    try:
        model = _decode(path)
        assert model.of_kind("face")
        assert model.of_kind("spline")     # smooth loft -> B-spline faces
        for ce in model.of_kind("coedge"):
            tgt = model.e(ce.edge) if ce.edge >= 0 else None
            assert tgt is not None and tgt.kind in ("edge", "tedge")
    finally:
        os.unlink(path)

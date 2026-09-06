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

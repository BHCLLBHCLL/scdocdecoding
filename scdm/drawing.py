"""G6-02: HLR drawing views — hidden-line-removed 2D polylines per view.

Uses OCCT HLRBRep to project a shape and keeps visible edges (outline included)
as 2D polylines in each view's projection plane. GUI-agnostic and unit-testable.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from scdm import kernel as K

Poly2 = List[Tuple[float, float]]


def view_polylines(shape, direction: Sequence[float], xaxis: Sequence[float] = (1, 0, 0),
                   deflection: float = 1e-4) -> List[Poly2]:
    """Visible-edge polylines of `shape` projected along `direction` (2D points).

    `xaxis` is the horizontal axis of the view (Ax2 X); vertical = direction x xaxis.
    """
    from OCC.Core.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCC.Core.HLRAlgo import HLRAlgo_Projector
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    algo = HLRBRep_Algo()
    algo.Add(shape)
    ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*direction), gp_Dir(*xaxis))
    algo.Projector(HLRAlgo_Projector(ax))
    algo.Update()
    algo.Hide()
    hlr = HLRBRep_HLRToShape(algo)
    polys: List[Poly2] = []
    for comp in (hlr.VCompound(), hlr.OutLineVCompound()):
        if comp is None:
            continue
        for e in K.explore(comp, "edge"):
            pts = K.edge_polyline(e, deflection)
            if len(pts) >= 2:
                polys.append([(p[0], p[1]) for p in pts])
    return polys


def three_views(shape) -> List[Tuple[str, List[Poly2]]]:
    """主视 / 俯视 / 右视 HLR polylines for `shape`."""
    return [
        ("主视", view_polylines(shape, (0, -1, 0), (1, 0, 0))),
        ("俯视", view_polylines(shape, (0, 0, -1), (1, 0, 0))),
        ("右视", view_polylines(shape, (1, 0, 0), (0, 1, 0))),
    ]


def extents(polys: List[Poly2]):
    """(xmin, ymin, xmax, ymax) over all polylines, or None when empty."""
    xs = [x for poly in polys for x, _ in poly]
    ys = [y for poly in polys for _, y in poly]
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))

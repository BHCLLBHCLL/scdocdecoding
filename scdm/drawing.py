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


# ----------------------------------------------------- TODO-5: sheet formats

SHEET_FORMATS = {
    # official DrawingFormats library (width/height in metres, extracted
    # 2026-09-06 from the installed SpaceClaim 2019 R3 files)
    "A0": (1.189, 0.841),
    "A1": (0.841, 0.594),
    "A2": (0.594, 0.420),
    "A3": (0.420, 0.297),
    "A4": (0.210, 0.297),
    "B": (0.4318, 0.2794),
    "C": (0.5588, 0.4318),
}


def sheet_template(fmt: str) -> str:
    """DrawingSheetDef XML fragment matching the official format
    structure (A4.scdoc): sheet size + SheetScaleDef + the border frame
    as LineSegment SketchCurveDefs (10 mm margin)."""
    w, h = SHEET_FORMATS[fmt]
    m = 0.01
    border = (
        f'<SketchCurveDef Id="1:92" xmlns="urn:sketch">'
        f'<color>Black</color>'
        f'<curve sctype="SpaceClaim.Geometry.LineSegment, Geometry">'
        f'<start>{m} {m} 0</start><dir>1 0 0</dir><length>{w - 2 * m}</length>'
        f'</curve></SketchCurveDef>'
    )
    return (
        f'<DrawingSheetDef Id="0:27"><updateState>6:29</updateState>'
        f'<viewSpecificVisibilityEnabled>False</viewSpecificVisibilityEnabled>'
        f'<renderingMode>Shaded</renderingMode>'
        f'<width>{w:g}</width><height>{h:g}</height>'
        f'<createdInVersion>0</createdInVersion>'
        f'<SheetScaleDef Id="0:29"><updateState>3:1</updateState>'
        f'<scale>1</scale>'
        f'<scaleFormat sctype="SpaceClaim.Annotations.FractionalScaleFormat, '
        f'Presentation"><denominator>1</denominator></scaleFormat>'
        f'<scaleNeverSet>False</scaleNeverSet></SheetScaleDef>'
        f'{border}</DrawingSheetDef>'
    )


def layout_three_views(shape, fmt: str):
    """Fit the three HLR views into the sheet with margins.

    Returns [(view_name, polylines, (x0, y0, x1, y1) placement rect)].
    Views are scaled uniformly so the widest view fits two columns."""
    w, h = SHEET_FORMATS[fmt]
    margin = 0.015
    views = three_views(shape)
    rects = []
    exts = [extents(p) for _, p in views]
    max_w = max((e[2] - e[0]) for e in exts if e)
    max_h = max((e[3] - e[1]) for e in exts if e)
    if max_w <= 0 or max_h <= 0:
        return []
    avail_w = (w - 3 * margin) / 2
    avail_h = (h - 3 * margin) / 2
    scale = min(avail_w / max_w, avail_h / max_h, 1.0)
    # 主视 top-left, 俯视 bottom-left, 右视 top-right
    slots = [(margin, h - margin - max_h * scale),
             (margin, margin),
             (2 * margin + avail_w, h - margin - max_h * scale)]
    for (name, polys), (sx, sy) in zip(views, slots):
        rects.append((name, polys, (sx, sy, sx + max_w * scale,
                                    sy + max_h * scale)))
    return rects

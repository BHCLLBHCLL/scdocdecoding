"""G6-02: HLR drawing views — hidden-line-removed 2D polylines per view.

Uses OCCT HLRBRep to project a shape and keeps visible edges (outline included)
as 2D polylines in each view's projection plane. GUI-agnostic and unit-testable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

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


def projected_view(shape, direction: Sequence[float],
                   xaxis: Sequence[float] = (1, 0, 0),
                   label: str = "投影") -> Tuple[str, List[Poly2]]:
    """P7: one HLR view along an arbitrary direction (user-chosen projection)."""
    d = tuple(float(v) for v in direction)
    if all(abs(v) < 1e-12 for v in d):
        raise ValueError("投影视图：方向不能为零向量")
    return label, view_polylines(shape, d, xaxis)


def _to_2d(p3, xaxis, yaxis):
    return (sum(p3[i] * xaxis[i] for i in range(3)),
            sum(p3[i] * yaxis[i] for i in range(3)))


def section_view(shape, origin: Sequence[float], normal: Sequence[float],
                 direction: Optional[Sequence[float]] = None,
                 xaxis: Sequence[float] = (1, 0, 0),
                 label: str = "剖视") -> Tuple[str, List[Poly2]]:
    """P7: cut the shape with a plane and project the section outline to 2D.

    The view direction defaults to the cutting-plane normal, so the section
    is seen face-on.
    """
    n = tuple(float(v) for v in normal)
    d = tuple(float(v) for v in (direction if direction is not None else n))
    xa = tuple(float(v) for v in xaxis)
    if abs(sum(xa[i] * d[i] for i in range(3))) > 0.99:
        xa = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
    # y = d x x  (right-handed view basis)
    ya = (d[1] * xa[2] - d[2] * xa[1],
          d[2] * xa[0] - d[0] * xa[2],
          d[0] * xa[1] - d[1] * xa[0])
    polys: List[Poly2] = []
    for poly in K.section_outline(shape, tuple(origin), n):
        polys.append([_to_2d(p, xa, ya) for p in poly])
    return label, polys


def annotate(views) -> List[str]:
    """P7: one dimension note per view (overall width x height, in mm)."""
    notes = []
    for name, polys in views:
        e = extents(polys)
        if e is None:
            notes.append(f"{name}: -")
            continue
        notes.append(f"{name}: {(e[2] - e[0]) * 1000:.1f} x "
                     f"{(e[3] - e[1]) * 1000:.1f} mm")
    return notes


@dataclass
class Dimension:
    """P17: a dimension object tied to a view interval.

    offset shifts the dimension line away from the measured interval (the GUI
    drags it); changing it never changes the measured value or the geometry.
    """
    view: str
    axis: str                                  # 'h' | 'v'
    value_mm: float
    a: Tuple[float, float]
    b: Tuple[float, float]
    offset: float = 0.01
    assoc: Optional[dict] = None      # P24: edge selector for re-measurement
    stale: bool = False               # P48: association lost; value not trusted

    def normal(self):
        """P48: unit direction the offset moves the dimension line along."""
        if self.axis == "h":
            return (0.0, 1.0)
        if self.axis == "v":
            return (1.0, 0.0)
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        L = math.hypot(dx, dy) or 1.0
        return (-dy / L, dx / L)

    def handle_point(self):
        """P48: the draggable point - the middle of the dimension line."""
        return self.text_at()

    def offset_for_point(self, p) -> float:
        """P48: the offset that would put the dimension line through p."""
        (ax, ay) = self.a
        (nx, ny) = self.normal()
        return (p[0] - ax) * nx + (p[1] - ay) * ny

    def drag_to(self, p, minimum=None) -> float:
        """P48: move the dimension line to p.

        Only the offset changes - the measured value, the endpoints and the
        geometry are untouched, which is the whole point of a dimension object
        (the value is a measurement, not a driving parameter).
        """
        value = self.offset_for_point(p)
        if minimum is not None:
            value = max(minimum, value)
        self.offset = value
        return self.offset

    def drag_by(self, du: float, dv: float, minimum=None) -> float:
        """P48: nudge the line by (du, dv) in view coordinates."""
        (hx, hy) = self.handle_point()
        return self.drag_to((hx + du, hy + dv), minimum)
    def line(self):
        """((x1, y1), (x2, y2)) of the dimension line in view coordinates."""
        (ax, ay), (bx, by) = self.a, self.b
        if self.axis == "h":
            return ((ax, ay + self.offset), (bx, by + self.offset))
        if self.axis == "v":
            return ((ax + self.offset, ay), (bx + self.offset, by))
        # arbitrary span (edge-associated): offset along its normal
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        return ((ax + nx * self.offset, ay + ny * self.offset),
                (bx + nx * self.offset, by + ny * self.offset))

    def text_at(self):
        (p, q) = self.line()
        return ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)


def edge_selector(shape, edge):
    """P24: identity for an edge that survives a moderate geometry change."""
    pts = K.edge_polyline(edge, 1e-4)
    if len(pts) < 2:
        return None
    mid = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return {"mid": mid, "length": length}


def _projected_length(pts, direction, xaxis) -> float:
    """Length of a 3D polyline projected into the view plane."""
    d = tuple(float(v) for v in direction)
    L = math.sqrt(sum(v * v for v in d)) or 1.0
    d = tuple(v / L for v in d)
    xa = tuple(float(v) for v in xaxis)
    ax = sum(xa[i] * d[i] for i in range(3))
    xa = tuple(xa[i] - ax * d[i] for i in range(3))
    nx = math.sqrt(sum(v * v for v in xa)) or 1.0
    xa = tuple(v / nx for v in xa)
    ya = (d[1] * xa[2] - d[2] * xa[1], d[2] * xa[0] - d[0] * xa[2],
          d[0] * xa[1] - d[1] * xa[0])
    total = 0.0
    uv = [(sum(p[i] * xa[i] for i in range(3)),
           sum(p[i] * ya[i] for i in range(3))) for p in pts]
    for i in range(len(uv) - 1):
        total += math.dist(uv[i], uv[i + 1])
    return total


def dimension_for_edge(shape, edge, direction=(0.0, 0.0, -1.0),
                       xaxis=(1.0, 0.0, 0.0), view="投影"):
    """P24: a dimension associated with an edge (value = projected length)."""
    sel = edge_selector(shape, edge)
    if sel is None:
        return None
    pts = K.edge_polyline(edge, 1e-4)
    d = tuple(float(v) for v in direction)
    L = math.sqrt(sum(v * v for v in d)) or 1.0
    d = tuple(v / L for v in d)
    xa = tuple(float(v) for v in xaxis)
    ax = sum(xa[i] * d[i] for i in range(3))
    xa = tuple(xa[i] - ax * d[i] for i in range(3))
    nx = math.sqrt(sum(v * v for v in xa)) or 1.0
    xa = tuple(v / nx for v in xa)
    ya = (d[1] * xa[2] - d[2] * xa[1], d[2] * xa[0] - d[0] * xa[2],
          d[0] * xa[1] - d[1] * xa[0])
    a = (sum(pts[0][i] * xa[i] for i in range(3)),
         sum(pts[0][i] * ya[i] for i in range(3)))
    b = (sum(pts[-1][i] * xa[i] for i in range(3)),
         sum(pts[-1][i] * ya[i] for i in range(3)))
    return Dimension(view, "edge", _projected_length(pts, direction, xaxis) * 1000.0,
                     a, b, 0.01, assoc=sel)


def remeasure_edge(shape, selector, direction=(0.0, 0.0, -1.0),
                   xaxis=(1.0, 0.0, 0.0), tol_ratio: float = 0.3):
    """P24: re-find the edge for a selector and return its projected length (mm).

    The association is a heuristic by design: the nearest edge midpoint within
    30% of the stored length wins. Returns None when the edge is gone (the
    dimension should then be marked stale rather than silently wrong).
    """
    if not selector:
        return None
    old_mid = selector.get("mid")
    old_len = float(selector.get("length") or 0.0)
    if old_mid is None or old_len <= 0:
        return None
    tol = old_len * max(0.05, tol_ratio)
    best = None
    best_d = None
    for e in K.explore(shape, "edge"):
        pts = K.edge_polyline(e, 1e-3)
        if len(pts) < 2:
            continue
        mid = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        d = math.dist(mid, old_mid)
        if d <= tol and (best_d is None or d < best_d):
            best_d, best = d, pts
    if best is None:
        return None
    return _projected_length(best, direction, xaxis) * 1000.0


def refresh_dimensions(shape, dims):
    """P24: re-measure associated dimensions; returns (dims, stale_count)."""
    stale = 0
    for d in dims:
        if getattr(d, "assoc", None) is None:
            continue
        value = remeasure_edge(shape, d.assoc)
        if value is None:
            # P48: keep the last known value but mark it untrusted, so the
            # sheet can draw it as a warning instead of a wrong measurement
            d.stale = True
            stale += 1
        else:
            d.value_mm = value
            d.stale = False
    return dims, stale


def dimensions_for(views, offset: float = 0.01) -> List["Dimension"]:
    """Overall horizontal + vertical dimension for every view (mm values)."""
    out: List[Dimension] = []
    for name, polys in views:
        e = extents(polys)
        if e is None:
            continue
        out.append(Dimension(name, "h", (e[2] - e[0]) * 1000.0,
                             (e[0], e[1]), (e[2], e[1]), -offset))
        out.append(Dimension(name, "v", (e[3] - e[1]) * 1000.0,
                             (e[0], e[1]), (e[0], e[3]), -offset))
    return out


def _view_placements(views, fmt: str):
    """Per-view (ox, oy, scale, sx, sy, avail_w, avail_h) in sheet metres."""
    w, h = SHEET_FORMATS[fmt]
    m = 0.015
    boxes = [b for b in (extents(p) for _n, p in views) if b]
    if not boxes:
        raise ValueError("没有可导出的视图")
    max_w = max(b[2] - b[0] for b in boxes)
    max_h = max(b[3] - b[1] for b in boxes)
    cols = 2 if len(views) > 1 else 1
    rows = max(1, (len(views) + cols - 1) // cols)
    avail_w = (w - (cols + 1) * m) / cols
    avail_h = (h - (rows + 1) * m) / rows
    scale = min(avail_w / max_w if max_w else 1.0,
                avail_h / max_h if max_h else 1.0, 1.0)
    out = []
    for i, (name, polys) in enumerate(views):
        col, row = i % cols, i // cols
        e = extents(polys)
        sx = (e[0] + e[2]) / 2.0 if e else 0.0
        sy = (e[1] + e[3]) / 2.0 if e else 0.0
        out.append({"name": name, "ox": m + col * (avail_w + m),
                    "oy": h - m - row * (avail_h + m), "scale": scale,
                    "sx": sx, "sy": sy, "avail_w": avail_w,
                    "avail_h": avail_h, "mm": 1000.0})
    return out


def _place(pt, pl):
    """View coords (metres) -> sheet coords (mm)."""
    x, y = pt
    return ((pl["ox"] + pl["avail_w"] / 2 + (x - pl["sx"]) * pl["scale"]) * pl["mm"],
            (pl["oy"] - pl["avail_h"] / 2 - (y - pl["sy"]) * pl["scale"]) * pl["mm"])


_DXF_HEADER = "0\nSECTION\n2\nENTITIES\n"
_DXF_FOOTER = "0\nENDSEC\n0\nEOF\n"


def _dxf_line(p1, p2, layer: str = "0") -> str:
    return ("0\nLINE\n8\n%s\n10\n%.4f\n20\n%.4f\n11\n%.4f\n21\n%.4f\n"
            % (layer, p1[0], p1[1], p2[0], p2[1]))


def _dxf_text(p, height, text, layer: str = "0") -> str:
    return ("0\nTEXT\n8\n%s\n10\n%.4f\n20\n%.4f\n40\n%.4f\n1\n%s\n"
            % (layer, p[0], p[1], height, text))


def write_dxf(views, path: str, fmt: str = "A4", dimensions=True,
              extra_lines=None) -> str:
    """P17/P26: export the views (+ dimensions + extra lines) as ASCII DXF.

    extra_lines entries are (uv1, uv2, layer, text) in view coordinates - used
    by the sheet-metal flat pattern for bend lines and their angle labels.
    """
    placements = _view_placements(views, fmt)
    # P48: True derives them, False drops them, a list means the caller owns
    # the live objects (so dragged offsets and stale flags are what gets out)
    if dimensions is True:
        dims = dimensions_for(views)
    elif dimensions:
        dims = list(dimensions)
    else:
        dims = []
    body = []
    for (name, polys), pl in zip(views, placements):
        for poly in polys:
            pts = [_place(p, pl) for p in poly]
            for i in range(len(pts) - 1):
                body.append(_dxf_line(pts[i], pts[i + 1]))
        if dims:
            for d in dims:
                if d.view != name:
                    continue
                p, q = d.line()
                sp, sq = _place(p, pl), _place(q, pl)
                body.append(_dxf_line(sp, sq))
                tx, ty = d.text_at()
                body.append(_dxf_text(_place((tx, ty), pl), 3.5,
                                      "%.1f" % d.value_mm))
        for item in extra_lines or ():
            uv1, uv2, layer, text = item
            p1, p2 = _place(uv1, pl), _place(uv2, pl)
            body.append(_dxf_line(p1, p2, layer=layer))
            if text:
                body.append(_dxf_text(p1, 3.0, text, layer=layer))
    with open(path, "w", encoding="utf-8") as f:
        f.write(_DXF_HEADER + "".join(body) + _DXF_FOOTER)
    return path


def svg_sheet(views, path: str, fmt: str = "A4", title: str = "",
              annotate_views: bool = True, dimensions=True) -> str:
    """P7: write the views to a scaled SVG sheet (border + dimension notes).

    ``dimensions`` is True (derive from the views), False (none) or a list of
    Dimension objects (P48: the GUI passes the live, draggable ones so their
    offsets and stale flags are what gets exported).
    """
    if dimensions is True:
        dims = dimensions_for(views)
    elif dimensions:
        dims = list(dimensions)
    else:
        dims = []
    w, h = SHEET_FORMATS[fmt]
    m = 0.015
    boxes = [extents(polys) for _n, polys in views]
    boxes = [b for b in boxes if b]
    if not boxes:
        raise ValueError("没有可导出的视图")
    max_w = max(b[2] - b[0] for b in boxes)
    max_h = max(b[3] - b[1] for b in boxes)
    cols = 2 if len(views) > 1 else 1
    rows = max(1, (len(views) + cols - 1) // cols)
    avail_w = (w - (cols + 1) * m) / cols
    avail_h = (h - (rows + 1) * m) / rows
    scale = min(avail_w / max_w if max_w else 1.0,
                avail_h / max_h if max_h else 1.0, 1.0)
    mm = 1000.0
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * mm:.3f}" '
           f'height="{h * mm:.3f}" viewBox="0 0 {w * mm:.3f} {h * mm:.3f}">',
           f'<rect x="0" y="0" width="{w * mm:.3f}" height="{h * mm:.3f}" '
           f'fill="white" stroke="black" stroke-width="0.35"/>']
    if title:
        out.append(f'<text x="{m * mm:.2f}" y="{(h - m / 2) * mm:.2f}" '
                   f'font-size="4">{title}</text>')
    notes = annotate(views) if annotate_views else [""] * len(views)
    for i, ((name, polys), note) in enumerate(zip(views, notes)):
        col, row = i % cols, i // cols
        ox = m + col * (avail_w + m)
        oy = h - m - row * (avail_h + m)      # SVG y grows downward
        e = extents(polys)
        if e is None:
            continue
        sx = (e[0] + e[2]) / 2.0
        sy = (e[1] + e[3]) / 2.0
        for poly in polys:
            pts = " ".join(
                f"{(ox + (avail_w / 2) + (x - sx) * scale) * mm:.3f},"
                f"{(oy - avail_h / 2 - (y - sy) * scale) * mm:.3f}"
                for x, y in poly)
            out.append(f'<polyline fill="none" stroke="black" '
                       f'stroke-width="0.2" points="{pts}"/>')
        out.append(f'<text x="{ox * mm:.2f}" y="{(oy + 4) * mm:.2f}" '
                   f'font-size="3.5">{note}</text>')
        if dims:
            for d in dims:
                if d.view != name:
                    continue
                (px, py), (qx, qy) = d.line()
                tx, ty = d.text_at()
                sp = _place((px, py), {"ox": ox, "oy": oy, "scale": scale,
                                       "sx": sx, "sy": sy,
                                       "avail_w": avail_w, "avail_h": avail_h,
                                       "mm": mm})
                sq = _place((qx, qy), {"ox": ox, "oy": oy, "scale": scale,
                                       "sx": sx, "sy": sy,
                                       "avail_w": avail_w, "avail_h": avail_h,
                                       "mm": mm})
                st = _place((tx, ty), {"ox": ox, "oy": oy, "scale": scale,
                                       "sx": sx, "sy": sy,
                                       "avail_w": avail_w, "avail_h": avail_h,
                                       "mm": mm})
                # P48: a dimension whose edge association was lost keeps its
                # stored value but is drawn as a warning, never as a fact
                colour = "#c60" if getattr(d, "stale", False) else "#b00"
                value = f"{d.value_mm:.1f}" + ("?" if getattr(d, "stale", False)
                                               else "")
                out.append(f'<line class="dim" x1="{sp[0]:.3f}" y1="{sp[1]:.3f}" '
                           f'x2="{sq[0]:.3f}" y2="{sq[1]:.3f}" stroke="{colour}" '
                           f'stroke-width="0.2"/>')
                out.append(f'<text class="dim" x="{st[0]:.3f}" y="{st[1]:.3f}" '
                           f'font-size="3" fill="{colour}">'
                           f'{value}</text>')
    out.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


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

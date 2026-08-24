"""M5-03: additive print-prep helpers (build volume / orientation / supports / lattice).

All operations are OCCT-based and unit-testable; the additive ribbon commands call
into these helpers on the selected body.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from scdm import kernel as K

Vec3 = Tuple[float, float, float]


def shape_bbox(shape):
    """Axis-aligned bounding box of a shape: ((xmin,ymin,zmin), (xmax,ymax,zmax))."""
    pts = []
    for v in K.explore(shape, "vertex"):
        p = _vertex_point(v)
        if p is not None:
            pts.append(p)
    if not pts:
        return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _vertex_point(v):
    try:
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopoDS import topods
        p = BRep_Tool().Pnt(topods.Vertex(v))
        return (p.X(), p.Y(), p.Z())
    except Exception:
        return None


def build_volume(shape, margin_mm: float = 1.0, scale: float = 1000.0):
    """The printer build volume: the body's bbox grown by margin_mm on each side."""
    lo, hi = shape_bbox(shape)
    m = margin_mm / scale
    return K.make_box(hi[0] - lo[0] + 2 * m, hi[1] - lo[1] + 2 * m,
                      hi[2] - lo[2] + 2 * m,
                      origin=(lo[0] - m, lo[1] - m, lo[2] - m))


def orient_min_height(shape):
    """Rotate the shape so its shortest bbox side is along Z (min build height).

    Returns the rotated shape (rotation about the bbox centre).
    """
    lo, hi = shape_bbox(shape)
    dx, dy, dz = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
    if dz <= dx and dz <= dy:
        return shape  # already lowest along Z
    centre = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
    if dx <= dy and dx <= dz:
        # rotate about Y by 90deg so X becomes Z
        out = K.rotate(shape, centre, (0, 1, 0), math.pi / 2)
    else:
        out = K.rotate(shape, centre, (1, 0, 0), math.pi / 2)
    return out


def support_blocks(shape, count: int = 4, thickness_mm: float = 1.0,
                   height_mm: float = 5.0, scale: float = 1000.0) -> List:
    """Simple support pillars between the body's bottom face and the ground (z=0)."""
    lo, hi = shape_bbox(shape)
    if lo[2] <= 1e-9:
        return []
    t = thickness_mm / scale
    h = lo[2]
    xs = [lo[0], hi[0] - t]
    ys = [lo[1], hi[1] - t]
    out = []
    for x in xs:
        for y in ys:
            out.append(K.make_box(t, t, h, origin=(x, y, 0.0)))
    return out


def lattice(volume_shape, spacing_mm: float = 5.0, strut_mm: float = 0.5,
            scale: float = 1000.0) -> List:
    """A simple strut lattice (vertical cylinders) filling the given volume shape."""
    lo, hi = shape_bbox(volume_shape)
    s = spacing_mm / scale
    r = strut_mm / 2.0 / scale
    out = []
    x = lo[0] + s / 2
    while x < hi[0]:
        y = lo[1] + s / 2
        while y < hi[1]:
            out.append(K.make_cylinder(r, hi[2] - lo[2], origin=(x, y, lo[2])))
            y += s
        x += s
    return out

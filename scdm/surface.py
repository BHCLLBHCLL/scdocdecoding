"""H6: surface-page kernel — untrim, extend, offset, thicken, patch, blend.

All functions accept/produce OCCT shapes (faces/shells/solids); metres.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence

from scdm import kernel as K


def _occ():
    return K._occ()


def _face_area(shape) -> float:
    o = _occ()
    from OCC.Core.GProp import GProp_GProps
    p = GProp_GProps()
    o["brepgprop"].SurfaceProperties(shape, p)
    return p.Mass()


def surface_of(face):
    """Underlying Geom_Surface of a face."""
    o = _occ()
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopoDS import topods
    return BRep_Tool().Surface_s(topods.Face(face)) if hasattr(BRep_Tool(), "Surface_s") else BRep_Tool().Surface(topods.Face(face))


def untrim(face, expand: float = 1.0):
    """Rebuild a face over its surface's NATURAL UV bounds (drop trims).

    Bounds that are infinite on the underlying surface (cylinder V, plane
    U/V) are replaced by the face's current range expanded by `expand`
    times on each side — the seam/trim wires disappear either way.
    """
    import math as _m
    o = _occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.TopoDS import topods
    surf = surface_of(face)
    u1, u2, v1, v2 = surf.Bounds()
    ad = BRepAdaptor_Surface(topods.Face(face))
    fu1, fu2 = ad.FirstUParameter(), ad.LastUParameter()
    fv1, fv2 = ad.FirstVParameter(), ad.LastVParameter()

    def fin(x, cur_lo, cur_hi):
        if _m.isfinite(x) and abs(x) < 1e50:
            return x
        r = cur_hi - cur_lo
        return cur_lo - r * expand, cur_hi + r * expand

    if (not _m.isfinite(u1) or not _m.isfinite(u2)
            or abs(u1) > 1e50 or abs(u2) > 1e50):
        u1, u2 = fu1 - (fu2 - fu1) * expand, fu2 + (fu2 - fu1) * expand
    if (not _m.isfinite(v1) or not _m.isfinite(v2)
            or abs(v1) > 1e50 or abs(v2) > 1e50):
        v1, v2 = fv1 - (fv2 - fv1) * expand, fv2 + (fv2 - fv1) * expand
    f = BRepBuilderAPI_MakeFace(surf, u1, u2, v1, v2, 1e-6).Face()
    if f.IsNull():
        raise K.KernelError("untrim 失败")
    return f


def extend_face(face, length: float, in_u: bool = True,
                after: bool = True, continuity: int = 1):
    """Extend a face's underlying surface by `length`.

    B-spline surfaces: GeomLib ExtendSurfByLength (in U or V, at the start
    or end).  Analytic surfaces: rebuild over expanded UV bounds (plane).
    Returns the new face (natural bounds).
    """
    o = _occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface, GeomAbs_Plane
    from OCC.Core.TopoDS import topods
    from OCC.Core.GeomLib import geomlib_ExtendSurfByLength
    ad = BRepAdaptor_Surface(topods.Face(face))
    st = ad.GetType()
    if st == GeomAbs_BSplineSurface:
        bs = ad.BSpline()
        geomlib_ExtendSurfByLength(bs, length, continuity, in_u, after)
        return BRepBuilderAPI_MakeFace(bs, 1e-6).Face()
    if st == GeomAbs_Plane:
        u1, u2, v1, v2 = (ad.FirstUParameter(), ad.LastUParameter(),
                          ad.FirstVParameter(), ad.LastVParameter())
        if in_u:
            if after:
                u2 += length
            else:
                u1 -= length
        else:
            if after:
                v2 += length
            else:
                v1 -= length
        surf = surface_of(face)
        return BRepBuilderAPI_MakeFace(surf, u1, u2, v1, v2, 1e-6).Face()
    # generic: expand UV range by length along the chosen direction
    surf = surface_of(face)
    u1, u2, v1, v2 = (ad.FirstUParameter(), ad.LastUParameter(),
                      ad.FirstVParameter(), ad.LastVParameter())
    if in_u:
        if after:
            u2 += length
        else:
            u1 -= length
    else:
        if after:
            v2 += length
        else:
            v1 -= length
    return BRepBuilderAPI_MakeFace(surf, u1, u2, v1, v2, 1e-6).Face()


def offset_face(face, dist: float):
    """Offset a face's surface by `dist` along its normal, keeping the
    face's own UV bounds (Geom_OffsetSurface rebuild)."""
    from OCC.Core.Geom import Geom_OffsetSurface
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.TopoDS import topods
    surf = surface_of(face)
    off = Geom_OffsetSurface(surf, dist)
    ad = BRepAdaptor_Surface(topods.Face(face))
    f = BRepBuilderAPI_MakeFace(off, ad.FirstUParameter(), ad.LastUParameter(),
                                ad.FirstVParameter(), ad.LastVParameter(),
                                1e-6).Face()
    if f.IsNull():
        raise K.KernelError("偏移失败")
    return f


def thicken(face, thickness: float, reverse: bool = False):
    """Solidify a face by extruding along its normal (one-sided thicken).
    reverse=True extrudes opposite the normal."""
    o = _occ()
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.TopoDS import topods
    n, _c = K.face_normal_center(topods.Face(face))
    sgn = -1.0 if reverse else 1.0
    v = o["gp"].gp_Vec(n[0] * thickness * sgn, n[1] * thickness * sgn,
                       n[2] * thickness * sgn)
    return BRepPrimAPI_MakePrism(face, v).Shape()


def patch_fill(boundary_edges: Sequence, continuity: int = 0):
    """N-sided patch: fill a closed boundary (wire/edges) with a surface
    that meets each edge with the given continuity (0=G0, 1=G1)."""
    o = _occ()
    from OCC.Core.BRepFill import BRepFill_Filling
    from OCC.Core.GeomAbs import GeomAbs_C0, GeomAbs_G1
    fill = BRepFill_Filling()
    cont = {0: GeomAbs_C0, 1: GeomAbs_G1}.get(continuity, GeomAbs_C0)
    n = 0
    for e in boundary_edges:
        fill.Add(e, cont)
        n += 1
    if n < 3:
        raise K.KernelError("补面：至少需要三条边界")
    fill.Build()
    if not fill.IsDone():
        raise K.KernelError("补面失败")
    return fill.Face()


def wire_of(face):
    """Boundary wires of a face as edge lists."""
    return K.explore(face, "edge")


def blend_loft(wire1, wire2, ruled: bool = False):
    """Smooth blend surface (shell) between two boundary wires via
    ThruSections (ruled=False gives a B-spline blend)."""
    o = _occ()
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    ts = BRepOffsetAPI_ThruSections(False, ruled, 1e-6)
    ts.AddWire(wire1)
    ts.AddWire(wire2)
    ts.Build()
    if not ts.IsDone():
        raise K.KernelError("曲面过渡失败")
    return ts.Shape()


def make_wire_from_edges(edges: Sequence):
    o = _occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire
    mk = BRepBuilderAPI_MakeWire()
    for e in edges:
        mk.Add(e)
    if not mk.IsDone():
        raise K.KernelError("线框构建失败")
    return mk.Wire()

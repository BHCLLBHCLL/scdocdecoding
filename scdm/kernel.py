"""Open CASCADE modeling kernel (pythonocc-core).

Public SpaceClaim 2019 editing semantics (help.spaceclaim.com):
Pull offsets/extrudes faces; Move transforms; Fill heals; Combine fuse/cut/common.
No SpaceClaim binaries are used.
"""
from __future__ import annotations

import math
import os
import tempfile
from typing import Any, Iterable, List, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]


class KernelError(RuntimeError):
    pass


def available() -> bool:
    try:
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox  # noqa: F401
        return True
    except Exception:
        return False


def _occ():
    if not available():
        raise KernelError("pythonocc-core 未安装。请: conda install -c conda-forge pythonocc-core")
    import OCC.Core.BRepAlgoAPI as algo
    import OCC.Core.BRepBuilderAPI as bapi
    import OCC.Core.BRepFilletAPI as fillet
    import OCC.Core.BRepGProp as brepgprop_mod
    import OCC.Core.BRepMesh as mesh
    import OCC.Core.BRepOffsetAPI as offset
    import OCC.Core.BRepPrimAPI as prim
    import OCC.Core.GProp as gprop
    import OCC.Core.GeomAbs as geomabs
    import OCC.Core.IFSelect as ifs
    import OCC.Core.STEPControl as step
    import OCC.Core.StlAPI as stl
    import OCC.Core.TopAbs as topabs
    import OCC.Core.TopExp as topexp
    import OCC.Core.TopLoc as toploc
    import OCC.Core.TopoDS as topods
    import OCC.Core.gp as gp
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools
    return {
        "algo": algo, "bapi": bapi, "fillet": fillet, "prim": prim,
        "gp": gp, "topabs": topabs, "topexp": topexp, "topods": topods,
        "mesh": mesh, "gprop": gprop, "brepgprop": brepgprop_mod,
        "offset": offset, "step": step, "ifs": ifs, "stl": stl,
        "BRep_Tool": BRep_Tool, "BRepAdaptor_Surface": BRepAdaptor_Surface,
        "breptools": breptools, "toploc": toploc, "geomabs": geomabs,
    }


def _as_face(shape):
    o = _occ()
    return o["topods"].topods.Face(shape)


def _as_edge(shape):
    o = _occ()
    return o["topods"].topods.Edge(shape)


def _as_wire(shape):
    o = _occ()
    return o["topods"].topods.Wire(shape)


def _as_solid(shape):
    o = _occ()
    return o["topods"].topods.Solid(shape)


def explore(shape, kind: str) -> List[Any]:
    o = _occ()
    kind_map = {
        "face": o["topabs"].TopAbs_FACE,
        "edge": o["topabs"].TopAbs_EDGE,
        "solid": o["topabs"].TopAbs_SOLID,
        "vertex": o["topabs"].TopAbs_VERTEX,
        "wire": o["topabs"].TopAbs_WIRE,
        "shell": o["topabs"].TopAbs_SHELL,
    }
    mod = o["topods"]
    topods = getattr(mod, "topods", mod)
    caster = {
        "face": topods.Face,
        "edge": topods.Edge,
        "solid": topods.Solid,
        "vertex": topods.Vertex,
        "wire": topods.Wire,
        "shell": topods.Shell,
    }[kind]
    exp = o["topexp"].TopExp_Explorer(shape, kind_map[kind])
    out = []
    while exp.More():
        out.append(caster(exp.Current()))
        exp.Next()
    return out


def make_box(dx: float, dy: float, dz: float, origin: Vec3 = (0.0, 0.0, 0.0)):
    o = _occ()
    p = o["gp"].gp_Pnt(*origin)
    return o["prim"].BRepPrimAPI_MakeBox(p, dx, dy, dz).Shape()


def make_cylinder(radius: float, height: float, origin: Vec3 = (0.0, 0.0, 0.0),
                  axis: Vec3 = (0.0, 0.0, 1.0)):
    o = _occ()
    ax = o["gp"].gp_Ax2(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*axis))
    return o["prim"].BRepPrimAPI_MakeCylinder(ax, radius, height).Shape()


def make_sphere(radius: float, origin: Vec3 = (0.0, 0.0, 0.0)):
    o = _occ()
    return o["prim"].BRepPrimAPI_MakeSphere(o["gp"].gp_Pnt(*origin), radius).Shape()


def make_torus(major: float, minor: float, origin: Vec3 = (0.0, 0.0, 0.0),
               axis: Vec3 = (0.0, 0.0, 1.0)):
    o = _occ()
    ax = o["gp"].gp_Ax2(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*axis))
    return o["prim"].BRepPrimAPI_MakeTorus(ax, major, minor).Shape()


def make_plane_face(origin: Vec3, normal: Vec3, half: float = 0.05):
    o = _occ()
    pln = o["gp"].gp_Pln(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*normal))
    return o["bapi"].BRepBuilderAPI_MakeFace(pln, -half, half, -half, half).Face()


def _boolean(op_name: str, a, b):
    o = _occ()
    cls = {"fuse": o["algo"].BRepAlgoAPI_Fuse,
           "cut": o["algo"].BRepAlgoAPI_Cut,
           "common": o["algo"].BRepAlgoAPI_Common}[op_name]
    op = cls(a, b)
    op.Build()
    if not op.IsDone():
        raise KernelError(f"布尔 {op_name} 失败")
    return op.Shape()


def fuse(a, b):
    return _boolean("fuse", a, b)


def cut(a, b):
    return _boolean("cut", a, b)


def common(a, b):
    return _boolean("common", a, b)


def translate(shape, vec: Vec3):
    o = _occ()
    tr = o["gp"].gp_Trsf()
    tr.SetTranslation(o["gp"].gp_Vec(*vec))
    return o["bapi"].BRepBuilderAPI_Transform(shape, tr, True).Shape()


def rotate(shape, origin: Vec3, axis: Vec3, angle_rad: float):
    o = _occ()
    tr = o["gp"].gp_Trsf()
    ax = o["gp"].gp_Ax1(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*axis))
    tr.SetRotation(ax, angle_rad)
    return o["bapi"].BRepBuilderAPI_Transform(shape, tr, True).Shape()


def copy_shape(shape):
    o = _occ()
    return o["bapi"].BRepBuilderAPI_Copy(shape).Shape()


def mirror(shape, origin: Vec3, normal: Vec3):
    o = _occ()
    tr = o["gp"].gp_Trsf()
    ax = o["gp"].gp_Ax2(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*normal))
    tr.SetMirror(ax)
    return o["bapi"].BRepBuilderAPI_Transform(shape, tr, True).Shape()


def pattern_linear(shape, vec: Vec3, count: int, fuse_together: bool = False) -> List[Any]:
    if count < 1:
        return []
    out = [copy_shape(shape)]
    for i in range(1, count):
        out.append(translate(shape, (vec[0] * i, vec[1] * i, vec[2] * i)))
    if fuse_together and len(out) > 1:
        acc = out[0]
        for s in out[1:]:
            acc = fuse(acc, s)
        return [acc]
    return out


def split_by_plane(shape, origin: Vec3, normal: Vec3) -> List[Any]:
    o = _occ()
    tool = make_plane_face(origin, normal, half=1.0e3)
    splitter = o["algo"].BRepAlgoAPI_Splitter()
    from OCC.Core.TopTools import TopTools_ListOfShape
    args = TopTools_ListOfShape()
    args.Append(shape)
    tools = TopTools_ListOfShape()
    tools.Append(tool)
    splitter.SetArguments(args)
    splitter.SetTools(tools)
    splitter.Build()
    if not splitter.IsDone():
        raise KernelError("分割失败")
    solids = explore(splitter.Shape(), "solid")
    return solids or [splitter.Shape()]


def edge_polyline(edge, deflection: float = 1e-3) -> List[Vec3]:
    """Discretize an edge into a polyline of 3D points (projection source)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection
    from OCC.Core.TopoDS import topods
    try:
        crv = BRepAdaptor_Curve(topods.Edge(edge))
        disc = GCPnts_QuasiUniformDeflection(crv, deflection)
        if not disc.IsDone():
            return []
        return [(crv.Value(disc.Parameter(i)).X(),
                 crv.Value(disc.Parameter(i)).Y(),
                 crv.Value(disc.Parameter(i)).Z())
                for i in range(1, disc.NbPoints() + 1)]
    except Exception:
        return []


def vertex_point(vertex) -> Vec3:
    """3D position of a vertex."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopoDS import topods
    p = BRep_Tool().Pnt(topods.Vertex(vertex))
    return (p.X(), p.Y(), p.Z())


def pattern_circular(shape, axis: Vec3, angle_deg: float, count: int) -> List[Any]:
    """`count` copies rotated about axis through the origin (original included)."""
    out = [shape]
    for i in range(1, max(count, 1)):
        out.append(rotate(shape, (0.0, 0.0, 0.0), axis, math.radians(angle_deg * i)))
    return out


def _cyl_axis(face) -> Optional[Tuple[Vec3, Vec3]]:
    """(direction, location) of a cylindrical face's axis, else None."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    from OCC.Core.TopoDS import topods
    try:
        s = BRepAdaptor_Surface(topods.Face(face))
        if s.GetType() != GeomAbs_Cylinder:
            return None
        ax = s.Cylinder().Axis()
        d = ax.Direction()
        loc = ax.Location()
        return ((d.X(), d.Y(), d.Z()), (loc.X(), loc.Y(), loc.Z()))
    except Exception:
        return None


# ----------------------------------------------------------------------
# R104/A-1: rigid transforms as explicit 4x4 matrices
#
# A mate or an alignment is a rigid transform that has to be *replayable*: the
# shape changes, so `KBody.base_pose` must carry the same transform or the
# feature history stops reproducing the body (see scdm.features.apply_pose).
# Row-major, translation in column 3 - the same layout as scdm.mates.Mat4.
# ----------------------------------------------------------------------
Mat4 = Tuple[Tuple[float, float, float, float], ...]


def _m4_identity() -> Mat4:
    return ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def _m4_mul(a: Mat4, b: Mat4) -> Mat4:
    """a ∘ b - b is applied first."""
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4))
                       for j in range(4)) for i in range(4))


def _m4_translate(vec) -> Mat4:
    v = tuple(float(c) for c in vec)
    return ((1.0, 0.0, 0.0, v[0]), (0.0, 1.0, 0.0, v[1]),
            (0.0, 0.0, 1.0, v[2]), (0.0, 0.0, 0.0, 1.0))


def _m4_rot(origin, axis, angle_rad: float) -> Mat4:
    """Rotation about `axis` through `origin` (Rodrigues, no OCCT needed)."""
    x, y, z = (float(c) for c in axis)
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-15:
        return _m4_identity()
    x, y, z = x / n, y / n, z / n
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    C = 1.0 - c
    r = ((c + x * x * C, x * y * C - z * s, x * z * C + y * s),
         (y * x * C + z * s, c + y * y * C, y * z * C - x * s),
         (z * x * C - y * s, z * y * C + x * s, c + z * z * C))
    o = tuple(float(v) for v in origin)
    t = tuple(o[i] - sum(r[i][j] * o[j] for j in range(3)) for i in range(3))
    return ((r[0][0], r[0][1], r[0][2], t[0]),
            (r[1][0], r[1][1], r[1][2], t[1]),
            (r[2][0], r[2][1], r[2][2], t[2]),
            (0.0, 0.0, 0.0, 1.0))


def align_axes_matrix(moving_face, target_face) -> Mat4:
    """The rigid transform `align_axes` applies (R104/A-1: replayable pose)."""
    a1 = _cyl_axis(moving_face)
    a2 = _cyl_axis(target_face)
    if a1 is None or a2 is None:
        raise KernelError("轴对齐需要两个圆柱面")
    d1, p1 = a1
    d2, p2 = a2
    dot = max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1] + d1[2] * d2[2]))
    cross = (d1[1] * d2[2] - d1[2] * d2[1],
             d1[2] * d2[0] - d1[0] * d2[2],
             d1[0] * d2[1] - d1[1] * d2[0])
    L = math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)
    if L < 1e-9:
        axis = (1.0, 0.0, 0.0) if abs(d1[0]) < 0.9 else (0.0, 1.0, 0.0)
        angle = math.pi if dot < 0 else 0.0
    else:
        axis = (cross[0] / L, cross[1] / L, cross[2] / L)
        angle = math.acos(dot)
    m = _m4_rot(p1, axis, angle) if angle > 1e-12 else _m4_identity()
    # after the rotation the axis passes p1 with direction d2; shift the
    # perpendicular part of the p1->p2 offset
    off = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    along = off[0] * d2[0] + off[1] * d2[1] + off[2] * d2[2]
    off = (off[0] - along * d2[0], off[1] - along * d2[1], off[2] - along * d2[2])
    if off[0] * off[0] + off[1] * off[1] + off[2] * off[2] > 1e-24:
        m = _m4_mul(_m4_translate(off), m)
    return m


def align_axes(moving, moving_face, target_face):
    """Coaxial mate: rotate+translate `moving` so its cylinder axis matches the
    target cylinder axis (any point along the axis line is acceptable).

    R104/A-1: built from `align_axes_matrix` so the very same transform can be
    recorded as a replayable pose instead of being applied and forgotten.
    """
    return apply_mat4(moving, align_axes_matrix(moving_face, target_face))


def edge_face_counts(shape):
    """[(edge, how many faces use it, one owner face or None)] - one pass (R75).

    R75 lesson: `FindFromIndex` returns a VIEW into the C++ map, and the map
    is a local of this function - returning those lists gave dangling handles
    that read as size 0 in the caller (the seam classifier then said "no
    seams" everywhere).  Everything is therefore materialised HERE, while the
    map is still alive.
    """
    import OCC.Core.TopExp as _TE
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE

    m = TopTools_IndexedDataMapOfShapeListOfShape()
    _TE.topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Size() + 1):
        faces = m.FindFromIndex(i)
        n = faces.Size()
        out.append((m.FindKey(i), n, faces.First() if n else None))
    return out


def free_edges(shape) -> List[Any]:
    """Edges used by fewer than two faces (R75 acceptance metric).

    NOTE: this includes the SEAM edge of a periodic face (a cylinder patch
    stores its seam as one edge used twice by the SAME face, so the ancestor
    map reports a single face).  Use `open_edges()` when the question is
    "is this shell watertight"."""
    return [e for (e, n, _f) in edge_face_counts(shape) if n < 2]


def is_seam_edge(edge, face) -> bool:
    """Does this edge lie on the seam of a periodic face? (R75)

    Classified by projecting the edge's midpoint onto the face's surface and
    testing the periodic parameter - the same test the R75 report tool uses.
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCC.Core.TopoDS import topods
    try:
        surf = BRepAdaptor_Surface(face)
        if not (surf.IsUPeriodic() or surf.IsVPeriodic()):
            return False
        ad = BRepAdaptor_Curve(topods.Edge(edge))
        mid = ad.Value(0.5 * (ad.FirstParameter() + ad.LastParameter()))
        pr = GeomAPI_ProjectPointOnSurf(mid, surf.Surface().Surface())
        if not pr.NbPoints():
            return False
        u, v = pr.LowerDistanceParameters()
        if surf.IsUPeriodic():
            per = surf.UPeriod()
            if min(abs(u), abs(abs(u) - per)) < 1e-6:
                return True
        if surf.IsVPeriodic():
            per = surf.VPeriod()
            if min(abs(v), abs(abs(v) - per)) < 1e-6:
                return True
    except Exception:
        return False
    return False


def watertight_report(shape) -> dict:
    """Countable watertightness of ONE shape (R83/P402).

    The same four numbers the R75-R82 instruments report, so the check command,
    the GUI and `tools/free_edge_report.py` cannot drift (rule 84):
    `free_edges` (all single-face edges), `open_edges` (the real gaps),
    `seam_edges` (a periodic face's seam - not a gap) and `free_loops`.
    """
    free = free_edges(shape)
    opened = open_edges(shape)
    return {"free_edges": len(free), "open_edges": len(opened),
            "seam_edges": len(free) - len(opened),
            "free_loops": len(_free_boundary_wires(shape))}


def open_edge_points(shape, limit: int = 32) -> List[Any]:
    """Midpoints of up to `limit` open edges (for 3D markers, R83).

    Returns a list of (x, y, z) in model units - the same space the markup
    notes live in, so the caller can drop a marker straight onto the gap.
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.TopoDS import topods

    out = []
    for edge in open_edges(shape)[:max(0, int(limit))]:
        try:
            ad = BRepAdaptor_Curve(topods.Edge(edge))
            p = ad.Value(0.5 * (ad.FirstParameter() + ad.LastParameter()))
        except Exception:
            continue
        out.append((p.X(), p.Y(), p.Z()))
    return out


def watertight_text(rep) -> str:
    """Chinese one-liner for the check command / status bar (R83)."""
    rep = rep or {}
    gaps = int(rep.get("open_edges") or 0)
    if not gaps:
        return "封闭 ✓"
    text = "未封闭 %d 处" % gaps
    loops = int(rep.get("free_loops") or 0)
    seams = int(rep.get("seam_edges") or 0)
    if loops:
        text += "（自由环 %d" % loops
        if seams:
            text += "，缝边 %d" % seams
        text += "）"
    elif seams:
        text += "（缝边 %d）" % seams
    return text

def open_edges(shape) -> List[Any]:
    """The edges that really leave the shell open (free minus seams)."""
    out = []
    for (edge, n, face) in edge_face_counts(shape):
        if n >= 2 or face is None:
            continue
        if is_seam_edge(edge, face):
            continue
        out.append(edge)
    return out

def _free_boundary_wires(shell) -> List[Any]:
    """Closed boundary wires of a shell (holes / missing faces)."""
    from OCC.Core.ShapeAnalysis import ShapeAnalysis_FreeBounds
    try:
        fab = ShapeAnalysis_FreeBounds(shell, False, True, False)
        return explore(fab.GetClosedWires(), "wire")
    except Exception:
        return []


def _as_shell(shape):
    """Cast the first shell found in `shape` (TopoDS_Shell for ShapeFix APIs)."""
    from OCC.Core.TopoDS import topods
    shells = explore(shape, "shell")
    if shells:
        return topods.Shell(shells[0])
    return shape


def fill_missing_faces(shape) -> Tuple[Any, int]:
    """Sew faces, cap open boundary loops with planar faces, re-solidify.

    Returns (solid, faces_added).
    """
    o = _occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.ShapeFix import ShapeFix_Solid
    faces = explore(shape, "face")
    if not faces:
        raise KernelError("没有可修复的面")
    shell = _as_shell(sew_faces(faces))
    added = 0
    for w in _free_boundary_wires(shell):
        try:
            faces.append(BRepBuilderAPI_MakeFace(o["topods"].Wire(w)).Face())
            added += 1
        except Exception:
            continue
    if added:
        shell = _as_shell(sew_faces(faces))
    solid = ShapeFix_Solid().SolidFromShell(shell)
    return solid, added


def solidify_shell(shape):
    """Sew the shape's faces and build an oriented solid from the closed shell."""
    from OCC.Core.ShapeFix import ShapeFix_Solid
    faces = explore(shape, "face")
    if not faces:
        raise KernelError("没有可实体化的面")
    shell = _as_shell(sew_faces(faces))
    return ShapeFix_Solid().SolidFromShell(shell)


def share_topology(shapes: Sequence) -> List[List[Any]]:
    """Imprint bodies on each other (General Fuse) so interfaces are shared.

    Returns, for each input shape (same order), the list of imprinted pieces
    that replace it. Fails when shapes do not intersect/touch.
    """
    from OCC.Core.BOPAlgo import BOPAlgo_Builder
    from OCC.Core.TopTools import TopTools_ListOfShape
    if len(shapes) < 2:
        raise KernelError("共享拓扑需要至少两个实体")
    b = BOPAlgo_Builder()
    args = TopTools_ListOfShape()
    for s in shapes:
        args.Append(s)
    b.SetArguments(args)
    b.Perform()
    out = []
    images = b.Images()
    for s in shapes:
        try:
            out.append(list(images.Find(s)))
        except Exception:
            out.append([s])
    return out


def unify_same_domain(shape):
    """Merge coplanar faces / colinear edges (needed after boolean ops)."""
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, False)
    u.Build()
    return u.Shape()


def midsurface_plate(shape) -> Tuple[Any, float]:
    """Plate midsurface: the largest pair of parallel opposite planar faces,
    the larger face translated to the mid plane. Returns (face, thickness).

    Uses an exact face transform, so concave outlines and inner holes survive.
    Coplanar fragments are merged first (e.g. after boolean fuses).
    """
    shape = unify_same_domain(shape)
    faces = explore(shape, "face")
    planes = []
    for f in faces:
        try:
            n, c = face_normal_center(f)
            planes.append((n, c, f))
        except Exception:
            continue
    best = None
    for i in range(len(planes)):
        n1, c1, f1 = planes[i]
        for j in range(i + 1, len(planes)):
            n2, c2, f2 = planes[j]
            dot = n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]
            if dot < -0.999:
                a = min(area(f1), area(f2))
                if best is None or a > best[0]:
                    best = (a, c1, c2, f1)
    if best is None:
        raise KernelError("中面：未找到平行的对面（仅支持板类实体）")
    _a, c1, c2, f1 = best
    thickness = math.dist(c1, c2)
    shift = ((c2[0] - c1[0]) / 2.0, (c2[1] - c1[1]) / 2.0, (c2[2] - c1[2]) / 2.0)
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Trsf, gp_Vec
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(*shift))
    face = topods.Face(BRepBuilderAPI_Transform(f1, tr, True).Shape())
    return face, thickness


def section_outline(shape, origin: Vec3, normal: Vec3) -> List[List[Vec3]]:
    """Cross-section polylines of `shape` cut by the plane (BRepAlgoAPI_Section)."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    pln = gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))
    sec = BRepAlgoAPI_Section(shape, pln)
    sec.Build()
    out = []
    for e in explore(sec.Shape(), "edge"):
        p = edge_polyline(e, 1e-5)
        if len(p) >= 2:
            out.append(p)
    return out


def cyl_axis(face) -> Optional[Tuple[Vec3, Vec3]]:
    """Public alias of _cyl_axis: (direction, location) of a cylinder axis."""
    return _cyl_axis(face)


def face_cylinder_radius(face) -> Optional[float]:
    """Radius when the face is cylindrical, else None."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    from OCC.Core.TopoDS import topods
    try:
        s = BRepAdaptor_Surface(topods.Face(face))
        if s.GetType() == GeomAbs_Cylinder:
            return float(s.Cylinder().Radius())
    except Exception:
        return None
    return None


def edge_loop(shape, edge_i: int, max_edges: int = 256) -> List[int]:
    """Closed edge loop: boundary edges of the simplest face containing the edge.

    Double-click ring selection. Faces sharing the picked edge are ranked by edge
    count; the smallest face's boundary is the loop (a box edge yields the 4 edges
    of one of its faces).
    """
    edges = explore(shape, "edge")
    if not (0 <= edge_i < len(edges)):
        return []

    def ekey(p0, p1):
        return (round(p0[0] * 1e5), round(p0[1] * 1e5), round(p0[2] * 1e5),
                round(p1[0] * 1e5), round(p1[1] * 1e5), round(p1[2] * 1e5))

    edge_keys = {}
    canon = {}
    for i, e in enumerate(edges):
        p = edge_polyline(e, 1e-5)
        if len(p) >= 2:
            k = ekey(p[0], p[-1])
            canon.setdefault(k, i)
            edge_keys.setdefault(k, []).append(i)
    # map any (orientation-duplicated) edge index to its canonical first index
    dedup = {}
    for k, idxs in edge_keys.items():
        for i in idxs:
            dedup[i] = canon[k]
    target = dedup.get(edge_i, edge_i)
    best = None
    for f in explore(shape, "face"):
        idxs = set()
        for e in explore(f, "edge"):
            p = edge_polyline(e, 1e-5)
            if len(p) < 2:
                continue
            ci = dedup.get(edge_keys.get(ekey(p[0], p[-1]), [None])[0])
            if ci is not None:
                idxs.add(ci)
        if target in idxs and (best is None or len(idxs) < len(best)):
            best = idxs
            if len(idxs) <= 3:
                break
    return sorted(best) if best else [target]


def face_normal_center(face) -> Tuple[Vec3, Vec3]:
    o = _occ()
    adapt = o["BRepAdaptor_Surface"](face)
    um = 0.5 * (adapt.FirstUParameter() + adapt.LastUParameter())
    vm = 0.5 * (adapt.FirstVParameter() + adapt.LastVParameter())
    pnt = o["gp"].gp_Pnt()
    d1u = o["gp"].gp_Vec()
    d1v = o["gp"].gp_Vec()
    adapt.D1(um, vm, pnt, d1u, d1v)
    n = d1u.Crossed(d1v)
    if n.Magnitude() < 1e-18:
        n = o["gp"].gp_Vec(0, 0, 1)
    else:
        n.Normalize()
    try:
        orient = face.Orientation()
    except Exception:
        orient = o["topabs"].TopAbs_FORWARD
    if orient != o["topabs"].TopAbs_FORWARD:
        n.Reverse()
    return (n.X(), n.Y(), n.Z()), (pnt.X(), pnt.Y(), pnt.Z())


def pull_face(solid, face, distance: float):
    """SpaceClaim Pull on a planar face: extrude and fuse/cut into the solid."""
    o = _occ()
    n, _c = face_normal_center(face)
    vec = o["gp"].gp_Vec(n[0] * distance, n[1] * distance, n[2] * distance)
    prism = o["prim"].BRepPrimAPI_MakePrism(face, vec).Shape()
    if distance >= 0:
        return fuse(solid, prism)
    return cut(solid, prism)


def pull_face_symmetric(solid, face, distance: float):
    """SpaceClaim Pull > symmetric: extrude the face an equal amount both ways.

    Build a prism centred on the face plane (extends distance/2 on each side of the
    original face) and fuse it into the solid.
    """
    o = _occ()
    n, c = face_normal_center(face)
    half = distance / 2.0
    prism = o["prim"].BRepPrimAPI_MakePrism(
        face, o["gp"].gp_Vec(n[0] * distance, n[1] * distance, n[2] * distance)
    ).Shape()
    # Shift the prism back by half so it straddles the original face.
    prism = translate(prism, (-n[0] * half, -n[1] * half, -n[2] * half))
    if distance >= 0:
        return fuse(solid, prism)
    return cut(solid, prism)


def replace_face(solid, src_face, dst_face):
    """SpaceClaim Replace (limited, planar): move src_face material flush to dst_face.

    Both faces must be planar. The source face is extruded along the vector from its
    centre to the destination centre and then, if that overlaps the target plane, the
    resulting wedge is fused; the original source face is left in place. This gives the
    practical "make this face meet that face" effect for Box/prism-style geometry.
    """
    o = _occ()
    sn, sc = face_normal_center(src_face)
    dn, dc = face_normal_center(dst_face)
    vec = (dc[0] - sc[0], dc[1] - sc[1], dc[2] - sc[2])
    mag = math.sqrt(sum(v * v for v in vec))
    if mag < 1e-12:
        return solid
    direction = (vec[0] / mag, vec[1] / mag, vec[2] / mag)
    extrude = o["prim"].BRepPrimAPI_MakePrism(
        src_face, o["gp"].gp_Vec(direction[0] * mag, direction[1] * mag, direction[2] * mag)
    ).Shape()
    return fuse(solid, extrude)


def align_faces_matrix(moving_face, target_face) -> Mat4:
    """The rigid transform `align_faces` applies (R104/A-1: replayable pose)."""
    n1, c1 = face_normal_center(moving_face)
    n2, c2 = face_normal_center(target_face)
    desired = (-n2[0], -n2[1], -n2[2])
    dot = n1[0] * desired[0] + n1[1] * desired[1] + n1[2] * desired[2]
    m = _m4_identity()
    if dot < 1.0 - 1e-12:
        axis = (
            n1[1] * desired[2] - n1[2] * desired[1],
            n1[2] * desired[0] - n1[0] * desired[2],
            n1[0] * desired[1] - n1[1] * desired[0],
        )
        mag = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
        if mag > 1e-12:
            ang = math.acos(max(-1.0, min(1.0, dot)))
            m = _m4_rot(c1, (axis[0] / mag, axis[1] / mag, axis[2] / mag), ang)
    # NOTE: the rotation is about c1, so the moving face centre stays at c1;
    # translate by the centre delta to land on the target centre.
    vec = (c2[0] - c1[0], c2[1] - c1[1], c2[2] - c1[2])
    return _m4_mul(_m4_translate(vec), m)


def align_faces(moving, moving_face, target_face):
    """Assembly Mate: transform the moving shape so its face coincides with the
    target.

    Rotates the moving shape so its face normal opposes the target normal, then
    translates so the face centres coincide.  R104/A-1: the transform comes from
    `align_faces_matrix`, so a caller can record it as a replayable pose.
    """
    return apply_mat4(moving, align_faces_matrix(moving_face, target_face))


def fill_faces(solid, faces: Sequence):
    """SpaceClaim Fill: remove faces and heal (OCCT Defeaturing)."""
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Defeaturing
    except Exception as exc:
        raise KernelError("当前 OCCT 无 Defeaturing") from exc
    d = BRepAlgoAPI_Defeaturing()
    d.SetShape(solid)
    for f in faces:
        d.AddFaceToRemove(f)
    d.Build()
    if not d.IsDone():
        raise KernelError("填充失败")
    return d.Shape()


def offset_faces(solid, face, distance: float):
    return pull_face(solid, face, distance)


def _edge_length(edge, deflection: float = 2e-3) -> float:
    """Polyline length of an edge (cheap, coarse - only used for guarding)."""
    pts = edge_polyline(edge, deflection)
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def edge_treatment_violation(shape, radius: float, edges=None):
    """P14: the first edge shorter than 2*radius, else None.

    Heuristic pre-flight: OCCT's fillet/chamfer can hit a native access
    violation (uncatchable from Python) when the radius approaches the local
    material width - e.g. 1mm radius on a 1mm-thick shelled wall. Refusing the
    operation with a KernelError keeps the process alive.
    """
    src = list(edges) if edges is not None else explore(shape, "edge")
    for e in src:
        L = _edge_length(e)
        if L < 2.0 * float(radius):
            return L
    return None


def min_wall_gap(shape, max_faces: int = 400):
    """Minimum distance between parallel opposite PLANAR faces (~wall thickness).

    P14: this is the proxy that catches thin-walled solids - a 1mm shell has
    no 1mm-long edges, but its inner and outer faces are 1mm apart.
    Returns None when the shape has too many faces for the O(n^2) scan.
    """
    planar = []
    for f in explore(shape, "face"):
        n, c = face_normal_center(f)
        planar.append((tuple(float(v) for v in n),
                       tuple(float(v) for v in c)))
        if len(planar) > max_faces:
            return None
    best = None
    for i in range(len(planar)):
        n1, c1 = planar[i]
        for j in range(i + 1, len(planar)):
            n2, c2 = planar[j]
            if sum(n1[k] * n2[k] for k in range(3)) > -0.999:
                continue
            d = abs(sum((c2[k] - c1[k]) * n1[k] for k in range(3)))
            if d > 1e-9 and (best is None or d < best):
                best = d
    return best


def _guard_edge_treatment(shape, radius: float, edges, kind: str,
                          mm: float = 1000.0) -> None:
    if radius <= 0:
        raise KernelError("%s：半径/距离必须为正" % kind)
    short = edge_treatment_violation(shape, radius, edges)
    if short is not None:
        raise KernelError(
            "%s %.3fmm 被拒绝：存在长度仅 %.3fmm 的边（需小于边长的一半）。"
            "该几何会触发 OCCT 原生崩溃，请减小半径或先加厚材料。"
            % (kind, radius * mm, short * mm))
    gap = min_wall_gap(shape)
    if gap is not None and radius >= gap * 0.5:
        raise KernelError(
            "%s %.3fmm 被拒绝：检测到最小壁厚 %.3fmm（须小于壁厚的一半）。"
            "该几何会触发 OCCT 原生崩溃，请减小半径或先加厚材料。"
            % (kind, radius * mm, gap * mm))


def fillet_edges(shape, radius: float, edges: Optional[Sequence] = None):
    _guard_edge_treatment(shape, radius, edges, "倒圆半径")   # P14
    o = _occ()
    mk = o["fillet"].BRepFilletAPI_MakeFillet(shape)
    use = list(edges) if edges is not None else explore(shape, "edge")
    for e in use:
        mk.Add(radius, e)
    mk.Build()
    if not mk.IsDone():
        raise KernelError("倒圆失败")
    return mk.Shape()


def chamfer_edges(shape, dist: float, edges: Optional[Sequence] = None):
    _guard_edge_treatment(shape, dist, edges, "倒角距离")   # P14
    o = _occ()
    mk = o["fillet"].BRepFilletAPI_MakeChamfer(shape)
    use = list(edges) if edges is not None else explore(shape, "edge")
    for e in use:
        mk.Add(dist, e)
    mk.Build()
    if not mk.IsDone():
        raise KernelError("倒角失败")
    return mk.Shape()


def shell_solid(shape, thickness: float, opening_faces: Sequence):
    o = _occ()
    from OCC.Core.TopTools import TopTools_ListOfShape
    faces = TopTools_ListOfShape()
    for f in opening_faces:
        faces.Append(f)
    mk = o["offset"].BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(shape, faces, -abs(thickness), 1e-4)
    mk.Build()
    if not mk.IsDone():
        raise KernelError("抽壳失败")
    return mk.Shape()


def sew_bodies(faces: Iterable, tol: float = 1e-6):
    """Sew faces and keep EVERY lobe (P29 import fidelity).

    sew_faces collapses the result to the first solid/shell, which silently
    discards the other lobes - official bodies routinely sew into several
    shells (SampleModel1: 8 shells / 103 faces -> 4 faces after collapsing).
    A single closed shell still becomes a solid, so callers that need a solid
    keep working; multi-lobe results come back as the sewn compound.
    """
    o = _occ()
    sew = o["bapi"].BRepBuilderAPI_Sewing(tol)
    n = 0
    for f in faces:
        sew.Add(f)
        n += 1
    if n == 0:
        raise KernelError("没有可缝合的面")
    sew.Perform()
    sewn = sew.SewedShape()
    n_sewn = len(explore(sewn, "face"))

    def _keeps_all(candidate):
        """Only accept a conversion that does not drop faces (P29)."""
        try:
            return len(explore(candidate, "face")) >= n_sewn
        except Exception:
            return False

    solids = explore(sewn, "solid")
    shells = explore(sewn, "shell")
    if len(solids) == 1 and len(shells) <= 1 and _keeps_all(solids[0]):
        return solids[0]
    if not solids and len(shells) == 1:
        try:
            solid = o["bapi"].BRepBuilderAPI_MakeSolid(shells[0]).Solid()
            if _keeps_all(solid):
                return solid
        except Exception:
            pass
        return sewn
    if len(solids) > 1 and not shells:
        out = solids[0]
        for s in solids[1:]:
            try:
                out = fuse(out, s)
            except Exception:
                return sewn
        if _keeps_all(out):
            return out
        return sewn
    return sewn


def sew_faces(faces: Iterable, tol: float = 1e-6):
    o = _occ()
    sew = o["bapi"].BRepBuilderAPI_Sewing(tol)
    n = 0
    for f in faces:
        sew.Add(f)
        n += 1
    if n == 0:
        raise KernelError("没有可缝合的面")
    sew.Perform()
    sewn = sew.SewedShape()
    solids = explore(sewn, "solid")
    if solids:
        return solids[0]
    shells = explore(sewn, "shell")
    if shells:
        try:
            return o["bapi"].BRepBuilderAPI_MakeSolid(shells[0]).Solid()
        except Exception:
            return sewn
    return sewn


def helix_solid(radius: float, pitch: float, height: float, tube_radius: float,
                origin: Vec3 = (0.0, 0.0, 0.0)):
    """SpaceClaim Insert Helix: sweep a circular profile along a helical spine.

    Returns a solid (a spring-like tube). Falls back to a plain cylinder if the
    sweep fails, so the command always produces a usable body.
    """
    o = _occ()
    try:
        spine = helix_edge(radius, pitch, height, origin)
        circ = o["prim"].BRepPrimAPI_MakeCircle(
            o["gp"].gp_Pnt(origin[0] + radius, origin[1], origin[2]),
            o["gp"].gp_Dir(0, 0, 1), tube_radius).Edge()
        wire = o["bapi"].BRepBuilderAPI_MakeWire(circ).Wire()
        pipe = o["offset"].BRepOffsetAPI_MakePipe(spine, wire)
        pipe.Build()
        if pipe.IsDone():
            sh = pipe.Shape()
            if volume(sh) > 1e-15:
                return sh
    except Exception:
        pass
    return make_cylinder(tube_radius * 2.0, height, origin)


def draft_face(solid, face, angle_rad: float, neutral_dir: Vec3 = (0.0, 0.0, 1.0)):
    """SpaceClaim Draft: taper the solid about a neutral direction by angle_rad."""
    o = _occ()
    # this binding exposes the 3-arg ctor: (shape, neutral direction, angle in radians)
    mk = o["offset"].BRepOffsetAPI_MakeDraft(solid, o["gp"].gp_Dir(*neutral_dir), angle_rad)
    if not mk.IsDone() or mk.Shape().IsNull():
        raise KernelError("拔模失败")
    return mk.Shape()


def fillet_variable(shape, spec):
    """Variable-radius fillet.

    spec: list of entries, either
      (edge, radius)                 -- constant radius on that edge
      (edge, [(u, r), ...])          -- radius evolving along the edge
        u in [0, 1] relative parameter, r the local radius.
    Tangent-continuous edges of each entry are absorbed into the contour.
    """
    o = _occ()
    mk = o["fillet"].BRepFilletAPI_MakeFillet(shape)
    from OCC.Core.TColgp import TColgp_Array1OfPnt2d
    from OCC.Core.gp import gp_Pnt2d
    from OCC.Core.TopoDS import topods
    for item in spec:
        edge, rad = item
        rmax = (float(rad) if isinstance(rad, (int, float))
                else max(float(r) for _u, r in rad))
        _guard_edge_treatment(shape, rmax, [edge], "变半径倒圆")   # P14
        mk.Add(topods.Edge(edge))
        idx = mk.NbContours()
        if isinstance(rad, (int, float)):
            mk.SetRadius(float(rad), idx, 1)
        else:
            pairs = sorted(rad)
            arr = TColgp_Array1OfPnt2d(1, len(pairs))
            for k, (u, r) in enumerate(pairs, start=1):
                arr.SetValue(k, gp_Pnt2d(float(u), float(r)))
            mk.SetRadius(arr, idx, 1)
    mk.Build()
    if not mk.IsDone():
        raise KernelError("变半径圆角失败")
    return mk.Shape()


def _face_prism(face, thickness: float):
    """Slab of material between a planar face and its inward offset."""
    o = _occ()
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.TopoDS import topods
    nrm, _ctr = face_normal_center(topods.Face(face))
    v = o["gp"].gp_Vec(-nrm[0] * thickness, -nrm[1] * thickness,
                       -nrm[2] * thickness)
    return BRepPrimAPI_MakePrism(face, v).Shape()


def shell_multi(shape, groups, default_thickness=None):
    """Shell with per-group thickness (SpaceClaim 多厚度抽壳).

    groups: [(faces_to_remove, thickness), ...].  The wall layer is built
    as the union of per-face inward prisms (each face offset by its own
    thickness); the cavity = shape - wall_layer.  Single-thickness input
    reduces exactly to a uniform shell.
    """
    o = _occ()
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    all_faces = explore(shape, "face")
    if default_thickness is None:
        default_thickness = groups[0][1]
    grouped = set()
    wall = None
    for f in all_faces:
        t = default_thickness
        hit = None
        for faces, tg in groups:
            if any(f.IsSame(gf) for gf in faces):
                t = tg
                break
        try:
            pr = _face_prism(f, t)
        except Exception:
            continue
        if pr is None or pr.IsNull():
            continue
        wall = pr if wall is None else BRepAlgoAPI_Fuse(wall, pr).Shape()
    if wall is None:
        raise KernelError("多厚度抽壳失败（无法构建壁层）")
    cavity = BRepAlgoAPI_Cut(shape, wall).Shape()
    return BRepAlgoAPI_Cut(shape, cavity).Shape()


def draft_neutral(solid, draft_faces, angle_rad: float, neutral_face):
    """SpaceClaim 中性面拔模: draft_faces taper about the neutral FACE's
    plane (the plane the pull direction is measured against)."""
    o = _occ()
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.TopoDS import topods
    nf = topods.Face(neutral_face)
    ad = BRepAdaptor_Surface(nf)
    if ad.GetType() != GeomAbs_Plane:
        raise KernelError("中性面必须是平面")
    pln = ad.Plane()
    mk = o["offset"].BRepOffsetAPI_DraftAngle(solid)
    drf = topods.Face(draft_faces) if not isinstance(
        draft_faces, (list, tuple)) else None
    faces = ([topods.Face(f) for f in draft_faces]
             if isinstance(draft_faces, (list, tuple)) else [drf])
    for f in faces:
        mk.Add(f, pln.Axis().Direction(), angle_rad, pln)
    if not mk.AddDone():
        raise KernelError("拔模失败（面不可拔模）")
    mk.Build()
    if not mk.IsDone():
        raise KernelError("拔模失败")
    return mk.Shape()


def _vertex_bbox(shape):
    """(lo, hi) bounding box from the shape's own vertices (no Bnd_Box dep)."""
    pts = [vertex_point(v) for v in explore(shape, "vertex")]
    if not pts:
        raise KernelError("无法计算包围盒：实体没有顶点")
    lo = tuple(min(p[i] for p in pts) for i in range(3))
    hi = tuple(max(p[i] for p in pts) for i in range(3))
    return lo, hi


def bounding_box(shape):
    """True axis-aligned bbox (BRepBndLib), degrading to the vertex box.

    A full sphere has only its two pole vertices, so a vertex-based box collapses
    to a line - anything that grids or encloses a curved body needs the real box.
    """
    o = _occ()
    try:
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.Bnd import Bnd_Box
        box = Bnd_Box()
        try:
            box.SetGap(0.0)          # Bnd_Box pads by default; keep it tight
        except Exception:
            pass
        brepbndlib.Add(shape, box)
        xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
        return (float(xmin), float(ymin), float(zmin)), (float(xmax), float(ymax), float(zmax))
    except Exception:
        return _vertex_bbox(shape)


def _face_frame(face, origin=None):
    n, c = face_normal_center(face)
    n = tuple(float(v) for v in n)
    base = tuple(float(v) for v in (origin if origin is not None else c))
    return n, base


def hole_simple(solid, face, diameter: float, depth: Optional[float] = None,
                origin: Optional[Vec3] = None):
    """SpaceClaim 简单孔: cut a cylindrical hole normal to a planar face.

    `depth=None` cuts through the whole body. The removed volume is exactly
    pi*r^2*depth (or pi*r^2*thickness for a through hole) - P4 feature family.
    """
    n, base = _face_frame(face, origin)
    r = float(diameter) / 2.0
    if depth is None:
        # P5 fix: a through cutter must span the body on BOTH sides of the
        # face - centring it on the face can miss the far side on bodies that
        # are not symmetric about that face (e.g. a 20x20x40 box).
        lo, hi = _vertex_bbox(solid)
        corners = [(x, y, z) for x in (lo[0], hi[0])
                   for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        d_pos = max(sum((c[i] - base[i]) * n[i] for i in range(3))
                    for c in corners)
        d_neg = max(sum((base[i] - c[i]) * n[i] for i in range(3))
                    for c in corners)
        margin = 1e-6
        start = tuple(base[i] - n[i] * (d_neg + margin) for i in range(3))
        h = d_neg + d_pos + 2.0 * margin
    else:
        d = float(depth)
        start = tuple(base[i] - n[i] * d for i in range(3))
        h = d + 1e-6
    return cut(solid, make_cylinder(r, h, origin=start, axis=n))


def hole_tapped(solid, face, nominal: float, pitch: float,
                depth: Optional[float] = None, origin: Optional[Vec3] = None):
    """P175: 攻丝孔 - cut at the TAP-DRILL diameter, not the nominal one.

    Metric rule: d_tap = nominal - pitch.  The thread is symbolic (a rendering
    and metadata concern), so the removed volume is exactly
    pi*(d_tap/2)^2*depth - using the nominal diameter here would silently make
    every tapped hole oversized.
    """
    if pitch <= 0 or nominal <= pitch:
        raise KernelError("螺纹参数非法：螺距必须为正且小于公称直径")
    d_tap = float(nominal) - float(pitch)
    return hole_simple(solid, face, d_tap, depth=depth, origin=origin)


def louver(solid, face, length: float, width: float, height: float = 0.0,
           origin: Optional[Vec3] = None):
    """P247: 百叶开口（钣金成形）——矩形通切。

    Signature mirrors the face-level forming pattern of sheetmetal.bead_groove
    (face + dimensions + optional origin).  Closed form: the SLOT removes
    length x width x thickness; ``height`` is the raised lip, which is
    annotation/metadata here (it is not modelled as added material yet).

    Current limitation, stated on purpose: the cutter is axis aligned, so the
    face normal must be one of the six axis directions (the face frame is used
    for the centre and the span).
    """
    if length <= 0 or width <= 0:
        raise KernelError("百叶长宽必须为正")
    if height < 0:
        raise KernelError("百叶唇高不能为负")
    n, base = _face_frame(face, origin)
    lo, hi = _vertex_bbox(solid)
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    d_pos = max(sum((c[i] - base[i]) * n[i] for i in range(3)) for c in corners)
    d_neg = max(sum((base[i] - c[i]) * n[i] for i in range(3)) for c in corners)
    margin = 1e-6
    # P253/R45: an ORIENTED prism cutter built in the face frame - this lifts
    # the old axis-aligned limitation (the rectangle lives on the face plane
    # and is pushed along the normal through the sheet)
    ref = [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0]
    u = [ref[i] - sum(ref[j] * n[j] for j in range(3)) * n[i] for i in range(3)]
    ul = sum(v * v for v in u) ** 0.5 or 1.0
    u = [v / ul for v in u]
    v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0]]
    hl, hw = length / 2.0, width / 2.0
    start = tuple(base[i] - n[i] * (d_neg + margin) for i in range(3))
    pts = [tuple(start[i] + u[i] * su * hl + v[i] * sv * hw for i in range(3))
           for (su, sv) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    profile = face_from_polygon(pts)
    thick = d_neg + d_pos
    if height > thick + 1e-12:
        raise KernelError("百叶唇高不能超过板厚")
    span = thick + 2.0 * margin
    out = cut(solid, prism(profile, tuple(n[i] * span for i in range(3))))
    if height > 0:
        # P265/R48: the lip is the material pushed up along one side of the
        # opening - a plate of the same footprint sitting ON the face, so it
        # never overlaps the slot and the closed form simply adds it back.
        lip_pts = [tuple(base[i] + u[i] * su * hl + v[i] * sv * hw
                         for i in range(3))
                   for (su, sv) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        lip = prism(face_from_polygon(lip_pts),
                    tuple(n[i] * float(height) for i in range(3)))
        try:
            out = fuse(out, lip)
        except KernelError:
            pass
    return out


def knockout(solid, face, diameter: float, web: float, web_count: int = 4,
             origin: Optional[Vec3] = None):
    """P277: 敲落（钣金成形）——带筋环切：敲落片靠 web_count 条筋挂在板料上。

    Parameters (kernel units; the GUI/op layer divides mm by 1000):
      diameter   outer diameter of the knockout (the circle you would punch)
      web        one feature size drives both the annular gap and the radial
                 webs: the gap is web wide, so the retained slug measures
                 diameter - 2*web across, and every web is a radial sector
                 whose area is exactly web**2
      web_count  number of webs keeping the slug attached (>= 1)

    Geometry: cut the ring-shaped cutter (outer cylinder D minus inner cylinder
    D-2*web - exact circular booleans, so the closed form is exact) out of the
    sheet, then fuse the web_count sectors back into the gap.  Without a web
    the slug is loose and the body splits in two, which is exactly what rule 66
    counts: shells/solids are asserted, not eyeballed.

    Closed form (thickness measured along the face normal, as in louver):
        ring area    = pi*(R**2 - r**2),  R = diameter/2,  r = R - web
        removed area = ring area - web_count*web**2
        removed vol  = removed area * thickness
    The sector angle is dtheta = 2*pi*web**2 / ring_area (area-exact sector, so
    there is no rectangle-vs-circle corner correction to hand-wave).

    Like louver the cutter is built in the face frame, so the normal may be any
    direction (the same prism/frame path as the louver cutter).
    """
    d = float(diameter)
    w = float(web)
    n_web = int(web_count)
    if d <= 0:
        raise KernelError("敲落直径必须为正")
    if w <= 0:
        raise KernelError("敲落筋宽必须为正")
    if w >= d:
        raise KernelError("敲落筋宽不能大于等于直径")
    if w >= d / 2.0:
        raise KernelError("敲落筋宽必须小于半径：环缝会吃掉整个敲落片")
    if n_web < 1:
        raise KernelError("敲落筋数必须 ≥ 1：没有筋的敲落会掉片")
    R = d / 2.0
    r = R - w
    ring_area = math.pi * (R * R - r * r)
    if n_web * w * w >= ring_area:
        # the webs would overlap and fill the gap: nothing is removed and the
        # closed form would go negative, so refuse instead of returning it
        raise KernelError("敲落：筋数×筋宽² 已覆盖整个环缝（没有材料被切除）")

    n, base = _face_frame(face, origin)
    lo, hi = _vertex_bbox(solid)
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    d_pos = max(sum((c[i] - base[i]) * n[i] for i in range(3)) for c in corners)
    d_neg = max(sum((base[i] - c[i]) * n[i] for i in range(3)) for c in corners)
    margin = 1e-6
    thick = d_neg + d_pos
    # face frame (u, v) in the plane of the face - same recipe as louver
    ref = [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0]
    u = [ref[i] - sum(ref[j] * n[j] for j in range(3)) * n[i] for i in range(3)]
    ul = sum(x * x for x in u) ** 0.5 or 1.0
    u = [x / ul for x in u]
    v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0]]
    # 1) ring cutter with margins (a through cut must clear both sheet faces)
    ring_start = tuple(base[i] - n[i] * (d_neg + margin) for i in range(3))
    ring_span = thick + 2.0 * margin
    ring = cut(make_cylinder(R, ring_span, origin=ring_start, axis=n),
               make_cylinder(r, ring_span, origin=ring_start, axis=n))
    out = cut(solid, ring)
    # 2) fuse the webs back: each is the ring sector (pie prism x ring, exact
    #    area web**2) intersected with the original material
    dtheta = 2.0 * math.pi * w * w / ring_area
    p0 = tuple(base[i] - n[i] * d_neg for i in range(3))
    arc_r = R + w                      # pie arc sits outside the ring: clipped
    steps = 8
    for k in range(n_web):
        ang = 2.0 * math.pi * k / n_web
        pts = [p0]
        for s in range(steps + 1):
            t = ang - dtheta / 2.0 + dtheta * s / steps
            pts.append(tuple(p0[i] + u[i] * arc_r * math.cos(t)
                             + v[i] * arc_r * math.sin(t) for i in range(3)))
        pie = prism(face_from_polygon(pts),
                    tuple(n[i] * thick for i in range(3)))
        # the web is the piece of ORIGINAL material inside the ring sector, so
        # it can only ever fill the local wall - using the ring sector alone
        # would grow a fin wherever the body extends further along the normal
        out = fuse(out, common(common(pie, ring), solid))
    return out


def _face_uv(face, origin=None):
    """(n, base, u, v): the face frame - the recipe louver/knockout inline."""
    n, base = _face_frame(face, origin)
    ref = [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0]
    u = [ref[i] - sum(ref[j] * n[j] for j in range(3)) * n[i] for i in range(3)]
    ul = sum(x * x for x in u) ** 0.5 or 1.0
    u = tuple(x / ul for x in u)
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0])
    return n, base, u, v


def _face_span(face, u, v):
    """(min_u, max_u, min_v, max_v) of a planar face in its own (u, v) frame."""
    pts = [vertex_point(w) for w in explore(face, "vertex")]
    if not pts:
        return (0.0, 0.0, 0.0, 0.0)
    us = [sum(p[i] * u[i] for i in range(3)) for p in pts]
    vs = [sum(p[i] * v[i] for i in range(3)) for p in pts]
    return (min(us), max(us), min(vs), max(vs))


def gusset(solid, face, length: float, height: float, thickness: float,
           origin: Optional[Vec3] = None):
    """P295: 角撑（钣金成形）——立在面上的直角三角形板（加料）。

    The triangle lives in the (u, n) plane with legs ``length`` along the face
    and ``height`` normal to it, extruded ``thickness`` along v.  Its base edge
    lies IN the face plane, so the fuse has a real face contact - no
    point-joint like the knockout webs.

    Closed form: volume = length * height / 2 * thickness (exact prism).
    """
    if length <= 0 or height <= 0 or thickness <= 0:
        raise KernelError("角撑尺寸必须为正")
    n, base, u, v = _face_uv(face, origin)
    lo_u, hi_u, lo_v, hi_v = _face_span(face, u, v)
    if length > (hi_u - lo_u) + 1e-12:
        raise KernelError("角撑长度超出所选面")
    if thickness > (hi_v - lo_v) + 1e-12:
        raise KernelError("角撑厚度超出所选面")
    hl, ht = length / 2.0, thickness / 2.0
    tri = []
    for (du, dn) in ((-hl, 0.0), (hl, 0.0), (-hl, height)):
        tri.append(tuple(base[i] + u[i] * du + n[i] * dn - v[i] * ht
                         for i in range(3)))
    plate = prism(face_from_polygon(tri),
                  tuple(v[i] * thickness for i in range(3)))
    return fuse(solid, plate)


def tab(solid, face, length: float, width: float, height: float,
        origin: Optional[Vec3] = None):
    """P295: 舌片（钣金成形）——面上的矩形局部凸出（加料）。

    A box of footprint ``length`` x ``width`` standing ``height`` proud of the
    face, centred on the face centre.  Closed form: volume = length * width *
    height; the footprint must fit the face (otherwise it is not a tab on this
    face but a modelling error).
    """
    if length <= 0 or width <= 0 or height <= 0:
        raise KernelError("舌片尺寸必须为正")
    n, base, u, v = _face_uv(face, origin)
    lo_u, hi_u, lo_v, hi_v = _face_span(face, u, v)
    if length > (hi_u - lo_u) + 1e-12:
        raise KernelError("舌片长度超出所选面")
    if width > (hi_v - lo_v) + 1e-12:
        raise KernelError("舌片宽度超出所选面")
    hl, hw = length / 2.0, width / 2.0
    pts = [tuple(base[i] + u[i] * su * hl + v[i] * sv * hw for i in range(3))
           for (su, sv) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return fuse(solid, prism(face_from_polygon(pts),
                             tuple(n[i] * height for i in range(3))))


def junction(solid, face, size: float, mode: str = "release",
             width: Optional[float] = None, origin: Optional[Vec3] = None):
    """P303: 钣金接缝——两折弯相交处的释放（三角）/ 接缝（矩形）/ 连接（搭接加料）。

    Geometry lives in the face plane (the (u, v) frame) at the face corner
    (u_min, v_min) and acts through the sheet thickness t measured along the
    face normal (as in louver/knockout):

        release  cut a right triangle (legs size)      -> removed = size**2/2 * t
        seam     cut a rectangle (size x width)       -> removed = size*width * t
        connect  fuse a rectangle patch (size x width)-> added   = size*width * t

    The face-frame route is used instead of the bbox-clamped rip heuristic
    because it is what makes the removed/added volume exactly decidable.
    """
    key = str(mode).lower()
    if key not in ("release", "seam", "connect"):
        raise KernelError("接缝模式未知：%s（可选 release/seam/connect）" % mode)
    size = float(size)
    if size <= 0:
        raise KernelError("接缝尺寸必须为正")
    if key in ("seam", "connect"):
        if width is None or float(width) <= 0:
            raise KernelError("接缝宽度必须为正")
        width = float(width)
    n, base, u, v = _face_uv(face, origin)
    lo_u, hi_u, lo_v, hi_v = _face_span(face, u, v)
    # the junction sits at the face corner (u_min, v_min) - the spot where two
    # bends meet.  It must stop short of the opposite edges: a tool face exactly
    # on the far boundary makes the boolean degenerate (measured: half the
    # triangle disappeared), so the bound is strict.
    if size >= (hi_u - lo_u) - 1e-9:
        raise KernelError("接缝尺寸必须小于面跨度（贴到对边会退化）")
    need_v = size if key == "release" else width
    if need_v >= (hi_v - lo_v) - 1e-9:
        raise KernelError("接缝尺寸必须小于面跨度（贴到对边会退化）")
    bu = sum(base[i] * u[i] for i in range(3))
    bv = sum(base[i] * v[i] for i in range(3))
    du0, dv0 = lo_u - bu, lo_v - bv          # base is the face centre: move to
                                             # the corner before placing
    def at(du, dv):
        return tuple(base[i] + u[i] * (du0 + du) + v[i] * (dv0 + dv)
                     for i in range(3))

    if key == "release":
        poly = [at(0.0, 0.0), at(size, 0.0), at(0.0, size)]
    else:
        poly = [at(0.0, 0.0), at(size, 0.0), at(size, width), at(0.0, width)]
    lo, hi = _vertex_bbox(solid)
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    d_pos = max(sum((c[i] - base[i]) * n[i] for i in range(3)) for c in corners)
    d_neg = max(sum((base[i] - c[i]) * n[i] for i in range(3)) for c in corners)
    if key == "connect":
        # a patch of the SAME plate thickness sitting on the face (like the
        # louver lip): it never overlaps the sheet, so the added volume is the
        # plain closed form
        plate = prism(face_from_polygon(poly),
                      tuple(n[i] * (d_neg + d_pos) for i in range(3)))
        return fuse(solid, plate)
    # cut: the tool must clear both sheet faces
    margin = 1e-6
    tool_poly = [tuple(p[i] - n[i] * (d_neg + margin) for i in range(3))
                 for p in poly]
    tool = prism(face_from_polygon(tool_poly),
                 tuple(n[i] * (d_neg + d_pos + 2.0 * margin) for i in range(3)))
    return cut(solid, tool)


def arc_segment_area(width: float, depth: float) -> float:
    """P353: 圆弧压筋的截面积——矢高 depth、弦长 width 的圆缺（闭式）。

    R = (w**2/4 + d**2) / (2d);  A = R**2*acos((R-d)/R) - (R-d)*sqrt(2Rd - d**2)
    """
    w = float(width)
    d = float(depth)
    if w <= 0 or d <= 0:
        raise KernelError("圆弧压筋：宽度与深度必须为正")
    R = (w * w / 4.0 + d * d) / (2.0 * d)
    if d > R + 1e-18:
        raise KernelError("圆弧压筋：深度超过半径")
    return (R * R * math.acos(max(-1.0, min(1.0, (R - d) / R)))
            - (R - d) * math.sqrt(max(0.0, 2.0 * R * d - d * d)))


def cross_break(solid, face, length: float, width: float, depth: float,
                kind: str = "v", origin: Optional[Vec3] = None):
    """P353: 十字压筋（cross-break）——面上沿 u 的浅 V 形/圆弧压槽（切除）。

    The groove runs ``length`` along the face frame u direction and its
    cross-section lives in the (v, n) plane:
        kind="v"   -> ½*width*depth*length            (triangular prism)
        kind="arc" -> arc_segment_area(width, depth)*length  (cylinder cut)
    The depth must stay below the plate thickness (a break that reaches through
    is a slit, not a break), and the tool overhangs the face plane by 1 µm so no
    tool face is coplanar with the sheet (rule 73).
    """
    key = str(kind).lower()
    if key not in ("v", "arc"):
        raise KernelError("压筋类型未知：%s（可选 v/arc）" % kind)
    L = float(length)
    w = float(width)
    d = float(depth)
    if L <= 0 or w <= 0 or d <= 0:
        raise KernelError("压筋尺寸必须为正")
    n, base, u, v = _face_uv(face, origin)
    lo_u, hi_u, lo_v, hi_v = _face_span(face, u, v)
    lo, hi = _vertex_bbox(solid)
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    d_pos = max(sum((c[i] - base[i]) * n[i] for i in range(3)) for c in corners)
    d_neg = max(sum((base[i] - c[i]) * n[i] for i in range(3)) for c in corners)
    thick = d_neg + d_pos
    if d >= thick:
        raise KernelError("压筋深度必须小于板厚：深度 %g ≥ 板厚 %g" % (d, thick))
    if L > (hi_u - lo_u) + 1e-12 or w > (hi_v - lo_v) + 1e-12:
        raise KernelError("压筋超出所选面")
    if key == "v":
        # overhang above the face by sliding the two FLANKS up (not the corners):
        # lifting the corners narrows the V inside the material (measured -0.33%),
        # while extending the flanks keeps the removed section exactly w x d / 2
        m = 1e-6
        grow = (d + m) / d
        profile = [(-w / 2.0 * grow, m), (w / 2.0 * grow, m), (0.0, -d)]
        # the profile is built in the (v, n) plane at the groove start
        start = tuple(base[i] - u[i] * (L / 2.0) for i in range(3))
        pts = [tuple(start[i] + v[i] * pv + n[i] * pn for i in range(3))
               for (pv, pn) in profile]
        tool = prism(face_from_polygon(pts), tuple(u[i] * L for i in range(3)))
        return cut(solid, tool)
    R = (w * w / 4.0 + d * d) / (2.0 * d)
    axis_pt = tuple(base[i] + n[i] * (R - d) - u[i] * (L / 2.0) for i in range(3))
    tool = make_cylinder(R, L, origin=axis_pt, axis=u)
    return cut(solid, tool)


def dimple_round(solid, face, diameter: float, depth: float,
                origin: Optional[Vec3] = None):
    """P218: 圆形凹坑（成形族）。

    Geometrically this is a shallow blind hole, so it reuses hole_simple -
    what makes it a form feature is the metadata and the tighter parameter
    validation (a dimple deeper than two diameters is a modelling error, not a
    forming operation).
    """
    if diameter <= 0:
        raise KernelError("凹坑直径必须为正")
    if depth <= 0:
        raise KernelError("凹坑深度必须为正")
    if depth > 4.0 * (diameter / 2.0):
        raise KernelError("凹坑深度不合理：不应超过 2 倍直径")
    return hole_simple(solid, face, diameter, depth=depth, origin=origin)


def hole_counterbore(solid, face, diameter: float, depth: float,
                     cbore_diameter: float, cbore_depth: float,
                     origin: Optional[Vec3] = None):
    """SpaceClaim 沉头孔: cylindrical counterbore at the face + pilot below it.

    The two cutters meet at the counterbore floor, so no volume is counted
    twice: removed = pi*R^2*cbore_depth + pi*r^2*(depth - cbore_depth).
    """
    n, base = _face_frame(face, origin)
    r = float(diameter) / 2.0
    R = float(cbore_diameter) / 2.0
    cd = float(cbore_depth)
    rest = max(float(depth) - cd, 0.0)
    start = tuple(base[i] - n[i] * cd for i in range(3))
    cutter = make_cylinder(R, cd + 1e-6, origin=start, axis=n)
    if rest > 0:
        pstart = tuple(base[i] - n[i] * (cd + rest) for i in range(3))
        cutter = fuse(cutter, make_cylinder(r, rest + 1e-6,
                                            origin=pstart, axis=n))
    return cut(solid, cutter)


def hole_countersink(solid, face, diameter: float, depth: float,
                     sink_diameter: float, angle_deg: float = 90.0,
                     origin: Optional[Vec3] = None):
    """SpaceClaim 锥沉孔: conical countersink at the face + pilot below it.

    removed = frustum(h) + pi*r^2*(depth - h), h = (R - r)/tan(angle/2).
    """
    o = _occ()
    n, base = _face_frame(face, origin)
    r = float(diameter) / 2.0
    R = float(sink_diameter) / 2.0
    if R <= r:
        raise KernelError("锥沉孔：锥口直径必须大于孔径")
    half = math.radians(float(angle_deg) / 2.0)
    h = (R - r) / math.tan(half)
    inner = tuple(base[i] - n[i] * h for i in range(3))
    ax = o["gp"].gp_Ax2(o["gp"].gp_Pnt(*inner), o["gp"].gp_Dir(*n))
    cutter = o["prim"].BRepPrimAPI_MakeCone(ax, r, R, h).Shape()
    rest = max(float(depth) - h, 0.0)
    if rest > 0:
        pstart = tuple(base[i] - n[i] * (h + rest) for i in range(3))
        cutter = fuse(cutter, make_cylinder(r, rest + 1e-6,
                                           origin=pstart, axis=n))
    return cut(solid, cutter)


def boss_round(solid, face, diameter: float, height: float,
               origin: Optional[Vec3] = None):
    """SpaceClaim 凸台: fuse a cylinder onto a planar face (volume += pi r^2 h)."""
    n, base = _face_frame(face, origin)
    r = float(diameter) / 2.0
    return fuse(solid, make_cylinder(r, float(height), origin=base, axis=n))


def pattern_path(shape, path_edge, count: int, align_tangent: bool = False):
    """Distribute `count` copies (including the original position) along the
    path curve of path_edge, evenly by arc length."""
    o = _occ()
    from OCC.Core.GCPnts import GCPnts_AbscissaPoint
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.TopoDS import topods
    from math import floor
    ad = BRepAdaptor_Curve(topods.Edge(path_edge))
    total = GCPnts_AbscissaPoint.Length(ad)
    out = []
    for k in range(count):
        t = total * k / max(1, count - 1) if count > 1 else 0.0
        u = GCPnts_AbscissaPoint(ad, t, ad.FirstParameter()).Parameter()
        p = ad.Value(u)
        tr = o["gp"].gp_Trsf()
        tr.SetTranslation(o["gp"].gp_Vec(
            p.X() - ad.Value(ad.FirstParameter()).X(),
            p.Y() - ad.Value(ad.FirstParameter()).Y(),
            p.Z() - ad.Value(ad.FirstParameter()).Z()))
        out.append(K_copy_transformed(shape, tr))
    return [s for s in out if s is not None]


def K_copy_transformed(shape, trsf):
    o = _occ()
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def pattern_fill(shape, rx: float, ry: float, ex: float, ey: float,
                 gap: float = 0.0, dx0: float = 0.0, dy0: float = 0.0):
    """Grid-fill copies of shape inside a rectangular region rx*ry:
    element footprint (ex, ey) with gap between footprints; (dx0, dy0) =
    first element origin offset."""
    o = _occ()
    import math
    step_x = ex + gap
    step_y = ey + gap
    cols = max(1, int(math.floor((rx + gap + 1e-12) / step_x)))
    rows = max(1, int(math.floor((ry + gap + 1e-12) / step_y)))
    out = []
    for r in range(rows):
        for c in range(cols):
            tr = o["gp"].gp_Trsf()
            tr.SetTranslation(o["gp"].gp_Vec(dx0 + c * step_x,
                                             dy0 + r * step_y, 0.0))
            out.append(K_copy_transformed(shape, tr))
    return out


def pull_auto(shape, subshape, direction=None, distance=0.001,
              mode: str = "auto"):
    """SpaceClaim Pull 的模式族自动分派（内核级）。

    face + direction  -> extrude/offset (out-of-plane pull)
    face, angle given -> draft about face normal
    edge              -> fillet (round) — use distance as radius
    edge + chamfer    -> chamfer
    wire/curve        -> sweep is handled by callers with a path
    solid             -> shell (distance = wall thickness, openings via
                         subshape being the solid's own faces)
    Returns (kind, result_shape).
    """
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID
    from OCC.Core.TopoDS import topods
    st = subshape.ShapeType()
    if st == TopAbs_EDGE:
        if mode == "chamfer":
            return ("chamfer", chamfer_edges(shape, distance, [subshape]))
        return ("fillet", fillet_edges(shape, distance, [subshape]))
    if st == TopAbs_FACE:
        f = topods.Face(subshape)
        nrm, ctr = face_normal_center(f)
        if direction is not None and mode == "draft":
            return ("draft", draft_face(shape, f, distance, direction))
        tr = _occ()["gp"].gp_Trsf()
        tr.SetTranslation(_occ()["gp"].gp_Vec(
            direction[0] * distance, direction[1] * distance,
            direction[2] * distance))
        moved = K_copy_transformed(shape, tr)
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
        d = sum(a * b for a, b in zip(nrm, direction)) if direction else 1.0
        if d >= 0:
            return ("extrude", BRepAlgoAPI_Fuse(shape, moved).Shape())
        return ("offset-cut", BRepAlgoAPI_Cut(shape, moved).Shape())
    if st == TopAbs_SOLID:
        return ("shell", shell_solid(shape, distance, []))
    raise KernelError("Pull：不支持的选择类型")


def face_from_polygon(pts: Sequence[Vec3]):
    """Planar face from a closed polygon.

    P29: official loops can repeat points (seam vertices, duplicated coedges) and
    OCCT raises StdFail_NotDone from MakePolygon::Close on those - dedupe first
    and require at least 3 distinct vertices.
    """
    o = _occ()
    clean = []
    for p in pts:
        p = (float(p[0]), float(p[1]), float(p[2]))
        if not clean or math.dist(clean[-1], p) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) < 1e-9:
        clean.pop()
    if len(clean) < 3:
        raise KernelError("多边形顶点不足（去重后 %d 个）" % len(clean))
    mk = o["bapi"].BRepBuilderAPI_MakePolygon()
    for p in clean:
        mk.Add(o["gp"].gp_Pnt(*p))
    mk.Close()
    if not mk.IsDone():
        raise KernelError("多边形失败")
    return o["bapi"].BRepBuilderAPI_MakeFace(mk.Wire(), True).Face()


def prism(face, vec: Vec3):
    o = _occ()
    return o["prim"].BRepPrimAPI_MakePrism(face, o["gp"].gp_Vec(*vec)).Shape()


def revolve(face, origin: Vec3, axis: Vec3, angle_rad: float):
    o = _occ()
    ax = o["gp"].gp_Ax1(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*axis))
    return o["prim"].BRepPrimAPI_MakeRevol(face, ax, angle_rad).Shape()


def helix_edge(radius: float, pitch: float, height: float, origin: Vec3 = (0, 0, 0)):
    """Approximate helix as a BSpline through samples."""
    o = _occ()
    import math
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSpline
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    n = max(16, int(height / max(pitch, 1e-6) * 16))
    arr = TColgp_Array1OfPnt(1, n)
    for i in range(n):
        t = i / (n - 1)
        z = origin[2] + height * t
        ang = 2 * math.pi * (height * t / max(pitch, 1e-6))
        arr.SetValue(i + 1, o["gp"].gp_Pnt(
            origin[0] + radius * math.cos(ang),
            origin[1] + radius * math.sin(ang), z))
    curve = GeomAPI_PointsToBSpline(arr).Curve()
    return o["bapi"].BRepBuilderAPI_MakeEdge(curve).Edge()


def volume(shape) -> float:
    o = _occ()
    props = o["gprop"].GProp_GProps()
    try:
        o["brepgprop"].brepgprop.VolumeProperties(shape, props)
    except Exception:
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties
        brepgprop_VolumeProperties(shape, props)
    return props.Mass()


def area(shape) -> float:
    o = _occ()
    props = o["gprop"].GProp_GProps()
    try:
        o["brepgprop"].brepgprop.SurfaceProperties(shape, props)
    except Exception:
        from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
        brepgprop_SurfaceProperties(shape, props)
    return props.Mass()


def cog(shape) -> Vec3:
    o = _occ()
    props = o["gprop"].GProp_GProps()
    try:
        o["brepgprop"].brepgprop.VolumeProperties(shape, props)
    except Exception:
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties
        brepgprop_VolumeProperties(shape, props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def _gprops(shape, surface: bool = False):
    """GProp_GProps for a shape (volume by default, surface for planar faces)."""
    o = _occ()
    props = o["gprop"].GProp_GProps()
    try:
        if surface:
            o["brepgprop"].brepgprop.SurfaceProperties(shape, props)
        else:
            o["brepgprop"].brepgprop.VolumeProperties(shape, props)
    except Exception:
        from OCC.Core.BRepGProp import (brepgprop_SurfaceProperties,
                                        brepgprop_VolumeProperties)
        fn = brepgprop_SurfaceProperties if surface else brepgprop_VolumeProperties
        fn(shape, props)
    return props


def section_props(face) -> dict:
    """P283: area, centroid and centroidal second moments of a PLANAR face.

    Returns {"area", "cx", "cy", "ix", "iy", "j"} with ix = integral(y**2 dA),
    iy = integral(x**2 dA) and j = ix + iy (polar).  The face is expected to lie
    in a plane parallel to XY - that is how scdm.beams builds every section, and
    it is what makes the beam closed forms checkable.
    """
    props = _gprops(face, surface=True)
    m = props.MatrixOfInertia()
    c = props.CentreOfMass()
    ix, iy = m.Value(1, 1), m.Value(2, 2)
    return {"area": props.Mass(), "cx": c.X(), "cy": c.Y(),
            "ix": ix, "iy": iy, "j": ix + iy}


def inertia(shape) -> dict:
    """P283: second moments of a SOLID about its own centre of mass.

    Returns {"ixx", "iyy", "izz", "ixy", "ixz", "iyz", "cog"}.  For a prismatic
    beam of length L with section area A and centroidal moments ix/iy:
        ixx = L*ix + A*L**3/12, iyy = L*iy + A*L**3/12, izz = L*(ix + iy)
    which is exactly what the beam tests assert against the closed form.
    """
    props = _gprops(shape)
    m = props.MatrixOfInertia()
    c = props.CentreOfMass()
    return {"ixx": m.Value(1, 1), "iyy": m.Value(2, 2), "izz": m.Value(3, 3),
            "ixy": m.Value(1, 2), "ixz": m.Value(1, 3), "iyz": m.Value(2, 3),
            "cog": (c.X(), c.Y(), c.Z())}


def interference_volume(a, b) -> float:
    inter = common(a, b)
    return abs(volume(inter))


def write_step(shape, path: str) -> None:
    o = _occ()
    w = o["step"].STEPControl_Writer()
    w.Transfer(shape, o["step"].STEPControl_AsIs)
    status = w.Write(path)
    if status != o["ifs"].IFSelect_RetDone:
        raise KernelError("STEP 写出失败")


def read_step(path: str):
    o = _occ()
    r = o["step"].STEPControl_Reader()
    if r.ReadFile(path) != o["ifs"].IFSelect_RetDone:
        raise KernelError("STEP 读取失败")
    r.TransferRoots()
    return r.OneShape()


def read_stl(path: str):
    o = _occ()
    from OCC.Core.StlAPI import StlAPI_Reader
    from OCC.Core.TopoDS import TopoDS_Shape
    shape = TopoDS_Shape()
    r = StlAPI_Reader()
    if not r.Read(shape, path):
        raise KernelError("STL 读取失败")
    return shape


def check_geometry(shape, min_area: float = 1e-7, min_edge: float = 1e-6):
    """H4 check-geometry suite. Returns a findings dict:

    {"small_faces": [face...], "short_edges": [edge...],
     "sliver_faces": [face...], "self_intersecting": bool,
     "inverted_faces": [face...], "open_shell": bool}
    Thresholds in metres / square metres.
    """
    faces = explore(shape, "face")
    edges = explore(shape, "edge")
    out = {"small_faces": [], "short_edges": [], "sliver_faces": [],
           "self_intersecting": False, "inverted_faces": [],
           "open_shell": False}
    for f in faces:
        a = area(f)
        if a < min_area:
            out["small_faces"].append(f)
            continue
        # sliver: face area tiny relative to its longest edge span
        emax = 0.0
        fedges = explore(f, "edge")
        for e in fedges:
            pts = edge_polyline(e, deflection=0.0005)
            if len(pts) < 2:
                continue
            p1, p2 = pts[0], pts[-1]
            d = (p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2
            emax = max(emax, d)
        if emax > 0 and a < 0.01 * emax:
            out["sliver_faces"].append(f)
    for e in edges:
        pts = edge_polyline(e, deflection=0.0005)
        if len(pts) >= 2:
            p1, p2 = pts[0], pts[-1]
            d = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2
                 + (p2[2] - p1[2]) ** 2) ** 0.5
            if d < min_edge:
                out["short_edges"].append(e)
    # self-intersection (OCCT BRepAlgoAPI_Check)
    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Check
        chk = BRepAlgoAPI_Check(shape)
        out["self_intersecting"] = not chk.IsValid()
    except Exception:
        pass
    # inverted faces: per-face oriented volume contribution should point
    # away from the body centre for a consistently oriented closed solid
    try:
        cog = _cog_vec(shape)
        for f in faces:
            tri = tessellate_faces(f, deflection=0.002)
            if not tri:
                continue
            fd = tri[0]
            n = fd.get("normal")
            if n is None:
                continue
            c = fd["vertices"][0] if fd["vertices"] else None
            if c is None:
                continue
            if (n[0] * (c[0] - cog[0]) + n[1] * (c[1] - cog[1])
                    + n[2] * (c[2] - cog[2])) < 0:
                out["inverted_faces"].append(f)
    except Exception:
        pass
    # open shell: an edge used by only one face
    try:
        from collections import Counter
        cnt = Counter()
        for f in faces:
            for e in explore(f, "edge"):
                cnt[e.TShape()] += 1
        lonely = [k for k, c in cnt.items() if c == 1]
        out["open_shell"] = bool(faces) and len(lonely) > 0
    except Exception:
        pass
    return out


def _cog_vec(shape):
    return cog(shape)


def repair_geometry(shape, findings, new_face_replacement=None):
    """Auto-fix what is fixable: small faces & slivers via unify-then-heal,
    short edges via ShapeFix_Wireframe, inverted faces via reversal.
    Returns (shape, report dict of applied fixes)."""
    report = {}
    cur = shape
    # 1) short edges
    if findings.get("short_edges"):
        try:
            from OCC.Core.ShapeFix import ShapeFix_Wireframe
            fx = ShapeFix_Wireframe(cur)
            fx.SetPrecision(max(findings.get("_min_edge", 1e-6), 1e-7))
            fx.FixSmallEdges()
            fx.FixGaps3d()
            fx.FixGaps2d()
            if fx.Shape() is not None and not fx.Shape().IsNull():
                cur = fx.Shape()
                report["short_edges"] = len(findings["short_edges"])
        except Exception:
            report["short_edges"] = "failed"
    # 2) inverted faces
    inv = findings.get("inverted_faces") or []
    if inv:
        fixed = 0
        for f in inv:
            try:
                cur = reverse_face(cur, f)
                fixed += 1
            except Exception:
                pass
        report["inverted_faces"] = fixed
    # 3) small faces / slivers: merge coplanar neighbours then heal
    if findings.get("small_faces") or findings.get("sliver_faces"):
        try:
            cur = unify_same_domain(cur)
            report["small_faces"] = report.get("small_faces", 0) if                 isinstance(report.get("small_faces"), int) else                 len(findings.get("small_faces", [])) +                 len(findings.get("sliver_faces", []))
        except Exception:
            pass
    return cur, report


def reverse_face(shape, face):
    """Return the shape with the given face's orientation reversed.

    ReShape ignores same-TShape replacements, so the replacement is a REBUILT
    face (new TShape) carrying the reversed orientation.
    """
    from OCC.Core.TopoDS import topods
    from OCC.Core.ShapeBuild import ShapeBuild_ReShape
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.TopAbs import TopAbs_SHAPE
    f = topods.Face(face)
    newf = BRepBuilderAPI_MakeFace(f.Reversed()).Face()
    rs = ShapeBuild_ReShape()
    rs.Replace(f, newf)
    return rs.Apply(shape, TopAbs_SHAPE)


def apply_mat4(shape, m):
    """Apply a row-major 4x4 transform (scdm.mates convention) to a shape."""
    o = _occ()
    tr = o["gp"].gp_Trsf()
    tr.SetValues(m[0][0], m[0][1], m[0][2], m[0][3],
                 m[1][0], m[1][1], m[1][2], m[1][3],
                 m[2][0], m[2][1], m[2][2], m[2][3])
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def write_iges(shape, path: str) -> None:
    o = _occ()
    from OCC.Core.IGESControl import IGESControl_Writer
    w = IGESControl_Writer()
    w.AddShape(shape)
    w.ComputeModel()
    if not w.Write(path):
        raise KernelError("IGES 写出失败")


def read_iges(path: str):
    o = _occ()
    from OCC.Core.IGESControl import IGESControl_Reader
    r = IGESControl_Reader()
    if r.ReadFile(path) != o["ifs"].IFSelect_RetDone:
        raise KernelError("IGES 读取失败")
    r.TransferRoots()
    return r.OneShape()


def _mesh_tris(shape, deflection: float = 0.001):
    """(vertices, triangles) from OCCT tessellation."""
    o = _occ()
    o["mesh"].BRepMesh_IncrementalMesh(shape, deflection, False, 0.5, True)
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopoDS import topods
    verts, tris, off = [], [], 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        from OCC.Core.TopLoc import TopLoc_Location
        loc = TopLoc_Location()
        poly = BRep_Tool().Triangulation(f, loc)
        if poly is not None:
            for k in range(1, poly.NbNodes() + 1):
                p = poly.Node(k).Transformed(loc.Transformation())
                verts.append((p.X(), p.Y(), p.Z()))
            for k in range(1, poly.NbTriangles() + 1):
                a, b, c = poly.Triangle(k).Get()
                tris.append((a + off - 1, b + off - 1, c + off - 1))
            off += poly.NbNodes()
        ex.Next()
    return verts, tris


def write_obj(shape, path: str) -> None:
    """Shape -> OBJ from tessellation (v/f lines)."""
    verts, tris = _mesh_tris(shape, deflection=0.001)
    lines = ["# exported by scdm"]
    for p in verts:
        lines.append("v %.9g %.9g %.9g" % (p[0], p[1], p[2]))
    for a, b, c in tris:
        lines.append("f %d %d %d" % (a + 1, b + 1, c + 1))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def read_obj(path: str):
    """OBJ (v/f mesh) -> shell body via weld + sew."""
    import numpy as np
    from scdm import facets as F
    pts, tris = [], []
    with open(path) as f:
        for ln in f:
            if ln.startswith("v "):
                x, y, z = ln.split()[1:4]
                pts.append((float(x), float(y), float(z)))
            elif ln.startswith("f "):
                idx = [int(t.split("/")[0]) - 1 for t in ln.split()[1:]]
                for k in range(1, len(idx) - 1):
                    tris.append((idx[0], idx[k], idx[k + 1]))
    if not tris:
        raise KernelError("OBJ 无面数据")
    pts = np.array(pts, dtype=np.float64)
    tris = np.array(tris, dtype=np.int64)
    pts, tris = F.weld(pts, tris, tol=1e-6)
    return F.mesh_to_shell(pts, tris)


def read_3mf(path: str):
    """3MF (zip + XML mesh) -> shell body. Mesh data only (welded)."""
    return _read_mesh_zip(
        path, ns="{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}")


def _read_mesh_zip(path, ns):
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".model"))
        root = ET.fromstring(z.read(name))
    ns_ = ns
    verts = {}
    for v in root.iter(ns_ + "vertex"):
        verts[int(v.get("id"))] = (float(v.get("x")), float(v.get("y")),
                                   float(v.get("z")))
    tris = []
    for t in root.iter(ns_ + "triangle"):
        tris.append((int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))))
    if not tris:
        raise KernelError("3MF 无网格数据")
    from scdm import facets as F
    import numpy as np
    pts = np.array([verts[i] for i in sorted(verts)], dtype=np.float64)
    idx = {vid: k for k, vid in enumerate(sorted(verts))}
    tris = np.array([[idx[a], idx[b], idx[c]] for a, b, c in tris],
                    dtype=np.int64)
    pts, tris = F.weld(pts, tris, tol=1e-6)
    return F.mesh_to_shell(pts, tris)


def write_3mf(shape, path: str) -> None:
    """Shape -> 3MF zip (tessellated mesh)."""
    import zipfile
    verts, tris = _mesh_tris(shape, deflection=0.001)
    xs, ys, zs = [], [], []
    vid = {}
    for k, p in enumerate(verts):
        vid[k] = k + 1
        xs.append("%.6g" % p[0]); ys.append("%.6g" % p[1]); zs.append("%.6g" % p[2])
    v_lines = "".join('<vertex id="%d" x="%s" y="%s" z="%s"/>' % (k + 1, xs[k], ys[k], zs[k]) for k in range(len(verts)))
    t_lines = "".join('<triangle v1="%d" v2="%d" v3="%d"/>' % (a + 1, b + 1, c + 1) for a, b, c in tris)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
           '<resources><object id="1" type="model"><mesh>'
           '<vertices>%s</vertices><triangles>%s</triangles>'
           '</mesh></object></resources>'
           '<build><item objectid="1"/></build></model>') % (v_lines, t_lines)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", xml)


def write_vrml(shape, path: str) -> None:
    o = _occ()
    from OCC.Core.VrmlAPI import VrmlAPI_Writer
    w = VrmlAPI_Writer()
    if not w.Write(shape, path):
        raise KernelError("VRML 写出失败")


def write_stl(shape, path: str, deflection: float = 0.1) -> None:
    tessellate_mesh(shape, deflection)
    o = _occ()
    w = o["stl"].StlAPI_Writer()
    w.Write(shape, path)


def write_brep(shape, path: str) -> None:
    o = _occ()
    try:
        o["breptools"].Write(shape, path)
    except Exception:
        from OCC.Core.BRepTools import breptools_Write
        breptools_Write(shape, path)


def read_brep(path: str):
    o = _occ()
    from OCC.Core.TopoDS import TopoDS_Shape
    from OCC.Core.BRep import BRep_Builder
    sh = TopoDS_Shape()
    try:
        o["breptools"].Read(sh, path, BRep_Builder())
    except Exception:
        from OCC.Core.BRepTools import breptools_Read
        breptools_Read(sh, path, BRep_Builder())
    return sh


def dumps_brep(shape) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".brep")
    os.close(fd)
    try:
        write_brep(shape, path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def loads_brep(data: bytes):
    fd, path = tempfile.mkstemp(suffix=".brep")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(data)
        return read_brep(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def tessellate_mesh(shape, deflection: float = 0.1):
    o = _occ()
    o["mesh"].BRepMesh_IncrementalMesh(shape, deflection, False, 0.5, True)
    return shape


def tessellate_faces(shape, deflection: float = 0.05):
    """Per-face triangles for VTK picking. Returns list of dicts."""
    o = _occ()
    tessellate_mesh(shape, deflection)
    loc = o["toploc"].TopLoc_Location()
    faces = []
    for i, face in enumerate(explore(shape, "face")):
        tri = o["BRep_Tool"].Triangulation(face, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        verts = []
        nb = tri.NbNodes()
        for n in range(1, nb + 1):
            p = tri.Node(n)
            if not loc.IsIdentity():
                p = p.Transformed(trsf)
            verts.append((p.X(), p.Y(), p.Z()))
        tris = []
        reverse = face.Orientation() != o["topabs"].TopAbs_FORWARD
        for t in range(1, tri.NbTriangles() + 1):
            n1, n2, n3 = tri.Triangle(t).Get()
            if reverse:
                tris.append((n1 - 1, n3 - 1, n2 - 1))
            else:
                tris.append((n1 - 1, n2 - 1, n3 - 1))
        nrm, ctr = face_normal_center(face)
        faces.append({
            "index": i,
            "vertices": verts,
            "triangles": tris,
            "normal": nrm,
            "center": ctr,
            "face": face,
        })
    return faces


def reverse_shape(shape):
    """Flip the orientation of a whole shape (reverse face normals).

    Used by the Facets > Reverse-Normals tool. Returns a copy with reversed
    top-level orientation; invalid shapes are left unchanged.
    """
    o = _occ()
    try:
        copy = o["bapi"].BRepBuilderAPI_Copy(shape).Shape()
        return copy.Reversed()
    except Exception:
        return shape


def compound(shapes: Sequence):
    o = _occ()
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound
    b = BRep_Builder()
    c = TopoDS_Compound()
    b.MakeCompound(c)
    for s in shapes:
        b.Add(c, s)
    return c

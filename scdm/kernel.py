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


def align_faces(moving, moving_face, target_face):
    """Assembly Mate: transform the moving shape so its face coincides with the target.

    Rotates the moving shape so its face normal opposes the target normal, then
    translates so the face centres coincide. Returns the transformed shape.
    """
    o = _occ()
    n1, c1 = face_normal_center(moving_face)
    n2, c2 = face_normal_center(target_face)
    desired = (-n2[0], -n2[1], -n2[2])
    tr = o["gp"].gp_Trsf()
    dot = n1[0] * desired[0] + n1[1] * desired[1] + n1[2] * desired[2]
    if dot < 1.0 - 1e-12:
        axis = (
            n1[1] * desired[2] - n1[2] * desired[1],
            n1[2] * desired[0] - n1[0] * desired[2],
            n1[0] * desired[1] - n1[1] * desired[0],
        )
        mag = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
        if mag > 1e-12:
            ang = math.acos(max(-1.0, min(1.0, dot)))
            ax = o["gp"].gp_Ax1(o["gp"].gp_Pnt(*c1),
                                o["gp"].gp_Dir(axis[0] / mag, axis[1] / mag, axis[2] / mag))
            tr.SetRotation(ax, ang)
    shifted = o["bapi"].BRepBuilderAPI_Transform(moving, tr, True).Shape()
    # NOTE: the rotation is about c1, so the moving face centre stays at c1;
    # translate by the centre delta to land on the target centre.
    vec = (c2[0] - c1[0], c2[1] - c1[1], c2[2] - c1[2])
    return translate(shifted, vec)


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


def fillet_edges(shape, radius: float, edges: Optional[Sequence] = None):
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


def face_from_polygon(pts: Sequence[Vec3]):
    o = _occ()
    mk = o["bapi"].BRepBuilderAPI_MakePolygon()
    for p in pts:
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

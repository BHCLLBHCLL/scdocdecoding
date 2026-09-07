"""Rebuild OCCT solids from decoded SAB topology (planar faces first)."""
from __future__ import annotations

from typing import Any, List, Optional

from scdm import kernel as K
from scdm.kdoc import KernelDoc


def import_model(model, color=(0.62, 0.66, 0.70)) -> KernelDoc:
    doc = KernelDoc()
    if model is None or not K.available():
        return doc
    bodies = model.of_kind("body")
    if not bodies:
        # some files may only expose faces
        faces = _faces_from_model(model, None)
        if faces:
            try:
                solid = K.sew_faces(faces)
                doc.add_body(solid, name="实体 1", color=color)
            except K.KernelError:
                pass
        return doc
    for i, body in enumerate(bodies, 1):
        faces = _faces_from_model(model, body)
        if not faces:
            continue
        try:
            solid = K.sew_faces(faces)
            name = model.doc_id_of(body) or f"实体 {i}"
            doc.add_body(solid, name=f"实体 {i}", color=color)
        except K.KernelError:
            continue
    return doc


def _faces_from_model(model, body) -> List[Any]:
    face_ents = model.body_faces(body) if body is not None else model.of_kind("face")
    occ_faces = []
    for face in face_ents:
        f = _rebuild_face(model, face)
        if f is not None:
            occ_faces.append(f)
            continue
        polys = model.face_loops_polygons(face)
        if not polys:
            continue
        try:
            occ_faces.append(K.face_from_polygon(polys[0]))
        except K.KernelError:
            continue
    return occ_faces


# -- curved-face rebuild (spline-surface clusters written by our own files) --
def _surface_kind(model, face_ent):
    """(kind, surface_ent) for a face's surface reference, or (None, None)."""
    s = model.e(face_ent.surface) if face_ent.surface >= 0 else None
    if s is None:
        return None, None
    return s.kind, s


def _inner_of_kind(model, head_ent, kind):
    """The head's inner-scope payload record of the given kind ('both',
    'nubs', ...), via cluster_owner back-links."""
    for e in model.inner:
        if e.cluster_owner == head_ent.idx and e.kind == kind:
            return e
    return None


def _bspline_surface(model, surf_head):
    """Geom_BSplineSurface from a spline-cluster head ('spline' chain) —
    degrees from its inner nurbs record, knots/mults/poles from 'both'.
    ACIS mult convention: npoles = sum(mults) - deg + 1."""
    from OCC.Core.TColgp import TColgp_Array2OfPnt
    from OCC.Core.TColStd import (TColStd_Array1OfInteger,
                                  TColStd_Array1OfReal,
                                  TColStd_Array2OfReal)
    from OCC.Core.Geom import Geom_BSplineSurface
    from OCC.Core.gp import gp_Pnt

    nurbs = _inner_of_kind(model, surf_head, "nurbs")
    both = _inner_of_kind(model, surf_head, "both")
    if nurbs is None or both is None or both.bsurf_poles is None:
        return None
    du = nurbs.bs_deg or 0
    dv = nurbs.bs_deg_v or 0
    um, vm = both.bsurf_u_mults, both.bsurf_v_mults
    # ACIS storage: endpoint multiplicities pre-decremented; restore OCCT's
    npu = sum(um) - du + 1
    npv = sum(vm) - dv + 1
    um_occt = [um[0] + 1] + um[1:-1] + [um[-1] + 1]
    vm_occt = [vm[0] + 1] + vm[1:-1] + [vm[-1] + 1]
    poles = both.bsurf_poles
    if du < 1 or dv < 1 or len(poles) != npu * npv:
        return None
    arr = TColgp_Array2OfPnt(1, npu, 1, npv)
    wts = TColStd_Array2OfReal(1, npu, 1, npv)
    for j in range(npv):
        for i in range(npu):
            x, y, z, w = poles[j * npu + i]
            arr.SetValue(i + 1, j + 1, gp_Pnt(x, y, z))
            wts.SetValue(i + 1, j + 1, w)
    uku = TColStd_Array1OfReal(1, len(both.bsurf_u_knots))
    umu = TColStd_Array1OfInteger(1, len(um_occt))
    for i, (k, m) in enumerate(zip(both.bsurf_u_knots, um_occt)):
        uku.SetValue(i + 1, k)
        umu.SetValue(i + 1, m)
    vku = TColStd_Array1OfReal(1, len(both.bsurf_v_knots))
    vmu = TColStd_Array1OfInteger(1, len(vm_occt))
    for i, (k, m) in enumerate(zip(both.bsurf_v_knots, vm_occt)):
        vku.SetValue(i + 1, k)
        vmu.SetValue(i + 1, m)
    try:
        return Geom_BSplineSurface(arr, wts, uku, vku, umu, vmu, du, dv)
    except Exception:
        return None


def _edge_curve(model, edge_ent):
    """Geom_Curve + (t0, t1) for an edge from its curve reference, or None."""
    from OCC.Core.Geom import (Geom_BSplineCurve, Geom_Ellipse, Geom_Line,
                               Geom_TrimmedCurve)
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt

    c = model.e(edge_ent.curve) if edge_ent.curve >= 0 else None
    if c is None:
        return None
    t0 = edge_ent.pstart if edge_ent.pstart is not None else 0.0
    t1 = edge_ent.pend if edge_ent.pend is not None else 1.0
    try:
        if c.kind == "straight" and c.direction:
            lin = Geom_Line(gp_Pnt(*c.origin), gp_Dir(*c.direction))
            return Geom_TrimmedCurve(lin, min(t0, t1), max(t0, t1))
        if c.kind == "ellipse":
            ratio = c.ratio if c.ratio else 1.0
            major = c.xdir or (1.0, 0.0, 0.0)
            mlen = (major[0] ** 2 + major[1] ** 2 + major[2] ** 2) ** 0.5
            if mlen < 1e-12 or ratio <= 0.0:
                return None
            ax = gp_Ax2(gp_Pnt(*c.origin), gp_Dir(*c.normal),
                        gp_Dir(*major))
            el = Geom_Ellipse(ax, mlen, mlen * ratio)
            return Geom_TrimmedCurve(el, min(t0, t1), max(t0, t1))
        if c.kind == "intcurve":
            nubs = _inner_of_kind(model, c, "nubs")
            if nubs is None or not nubs.bs_poles:
                return None
            npoles = len(nubs.bs_poles)
            deg = sum(nubs.bs_mults) - npoles + 1
            if deg < 1:
                return None
            from OCC.Core.TColgp import TColgp_Array1OfPnt
            from OCC.Core.TColStd import (TColStd_Array1OfInteger,
                                          TColStd_Array1OfReal)
            pts = TColgp_Array1OfPnt(1, npoles)
            for i, p in enumerate(nubs.bs_poles):
                pts.SetValue(i + 1, gp_Pnt(*p))
            nk = len(nubs.bs_knots)
            ku = TColStd_Array1OfReal(1, nk)
            mu = TColStd_Array1OfInteger(1, nk)
            for i, (k, m) in enumerate(zip(nubs.bs_knots, nubs.bs_mults)):
                ku.SetValue(i + 1, k)
                mu.SetValue(i + 1, m)
            bs = Geom_BSplineCurve(pts, ku, mu, deg)
            lo, hi = bs.FirstParameter(), bs.LastParameter()
            return Geom_TrimmedCurve(bs, min(t0, t1, lo, hi)
                                     if False else lo, hi)
    except Exception:
        return None
    return None


def _face_has_curved_edges(model, face_ent):
    """True when any loop edge's curve is not a straight line (ellipse
    arcs, intcurves) or is closed (v1 == v2) — such faces need the
    wire-based rebuild instead of the planar polygon shortcut."""
    for loop in model.loops_of_face(face_ent):
        for ce in model.coedges_of_loop(loop):
            edge_ent = model.e(ce.edge) if ce.edge >= 0 else None
            if edge_ent is None:
                continue
            if edge_ent.v1 >= 0 and edge_ent.v1 == edge_ent.v2:
                return True
            c = model.e(edge_ent.curve) if edge_ent.curve >= 0 else None
            if c is not None and c.kind != "straight":
                return True
    return False


def _planar_face_from_wires(model, face_ent, plane_ent):
    """Planar face rebuilt from real boundary curves (supports ellipse arcs
    and closed edges — cone caps, hole openings)."""
    from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                         BRepBuilderAPI_MakeFace,
                                         BRepBuilderAPI_MakeWire)
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCC.Core.ShapeFix import ShapeFix_Face
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    if plane_ent.origin is None or plane_ent.normal is None:
        return None
    pln = gp_Pln(gp_Pnt(*plane_ent.origin), gp_Dir(*plane_ent.normal))
    wires = []
    for loop in model.loops_of_face(face_ent):
        wmaker = BRepBuilderAPI_MakeWire()
        n = 0
        for ce in model.coedges_of_loop(loop):
            edge_ent = model.e(ce.edge) if ce.edge >= 0 else None
            if edge_ent is None:
                continue
            curve = _edge_curve(model, edge_ent)
            if curve is None:
                continue
            try:
                wmaker.Add(BRepBuilderAPI_MakeEdge(curve).Edge())
                n += 1
            except Exception:
                continue
        if n:
            try:
                wires.append(wmaker.Wire())
            except Exception:
                return None
    if not wires:
        return None
    try:
        mf = BRepBuilderAPI_MakeFace(pln, wires[0])
        for w in wires[1:]:
            mf.Add(w)
        if not mf.IsDone():
            return None
        fix = ShapeFix_Face(mf.Face())
        fix.SetPrecision(1e-6)
        fix.Perform()
        f = fix.Face()
        if BRepCheck_Analyzer(f).IsValid():
            return f
        return mf.Face()
    except Exception:
        return None


def _rebuild_face(model, face_ent):
    """Curved-face rebuild: spline-surface cluster faces (full parametric
    patch — our writer stores the surface window as the face window),
    cylinders ('cone' records with zero semi-angle), and planar faces whose
    loops carry curve edges.  Neighbours are stitched by sewing on
    coincident boundary geometry."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    kind, surf_ent = _surface_kind(model, face_ent)
    if kind == "spline":
        surf = _bspline_surface(model, surf_ent)
        if surf is None:
            return None
        try:
            mk = BRepBuilderAPI_MakeFace(surf, 1e-6)
            if not mk.IsDone():
                return None
            return mk.Face()
        except Exception:
            return None
    if kind == "cone":
        # cylinder (zero semi-angle): ACIS v = angle, u = axial.  The axial
        # range is derived geometrically from the boundary circles' centres
        # projected on the axis (the recorded uv_range mirrors the official
        # template values, not this body's real extents).
        semi = surf_ent.semangle if surf_ent.semangle is not None else 0.0
        if (abs(semi) > 1e-12 or not surf_ent.radius
                or surf_ent.origin is None or surf_ent.normal is None
                or surf_ent.xdir is None):
            return None
        try:
            from OCC.Core.Geom import Geom_CylindricalSurface
            from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
            axis = surf_ent.normal
            alen = (axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2) ** 0.5
            if alen < 1e-12:
                return None
            axis = (axis[0] / alen, axis[1] / alen, axis[2] / alen)
            v0, v1 = None, None
            for loop in model.loops_of_face(face_ent):
                for ce in model.coedges_of_loop(loop):
                    ee = model.e(ce.edge) if ce.edge >= 0 else None
                    c = (model.e(ee.curve)
                         if ee is not None and ee.curve >= 0 else None)
                    if c is not None and c.kind == "ellipse" and c.origin:
                        t = ((c.origin[0] - surf_ent.origin[0]) * axis[0]
                             + (c.origin[1] - surf_ent.origin[1]) * axis[1]
                             + (c.origin[2] - surf_ent.origin[2]) * axis[2])
                        v0 = t if v0 is None else min(v0, t)
                        v1 = t if v1 is None else max(v1, t)
            if v0 is None:
                v0, v1 = 0.0, 1.0
            from OCC.Core.gp import gp_Ax3
            ax = gp_Ax3(gp_Ax2(gp_Pnt(*surf_ent.origin), gp_Dir(*axis),
                               gp_Dir(*surf_ent.xdir)))
            surf = Geom_CylindricalSurface(ax, surf_ent.radius)
            mk = BRepBuilderAPI_MakeFace(surf, 0.0, 2.0 * 3.141592653589793,
                                         v0, v1, 1e-6)
            if not mk.IsDone():
                return None
            return mk.Face()
        except Exception:
            return None
    if kind == "plane" and _face_has_curved_edges(model, face_ent):
        return _planar_face_from_wires(model, face_ent, surf_ent)
    return None


def import_scdoc_bundle(data: dict) -> KernelDoc:
    model = data.get("model") if data else None
    color = (0.62, 0.66, 0.70)
    render = data.get("render") if data else None
    if render:
        for view in render:
            for it in view.get("items", []):
                for b in it.get("bodies", []):
                    if b.get("rgb"):
                        color = tuple(c / 255.0 for c in b["rgb"])
                        break
    fac = data.get("fac") if data else None
    models = (data.get("models") if data else None) or (
        [model] if model is not None else [])
    doc = KernelDoc()
    failed = 0
    for mdl in models:
        part_doc = import_model(mdl, color=color)
        if part_doc.bodies:
            for b in part_doc.bodies:
                doc.add_body(b.shape, name=b.name, color=b.color)
        else:
            failed += 1
    if doc.bodies:
        if failed and fac is not None and getattr(fac, "faces", None)                 and K.available():
            import numpy as np
            from scdm import facets as F
            vs, ts, off = [], [], 0
            for f in fac.faces:
                pts = np.asarray([c.position for c in f.corners],
                                 dtype=np.float64)
                tris = np.asarray(f.triangles, dtype=np.int64)
                if len(pts) == 0 or not len(tris):
                    continue
                vs.append(pts)
                ts.append(tris + off)
                off += len(pts)
            if vs:
                verts = np.vstack(vs)
                tris = np.vstack(ts)
                try:
                    verts, tris = F.weld(verts, tris, tol=1e-6)
                    doc.add_body(F.mesh_to_shell(verts, tris),
                                 name="网格导入", color=color)
                except Exception:
                    pass
        return doc
    doc = import_model(model, color=color)
    if doc.bodies:
        return doc
    # facet-mesh fallback: sew the display mesh into a shell body (marks
    # 「网格导入」through the name) — used when the SAB carries faces the
    # topology layer cannot rebuild (e.g. cylindrical faces)
    fac = data.get("fac") if data else None
    if fac is not None and getattr(fac, "faces", None) and K.available():
        import numpy as np
        from scdm import facets as F
        vs, ts, off = [], [], 0
        for f in fac.faces:
            pts = np.asarray([c.position for c in f.corners], dtype=np.float64)
            tris = np.asarray(f.triangles, dtype=np.int64)
            if len(pts) == 0 or not len(tris):
                continue
            vs.append(pts)
            ts.append(tris + off)
            off += len(pts)
        if vs:
            verts = np.vstack(vs)
            tris = np.vstack(ts)
            try:
                verts, tris = F.weld(verts, tris, tol=1e-6)
                shell = F.mesh_to_shell(verts, tris)
                doc.add_body(shell, name="网格导入", color=color)
            except Exception:
                pass
    if not doc.bodies and fac is not None and getattr(fac, "faces", None):
        xs, ys, zs = [], [], []
        for f in fac.faces:
            for c in f.corners:
                xs.append(c.position[0]); ys.append(c.position[1]); zs.append(c.position[2])
        if xs and K.available():
            dx = max(xs) - min(xs); dy = max(ys) - min(ys); dz = max(zs) - min(zs)
            if min(dx, dy, dz) > 1e-12:
                box = K.make_box(dx, dy, dz, origin=(min(xs), min(ys), min(zs)))
                doc.add_body(box, name="实体 1", color=color)
    return doc

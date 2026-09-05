"""H5: sheet-metal kernel (K-factor bends, unfold, rip, corner relief, jog).

Developed-length convention (SpaceClaim K-factor):
    bend allowance BA = theta_rad * (R_inner + K * t)
    developed length  = flat1 + BA + flat2
All lengths in metres (kernel convention).
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from scdm import kernel as K

Vec3 = Tuple[float, float, float]


def bend_allowance(angle_rad: float, r_inner: float, k: float,
                   t: float) -> float:
    """Bend allowance along the neutral axis (K = neutral offset / t)."""
    return abs(angle_rad) * (r_inner + k * t)


# ----------------------------------------------------------------------
# L-bend construction (from flat parameters)
# ----------------------------------------------------------------------
def bend_from_flat(width: float, t: float, len1: float, len2: float,
                   angle_rad: float, r_inner: float, k: float) -> "object":
    """Build a bent sheet from flat parameters: flat1 runs +x for len1,
    a bend of angle_rad (inner radius r_inner) turns the sheet up, flat2
    runs along the bend for len2.  Width along y.  The BEND SEGMENT is a
    revolve of flat1's end cross-section about the bend axis; flat2 is
    placed at the end of the bend.  Developed length is preserved by
    construction (flat lengths are the flat portions)."""
    o = K._occ()
    # flat1: x in [0, len1], z in [0, t]
    f1 = K.make_box(len1, width, t)
    # bend: revolve the end cross-section (face at x=len1) about the Y axis
    # through (len1, 0, r_inner) so the inner arc stays tangent to z=0
    faces = K.explore(f1, "face")
    end = None
    for f in faces:
        n, c = K.face_normal_center(f)
        if abs(abs(c[0]) - len1) < 1e-9 and abs(n[0]) > 0.9:
            end = f
            break
    if end is None:  # fallback: pick the face whose centre is at max x
        end = max(faces, key=lambda f: K.face_normal_center(f)[1][0])
    ax = o["gp"].gp_Ax1(o["gp"].gp_Pnt(len1, 0, t + r_inner),
                        o["gp"].gp_Dir(0, -1, 0))
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    rev = BRepPrimAPI_MakeRevol(end, ax, angle_rad).Shape()
    bent = K.fuse(f1, rev)
    # flat2: rotated plate attached at the bend end
    # end cross-section of the revolve at angle_rad:
    #   centre of outer arc at (len1 + r_inner*sin(a), r_inner + r_inner*(1-cos a))?
    # simpler: place flat2 by transforming a box with the same rotation as
    # the revolve end: rotation about the bend axis by angle_rad maps the
    # start cross-section plane onto the end plane.
    tr = o["gp"].gp_Trsf()
    tr.SetRotation(o["gp"].gp_Ax1(o["gp"].gp_Pnt(len1, 0, t + r_inner),
                                  o["gp"].gp_Dir(0, -1, 0)), angle_rad)
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    flat2 = K.make_box(len2, width, t)
    # flat2 is placed PAST the bend end (x in [len1, len1+len2]); after the
    # revolve rotation it lands as the vertical leg rising from the arc end
    pre = K.translate(flat2, (len1, 0, 0))
    flat2r = BRepBuilderAPI_Transform(pre, tr, True).Shape()
    out = K.fuse(bent, flat2r)
    return out


# ----------------------------------------------------------------------
# bend detection + unfold
# ----------------------------------------------------------------------
def detect_bends(solid, min_angle_deg: float = 5.0) -> List[dict]:
    """Find cylindrical bend faces in a prismatic sheet part.

    Coaxial cylinder pairs (inner/outer) collapse to one bend with
    r_inner = min radius.  Per bend: sweep angle from the two adjacent
    planar faces' normals; flat lengths from each face's extent along
    (axis x normal).
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    faces = K.explore(solid, "face")
    cyls, planes = [], []
    for f in faces:
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() == GeomAbs_Cylinder:
            cy = ad.Cylinder()
            loc = cy.Location()
            d = cy.Axis().Direction()
            cyls.append((f, cy.Radius(), (loc.X(), loc.Y(), loc.Z()),
                         _unit((d.X(), d.Y(), d.Z()))))
        else:
            n, c = K.face_normal_center(f)
            planes.append((f, n, c))

    def coax(a, b):
        return (M_dist_point_line(a[2], a[3], b[2]) < 1e-9
                and abs(abs(_dot(a[3], b[3])) - 1.0) < 1e-9)

    def M_dist_point_line(p, u, q):
        w = _sub(p, q)
        return _norm(_cross(u, w))

    used = [False] * len(cyls)
    bends = []
    for i, (f, r, org, ax) in enumerate(cyls):
        if used[i]:
            continue
        grp = [i]
        for j in range(i + 1, len(cyls)):
            if not used[j] and coax(cyls[i], cyls[j]):
                grp.append(j)
                used[j] = True
        used[i] = True
        r_inner = min(cyls[g][1] for g in grp)
        # edge -> adjacent planar faces map (TShape identity)
        edge_faces = {}
        for pf, pn, pc in planes:
            for e in K.explore(pf, "edge"):
                edge_faces.setdefault(e.TShape(), []).append((pf, pn))
        adj = []
        for g in grp:
            for e in K.explore(cyls[g][0], "edge"):
                for pf, pn in edge_faces.get(e.TShape(), []):
                    adj.append((pf, pn))
        # keep planar faces whose normal is perpendicular to the axis
        # (side walls have normal || axis)
        adj = [(pf, pn) for pf, pn in adj if abs(_dot(pn, ax)) < 0.5]
        # unique by normal, prefer the LARGEST face per normal direction
        import scdm.additive as A
        uniq = []
        for pf, pn in adj:
            hit = next((u for u in uniq if abs(_dot(pn, u[1])) > 0.999), None)
            if hit is None:
                uniq.append([pf, pn, K.area(pf)])
            elif K.area(pf) > hit[2]:
                hit[0], hit[2] = pf, K.area(pf)
        if len(uniq) < 2:
            continue
        n1, n2 = uniq[0][1], uniq[1][1]
        ang = math.acos(max(-1.0, min(1.0, _dot(n1, n2))))
        if ang < math.radians(min_angle_deg):
            continue
        axd = ax
        def flat_len(pf, pn):
            import scdm.additive as A
            (a0, b0, c0), (a1, b1, c1) = A.shape_bbox(pf)
            ext = (a1 - a0, b1 - b0, c1 - c0)
            perp = _unit(_cross(axd, pn))
            # extent along `perp` = projected bbox diagonal is an
            # overestimate; use the bbox extents' projection of the dominant
            # axes — for axis-aligned prisms the perp is axis-aligned
            comps = [abs(perp[0]), abs(perp[1]), abs(perp[2])]
            k = comps.index(max(comps))
            return ext[k]
        l1 = flat_len(uniq[0][0], n1)
        l2 = flat_len(uniq[1][0], n2)
        # thickness: r_outer - r_inner if the pair exists, else from flats
        rs = sorted(cyls[g][1] for g in grp)
        t = (rs[-1] - rs[0]) if len(rs) > 1 else None
        if t is None or t < 1e-9:
            t = min(_face_thick(pf) for pf, _ in uniq)
        # width: shared extent along the axis
        import scdm.additive as A
        (a0, b0, c0), (a1, b1, c1) = A.shape_bbox(solid)
        ext = (a1 - a0, b1 - b0, c1 - c0)
        comps = [abs(axd[0]), abs(axd[1]), abs(axd[2])]
        w = ext[comps.index(max(comps))]
        bends.append({"r_inner": r_inner, "angle_rad": ang,
                      "flat1_len": l1, "flat2_len": l2, "t": t, "width": w})
    return bends


def _unit(a):
    n = math.sqrt(sum(x * x for x in a))
    if n < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _face_thick(face):
    import scdm.additive as A
    (a0, b0, c0), (a1, b1, c1) = A.shape_bbox(face)
    return min(a1 - a0, b1 - b0, c1 - c0)


def unfold(solid, k: float = 0.42) -> "object":
    """Unfold a single-bend prismatic sheet to a flat strip, preserving the
    developed length (flat1 + BA + flat2)."""
    bends = detect_bends(solid)
    if not bends:
        raise K.KernelError("展开：未找到折弯（圆柱面）")
    b = bends[0]
    ba = bend_allowance(b["angle_rad"], b["r_inner"], k, b["t"])
    total = b["flat1_len"] + ba + b["flat2_len"]
    # strip occupies positive quadrant: length x, width y, thickness z
    return K.make_box(total, b["width"], b["t"])


# ----------------------------------------------------------------------
# rip / corner relief / jog
# ----------------------------------------------------------------------
def rip(solid, face, gap: float = 0.0) -> "object":
    """Cut a slit through the sheet along the LONGEST edge of `face`,
    freeing the corner.  Axis-aligned: the slit runs along the edge's
    dominant direction, cross-section gap x (bbox diag)."""
    import scdm.additive as A
    edges = K.explore(face, "edge")

    def elen(e):
        pts = K.edge_polyline(e, deflection=0.0005)
        if len(pts) < 2:
            return 0.0
        p1, p2 = pts[0], pts[-1]
        return ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2
                + (p2[2] - p1[2]) ** 2) ** 0.5

    e = max(edges, key=elen)
    pts = K.edge_polyline(e, deflection=0.0005)
    p1, p2 = pts[0], pts[-1]
    d = (abs(p2[0] - p1[0]), abs(p2[1] - p1[1]), abs(p2[2] - p1[2]))
    axis = d.index(max(d))
    L = max(d)
    if L < 1e-12:
        raise K.KernelError("rip：边长为零")
    n, _c = K.face_normal_center(face)
    t_min = min(A.shape_bbox(solid)[1][i] - A.shape_bbox(solid)[0][i]
                for i in range(3))
    c = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2)
    # slit frame: edge direction u, face normal n, in-plane perp v = u x n
    u = [0.0, 0.0, 0.0]
    u[axis] = 1.0
    v = [u[1] * n[2] - u[2] * n[1], u[2] * n[0] - u[0] * n[2],
         u[0] * n[1] - u[1] * n[0]]
    vl = math.sqrt(sum(x * x for x in v)) or 1.0
    v = [x / vl for x in v]
    if gap <= 0:
        gap = 1e-5
    ext = [L + 4 * t_min, 2 * t_min, gap]      # along u, along n, along v
    dirs = [u, n, v]
    dims = [0.0, 0.0, 0.0]
    origin = [0.0, 0.0, 0.0]
    for i in range(3):
        dom = max(range(3), key=lambda k: abs(dirs[i][k]))
        dims[dom] = ext[i]
        origin[dom] = c[dom] - ext[i] / 2
    slit = K.make_box(*dims, origin=tuple(origin))
    return K.cut(solid, slit)


def corner_relief(solid, corner: Vec3, size: float,
                  round_: bool = False) -> "object":
    """Cut a corner relief (round hole or square slot) at `corner`.

    The relief centre is clamped inside the solid's bbox so it always
    intersects the material near the corner."""
    import scdm.additive as A
    (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(solid)

    def snap(v, lo, hi):
        """Snap the relief centre a quarter-size inside the nearest bbox
        face — booleans with cut tools straddling a face are unreliable."""
        inset = size * 0.25
        if v >= hi - 1e-9:
            return hi - inset
        if v <= lo + 1e-9:
            return lo + inset
        return min(max(v, lo + inset), hi - inset)

    cx = snap(corner[0], x0, x1)
    cy = snap(corner[1], y0, y1)
    cz = snap(corner[2], z0, z1)
    h = min(size * 4, (z1 - z0) + size * 2)
    oz = min(max(cz - h / 2, z0 - size), z1)
    if round_:
        cyl = K.make_cylinder(size / 2, h, origin=(cx - size / 2,
                                                   cy - size / 2, oz))
        return K.cut(solid, cyl)
    cutbox = K.make_box(size, size, h, origin=(cx - size / 2, cy - size / 2,
                                               oz))
    return K.cut(solid, cutbox)


def jog(width: float, t: float, len1: float, web_h: float, len2: float,
        r_inner: float = 0.0) -> "object":
    """Z-jog (square corners): flat1 (z 0..t), vertical web, flat2 at
    z = web_h..web_h+t.  Sharp-corner construction; bend radii refine it
    later via fillet on the two inner corner edges."""
    f1 = K.make_box(len1, width, t)
    web = K.make_box(t, width, web_h, origin=(len1, 0, 0))
    f2 = K.make_box(len2, width, t,
                    origin=(len1 + t, 0, web_h))
    return K.fuse(K.fuse(f1, web), f2)

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
def hem(width: float, t: float, len1: float, hem_len: float,
        r_inner: Optional[float] = None, closed: bool = False) -> "object":
    """卷边: flat + 180-degree roll-back flange.

    closed=False (P6): open hem with inner radius r (default t/2); the return
    flange sits 2r above the flat and the bend volume is exact by Pappus:
    theta * (r + t/2) * t * width.
    closed=True (P18): crushed/closed hem - flat + fold + return plate lying
    directly on the flat, so the volume is exactly
    width * t * (len1 + hem_len) + 2 * width * t^2.
    """
    if closed:
        f1 = K.make_box(len1, width, t)
        fold = K.make_box(t, width, 2.0 * t, origin=(len1, 0.0, 0.0))
        # the return plate ends where the fold begins, so the three boxes are
        # disjoint and the union volume is exactly w*t*(len1+hem_len) + 2*w*t^2
        back = K.make_box(hem_len, width, t,
                          origin=(len1 - hem_len, 0.0, t))
        return K.fuse(K.fuse(f1, fold), back)
    r = (t / 2.0) if r_inner is None else float(r_inner)
    return bend_from_flat(width, t, len1, hem_len, math.pi, r, 0.42)


BEND_TABLES = {
    # material -> (K factor, inner-radius factor / thickness)
    "steel": (0.42, 1.0),
    "aluminum": (0.44, 1.0),
    "stainless": (0.40, 0.8),
    "copper": (0.45, 1.0),
}


def bend_table_entry(material: str, thickness_mm: float):
    """P26: (K, inner radius in mm) for a material/thickness from the table."""
    key = (material or "steel").strip().lower()
    entry = BEND_TABLES.get(key)
    if entry is None:
        raise ValueError("未知材料 %s（可选：%s）"
                         % (material, ", ".join(sorted(BEND_TABLES))))
    k, rf = entry
    return k, rf * float(thickness_mm)


def flat_pattern(solid, k: float = 0.42, bend_lines: bool = True):
    """P18/P26: developed outline of a bent sheet (+ bend-line positions).

    Returns {"length", "width", "outline", "bend_lines": [{"x", "radius",
    "angle_deg"}]}, x measured from the blank start along the developed length.
    """
    import scdm.additive as _A
    flat = unfold(solid, k=k)
    (x0, y0, _z0), (x1, y1, _z1) = _A.shape_bbox(flat)
    out = {"length": x1 - x0, "width": y1 - y0,
           "outline": [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
           "bend_lines": []}
    if bend_lines:
        try:
            bends = detect_bends(solid)
        except Exception:
            bends = []
        x = 0.0
        for b in bends:
            ba = bend_allowance(b["angle_rad"], b["r_inner"], k, b["t"])
            out["bend_lines"].append({
                "x": x + b["flat1_len"] + ba / 2.0,
                "radius": b["r_inner"],
                "angle_deg": math.degrees(b["angle_rad"]),
            })
            x += b["flat1_len"] + ba + b["flat2_len"]
    return out


def flat_pattern_dxf(solid, path: str, k: float = 0.42,
                     material: Optional[str] = None) -> str:
    """P18/P26: DXF of the blank with bend lines (layer BEND) + angle labels."""
    from scdm import drawing as D
    if material is not None:
        k, _r = bend_table_entry(material, 1.0)
    pat = flat_pattern(solid, k)
    outline = pat["outline"]
    y_lo, y_hi = outline[0][1], outline[2][1]
    extra = []
    for bl in pat["bend_lines"]:
        extra.append(((bl["x"], y_lo), (bl["x"], y_hi), "BEND",
                      "%.0f deg R%.2f" % (bl["angle_deg"], bl["radius"] * 1000.0)))
    return D.write_dxf([("展开", [outline])], path, dimensions=True,
                       extra_lines=extra)



def hem_flange_offset(t: float, r_inner: Optional[float] = None) -> float:
    """Z offset of the return flange above the flat (for verification)."""
    r = (t / 2.0) if r_inner is None else float(r_inner)
    return 2.0 * r


def bead_groove(solid, face, radius: float, length: Optional[float] = None,
                centre: Optional[Vec3] = None,
                along: Optional[Vec3] = None) -> "object":
    """P6 加强筋: half-round groove along a planar face.

    The cutter is a cylinder whose AXIS LIES IN the face plane, so exactly
    half of it is inside the material: removed = 0.5 * pi * r^2 * span,
    where span is the face extent along the chosen in-plane direction.
    """
    n, c = K.face_normal_center(face)
    n = tuple(float(v) for v in n)
    base = tuple(float(v) for v in (centre if centre is not None else c))
    if along is None:
        lo, hi = K._vertex_bbox(face)
        for i in sorted(range(3), key=lambda k: hi[k] - lo[k], reverse=True):
            v = [0.0, 0.0, 0.0]
            v[i] = 1.0
            if abs(sum(v[k] * n[k] for k in range(3))) < 0.9:
                along = tuple(v)
                span = hi[i] - lo[i]
                break
    else:
        along = tuple(float(v) for v in along)
        proj = [sum(K.vertex_point(x)[k] * along[k] for k in range(3))
                for x in K.explore(face, "vertex")]
        span = max(proj) - min(proj)
    if along is None:
        raise K.KernelError("加强筋：无法确定面内方向")
    L = (float(length) if length is not None else span) + 2e-6
    start = tuple(base[i] - along[i] * L / 2.0 for i in range(3))
    cutter = K.make_cylinder(float(radius), L, origin=start, axis=along)
    return K.cut(solid, cutter)


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
                edge_faces.setdefault(e.TShape(), []).append((pf, pn, pc))
        adj = []
        for g in grp:
            for e in K.explore(cyls[g][0], "edge"):
                for pf, pn, pc in edge_faces.get(e.TShape(), []):
                    adj.append((pf, pn, pc))
        # keep planar faces whose normal is perpendicular to the axis
        # (side walls have normal || axis)
        adj = [(pf, pn, pc) for pf, pn, pc in adj if abs(_dot(pn, ax)) < 0.5]
        # R50/P277: a bend's flats are TANGENT to the cylinder, so at least one
        # of their planes sits ~one radius away from the bend axis.  A knockout
        # contributes two coaxial cylinders (hole wall + slug wall) whose only
        # perpendicular neighbours are the RADIAL web planes, i.e. planes that
        # contain the axis (offset ~0).  Without this test the slug wall faked a
        # second "bend" and flat_pattern silently returned a wrong developed
        # length (rule 60: downstream must not merely "not raise").  The test is
        # group-level - it only drops a candidate when EVERY adjacent plane is
        # radial, so a rolled strip whose free end is a radial cut stays a bend.
        org = cyls[i][2]
        rad = min(cyls[g][1] for g in grp)
        offs = [abs(_dot(pn, _sub(org, pc))) for _pf, pn, pc in adj]
        if not offs or max(offs) <= 0.5 * rad:
            continue
        # unique by normal, prefer the LARGEST face per normal direction
        import scdm.additive as A
        uniq = []
        for pf, pn, _pc in adj:
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
            # P315: project the face's own vertices onto perp.  The old bbox
            # shortcut only held for axis-aligned prisms ("for axis-aligned
            # prisms the perp is axis-aligned"); with a slanted flange (an
            # axial bend below 90 degrees) it measured the wrong flat and the
            # developed length was off by ~5%.
            perp = _unit(_cross(axd, pn))
            pts = [K.vertex_point(v) for v in K.explore(pf, "vertex")]
            if not pts:
                return 0.0
            vals = [sum(p[i] * perp[i] for i in range(3)) for p in pts]
            return max(vals) - min(vals)
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
                      "flat1_len": l1, "flat2_len": l2, "t": t, "width": w,
                      "f1": uniq[0][0], "f2": uniq[1][0]})
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
    """Unfold a prismatic sheet to a flat strip, preserving the developed
    length (TODO-2: multi-bend chains).

    Single bend: flat1 + BA + flat2.  Multi-bend: bends are ordered along
    the chain via shared planar-face handles (a Z/U profile); intermediate
    flats are counted once, end flats once:

        total = flat(start) + Σ BA_i + Σ flat(intermediate) + flat(end)

    The result is a strip (length x width x t), same shape class as the
    single-bend path.
    """
    bends = detect_bends(solid)
    if not bends:
        raise K.KernelError("展开：未找到折弯（圆柱面）")
    if len(bends) == 1:
        b = bends[0]
        ba = bend_allowance(b["angle_rad"], b["r_inner"], k, b["t"])
        total = b["flat1_len"] + ba + b["flat2_len"]
        return K.make_box(total, b["width"], b["t"])
    order = _chain_order(bends)
    total = 0.0
    prev_sig = None
    for idx in order:
        b = bends[idx]
        ba = bend_allowance(b["angle_rad"], b["r_inner"], k, b["t"])
        total += ba
        s1, s2 = _flat_sig(b, 0), _flat_sig(b, 1)
        # entry side = the flat not shared with the previous bend; the
        # two faces of one flat share the midplane up to thickness t;
        # prev_sig tracks the EXIT side (the flat facing the next bend)
        if prev_sig is not None and _same_flat(s1, prev_sig, b["t"]):
            total += b["flat2_len"]   # entry = f2 -> exit = f1
            prev_sig = s1
        else:
            total += b["flat1_len"]   # entry = f1 -> exit = f2
            prev_sig = s2
    # trailing flat: the last bend's exit side
    last = bends[order[-1]]
    ls1, ls2 = _flat_sig(last, 0), _flat_sig(last, 1)
    total += last["flat2_len"] if _same_flat(ls2, prev_sig, last["t"])         else last["flat1_len"]
    return K.make_box(total, bends[0]["width"], bends[0]["t"])


def _flat_sig(b, side):
    """Plane signature (unit normal, offset) of bend side face 0|1."""
    f = b["f1"] if side == 0 else b["f2"]
    n, c = K.face_normal_center(f)
    return (tuple(round(float(x), 9) for x in n),
            round(float(_dot(n, c)), 9))


def _same_flat(sig_a, sig_b, t):
    """Two faces belong to the same sheet flat when their planes are
    parallel and their offsets differ by ~thickness (the two sides of
    one plate)."""
    na, da = sig_a
    nb, db = sig_b
    if abs(_dot(na, nb)) < 0.999:
        return False
    return abs(abs(da) - abs(db)) <= 2.0 * t + 1e-9


def _chain_order(bends):
    """Order bend indices along the part chain by shared sheet flats.

    Ends (unshared flats) anchor the walk; disconnected bends (e.g. a
    branch) are appended in detection order so nothing is dropped.
    """
    n = len(bends)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            ti = 0.5 * (bends[i]["t"] + bends[j]["t"])
            if any(_same_flat(_flat_sig(bends[i], a),
                              _flat_sig(bends[j], b_), ti)
                   for a in (0, 1) for b_ in (0, 1)):
                adj[i].append(j)
                adj[j].append(i)
    used = [False] * n
    order = []

    def walk(i):
        used[i] = True
        order.append(i)
        for j in adj[i]:
            if not used[j]:
                walk(j)

    # start from chain ends (degree 1) when present
    for i in range(n):
        if len(adj[i]) <= 1 and not used[i]:
            walk(i)
    for i in range(n):
        if not used[i]:
            walk(i)
    return order


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


def bend_relief(solid, width: float, depth: float,
                end: int = 0, round_: bool = False) -> "object":
    """TODO-3: bend relief — a slot cut at the END of a bend line so the
    flange does not tear when the flat is folded.

    Reuses the corner_relief mechanism (bbox-clamped boolean cut).  The
    slot spans the bend line perpendicular to it: `width` along the bend
    tangent direction (the bend extends past both tangent lines), and
    `depth` along the bend axis beyond the cylinder end (`end` 0 = axis
    min end, 1 = axis max end).  Every detected bend gets a slot.
    """
    import scdm.additive as A
    (x0, y0, z0), (x1, y1, z1) = A.shape_bbox(solid)
    out = solid
    for b in detect_bends(solid):
        f = b["f1"]
        n, _c = K.face_normal_center(f)
        # standard fixture orientation: flats normal +-z, bend axis along
        # y; the bend LINE sits at the entry flat's far edge along x
        (fa0, fb0, fc0), (fa1, fb1, fc1) = A.shape_bbox(f)
        line_x = fa1 if fa1 > x0 + (x1 - x0) * 0.5 else fa0
        axis_pos = y0 if end == 0 else y1
        # slot straddles the bend-line END: centred on (line_x, axis_pos)
        if round_:
            # make_cylinder origin IS the axis centre; the slot straddles
            # the bend-line end (axis_pos) by radius on each side
            cut = K.make_cylinder(width / 2, depth * 2,
                                  origin=(line_x, axis_pos, z0 - depth))
            out = K.cut(out, cut)
            continue
        cutbox = K.make_box(width, depth, (z1 - z0) + 2 * depth,
                            origin=(line_x - width / 2,
                                    axis_pos - depth / 2, z0 - depth))
        out = K.cut(out, cutbox)
    return out


def conical_bend(angle_rad: float, t: float, height: float, r1: float, r2: float,
                 origin: Vec3 = (0.0, 0.0, 0.0), k: float = 0.42):
    """P311: 圆锥折弯——内外表面都是锥面的弯板段（母线为斜线的旋转面）。

    Builds the solid by revolving a TRAPEZOID about the cone axis: the section
    spans radius r1..r1+t at z=0 and r2..r2+t at z=height, so the inner and
    outer surfaces are cones.  Revolving a rectangle instead would give the
    ordinary cylindrical bend, which is why a cone must never be reported as a
    cylindrical bend (detect_bends filters cylinders only, on purpose).

    Closed forms (Pappus centroid theorem - the axis never meets the section):
        volume   = angle_rad * ((r1 + r2)/2 + t/2) * t * height
        BA       = angle_rad * ((r1 + r2)/2 + k * t)      (developed length)
    """
    ang = float(angle_rad)
    t = float(t)
    h = float(height)
    r1 = float(r1)
    r2 = float(r2)
    if t <= 0 or h <= 0:
        raise K.KernelError("圆锥折弯：板厚与高度必须为正")
    if r1 <= 0 or r2 <= 0:
        raise K.KernelError("圆锥折弯：半径必须为正（转轴不能穿过截面）")
    if abs(r2 - r1) < 1e-12:
        raise K.KernelError("圆锥折弯：两端半径相同即圆柱折弯，请用 bend_from_flat")
    if not (0.0 < ang <= 2.0 * math.pi + 1e-12):
        raise K.KernelError("圆锥折弯：角度必须在 (0, 2π] 内")
    ox, oy, oz = (float(v) for v in origin)
    pts = [(ox + r1, oy, oz), (ox + r1 + t, oy, oz),
           (ox + r2 + t, oy, oz + h), (ox + r2, oy, oz + h)]
    face = K.face_from_polygon(pts)
    return K.revolve(face, (ox, oy, oz), (0.0, 0.0, 1.0), ang)


def conical_bend_allowance(angle_rad: float, r1: float, r2: float, k: float,
                           t: float) -> float:
    """P311: 圆锥折弯的中性层展开长（在中间母线上用 K 因子）。"""
    return abs(float(angle_rad)) * ((float(r1) + float(r2)) / 2.0
                                    + float(k) * float(t))


def axial_bend(length: float, width: float, t: float, flange: float,
               angle_rad: float, r_inner: float = 0.0, k: float = 0.42):
    """P311: 轴向折弯——折弯轴平行于板料走向的 U 型槽（底板 + 两条立边）。

    The bend axes run along x (the strip direction), so this is the bend of a
    sheet edge rather than across the sheet: base plate plus two flanges.

    Closed forms:  base = length*width*t,
                   each flange = angle_rad * (r + t/2) * t * length (Pappus),
                   developed length = width + 2 * (flange + BA),
                   BA = angle_rad * (r + k * t).
    """
    L = float(length)
    w = float(width)
    t = float(t)
    fl = float(flange)
    ang = float(angle_rad)
    r = float(r_inner)
    if min(L, w, t, fl) <= 0:
        raise K.KernelError("轴向折弯：长度/宽度/板厚/立边必须为正")
    if r < 0:
        raise K.KernelError("轴向折弯：内半径不能为负")
    # past 90 degrees the flange folds back over the base and the Pappus sum
    # would double count the overlap, so the closed form stops at a right angle
    if not (0.0 < ang <= math.pi / 2.0 + 1e-12):
        raise K.KernelError("轴向折弯：折弯角度必须在 (0, 90°] 内（更大的角会折回底板）")
    if not (0.0 <= float(k) <= 1.0):
        raise K.KernelError("轴向折弯：K 因子必须在 [0, 1] 内")
    base = K.make_box(L, w, t)
    out = base
    big = 10.0 * (r + t + L + w + fl)
    r_mid = r + t / 2.0
    # a U-channel's flanges rise OUTSIDE the base footprint: the y=0 edge bends
    # toward -y, the y=w edge toward +y (R58: the inside quadrants put the
    # flanges in the base and the fuse swallowed half of them)
    for (y_edge, outward) in ((0.0, -1.0), (w, 1.0)):
        ay, az = y_edge, t + r
        alpha0 = -math.pi / 2.0                 # sweep start (points -z)
        alpha1 = (alpha0 - ang) if outward < 0 else (alpha0 + ang)
        # tangent at the sweep end = the sheet direction leaving the bend
        if outward < 0:
            d = (math.sin(alpha1), -math.cos(alpha1))
        else:
            d = (-math.sin(alpha1), math.cos(alpha1))
        nrm = (math.cos(alpha1), math.sin(alpha1))   # sheet normal at the exit
        # 1) bend sector: the ring clipped by the start half-space and by the
        #    end plane.  Sweeping the edge face with MakeRevol looks simpler but
        #    the swept FACE does not fuse cleanly (R58 measured half a flange
        #    lost), so the sector is exact cylinders intersected with boxes.
        ring = K.cut(K.make_cylinder(r + t, L, origin=(0.0, ay, az),
                                     axis=(1.0, 0.0, 0.0)),
                     K.make_cylinder(r, L, origin=(0.0, ay, az),
                                     axis=(1.0, 0.0, 0.0)))
        oy = (ay - big) if outward < 0 else ay
        start = K.make_box(big, big, big, origin=(-big / 2.0, oy, az - big))
        beta = math.atan2(-d[1], -d[0])         # local +y  ->  -d
        # the end box must have its local y=0 plane THROUGH the bend axis
        # (origin at (ay, az)): built at world y=0 it would be tangent to the
        # ring for the y=w flange and cut the sector wrongly
        end = K.make_box(big, big, big,
                         origin=(-big / 2.0, ay, az - big / 2.0))
        end = K.rotate(end, (0.0, ay, az), (1.0, 0.0, 0.0), beta)
        out = K.fuse(out, K.common(K.common(ring, start), end))
        # 2) the STRAIGHT flange past the bend, following the exit tangent.
        #    R58 shipped without it: the parameter never reached the geometry,
        #    so the closed form and the solid disagreed AND the flange had no
        #    tangent flat - which is why the bend detector could not pair it
        #    (uniq < 2).  With it, the flange's outer face is genuinely tangent
        #    to the bend cylinder and detect_bends/unfold read the U-channel.
        cy = ay + r_mid * nrm[0]
        cz = az + r_mid * nrm[1]
        pts = []
        for (sn, sd) in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
            pts.append((0.0,
                        cy + nrm[0] * sn * t / 2.0 + d[0] * sd * fl,
                        cz + nrm[1] * sn * t / 2.0 + d[1] * sd * fl))
        out = K.fuse(out, K.prism(K.face_from_polygon(pts), (L, 0.0, 0.0)))
    return out


def axial_bend_allowance(angle_rad: float, r_inner: float, k: float,
                         t: float) -> float:
    """P311: 轴向折弯的单边折弯余量 BA = θ·(r + Kt)（与圆柱折弯同式）。"""
    return bend_allowance(angle_rad, r_inner, k, t)


def detect_conical(solid) -> List[dict]:
    """P311: 圆锥面识别——返回 [{r_at_start, r_at_end, semi_angle_rad, height}]。

    Cones are kept SEPARATE from detect_bends (cylinders only): reporting a
    conical bend as a cylindrical one would let unfold/flat_pattern silently
    use the wrong developed length (the rule 60/67 failure mode).
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone
    out: List[dict] = []
    for f in K.explore(solid, "face"):
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Cone:
            continue
        cone = ad.Cone()
        ax = cone.Axis()
        loc = ax.Location()
        d = ax.Direction()
        semi = float(cone.SemiAngle())
        v0, v1 = ad.FirstVParameter(), ad.LastVParameter()
        u0 = 0.5 * (ad.FirstUParameter() + ad.LastUParameter())

        def _radius(v):
            """Distance from the sample point to the cone axis (parametrisation
            independent - the raw v parameter is not an axial distance)."""
            p = ad.Value(u0, v)
            w = (p.X() - loc.X(), p.Y() - loc.Y(), p.Z() - loc.Z())
            cr = (d.Y() * w[2] - d.Z() * w[1], d.Z() * w[0] - d.X() * w[2],
                  d.X() * w[1] - d.Y() * w[0])
            return math.sqrt(sum(c * c for c in cr))

        p0, p1 = ad.Value(u0, v0), ad.Value(u0, v1)
        axial = abs((p1.X() - p0.X()) * d.X() + (p1.Y() - p0.Y()) * d.Y()
                    + (p1.Z() - p0.Z()) * d.Z())
        out.append({"r_at_start": _radius(v0),
                    "r_at_end": _radius(v1),
                    "semi_angle_rad": semi,
                    "height": axial,
                    "axis": (d.X(), d.Y(), d.Z()),
                    "location": (loc.X(), loc.Y(), loc.Z()),
                    "face": f})
    return out


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

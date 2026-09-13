"""P283: 梁/焊件首批 —— 6 种截面轮廓 + 闭式截面特性（面积/惯性矩）。

Kernel units are metres (the op/GUI layers divide mm by 1000, as everywhere).

Every section is exact geometry - planar polygons for the rolled shapes and
exact cylinders for the round ones - so `closed_form` can be asserted at
machine precision instead of a modelling tolerance.  Sections live in the XY
plane and extrude along the given axis; `center=True` (the default) puts the
section centroid on the origin, which is what "place a beam on a sketch or an
edge" wants.

Profile parameters (all lengths):
    flat  b, h           rectangle
    rod   d              solid round bar (centred on the origin)
    pipe  d, t           round tube: outer diameter, wall thickness
    i     h, b, tw, tf   I-beam: height, flange width, web, flange thickness
    t     h, b, tw, tf   T-beam, flange on top, web foot at y=0
    l     a, b, t        unequal-leg angle: vertical leg a, horizontal leg b,
                         corner at the origin

Closed form (centroidal; `ix` = second moment about the section x axis,
`iy` about y, `j` = ix + iy):
    flat  A = b*h,               ix = b*h**3/12,      iy = h*b**3/12
    rod   A = pi*r**2,           ix = iy = pi*r**4/4
    pipe  A = pi*(ro**2-ri**2),  ix = iy = pi*(ro**4-ri**4)/4
    i     A = 2*b*tf + (h-2*tf)*tw
          ix = (b*h**3 - (b-tw)*(h-2*tf)**3)/12
          iy = (2*tf*b**3 + (h-2*tf)*tw**3)/12
    t     A = b*tf + (h-tf)*tw,  centroid + parallel-axis theorem
    l     A = t*(a + b - t),     centroid + parallel-axis theorem
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from scdm import kernel as K

Vec3 = Tuple[float, float, float]

PROFILES = ("flat", "rod", "pipe", "i", "t", "l")

LABELS = {
    "flat": "扁钢",
    "rod": "圆钢",
    "pipe": "圆管",
    "i": "工字钢",
    "t": "T 型钢",
    "l": "角钢",
}

PARAMS = {
    "flat": ("b", "h"),
    "rod": ("d",),
    "pipe": ("d", "t"),
    "i": ("h", "b", "tw", "tf"),
    "t": ("h", "b", "tw", "tf"),
    "l": ("a", "b", "t"),
}

# GUI/op defaults in mm (the op layer divides by 1000)
DEFAULTS = {
    "flat": {"b": 40.0, "h": 10.0},
    "rod": {"d": 20.0},
    "pipe": {"d": 60.0, "t": 3.0},
    "i": {"h": 100.0, "b": 50.0, "tw": 5.0, "tf": 7.0},
    "t": {"h": 100.0, "b": 100.0, "tw": 6.0, "tf": 8.0},
    "l": {"a": 50.0, "b": 50.0, "t": 5.0},
}


def _validate(profile, dims) -> Tuple[str, Dict[str, float]]:
    """Coerce + bound-check the profile parameters (raises K.KernelError)."""
    key = str(profile).lower()
    if key not in PROFILES:
        raise K.KernelError("未知梁截面：%s（可选 %s）"
                            % (profile, "/".join(PROFILES)))
    out: Dict[str, float] = {}
    for name in PARAMS[key]:
        if dims.get(name) is None:
            raise K.KernelError("梁截面 %s 缺少参数 %s" % (key, name))
        try:
            value = float(dims[name])
        except (TypeError, ValueError):
            raise K.KernelError("梁截面 %s 的参数 %s 不是数字" % (key, name))
        if value <= 0:
            raise K.KernelError("梁截面 %s 的参数 %s 必须为正" % (key, name))
        out[name] = value
    # a profile that degenerates (zero web, wall thicker than the radius) is a
    # modelling error, not a beam: refuse it instead of building a sliver
    if key == "pipe" and 2.0 * out["t"] >= out["d"]:
        raise K.KernelError("圆管壁厚必须小于半径（2×t < d）")
    if key in ("i", "t"):
        if out["tf"] >= out["h"]:
            raise K.KernelError("翼缘厚度必须小于截面高度")
        if key == "i" and 2.0 * out["tf"] >= out["h"]:
            raise K.KernelError("工字钢上下翼缘会相接：2×tf 必须小于高度")
        if out["tw"] >= out["b"]:
            raise K.KernelError("腹板厚度必须小于翼缘宽度")
    if key == "l" and out["t"] >= min(out["a"], out["b"]):
        raise K.KernelError("角钢厚度必须小于两肢长度")
    return key, out


def closed_form(profile, **dims) -> Dict[str, float]:
    """Exact area / centroid / centroidal second moments of a section."""
    key, d = _validate(profile, dims)
    if key == "flat":
        b, h = d["b"], d["h"]
        area, cx, cy = b * h, b / 2.0, h / 2.0
        ix, iy = b * h ** 3 / 12.0, h * b ** 3 / 12.0
    elif key == "rod":
        r = d["d"] / 2.0
        area = math.pi * r * r
        cx = cy = 0.0
        ix = iy = math.pi * r ** 4 / 4.0
    elif key == "pipe":
        ro = d["d"] / 2.0
        ri = ro - d["t"]
        area = math.pi * (ro * ro - ri * ri)
        cx = cy = 0.0
        ix = iy = math.pi * (ro ** 4 - ri ** 4) / 4.0
    elif key == "i":
        h, b, tw, tf = d["h"], d["b"], d["tw"], d["tf"]
        area = 2.0 * b * tf + (h - 2.0 * tf) * tw
        cx = cy = 0.0
        ix = (b * h ** 3 - (b - tw) * (h - 2.0 * tf) ** 3) / 12.0
        iy = (2.0 * tf * b ** 3 + (h - 2.0 * tf) * tw ** 3) / 12.0
    elif key == "t":
        h, b, tw, tf = d["h"], d["b"], d["tw"], d["tf"]
        a1, y1 = b * tf, h - tf / 2.0            # flange
        a2, y2 = (h - tf) * tw, (h - tf) / 2.0   # web
        area = a1 + a2
        cx, cy = 0.0, (a1 * y1 + a2 * y2) / area
        ix = (b * tf ** 3 / 12.0 + a1 * (y1 - cy) ** 2
              + tw * (h - tf) ** 3 / 12.0 + a2 * (y2 - cy) ** 2)
        iy = tf * b ** 3 / 12.0 + (h - tf) * tw ** 3 / 12.0
    else:  # l
        a, b, t = d["a"], d["b"], d["t"]
        a1, x1, y1 = t * a, t / 2.0, a / 2.0                # vertical leg
        a2, x2, y2 = t * (b - t), (b + t) / 2.0, t / 2.0    # horizontal leg
        area = a1 + a2
        cx = (a1 * x1 + a2 * x2) / area
        cy = (a1 * y1 + a2 * y2) / area
        ix = (t * a ** 3 / 12.0 + a1 * (y1 - cy) ** 2
              + (b - t) * t ** 3 / 12.0 + a2 * (y2 - cy) ** 2)
        iy = (a * t ** 3 / 12.0 + a1 * (x1 - cx) ** 2
              + t * (b - t) ** 3 / 12.0 + a2 * (x2 - cx) ** 2)
    return {"area": area, "cx": cx, "cy": cy, "ix": ix, "iy": iy,
            "j": ix + iy}


def outline(profile, **dims) -> List[Vec3]:
    """Raw section polygon (z = 0) in the profile own coordinates."""
    key, d = _validate(profile, dims)
    if key == "flat":
        b, h = d["b"], d["h"]
        pts = [(0.0, 0.0), (b, 0.0), (b, h), (0.0, h)]
    elif key == "i":
        h, b, tw, tf = d["h"], d["b"], d["tw"], d["tf"]
        H, B, W = h / 2.0, b / 2.0, tw / 2.0
        pts = [(-B, -H), (B, -H), (B, -H + tf), (W, -H + tf),
               (W, H - tf), (B, H - tf), (B, H), (-B, H),
               (-B, H - tf), (-W, H - tf), (-W, -H + tf), (-B, -H + tf)]
    elif key == "t":
        h, b, tw, tf = d["h"], d["b"], d["tw"], d["tf"]
        B, W = b / 2.0, tw / 2.0
        pts = [(-W, 0.0), (W, 0.0), (W, h - tf), (B, h - tf),
               (B, h), (-B, h), (-B, h - tf), (-W, h - tf)]
    elif key == "l":
        a, b, t = d["a"], d["b"], d["t"]
        pts = [(0.0, 0.0), (b, 0.0), (b, t), (t, t), (t, a), (0.0, a)]
    else:
        raise K.KernelError("圆截面（rod/pipe）没有多边形轮廓：请用 section_face")
    return [(float(x), float(y), 0.0) for x, y in pts]


def _unit(a: Sequence[float]) -> Vec3:
    n = math.sqrt(sum(float(v) * float(v) for v in a))
    if n < 1e-12:
        raise K.KernelError("梁轴方向不能为零向量")
    return (float(a[0]) / n, float(a[1]) / n, float(a[2]) / n)


def _frame(axis: Sequence[float]) -> Tuple[Vec3, Vec3, Vec3]:
    """(n, u, v) with u, v spanning the plane normal to n."""
    n = _unit(axis)
    ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    dot = sum(ref[i] * n[i] for i in range(3))
    u = [ref[i] - dot * n[i] for i in range(3)]
    ul = math.sqrt(sum(v * v for v in u)) or 1.0
    u = [v / ul for v in u]
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0])
    return n, (u[0], u[1], u[2]), v


def _circle_wire(radius: float, origin: Vec3, axis: Vec3):
    o = K._occ()
    ax = o["gp"].gp_Ax2(o["gp"].gp_Pnt(*origin), o["gp"].gp_Dir(*axis))
    circ = o["gp"].gp_Circ(ax, float(radius))
    edge = o["bapi"].BRepBuilderAPI_MakeEdge(circ).Edge()
    return o["bapi"].BRepBuilderAPI_MakeWire(edge).Wire()


def section_face(profile, center: bool = True, origin: Vec3 = (0.0, 0.0, 0.0),
                 axis: Vec3 = (0.0, 0.0, 1.0), **dims):
    """Planar section face placed at `origin` normal to `axis`.

    `center=True` moves the section centroid onto the origin (rod/pipe are
    centred by construction).
    """
    key, d = _validate(profile, dims)
    n, u, v = _frame(axis)
    if key in ("rod", "pipe"):
        ro = d["d"] / 2.0
        mk = K._occ()["bapi"].BRepBuilderAPI_MakeFace(
            _circle_wire(ro, origin, n), True)
        if key == "pipe":
            # the hole wire must run OPPOSITE to the outer one, otherwise the
            # face is self-intersecting nonsense (measured 9.5x the ring area)
            mk.Add(_circle_wire(ro - d["t"], origin, n).Reversed())
        return mk.Face()
    cf = closed_form(key, **d)
    dx = cf["cx"] if center else 0.0
    dy = cf["cy"] if center else 0.0
    pts = [tuple(float(origin[i]) + u[i] * (x - dx) + v[i] * (y - dy)
                 for i in range(3)) for x, y, _z in outline(key, **d)]
    return K.face_from_polygon(pts)


def beam(profile, length: float, center: bool = True,
         origin: Vec3 = (0.0, 0.0, 0.0), axis: Vec3 = (0.0, 0.0, 1.0), **dims):
    """Prismatic beam: the section extruded along `axis` for `length`.

    Closed form: volume = area * length (round shapes are exact cylinders, the
    rolled ones exact polygons); the solid moments are the section moments plus
    the prism term (see K.inertia).
    """
    key, d = _validate(profile, dims)
    L = float(length)
    if L <= 0:
        raise K.KernelError("梁长度必须为正")
    n = _unit(axis)
    if key == "rod":
        return K.make_cylinder(d["d"] / 2.0, L, origin=origin, axis=n)
    if key == "pipe":
        ro = d["d"] / 2.0
        ri = ro - d["t"]
        m = 1e-6
        start = tuple(float(origin[i]) - n[i] * m for i in range(3))
        # only the inner cutter overshoots, so the tube keeps its exact length
        outer = K.make_cylinder(ro, L, origin=origin, axis=n)
        inner = K.make_cylinder(ri, L + 2.0 * m, origin=start, axis=n)
        return K.cut(outer, inner)
    face = section_face(key, center=center, origin=origin, axis=n, **d)
    return K.prism(face, tuple(n[i] * L for i in range(3)))


def beam_along(profile, p0: Vec3, p1: Vec3, center: bool = True, **dims):
    """Beam from `p0` to `p1` (the section follows the segment direction)."""
    axis = (float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]),
            float(p1[2]) - float(p0[2]))
    length = math.sqrt(sum(a * a for a in axis))
    if length <= 0:
        raise K.KernelError("梁：起点与终点不能重合")
    return beam(profile, length, center=center, origin=p0, axis=axis, **dims)


def spec_label(profile, **dims) -> str:
    """Human label, e.g. '工字钢 I 100x50x5x7' (dims in the caller units)."""
    key, d = _validate(profile, dims)
    if key == "flat":
        return "扁钢 %g×%g" % (d["b"], d["h"])
    if key == "rod":
        return "圆钢 Ø%g" % d["d"]
    if key == "pipe":
        return "圆管 Ø%g×%g" % (d["d"], d["t"])
    if key == "i":
        return "工字钢 I %g×%g×%g×%g" % (d["h"], d["b"], d["tw"], d["tf"])
    if key == "t":
        return "T 型钢 %g×%g×%g×%g" % (d["h"], d["b"], d["tw"], d["tf"])
    return "角钢 %g×%g×%g" % (d["a"], d["b"], d["t"])

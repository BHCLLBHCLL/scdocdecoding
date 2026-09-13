"""M4-11: script record/replay (Python JSON journal).

A Recorder captures geometry operations as (id, options) steps and saves them as a
JSON script; a Player replays them against a fresh KernelDoc. The operations mirror
the direct-modeling tools but take (kdoc, options, scale) and are GUI-agnostic, so a
scripted run is fully reproducible and unit-testable.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from scdm import kernel as K


class Recorder:
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.enabled = False

    def start(self) -> None:
        self.steps = []
        self.enabled = True

    def stop(self) -> List[Dict[str, Any]]:
        self.enabled = False
        return list(self.steps)

    def note(self, cmd_id: str, **opts) -> None:
        if self.enabled:
            self.steps.append({"cmd": cmd_id, "opts": opts})

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"format": "scdm-script", "version": 1, "steps": self.steps}, f,
                      ensure_ascii=False, indent=2)


def load_script(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("steps", [])


# --- replay operations --------------------------------------------------------

def _last(kdoc):
    return kdoc.bodies[-1] if kdoc.bodies else None


def _resolve(kdoc, target: str, index: int = 0):
    if target == "last":
        return _last(kdoc)
    if target == "first":
        return kdoc.bodies[0] if kdoc.bodies else None
    if 0 <= index < len(kdoc.bodies):
        return kdoc.bodies[index]
    return None


def op_insert_cyl(kdoc, opts, scale):
    sh = K.make_cylinder(opts.get("r", 5) / scale, opts.get("h", 10) / scale)
    return kdoc.add_body(sh, name="圆柱"), "插入圆柱"


def op_insert_sphere(kdoc, opts, scale):
    sh = K.make_sphere(opts.get("r", 5) / scale)
    return kdoc.add_body(sh, name="球"), "插入球"


def op_pull(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("拉动：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    d = opts.get("distance", 5.0) / scale
    if opts.get("symmetric"):
        body.shape = K.pull_face_symmetric(body.shape, faces[fi], d)
    else:
        body.shape = K.pull_face(body.shape, faces[fi], d)
    return body, f"拉动 {opts.get('distance', 5.0)}mm"


def op_move(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("移动：实体不存在")
    d = opts.get("distance", 10.0) / scale
    ax = tuple(opts.get("axis", (1.0, 0.0, 0.0)))
    vec = (ax[0] * d, ax[1] * d, ax[2] * d)
    if opts.get("copy"):
        kdoc.add_body(K.translate(body.shape, vec), name=body.name + " 副本")
    else:
        body.shape = K.translate(body.shape, vec)
    return body, f"移动 {opts.get('distance', 10.0)}mm"


def op_combine(kdoc, opts, scale):
    a = _resolve(kdoc, "first")
    b = _resolve(kdoc, "last")
    if a is None or b is None or a is b:
        raise ValueError("合并需要两个实体")
    mode = opts.get("mode", "fuse")
    if mode == "cut":
        a.shape = K.cut(a.shape, b.shape)
    elif mode == "common":
        a.shape = K.common(a.shape, b.shape)
    else:
        a.shape = K.fuse(a.shape, b.shape)
    kdoc.remove(b.id)
    return a, f"合并 ({mode})"


def op_split(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("分割：实体不存在")
    origin = tuple(opts.get("origin", (0, 0, 0)))
    normal = tuple(opts.get("normal", (1.0, 0.0, 0.0)))
    parts = K.split_by_plane(body.shape, origin, normal)
    kdoc.remove(body.id)
    for i, sh in enumerate(parts, 1):
        kdoc.add_body(sh, name=f"{body.name} 段{i}")
    return None, "已分割"


def op_blend(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("倒圆：实体不存在")
    body.shape = K.fillet_edges(body.shape, opts.get("radius", 1.0) / scale)
    return body, "已倒圆"


def op_chamfer(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("倒角：实体不存在")
    body.shape = K.chamfer_edges(body.shape, opts.get("distance", 1.0) / scale)
    return body, "已倒角"


def op_mirror(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("镜像：实体不存在")
    mir = K.mirror(body.shape, tuple(opts.get("origin", (0, 0, 0))),
                   tuple(opts.get("normal", (1, 0, 0))))
    return kdoc.add_body(mir, name=body.name + " 镜像"), "已镜像"


def op_pattern(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("阵列：实体不存在")
    step = opts.get("step", 15.0) / scale
    count = opts.get("count", 3)
    mode = opts.get("mode", "linear")
    if mode == "path":
        faces = K.explore(body.shape, "face")
        edges = K.explore(body.shape, "edge")
        copies = K.pattern_path(body.shape, edges[0], count)
        for i, sh in enumerate(copies[1:], 2):
            kdoc.add_body(sh, name=f"{body.name} 路径阵列{i}")
        return body, f"沿路径阵列 ×{count}"
    if mode == "fill":
        ex = opts.get("elem", 10.0) / scale
        gap = opts.get("gap", 2.0) / scale
        rx = opts.get("region", 100.0) / scale
        copies = K.pattern_fill(body.shape, rx, rx, ex, ex, gap=gap)
        for i, sh in enumerate(copies[1:], 2):
            kdoc.add_body(sh, name=f"{body.name} 填充阵列{i}")
        return body, f"填充阵列 ×{len(copies)}"
    shapes = K.pattern_linear(body.shape, (step, 0, 0), count)
    for i, sh in enumerate(shapes[1:], 2):
        kdoc.add_body(sh, name=f"{body.name} 阵列{i}")
    return body, f"线性阵列 ×{count}"


def op_blend_variable(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("变半径圆角：实体不存在")
    edges = K.explore(body.shape, "edge")
    sel = opts.get("edges", [0])
    radii = opts.get("radii", [opts.get("radius", 2.0)])
    spec = [(edges[i], r / scale) for i, r in
            zip(sel, radii * len(sel) if len(radii) < len(sel) else radii)]
    body.shape = K.fillet_variable(body.shape, spec)
    return body, "变半径圆角"


def op_shell_multi(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("多厚度抽壳：实体不存在")
    faces = K.explore(body.shape, "face")
    groups = []
    for g in opts.get("groups", [{"faces": [0], "thickness": 1.0}]):
        gf = [faces[i] for i in g.get("faces", [0]) if i < len(faces)]
        groups.append((gf, g.get("thickness", 1.0) / scale))
    body.shape = K.shell_multi(body.shape, groups)
    return body, "多厚度抽壳"


def op_draft_neutral(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("中性面拔模：实体不存在")
    faces = K.explore(body.shape, "face")
    sel = opts.get("neutral", 2)
    if sel == "planar":
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.GeomAbs import GeomAbs_Plane
        from OCC.Core.TopoDS import topods
        nf = next(f for f in faces if BRepAdaptor_Surface(
            topods.Face(f)).GetType() == GeomAbs_Plane)
    else:
        nf = faces[sel]
    df = [faces[i] for i in opts.get("faces", [0]) if i < len(faces)]
    import math
    ang = math.radians(opts.get("angle", 5.0))
    ok_faces = []
    cur = body.shape
    for f in df:
        try:
            cur = K.draft_neutral(cur, f, ang, nf)
            ok_faces.append(f)
        except Exception:
            continue  # undraftable (e.g. adjacent to a fillet) — skip
    if not ok_faces:
        raise ValueError("拔模：没有可拔模的面")
    body.shape = cur
    return body, f"中性面拔模 ×{len(ok_faces)}"


def op_pull_auto(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("拉动：实体不存在")
    what = opts.get("what", "face")
    idx = opts.get("index", 0)
    sub = (K.explore(body.shape, "face") if what == "face"
           else K.explore(body.shape, "edge"))[idx]
    dist = opts.get("distance", 2.0) / scale
    direction = opts.get("direction", (0, 0, 1))
    mode = opts.get("mode", "auto")
    kind, shape = K.pull_auto(body.shape, sub, direction, dist, mode)
    body.shape = shape
    return body, f"拉动（{kind}）"


def op_shell(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("抽壳：实体不存在")
    faces = K.explore(body.shape, "face")
    body.shape = K.shell_solid(body.shape, opts.get("thickness", 1.0) / scale, [faces[0]])
    return body, "已抽壳"


def op_helix(kdoc, opts, scale):
    sh = K.helix_solid(opts.get("r1", 3.0) / scale, opts.get("r2", 2.0) / scale,
                       opts.get("h", 20.0) / scale, opts.get("pitch", 0.4) / scale)
    return kdoc.add_body(sh, name="螺旋"), "插入螺旋"


def op_enclose(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("包围体：实体不存在")
    from scdm.additive import build_volume
    vol = build_volume(body.shape, opts.get("margin", 1.0), scale)
    return kdoc.add_body(vol, name="包围体"), "创建包围体"


def op_fill(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("填充：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if fi >= len(faces):
        raise ValueError("填充：面索引越界")
    body.shape = K.fill_faces(body.shape, [faces[fi]])
    return body, "填充面"


def _all_faces(kdoc):
    faces = []
    for b in kdoc.bodies:
        faces.extend(K.explore(b.shape, "face"))
    return faces


def op_stitch(kdoc, opts, scale):
    solid = K.sew_faces(_all_faces(kdoc))
    kdoc.bodies = []
    return kdoc.add_body(solid, name="缝合体"), "缝合"


def op_repair_missing(kdoc, opts, scale):
    solid, added = K.fill_missing_faces(K.compound(_all_faces(kdoc)))
    kdoc.bodies = []
    kdoc.add_body(solid, name="修复体")
    return None, f"补缺失面 ×{added}"


def op_repair_solidify(kdoc, opts, scale):
    solid = K.solidify_shell(K.sew_faces(_all_faces(kdoc)))
    kdoc.bodies = []
    return kdoc.add_body(solid, name="实体"), "实体化"


def op_repair_check(kdoc, opts, scale):
    """H4 检查几何：全项检出 + 自动修复。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("检查几何：实体不存在")
    min_area = opts.get("min_area_mm2", 1.0) / (scale ** 2)
    min_edge = opts.get("min_edge_mm", 0.1) / scale
    fnd = K.check_geometry(body.shape, min_area=min_area, min_edge=min_edge)
    counts = {k: (len(v) if isinstance(v, list) else v) for k, v in fnd.items()}
    total = sum(v for v in counts.values() if isinstance(v, int))
    if total == 0:
        return body, "检查几何：未发现问题"
    fixed, rep = K.repair_geometry(body.shape, fnd)
    body.shape = fixed
    fixedn = sum(v for v in rep.values() if isinstance(v, int))
    return body, f"检查几何：{total} 项问题，已修复 {fixedn}"


def _op_hole(kdoc, opts, scale, kind):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("孔：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("孔：面序号越界")
    face = faces[fi]
    d = opts.get("diameter", 5.0) / scale
    depth = opts.get("depth", 0.0)
    if kind == "simple":
        body.shape = K.hole_simple(
            body.shape, face, d, depth=None if depth <= 0 else depth / scale)
        return body, f"孔 d={opts.get('diameter', 5.0)}mm"
    if kind == "tapped":
        # R32/P187: same op surface as the other holes, plus nominal/pitch
        body.shape = K.hole_tapped(
            body.shape, face, opts.get("nominal", 6.0) / scale,
            opts.get("pitch", 1.0) / scale,
            depth=None if depth <= 0 else depth / scale)
        return body, ("攻丝孔 M%g×%g" % (opts.get("nominal", 6.0),
                                         opts.get("pitch", 1.0)))
    if kind == "cbore":
        body.shape = K.hole_counterbore(
            body.shape, face, d, depth / scale,
            opts.get("cbore_diameter", 10.0) / scale,
            opts.get("cbore_depth", 3.0) / scale)
        return body, f"沉头孔 d={opts.get('diameter', 5.0)}mm"
    body.shape = K.hole_countersink(
        body.shape, face, d, depth / scale,
        opts.get("sink_diameter", 10.0) / scale,
        angle_deg=opts.get("angle", 90.0))
    return body, f"锥沉孔 d={opts.get('diameter', 5.0)}mm"


def op_hole(kdoc, opts, scale):
    return _op_hole(kdoc, opts, scale, "simple")


def op_hole_tapped(kdoc, opts, scale):
    return _op_hole(kdoc, opts, scale, "tapped")


def op_louver(kdoc, opts, scale):
    """P271: 百叶（钣金成形）——矩形开口 + 可选唇边。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("百叶：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("百叶：面序号越界")
    body.shape = K.louver(body.shape, faces[fi],
                          opts.get("length", 10.0) / scale,
                          opts.get("width", 3.0) / scale,
                          height=opts.get("height", 0.0) / scale)
    return body, ("百叶 %g×%g" % (opts.get("length", 10.0),
                                   opts.get("width", 3.0)))


def op_knockout(kdoc, opts, scale):
    """P278: 敲落（钣金成形）——带筋环切（diameter/web/web_count）。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("敲落：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("敲落：面序号越界")
    d = opts.get("diameter", 10.0)
    web = opts.get("web", 1.0)
    count = int(opts.get("web_count", 4))
    body.shape = K.knockout(body.shape, faces[fi], d / scale, web / scale,
                            count)
    return body, ("敲落 Ø%g×%d筋" % (d, count))


def op_gusset(kdoc, opts, scale):
    """P295: 角撑（钣金成形）——面上的直角三角形加料。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("角撑：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("角撑：面序号越界")
    body.shape = K.gusset(body.shape, faces[fi],
                          opts.get("length", 5.0) / scale,
                          opts.get("height", 3.0) / scale,
                          opts.get("thickness", 1.0) / scale)
    return body, ("角撑 %g×%g×%g" % (opts.get("length", 5.0),
                                     opts.get("height", 3.0),
                                     opts.get("thickness", 1.0)))


def op_tab(kdoc, opts, scale):
    """P295: 舌片（钣金成形）——面上的矩形局部凸出。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("舌片：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("舌片：面序号越界")
    body.shape = K.tab(body.shape, faces[fi],
                       opts.get("length", 5.0) / scale,
                       opts.get("width", 3.0) / scale,
                       opts.get("height", 1.0) / scale)
    return body, ("舌片 %g×%g×%g" % (opts.get("length", 5.0),
                                     opts.get("width", 3.0),
                                     opts.get("height", 1.0)))


def op_dimple(kdoc, opts, scale):
    """P223: 圆形凹坑（成形族）——与孔族同 op 面但走成形校验。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("凹坑：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("凹坑：面序号越界")
    body.shape = K.dimple_round(body.shape, faces[fi],
                                opts.get("diameter", 8.0) / scale,
                                opts.get("depth", 2.0) / scale)
    return body, ("圆形凹坑 Ø%g×%g" % (opts.get("diameter", 8.0),
                                        opts.get("depth", 2.0)))


def op_hole_cbore(kdoc, opts, scale):
    return _op_hole(kdoc, opts, scale, "cbore")


def op_hole_csink(kdoc, opts, scale):
    return _op_hole(kdoc, opts, scale, "csink")


def op_boss(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("凸台：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("凸台：面序号越界")
    body.shape = K.boss_round(body.shape, faces[fi],
                              opts.get("diameter", 6.0) / scale,
                              opts.get("height", 4.0) / scale)
    return body, f"凸台 d={opts.get('diameter', 6.0)}mm"


def op_beam(kdoc, opts, scale):
    """P283: 梁——6 种截面轮廓沿轴拉伸（新建实体）。"""
    from scdm import beams as BEAMS
    key = str(opts.get("profile", "i")).lower()
    if key not in BEAMS.PROFILES:
        raise ValueError("梁：未知截面 %s" % opts.get("profile"))
    dims = {}
    for name in BEAMS.PARAMS[key]:
        if opts.get(name) is None:
            raise ValueError("梁：截面 %s 缺少参数 %s" % (key, name))
        dims[name] = opts[name] / scale
    length = opts.get("length", 200.0) / scale
    org = tuple(float(v) / scale for v in opts.get("origin", (0.0, 0.0, 0.0)))
    axis = tuple(float(v) for v in opts.get("axis", (0.0, 0.0, 1.0)))
    solid = BEAMS.beam(key, length, origin=org, axis=axis, **dims)
    spec = BEAMS.spec_label(key, **{k: v * scale for k, v in dims.items()})
    body = kdoc.add_body(solid, name=spec)
    return body, ("已创建%s" % spec)


def op_beam_polyline(kdoc, opts, scale):
    """P291: 折线梁——每个线段一个实体，并登记为一个焊件组元。"""
    from scdm import beams as BEAMS
    key = str(opts.get("profile", "i")).lower()
    names = list(BEAMS.PARAMS.get(key, ()))
    dims_mm = {}
    for name in names:
        if opts.get(name) is None:
            raise ValueError("折线梁：截面 %s 缺少参数 %s" % (key, name))
        dims_mm[name] = opts[name]
    pts_mm = opts.get("points") or []
    if len(pts_mm) < 2:
        raise ValueError("折线梁：至少需要两个点")
    pts = [tuple(float(v) / scale for v in p) for p in pts_mm]
    lengths = BEAMS.segment_lengths(pts)
    solids = BEAMS.beam_polyline(key, pts, **{k: v / scale for k, v in dims_mm.items()})
    spec = BEAMS.spec_label(key, **dims_mm)
    weld = BEAMS.Weldment(profile=key, dims=dict(dims_mm),
                          material=str(opts.get("material", "steel")))
    bodies = []
    for i, (solid, length) in enumerate(zip(solids, lengths)):
        name = weld.add_member(pts[i], pts[i + 1],
                               name="M%d" % (i + 1))
        body = kdoc.add_body(solid, name="%s %s" % (spec, name))
        # feature params are mm (the stack convention): keep the source points
        # in mm, not the kernel-unit copy that was just built
        kdoc.record_feature(body.id, "beam_polyline", profile=key,
                            p0=[float(v) for v in pts_mm[i]],
                            p1=[float(v) for v in pts_mm[i + 1]], spec=spec,
                            index=i + 1, count=len(solids), **dims_mm)
        bodies.append(body)
    kdoc.weldments.append(weld)
    return bodies[0], ("已创建折线梁 %s（%d 段，焊件组元）" % (spec, len(bodies)))


def op_insert_box(kdoc, opts, scale):
    from scdm.kdoc import KBody
    w = opts.get("w", 10.0) / scale
    h = opts.get("h", 10.0) / scale
    d = opts.get("d", 10.0) / scale
    org = tuple(o / scale for o in opts.get("origin", (0, 0, 0)))
    name = opts.get("name", "Box")
    body = kdoc.add_body(K.make_box(w, h, d, origin=org), name=name)
    return body, f"已创建盒体 {name}"


def op_sheet_junction(kdoc, opts, scale):
    """P303: 钣金接缝——释放（三角缺口）/ 接缝（矩形缺口）/ 连接（矩形搭接）。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("接缝：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("接缝：面序号越界")
    mode = str(opts.get("mode", "release"))
    width = opts.get("width")
    body.shape = K.junction(body.shape, faces[fi],
                            opts.get("size", 4.0) / scale, mode=mode,
                            width=(None if width is None else width / scale))
    return body, ("接缝 %s %g" % (mode, opts.get("size", 4.0)))


def op_sheet_conical(kdoc, opts, scale):
    """P311: 圆锥折弯——内外表面都是锥面的弯板段（新建实体）。"""
    from scdm import sheetmetal as SM
    import math
    solid = SM.conical_bend(math.radians(opts.get("angle", 90.0)),
                            opts.get("thickness", 1.0) / scale,
                            opts.get("height", 30.0) / scale,
                            opts.get("r1", 20.0) / scale,
                            opts.get("r2", 30.0) / scale,
                            k=opts.get("k", 0.42))
    return kdoc.add_body(solid, name="圆锥折弯件"), "已创建圆锥折弯"


def op_sheet_axial(kdoc, opts, scale):
    """P311: 轴向折弯——折弯轴平行于走向的 U 型槽（新建实体）。"""
    from scdm import sheetmetal as SM
    import math
    solid = SM.axial_bend(opts.get("length", 80.0) / scale,
                          opts.get("width", 30.0) / scale,
                          opts.get("thickness", 1.0) / scale,
                          opts.get("flange", 10.0) / scale,
                          math.radians(opts.get("angle", 90.0)),
                          opts.get("r_inner", 2.0) / scale,
                          opts.get("k", 0.42))
    return kdoc.add_body(solid, name="轴向折弯件"), "已创建轴向折弯"


def op_sheet_bend(kdoc, opts, scale):
    from scdm import sheetmetal as SM
    import math
    if opts.get("create", True):
        w = opts.get("width", 20.0) / scale
        t = opts.get("thickness", 1.0) / scale
        l1 = opts.get("flat1", 30.0) / scale
        l2 = opts.get("flat2", 20.0) / scale
        r = opts.get("r_inner", 2.0) / scale
        k = min(max(opts.get("k", 0.42), 0.0), 1.0)
        ang = math.radians(opts.get("angle", 90.0))
        body = _mk_body(kdoc, opts.get("name", "折弯件"))
        body.shape = SM.bend_from_flat(w, t, l1, l2, ang, r, k)
        return body, "折弯件已创建"
    raise ValueError("折弯：需要 create=true")


def _mk_body(kdoc, name):
    return kdoc.add_body(K.make_box(0.001, 0.001, 0.001), name=name)


def op_sheet_hem(kdoc, opts, scale):
    from scdm import sheetmetal as SM
    w = opts.get("width", 20.0) / scale
    t = opts.get("thickness", 1.0) / scale
    l1 = opts.get("flat1", 30.0) / scale
    hl = opts.get("hem", 5.0) / scale
    r = opts.get("r_inner", 0.5) / scale
    solid = SM.hem(w, t, l1, hl, r)
    return kdoc.add_body(solid, name="卷边件"), "已创建卷边"


def op_sheet_bead(kdoc, opts, scale):
    from scdm import sheetmetal as SM
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("加强筋：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("加强筋：面序号越界")
    length = opts.get("length", 0.0)
    body.shape = SM.bead_groove(body.shape, faces[fi],
                                opts.get("radius", 2.0) / scale,
                                length=None if length <= 0 else length / scale)
    return body, f"加强筋 r={opts.get('radius', 2.0)}mm"


def op_sheet_unfold(kdoc, opts, scale):
    from scdm import sheetmetal as SM
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("展开：实体不存在")
    k = min(max(opts.get("k", 0.42), 0.0), 1.0)
    body.shape = SM.unfold(body.shape, k=k)
    return body, f"已展开（K={k:g}）"


def op_surface_thicken(kdoc, opts, scale):
    from scdm import surface as S
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("加厚：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face", 0)
    t = opts.get("thickness", 1.0) / scale
    solid = S.thicken(faces[fi], t, reverse=opts.get("reverse", False))
    kdoc.add_body(solid, name="加厚体")
    return body, "已加厚"


def op_surface_offset(kdoc, opts, scale):
    from scdm import surface as S
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("偏移面：实体不存在")
    faces = K.explore(body.shape, "face")
    of = S.offset_face(faces[opts.get("face", 0)],
                       opts.get("distance", 1.0) / scale)
    kdoc.add_body(of, name="偏移面")
    return body, "已偏移"


def op_surface_untrim(kdoc, opts, scale):
    from scdm import surface as S
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("去修剪：实体不存在")
    faces = K.explore(body.shape, "face")
    body.shape = S.untrim(faces[opts.get("face", 0)])
    return body, "已去修剪"


OPS = {
    "insert.cyl": op_insert_cyl,
    "insert.sphere": op_insert_sphere,
    "insert.helix": op_helix,
    "prep.enclose": op_enclose,
    "tool.pull": op_pull,
    "tool.move": op_move,
    "tool.fill": op_fill,
    "tool.combine": op_combine,
    "tool.split_body": op_split,
    "create.blend": op_blend,
    "create.chamfer": op_chamfer,
    "create.mirror": op_mirror,
    "create.pattern": op_pattern,
    "create.shell": op_shell,
    "repair.stitch": op_stitch,
    "repair.gaps": op_stitch,
    "repair.solidify": op_repair_solidify,
    "repair.missing": op_repair_missing,
    "create.blend_variable": op_blend_variable,
    "create.shell_multi": op_shell_multi,
    "create.draft_neutral": op_draft_neutral,
    "tool.pull_auto": op_pull_auto,
    "repair.check": op_repair_check,
    "insert.box": op_insert_box,
    "sheet.bend": op_sheet_bend,
    "sheet.unfold": op_sheet_unfold,
    "sheet.hem": op_sheet_hem,
    "sheet.bead": op_sheet_bead,
    "surface.thicken": op_surface_thicken,
    "surface.offset": op_surface_offset,
    "surface.untrim": op_surface_untrim,
    "create.hole": op_hole,
    "create.hole_tapped": op_hole_tapped,
    "create.hole_cbore": op_hole_cbore,
    "create.hole_csink": op_hole_csink,
    "create.boss": op_boss,
    "create.dimple": op_dimple,
    "create.louver": op_louver,
    "create.knockout": op_knockout,
    "create.beam": op_beam,
    "create.beam_polyline": op_beam_polyline,
    "create.gusset": op_gusset,
    "create.tab": op_tab,
    "sheet.junction": op_sheet_junction,
    "sheet.conical": op_sheet_conical,
    "sheet.axial": op_sheet_axial,
}


def replay(steps: List[Dict[str, Any]], kdoc, scale: float = 1000.0) -> List[str]:
    """Replay steps against a KernelDoc; returns the status messages."""
    out = []
    for step in steps:
        cmd = step.get("cmd")
        opts = step.get("opts", {})
        fn = OPS.get(cmd)
        if fn is None:
            out.append(f"跳过未知命令 {cmd}")
            continue
        fn(kdoc, opts, scale)
        out.append(f"OK {cmd}")
    return out

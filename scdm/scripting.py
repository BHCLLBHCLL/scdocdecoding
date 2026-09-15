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
    from scdm import features as FEAT
    sel = FEAT.selector_for(body.shape, faces[fi])
    if opts.get("symmetric"):
        body.shape = K.pull_face_symmetric(body.shape, faces[fi], d)
    else:
        body.shape = K.pull_face(body.shape, faces[fi], d)
    kdoc.record_feature(body.id, "pull", selector=sel,
                        distance=opts.get("distance", 5.0),
                        symmetric=bool(opts.get("symmetric")))
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
        kdoc.translate_body(body.id, vec)      # R103/A-1: base follows
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
    radius = opts.get("radius", 1.0)
    body.shape = K.fillet_edges(body.shape, radius / scale)
    kdoc.record_feature(body.id, "fillet", radius=radius)
    return body, "已倒圆"


def op_chamfer(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("倒角：实体不存在")
    distance = opts.get("distance", 1.0)
    body.shape = K.chamfer_edges(body.shape, distance / scale)
    kdoc.record_feature(body.id, "chamfer", distance=distance)
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
    from scdm import features as FEAT
    sel = FEAT.selector_for(body.shape, faces[0])
    thickness = opts.get("thickness", 1.0)
    body.shape = K.shell_solid(body.shape, thickness / scale, [faces[0]])
    kdoc.record_feature(body.id, "shell", selectors=[sel], thickness=thickness)
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
    return _geometry_check(kdoc, opts, scale, "检查几何")


def op_prep_small(kdoc, opts, scale):
    """R91/P423: 小特征（Defeaturing）走**同一套**几何检查/修复。

    小面检出与修复早已由 `repair.check` 的全项检查覆盖，所以这里不另写实现：
    两个命令入口、一处实现与一处文案（纪律 84），占位命令因此减一。
    """
    return _geometry_check(kdoc, opts, scale, "小特征")


def _geometry_check(kdoc, opts, scale, prefix):
    """Shared H4 check + auto-repair body (used by repair.check / prep.small)."""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("%s：实体不存在" % prefix)
    min_area = opts.get("min_area_mm2", 1.0) / (scale ** 2)
    min_edge = opts.get("min_edge_mm", 0.1) / scale
    fnd = K.check_geometry(body.shape, min_area=min_area, min_edge=min_edge)
    counts = {k: (len(v) if isinstance(v, list) else v) for k, v in fnd.items()}
    total = sum(v for v in counts.values() if isinstance(v, int))
    # R83/P402: the watertightness numbers ride along with the H4 findings -
    # same kernel helpers the report and the tools use (rule 84).
    wt = K.watertight_report(body.shape)
    tail = "；" + K.watertight_text(wt)
    if total == 0:
        return body, "%s：未发现问题%s" % (prefix, tail)
    fixed, rep = K.repair_geometry(body.shape, fnd)
    body.shape = fixed
    fixedn = sum(v for v in rep.values() if isinstance(v, int))
    wt = K.watertight_report(body.shape)
    return body, ("%s：%d 项问题，已修复 %d" % (prefix, total, fixedn)
                  + "；" + K.watertight_text(wt))


def _sel_of(body, face):
    """Pre-op face selector for a recorded feature (R103/A-2).

    Must be called BEFORE the shape is modified: the selector is resolved
    against the shape the feature is applied to.
    """
    from scdm import features as FEAT
    return FEAT.selector_for(body.shape, face)


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
    # R102/P0-1: the scripted hole populates the same feature history the GUI
    # writes, so a later parameter edit (or a replayed journal) can rebuild it.
    from scdm import features as FEAT
    sel = FEAT.selector_for(body.shape, face)
    if kind == "simple":
        body.shape = K.hole_simple(
            body.shape, face, d, depth=None if depth <= 0 else depth / scale)
        kdoc.record_feature(body.id, "hole", selector=sel,
                            diameter=opts.get("diameter", 5.0), depth=depth)
        return body, f"孔 d={opts.get('diameter', 5.0)}mm"
    if kind == "tapped":
        # R32/P187: same op surface as the other holes, plus nominal/pitch
        nominal = opts.get("nominal", 6.0)
        pitch = opts.get("pitch", 1.0)
        body.shape = K.hole_tapped(
            body.shape, face, nominal / scale, pitch / scale,
            depth=None if depth <= 0 else depth / scale)
        kdoc.record_feature(body.id, "hole_tapped", selector=sel,
                            nominal=nominal, pitch=pitch, depth=depth)
        return body, ("攻丝孔 M%g×%g" % (nominal, pitch))
    if kind == "cbore":
        body.shape = K.hole_counterbore(
            body.shape, face, d, depth / scale,
            opts.get("cbore_diameter", 10.0) / scale,
            opts.get("cbore_depth", 3.0) / scale)
        kdoc.record_feature(body.id, "hole_cbore", selector=sel,
                            diameter=opts.get("diameter", 5.0), depth=depth,
                            cbore_diameter=opts.get("cbore_diameter", 10.0),
                            cbore_depth=opts.get("cbore_depth", 3.0))
        return body, f"沉头孔 d={opts.get('diameter', 5.0)}mm"
    body.shape = K.hole_countersink(
        body.shape, face, d, depth / scale,
        opts.get("sink_diameter", 10.0) / scale,
        angle_deg=opts.get("angle", 90.0))
    kdoc.record_feature(body.id, "hole_csink", selector=sel,
                        diameter=opts.get("diameter", 5.0), depth=depth,
                        sink_diameter=opts.get("sink_diameter", 10.0),
                        angle=opts.get("angle", 90.0))
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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.louver(body.shape, faces[fi],
                          opts.get("length", 10.0) / scale,
                          opts.get("width", 3.0) / scale,
                          height=opts.get("height", 0.0) / scale)
    kdoc.record_feature(body.id, "louver", selector=sel,
                        length=opts.get("length", 10.0),
                        width=opts.get("width", 3.0),
                        height=opts.get("height", 0.0))
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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.knockout(body.shape, faces[fi], d / scale, web / scale,
                            count)
    kdoc.record_feature(body.id, "knockout", selector=sel, diameter=d,
                        web=web, web_count=count)
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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.gusset(body.shape, faces[fi],
                          opts.get("length", 5.0) / scale,
                          opts.get("height", 3.0) / scale,
                          opts.get("thickness", 1.0) / scale)
    kdoc.record_feature(body.id, "gusset", selector=sel,
                        length=opts.get("length", 5.0),
                        height=opts.get("height", 3.0),
                        thickness=opts.get("thickness", 1.0))
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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.tab(body.shape, faces[fi],
                       opts.get("length", 5.0) / scale,
                       opts.get("width", 3.0) / scale,
                       opts.get("height", 1.0) / scale)
    kdoc.record_feature(body.id, "tab", selector=sel,
                        length=opts.get("length", 5.0),
                        width=opts.get("width", 3.0),
                        height=opts.get("height", 1.0))
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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.dimple_round(body.shape, faces[fi],
                                opts.get("diameter", 8.0) / scale,
                                opts.get("depth", 2.0) / scale)
    kdoc.record_feature(body.id, "dimple", selector=sel,
                        diameter=opts.get("diameter", 8.0),
                        depth=opts.get("depth", 2.0))
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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.boss_round(body.shape, faces[fi],
                              opts.get("diameter", 6.0) / scale,
                              opts.get("height", 4.0) / scale)
    kdoc.record_feature(body.id, "boss", selector=sel,
                        diameter=opts.get("diameter", 6.0),
                        height=opts.get("height", 4.0))
    return body, f"凸台 d={opts.get('diameter', 6.0)}mm"


def op_asm_explode(kdoc, opts, scale):
    """R88/P415: 爆炸图——沿轴/径向/等比三种模式，位移可数、可还原。

    opts: mode=axis|radial|scale、distance_mm（等比模式下是倍率）、axis（沿轴方向）、
    restore=True 等价于把位移清零（先还原已记录的位移再加新的）。
    """
    from scdm import additive as A
    from scdm import assembly as ASM

    comps = list(getattr(kdoc, "components", []) or [])
    if not comps:
        raise ValueError("爆炸图：没有组件")
    centres = {}
    for comp in comps:
        pts = []
        for b in kdoc.bodies_of_component(comp.id):
            try:
                lo, hi = A.shape_bbox(b.shape)
            except Exception:
                continue
            pts.append(tuple((lo[i] + hi[i]) / 2.0 for i in range(3)))
        c = ASM.centroid(pts)
        if c is not None:
            centres[comp.id] = c
    mode = str(opts.get("mode", "axis")).lower()
    if opts.get("restore"):
        distance = 0.0
    elif mode == "scale":
        distance = float(opts.get("distance_mm", 0.2))
    else:
        distance = float(opts.get("distance_mm", 20.0)) / scale
    pivot = ASM.centroid([centres[c.id] for c in comps if c.id in centres])
    axis = tuple(float(v) for v in opts.get("axis", (1.0, 0.0, 0.0)))
    offsets = ASM.explode_offsets(
        centres, mode=mode, distance=distance, axis=axis, pivot=pivot,
        anchored=[c.id for c in comps if getattr(c, "anchored", False)],
        order=[c.id for c in comps])
    # R99/P440: an optional frame interpolates the offsets (frame 0 = home,
    # frame frames-1 = full explosion); the geometry is the same list of
    # translations, so a frame is as countable as the final state.
    frames = int(opts.get("frames", 0) or 0)
    frame = int(opts.get("frame", frames - 1 if frames >= 2 else 0) or 0)
    if frames >= 2:
        offsets = ASM.frame_offsets(offsets, frame, frames)
    moved = ASM.apply_explode(kdoc, offsets, K.translate)
    total = ASM.total_displacement(offsets)
    label = ASM.MODE_LABELS.get(mode, mode)
    if not moved:
        return None, "爆炸图：还原（%d 个组件回到原位）" % len(comps)
    detail = ("倍率 %g" % distance if mode == "scale"
              else "间距 %gmm" % (distance * scale))
    if frames >= 2:
        detail += "，帧 %d/%d" % (frame, frames - 1)
    return None, ("爆炸图（%s，%s）：%d/%d 个组件，总位移 %.3gmm"
                  % (label, detail, moved, len(comps), total * scale))

def op_beam(kdoc, opts, scale):
    """P283/R87: 梁——6 种截面轮廓沿轴拉伸；可用标准规格名（R87）。"""
    from scdm import beams as BEAMS
    spec_name = opts.get("spec")
    if spec_name:
        # R87/P416: standard table lookup (mm in, metres out)
        key, mm = BEAMS.spec_dims(spec_name)
        dims = {name: value / scale for name, value in mm.items()}
    else:
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
    if spec_name:
        # R87: the label names the standard spec the dims came from
        spec = BEAMS.named_spec_label(spec_name)
    else:
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


def op_sheet_cross_break(kdoc, opts, scale):
    """P353: 十字压筋——面上沿 u 的浅 V 形/圆弧压槽。"""
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("压筋：实体不存在")
    faces = K.explore(body.shape, "face")
    fi = opts.get("face_i", 0)
    if not (0 <= fi < len(faces)):
        raise ValueError("压筋：面序号越界")
    kind = str(opts.get("kind", "v"))
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.cross_break(body.shape, faces[fi],
                               opts.get("length", 10.0) / scale,
                               opts.get("width", 2.0) / scale,
                               opts.get("depth", 0.3) / scale,
                               kind=kind)
    kdoc.record_feature(body.id, "cross_break", selector=sel, kind=kind,
                        length=opts.get("length", 10.0),
                        width=opts.get("width", 2.0),
                        depth=opts.get("depth", 0.3))
    return body, ("压筋 %s %g×%g×%g" % (kind, opts.get("length", 10.0),
                                        opts.get("width", 2.0),
                                        opts.get("depth", 0.3)))


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
    sel = _sel_of(body, faces[fi])              # R103/A-2: recorded feature
    body.shape = K.junction(body.shape, faces[fi],
                            opts.get("size", 4.0) / scale, mode=mode,
                            width=(None if width is None else width / scale))
    kdoc.record_feature(body.id, "junction", selector=sel, mode=mode,
                        size=opts.get("size", 4.0), width=width)
    return body, ("接缝 %s %g" % (mode, opts.get("size", 4.0)))


def op_mesh_surface(kdoc, opts, scale):
    """P323: 面网格——派生件（不入 .scdm），返回可数指标。"""
    from scdm import mesh as ME
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("网格：实体不存在")
    mesh = ME.mesh_shape(body.shape, deflection=opts.get("deflection", 1.0) / scale)
    stats = ME.mesh_stats(mesh, shape=body.shape)
    verdict = ME.check_quality(mesh, opts.get("gates"))
    entry = kdoc.meshes.setdefault(body.id, {})
    entry["stats"] = stats
    entry["gates"] = verdict
    return body, ("网格：%d 三角形 / %d 顶点，退化 %d，面积误差 %.3g，门槛 %s"
                  % (stats["triangles"], stats["vertices"], stats["degenerate"],
                     stats["area_rel_error"],
                     "通过" if verdict["ok"]
                     else "超限 %d 项" % verdict["count"]))


def op_mesh_volume(kdoc, opts, scale):
    """P327: 体网格——体素四面体填充（体积和 vs 实体体积 = 离散误差）。"""
    from scdm import mesh as ME
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("体网格：实体不存在")
    fill = ME.tet_fill(body.shape, opts.get("cell", 2.0) / scale,
                       boundary=str(opts.get("boundary", "voxel")))
    stats = ME.tet_stats(fill, shape=body.shape)
    kdoc.meshes.setdefault(body.id, {})["volume"] = stats
    if stats["boundary"] == "clip":
        return body, ("体网格（贴体裁剪）：%d 实体格 / %d 边界格，体积误差 %.3g（体素版 %.3g）"
                      % (stats["cells"], stats["boundary_cells"],
                         stats["volume_clip_rel_error"], stats["volume_rel_error"]))
    if stats["boundary"] == "tets":
        return body, ("体网格（贴体四面体）：%d 实体格 / %d 边界格 / %d 四面体，"
                      "体积误差 %.3g（体素版 %.3g）"
                      % (stats["cells"], stats["boundary_cells"], stats["tets"],
                         stats["volume_rel_error"], 0.0))
    return body, ("体网格：%d 单元 / %d 四面体，体积误差 %.3g"
                  % (stats["cells"], stats["tets"], stats["volume_rel_error"]))


def op_sim_report(kdoc, opts, scale):
    """P348: 仿真报告导出（载荷/支撑/接触 + 网格与材料统计）。"""
    from scdm import simreport as SR
    path = opts.get("path")
    if not path:
        raise ValueError("仿真报告：需要 path")
    rep = SR.build_report(kdoc, scale)
    SR.write_report(path, rep)
    return (kdoc.body_by_id(opts["body_id"]) if opts.get("body_id") else None), \
        ("已导出仿真报告 %s（%s）" % (path, SR.report_text(rep)))


def op_mesh_report(kdoc, opts, scale):
    """P324: 网格质量报告导出（JSON/CSV）。"""
    from scdm import mesh as ME
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("网格报告：实体不存在")
    path = opts.get("path")
    if not path:
        raise ValueError("网格报告：需要 path")
    rep = ME.quality_report(body.shape,
                            deflection=opts.get("deflection", 1.0) / scale,
                            name=body.name)
    ME.write_report(path, rep, fmt=opts.get("fmt", "json"))
    return body, ("已导出网格报告 %s（%d 三角形）" % (path, rep["triangles"]))


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


def op_param_edit(kdoc, opts, scale):
    """R102/P0-1: change a recorded feature parameter and replay the body.

    The step id is `det.params` (the parameter command itself), so a recorded
    journal reproduces the same edit on a fresh document: the body is rebuilt
    from its base shape + feature stack, exactly like the GUI dialog does.
    """
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("参数编辑：实体不存在")
    rep = kdoc.edit_feature(body.id, int(opts.get("feature", 0)),
                            str(opts.get("param", "")), opts.get("value"), scale)
    if not rep.get("ok"):
        raise ValueError("参数编辑失败：%s" % rep.get("reason"))
    return body, "参数 %s：%s → %s" % (rep["param"], rep["old"], rep["value"])


def op_asm_mate(kdoc, opts, scale):
    """R104/A-1 + P1-1: a mate or an alignment as a replayable step.

    opts: type = rigid|revolute|cylindrical|planar|ball|screw|distance (the
    kinematic pairs) or faces|axes (the alignment paths); target/target2 plus
    index/index2 pick the two bodies, face_a/face_b the faces.
    """
    b1 = _resolve(kdoc, opts.get("target2", "first"), opts.get("index2", 0))
    b2 = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if b1 is None or b2 is None or b1 is b2:
        raise ValueError("配合：需要两个实体")
    f1 = K.explore(b1.shape, "face")
    f2 = K.explore(b2.shape, "face")
    i1 = int(opts.get("face_a", 0))
    i2 = int(opts.get("face_b", 0))
    if not (0 <= i1 < len(f1)) or not (0 <= i2 < len(f2)):
        raise ValueError("配合：面序号越界")
    mtype = str(opts.get("type", "rigid"))
    if mtype in ("faces", "axes"):          # R104/A-1 alignment paths
        kdoc.align_body(b2.id, mtype, f2[i2], f1[i1])
        return b2, "已对齐（%s）" % mtype
    rep = kdoc.mate_bodies(mtype, b1, f1[i1], b2, f2[i2],
                           value=opts.get("value", 0.0),
                           angle=opts.get("angle", 0.0),
                           slide=opts.get("slide", 0.0), scale=scale)
    if not rep["ok"]:
        raise ValueError("配合失败：%s" % rep["reason"])
    return b2, "配合 %s（剩余自由度 %d/6）" % (mtype, rep["dof"])


def op_sketch_pull(kdoc, opts, scale):
    """R105: the sketch -> solid bridge (Pull on a sketch, scripted).

    opts: distance (mm, default 10); sketch = index of the sketch to use when
    there is no GUI session (a script has no active-sketch state).
    """
    from scdm import sketchmode as SKM
    h = float(opts.get("distance", 10.0))
    session = None
    idx = opts.get("sketch")
    if idx is not None:
        sks = list(getattr(kdoc, "sketches", []) or [])
        if not (0 <= int(idx) < len(sks)):
            raise ValueError("草图拉伸：草图序号越界")
        sk = sks[int(idx)]
        session = SKM.SketchSession(sketch_id=sk.id, plane=sk.plane)
    rep = SKM.extrude_active(kdoc, h, scale, session)
    if not rep["ok"]:
        raise ValueError("草图拉伸失败：%s" % rep["reason"])
    return rep["bodies"][-1], "草图拉伸 ×%d（%gmm）" % (len(rep["bodies"]), h)


def op_sketch_drive(kdoc, opts, scale):
    """R107/A-3: drive one sketch dimension by number (script step).

    opts: sketch = sketch index, index = constraint index, value_mm = new value.
    """
    from scdm import sketchmode as SKM
    sks = list(getattr(kdoc, "sketches", []) or [])
    idx_sk = int(opts.get("sketch", 0))
    if not (0 <= idx_sk < len(sks)):
        raise ValueError("驱动尺寸：草图序号越界")
    sk = sks[idx_sk]
    rep = SKM.set_dimension(kdoc, sk.id, int(opts.get("index", 0)),
                            float(opts.get("value_mm", 0.0)), scale)
    if not rep["ok"]:
        raise ValueError("驱动尺寸失败：%s" % rep["reason"])
    syn = SKM.sync_sketch_bodies(kdoc, sk.id, scale)
    return None, "尺寸 %gmm（重建 %d 个实体）" % (rep["value_mm"],
                                                len(syn["updated"]))


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
    "prep.small": op_prep_small,        # R91/P423: same implementation
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
    "asm.explode": op_asm_explode,      # R88/P415
    "create.beam_polyline": op_beam_polyline,
    "create.gusset": op_gusset,
    "create.tab": op_tab,
    "sheet.junction": op_sheet_junction,
    "sheet.cross_break": op_sheet_cross_break,
    "sheet.conical": op_sheet_conical,
    "sheet.axial": op_sheet_axial,
    "sim.report": op_sim_report,
    "mesh.surface": op_mesh_surface,
    "mesh.volume": op_mesh_volume,
    "mesh.report": op_mesh_report,
    "det.params": op_param_edit,        # R102/P0-1: feature parameter edit
    "asm.mate": op_asm_mate,            # R104/A-1+P1-1: mate / alignment
    "sketch.pull": op_sketch_pull,      # R105: sketch -> solid bridge
    "sketch.drive": op_sketch_drive,    # R107/A-3: drive a dimension
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

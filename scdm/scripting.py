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

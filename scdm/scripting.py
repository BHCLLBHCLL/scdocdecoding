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
    shapes = K.pattern_linear(body.shape, (step, 0, 0), count)
    for i, sh in enumerate(shapes[1:], 2):
        kdoc.add_body(sh, name=f"{body.name} 阵列{i}")
    return body, f"线性阵列 ×{count}"


def op_shell(kdoc, opts, scale):
    body = _resolve(kdoc, opts.get("target", "last"), opts.get("index", 0))
    if body is None:
        raise ValueError("抽壳：实体不存在")
    faces = K.explore(body.shape, "face")
    body.shape = K.shell_solid(body.shape, opts.get("thickness", 1.0) / scale, [faces[0]])
    return body, "已抽壳"


OPS = {
    "insert.cyl": op_insert_cyl,
    "insert.sphere": op_insert_sphere,
    "tool.pull": op_pull,
    "tool.move": op_move,
    "tool.combine": op_combine,
    "tool.split_body": op_split,
    "create.blend": op_blend,
    "create.chamfer": op_chamfer,
    "create.mirror": op_mirror,
    "create.pattern": op_pattern,
    "create.shell": op_shell,
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

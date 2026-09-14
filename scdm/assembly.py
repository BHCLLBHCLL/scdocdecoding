"""R88/P415: 装配级操作 —— 爆炸图（位移向量可数、可还原）。

第一批爆炸图只有一个"每件 +X 等差平移"的 GUI 循环；本轮把它变成**可数、可复算、可还原**的装配操作：

    mode="axis"    offset_i = u_axis * distance * i        （i 为组件次序，1 起）
    mode="radial"  offset_i = u_i * distance * i           （u_i = unit(center_i - pivot)）
    mode="scale"   offset_i = (center_i - pivot) * distance（等比外扩，distance 是倍率）

锚定组件位移恒为零向量；`distance=0` 即**还原**（先减掉每件已记录的位移，再加新的）。
本模块刻意不依赖内核：平移由调用方以 `translate(shape, vec)` 传入，因此位移数学可以脱离 OpenCASCADE 单测。
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]

MODES = ("axis", "radial", "scale")
MODE_LABELS = {"axis": "沿轴", "radial": "径向", "scale": "等比"}


def _unit(v: Sequence[float]) -> Optional[Vec3]:
    n = math.sqrt(sum(float(c) * float(c) for c in v))
    if n < 1e-15:
        return None
    return (float(v[0]) / n, float(v[1]) / n, float(v[2]) / n)


def centroid(points: Sequence[Sequence[float]]) -> Optional[Vec3]:
    pts = [tuple(float(c) for c in p) for p in points]
    if not pts:
        return None
    n = float(len(pts))
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n,
            sum(p[2] for p in pts) / n)


def explode_offsets(centres: Dict[str, Sequence[float]], mode: str = "axis",
                    distance: float = 0.0,
                    axis: Sequence[float] = (1.0, 0.0, 0.0),
                    pivot: Optional[Sequence[float]] = None,
                    anchored: Optional[Sequence[str]] = None,
                    order: Optional[Sequence[str]] = None) -> Dict[str, Vec3]:
    """每个组件的位移向量（键为组件 id，值以调用方单位计）。

    Raises ValueError for an unknown mode or a radial/scale request without a
    pivot - a silent zero offset would look like "nothing happened".
    """
    key = str(mode).lower()
    if key not in MODES:
        raise ValueError("爆炸图：未知模式 %s（可选 %s）"
                         % (mode, "/".join(MODES)))
    locked = set(anchored or ())
    ids = list(order) if order is not None else list(centres)
    zero: Vec3 = (0.0, 0.0, 0.0)
    out: Dict[str, Vec3] = {cid: zero for cid in centres}
    if abs(float(distance)) < 1e-15:
        return out
    if key in ("radial", "scale"):
        if pivot is None:
            raise ValueError("爆炸图：%s 模式需要 pivot（装配中心）" % key)
        piv = tuple(float(c) for c in pivot)
    else:
        u_axis = _unit(axis)
        if u_axis is None:
            raise ValueError("爆炸图：轴方向不能是零向量")
        piv = None
    for i, cid in enumerate(ids, 1):
        if cid in locked or cid not in centres:
            continue
        c = tuple(float(v) for v in centres[cid])
        if key == "axis":
            out[cid] = tuple(u_axis[k] * float(distance) * i for k in range(3))
        else:
            rel = tuple(c[k] - piv[k] for k in range(3))
            if key == "scale":
                out[cid] = tuple(rel[k] * float(distance) for k in range(3))
            else:
                u = _unit(rel)
                if u is None:      # component sits ON the pivot: no direction
                    continue
                out[cid] = tuple(u[k] * float(distance) * i for k in range(3))
    return out


def frame_offsets(offsets: Dict[str, Sequence[float]], frame: int,
                  frames: int) -> Dict[str, Vec3]:
    """一帧的位移：`offset * t`，`t = frame / (frames - 1)`（R99/P440）。

    `frame=0` 是原位（全零向量）、`frame=frames-1` 是完整爆炸；帧位移是**闭式**的，
    所以"动画"不需要保存任何中间状态——这也是它能被回放/被测试的原因。
    """
    n = int(frames)
    i = int(frame)
    if n < 2:
        raise ValueError("爆炸动画：帧数至少为 2")
    if not 0 <= i <= n - 1:
        raise ValueError("爆炸动画：帧号必须在 0..%d" % (n - 1))
    t = float(i) / float(n - 1)
    return {cid: (float(v[0]) * t, float(v[1]) * t, float(v[2]) * t)
            for cid, v in offsets.items()}


def explode_frames(offsets: Dict[str, Sequence[float]], frames: int,
                   ) -> List[Dict[str, Vec3]]:
    """整个动画的每帧位移（R99/P440）。"""
    return [frame_offsets(offsets, i, frames) for i in range(int(frames))]

def total_displacement(offsets: Dict[str, Sequence[float]]) -> float:
    """L1 总位移（可数指标，调用方单位）。"""
    return sum(math.sqrt(sum(float(c) * float(c) for c in v))
               for v in offsets.values())


def apply_explode(kdoc, offsets: Dict[str, Sequence[float]],
                  translate: Callable) -> int:
    """先还原每件**已记录**的位移，再施加新位移；返回被动过的组件数。

    还原用 `Component.explosion`（第一批就存在这个字段），所以反复爆炸、
    或者 `distance=0` 都能回到原位——不需要保存原始几何。
    """
    moved = 0
    for comp in getattr(kdoc, "components", []) or []:
        prev = getattr(comp, "explosion", None)
        if prev:
            back = (-float(prev[0]), -float(prev[1]), -float(prev[2]))
            for b in kdoc.bodies_of_component(comp.id):
                b.shape = translate(b.shape, back)
            comp.explosion = None
        vec = offsets.get(comp.id)
        if vec is None or all(abs(float(c)) < 1e-15 for c in vec):
            continue
        for b in kdoc.bodies_of_component(comp.id):
            b.shape = translate(b.shape, vec)
        comp.explosion = tuple(float(c) for c in vec)
        moved += 1
    return moved


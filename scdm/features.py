"""P5: minimal feature history for parametric rebuild.

A `FeatureStack` records modelling operations against one body so that a
parameter change can rebuild the base primitive and replay the features on
top of it. The face a feature was applied to is stored as a *selector*
(normal + which extreme along that normal) instead of a face index, so it
survives the rebuild when the body's dimensions change.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scdm import kernel as K


def selector_for(shape, face) -> dict:
    """Face selector that survives a rebuild: outward normal + extreme along it."""
    n, c = K.face_normal_center(face)
    n = tuple(float(v) for v in n)
    lo, hi = K._vertex_bbox(shape)
    mid = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    proj = sum((c[i] - mid[i]) * n[i] for i in range(3))
    return {"normal": n, "pick": "max" if proj >= 0 else "min"}


def resolve_face(shape, selector) -> Optional[Any]:
    """The face matching a selector on the (rebuilt) shape, or None."""
    n = tuple(selector.get("normal", (0.0, 0.0, 1.0)))
    want_max = selector.get("pick", "max") == "max"
    best = None
    best_key = None
    for f in K.explore(shape, "face"):
        fn, fc = K.face_normal_center(f)
        if sum(fn[i] * n[i] for i in range(3)) < 0.999:
            continue
        key = sum(fc[i] * n[i] for i in range(3))
        if best is None or (key > best_key if want_max else key < best_key):
            best, best_key = f, key
    return best


_FEATURE_LABELS = {
    "hole": "孔 Ø{diameter:g}mm",
    "hole_tapped": "攻丝孔 M{nominal:g}×{pitch:g}",
    "dimple": "凹坑 Ø{diameter:g}×{depth:g}",
    "louver": "百叶 {length:g}×{width:g}",
    "knockout": "敲落 Ø{diameter:g}×{web_count:g}筋",
    "hole_cbore": "沉头孔 Ø{diameter:g}",
    "hole_csink": "锥沉孔 Ø{diameter:g}",
    "boss": "凸台 Ø{diameter:g}×{height:g}",
    "shell": "抽壳 {thickness:g}mm",
    "fillet": "倒圆 R{radius:g}mm",
    "chamfer": "倒角 {distance:g}mm",
    "pull": "拉动 {distance:g}mm",
    "offset": "偏移面 {distance:g}mm",
    "draft": "拔模 {angle:g}°",
}


@dataclass
class Feature:
    op: str
    params: Dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        """Human-readable name for the feature tree (P16)."""
        tpl = _FEATURE_LABELS.get(self.op)
        if not tpl:
            return self.op
        try:
            return tpl.format(**self.params)
        except Exception:
            return self.op


@dataclass
class FeatureStack:
    features: List[Feature] = field(default_factory=list)

    def add(self, op: str, **params) -> "Feature":
        f = Feature(op, dict(params))
        self.features.append(f)
        return f

    def clear(self) -> None:
        self.features.clear()

    def __len__(self) -> int:
        return len(self.features)

    def ops(self) -> List[str]:
        return [f.op for f in self.features]

    def apply(self, shape, scale: float = 1000.0):
        """Replay every feature in order onto a BASE shape (params in mm).

        Pass the unmodified base body - applying a stack to an already
        featured shape would run e.g. shell twice and fail.
        """
        for f in self.features:
            shape = _apply_one(shape, f, scale)
        return shape

    def as_dict(self) -> List[dict]:
        return [{"op": f.op, "params": dict(f.params)} for f in self.features]

    @classmethod
    def from_dict(cls, data) -> "FeatureStack":
        return cls([Feature(d["op"], dict(d.get("params", {}))) for d in data or []])


def _apply_one(shape, feature: Feature, scale: float):
    op = feature.op
    p = feature.params
    if op in ("hole", "hole_tapped", "hole_cbore", "hole_csink"):
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        d = float(p.get("diameter", 5.0)) / scale
        if op == "hole":
            depth = p.get("depth", 0.0)
            return K.hole_simple(shape, face, d,
                                 depth=None if depth <= 0 else depth / scale)
        if op == "hole_tapped":
            # R32/P187: the thread spec rides along with the feature so a
            # replay reconstructs the same tap-drill cut
            return K.hole_tapped(
                shape, face, float(p.get("nominal", 6.0)) / scale,
                float(p.get("pitch", 1.0)) / scale,
                depth=None if p.get("depth", 0.0) <= 0
                else float(p["depth"]) / scale)
        if op == "hole_cbore":
            return K.hole_counterbore(shape, face, d,
                                      float(p.get("depth", 10.0)) / scale,
                                      float(p.get("cbore_diameter", 10.0)) / scale,
                                      float(p.get("cbore_depth", 3.0)) / scale)
        return K.hole_countersink(shape, face, d,
                                  float(p.get("depth", 10.0)) / scale,
                                  float(p.get("sink_diameter", 10.0)) / scale,
                                  angle_deg=float(p.get("angle", 90.0)))
    if op == "louver":
        # P271: forming feature on a sheet face (optional lip via height)
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.louver(shape, face,
                        float(p.get("length", 10.0)) / scale,
                        float(p.get("width", 3.0)) / scale,
                        height=float(p.get("height", 0.0)) / scale)
    if op == "knockout":
        # P278: forming feature - ring cut held on by web_count radial webs
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.knockout(shape, face,
                          float(p.get("diameter", 10.0)) / scale,
                          float(p.get("web", 1.0)) / scale,
                          int(p.get("web_count", 4)))
    if op == "dimple":
        # R40/P223: forming feature - same face flow, dimple validation
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.dimple_round(shape, face,
                              float(p.get("diameter", 8.0)) / scale,
                              float(p.get("depth", 2.0)) / scale)
    if op == "boss":
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.boss_round(shape, face,
                            float(p.get("diameter", 6.0)) / scale,
                            float(p.get("height", 4.0)) / scale)
    if op == "pull":
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        d = float(p.get("distance", 0.0)) / scale
        if abs(d) < 1e-12:
            return shape
        if p.get("symmetric"):
            return K.pull_face_symmetric(shape, face, d)
        return K.pull_face(shape, face, d)
    if op == "offset":
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.offset_faces(shape, face, float(p.get("distance", 0.0)) / scale)
    if op == "draft":
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        neutral = tuple(p.get("neutral", (0.0, 0.0, 1.0)))
        return K.draft_face(shape, face, math.radians(float(p.get("angle", 5.0))),
                            neutral)
    if op == "shell":
        faces = []
        for sel in p.get("selectors", []) or []:
            f = resolve_face(shape, sel)
            if f is not None:
                faces.append(f)
        if not faces:
            all_faces = K.explore(shape, "face")
            if not all_faces:
                return shape
            faces = [all_faces[0]]
        return K.shell_solid(shape, float(p.get("thickness", 1.0)) / scale,
                             faces)
    if op == "fillet":
        return K.fillet_edges(shape, float(p.get("radius", 1.0)) / scale)
    if op == "chamfer":
        return K.chamfer_edges(shape, float(p.get("distance", 1.0)) / scale)
    return shape

_DOC_LABELS = {
    "pattern_linear": "线性阵列 ×{count}",
    "pattern_circular": "圆周阵列 ×{count}",
    "mirror": "镜像",
    "fuse": "合并（并集）",
    "cut": "合并（减去）",
    "common": "合并（相交）",
    "split": "分割实体",
}


@dataclass
class DocFeature:
    """P22: a document-level feature that produces/consumes whole bodies.

    inputs are SLOT indices into the replay timeline (base shapes first, then
    one slot per produced shape), so the history is a replayable DAG rather
    than a per-body operation list.
    """
    op: str
    inputs: List[int] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        tpl = _DOC_LABELS.get(self.op, self.op)
        try:
            return tpl.format(**self.params)
        except Exception:
            return self.op


@dataclass
class FeatureHistory:
    """Document-level feature list with replay / delete support (P22)."""
    features: List[DocFeature] = field(default_factory=list)

    def add(self, op: str, inputs, **params) -> DocFeature:
        f = DocFeature(op, [int(i) for i in inputs], dict(params))
        self.features.append(f)
        return f

    def remove_at(self, index: int) -> bool:
        if 0 <= index < len(self.features):
            del self.features[index]
            return True
        return False

    def __len__(self) -> int:
        return len(self.features)

    def ops(self) -> List[str]:
        return [f.op for f in self.features]

    def replay(self, base_shapes, scale: float = 1000.0):
        """Re-run the history over the base shapes; returns the live shapes."""
        shapes = list(base_shapes)
        live = list(range(len(shapes)))
        for f in self.features:
            idx = [i for i in f.inputs if 0 <= i < len(shapes)]
            if not idx:
                continue
            if f.op in ("pattern_linear", "pattern_circular"):
                count = max(2, int(f.params.get("count", 2)))
                if f.op == "pattern_linear":
                    vec = tuple(float(v) / scale
                                for v in f.params.get("vec_mm", (10.0, 0.0, 0.0)))
                    parts = K.pattern_linear(shapes[idx[0]], vec, count)
                else:
                    axis = tuple(f.params.get("axis", (0.0, 0.0, 1.0)))
                    angle = float(f.params.get("angle_deg", 30.0))
                    parts = K.pattern_circular(shapes[idx[0]], axis, angle, count)
                for p in parts[1:]:
                    shapes.append(p)
                    live.append(len(shapes) - 1)
            elif f.op == "mirror":
                normal = tuple(f.params.get("normal", (0.0, 0.0, 1.0)))
                origin = tuple(f.params.get("origin", (0.0, 0.0, 0.0)))
                shapes.append(K.mirror(shapes[idx[0]], origin, normal))
                live.append(len(shapes) - 1)
            elif f.op in ("fuse", "cut", "common") and len(idx) >= 2:
                fn = {"fuse": K.fuse, "cut": K.cut, "common": K.common}[f.op]
                res = fn(shapes[idx[0]], shapes[idx[1]])
                for i in idx[:2]:
                    if i in live:
                        live.remove(i)
                shapes.append(res)
                live.append(len(shapes) - 1)
            elif f.op == "split":
                plane_o = tuple(f.params.get("origin", (0.0, 0.0, 0.0)))
                plane_n = tuple(f.params.get("normal", (1.0, 0.0, 0.0)))
                for s in K.split_by_plane(shapes[idx[0]], plane_o, plane_n):
                    shapes.append(s)
                    live.append(len(shapes) - 1)
        return [shapes[i] for i in live]

    def as_dict(self) -> List[dict]:
        return [{"op": f.op, "inputs": list(f.inputs),
                 "params": dict(f.params)} for f in self.features]

    @classmethod
    def from_dict(cls, data) -> "FeatureHistory":
        return cls([DocFeature(d["op"], list(d.get("inputs", [])),
                               dict(d.get("params", {})))
                    for d in data or []])

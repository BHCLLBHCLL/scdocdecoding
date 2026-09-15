"""P5: minimal feature history for parametric rebuild.

A `FeatureStack` records modelling operations against one body so that a
parameter change can rebuild the base primitive and replay the features on
top of it. The face a feature was applied to is stored as a *selector*
(normal + which extreme along that normal) instead of a face index, so it
survives the rebuild when the body's dimensions change.
"""
from __future__ import annotations

import json
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
    "beam": "梁 {spec}",
    "beam_polyline": "折线梁 {spec} 段{index}/{count}",
    "gusset": "角撑 {length:g}×{height:g}×{thickness:g}",
    "tab": "舌片 {length:g}×{width:g}×{height:g}",
    "junction": "接缝 {mode} {size:g}",
    "cross_break": "压筋 {kind} {length:g}×{width:g}×{depth:g}",
    "hole_cbore": "沉头孔 Ø{diameter:g}",
    "hole_csink": "锥沉孔 Ø{diameter:g}",
    "boss": "凸台 Ø{diameter:g}×{height:g}",
    "shell": "抽壳 {thickness:g}mm",
    "fillet": "倒圆 R{radius:g}mm",
    "chamfer": "倒角 {distance:g}mm",
    "pull": "拉动 {distance:g}mm",
    "offset": "偏移面 {distance:g}mm",
    "draft": "拔模 {angle:g}°",
    "sketch": "草图拉伸 {height:g}mm",          # R106/B-1: the sketch *is* the feature
}


# --- R102/P0-1: editable feature parameters ---------------------------------
#
# Whitelist of the parameters a user may change *after* the fact.  Everything not
# listed stays fixed (selectors, face picks, profile names, material specs...):
# the point of the whitelist is that a replay is guaranteed to be well defined —
# a parameter outside it would need information the stack does not carry.
#
# Bounds are in the feature's own unit (mm / degree).  lo_open/hi_open mark strict
# inequalities, `integer` marks counts, `nonzero` rejects 0 (pull direction).


@dataclass(frozen=True)
class EditField:
    param: str
    label: str
    unit: str = "mm"
    lo: Optional[float] = None
    hi: Optional[float] = None
    lo_open: bool = False
    hi_open: bool = False
    integer: bool = False
    nonzero: bool = False

    def check(self, value: float) -> Optional[str]:
        """None when the value is acceptable, else a human-readable reason."""
        if not math.isfinite(value):
            return "%s 必须是有限数" % self.label
        if self.integer and abs(value - round(value)) > 1e-9:
            return "%s 必须是整数" % self.label
        if self.nonzero and abs(value) < 1e-12:
            return "%s 不能为 0" % self.label
        if self.lo is not None and (value < self.lo
                                    or (self.lo_open and abs(value - self.lo) < 1e-12)):
            return "%s 必须%s %g%s" % (self.label,
                                       "大于" if self.lo_open else "不小于",
                                       self.lo,
                                       (" " + self.unit) if self.unit else "")
        if self.hi is not None and (value > self.hi
                                    or (self.hi_open and abs(value - self.hi) < 1e-12)):
            return "%s 必须%s %g%s" % (self.label,
                                       "小于" if self.hi_open else "不大于",
                                       self.hi,
                                       (" " + self.unit) if self.unit else "")
        return None


def _f(param, label, unit="mm", **kw) -> EditField:
    return EditField(param, label, unit, **kw)


EDIT_SCHEMA: Dict[str, tuple] = {
    "hole": (_f("diameter", "直径", lo=0.0, lo_open=True),
             _f("depth", "深度（0=通孔）", lo=0.0)),
    "hole_tapped": (_f("nominal", "公称直径", lo=0.0, lo_open=True),
                    _f("pitch", "螺距", lo=0.0, lo_open=True),
                    _f("depth", "深度（0=通孔）", lo=0.0)),
    "hole_cbore": (_f("diameter", "直径", lo=0.0, lo_open=True),
                   _f("depth", "深度（0=通孔）", lo=0.0),
                   _f("cbore_diameter", "沉孔直径", lo=0.0, lo_open=True),
                   _f("cbore_depth", "沉孔深度", lo=0.0, lo_open=True)),
    "hole_csink": (_f("diameter", "直径", lo=0.0, lo_open=True),
                   _f("depth", "深度（0=通孔）", lo=0.0),
                   _f("sink_diameter", "锥沉直径", lo=0.0, lo_open=True),
                   _f("angle", "锥角", "°", lo=0.0, hi=180.0,
                      lo_open=True, hi_open=True)),
    "dimple": (_f("diameter", "直径", lo=0.0, lo_open=True),
               _f("depth", "深度", lo=0.0, lo_open=True)),
    "boss": (_f("diameter", "直径", lo=0.0, lo_open=True),
             _f("height", "高度", lo=0.0, lo_open=True)),
    "louver": (_f("length", "长度", lo=0.0, lo_open=True),
               _f("width", "宽度", lo=0.0, lo_open=True),
               _f("height", "翻边高度", lo=0.0)),
    "knockout": (_f("diameter", "直径", lo=0.0, lo_open=True),
                 _f("web", "筋宽", lo=0.0),
                 _f("web_count", "筋数", "", lo=1.0, integer=True)),
    "gusset": (_f("length", "长度", lo=0.0, lo_open=True),
               _f("height", "高度", lo=0.0, lo_open=True),
               _f("thickness", "厚度", lo=0.0, lo_open=True)),
    "tab": (_f("length", "长度", lo=0.0, lo_open=True),
            _f("width", "宽度", lo=0.0, lo_open=True),
            _f("height", "高度", lo=0.0, lo_open=True)),
    "junction": (_f("size", "尺寸", lo=0.0, lo_open=True),),
    "cross_break": (_f("length", "长度", lo=0.0, lo_open=True),
                    _f("width", "宽度", lo=0.0, lo_open=True),
                    _f("depth", "深度", lo=0.0, lo_open=True)),
    "beam": (_f("length", "长度", lo=0.0, lo_open=True),),
    "pull": (_f("distance", "距离", nonzero=True),),
    "offset": (_f("distance", "距离", nonzero=True),),
    "draft": (_f("angle", "角度", "°", lo=-89.0, hi=89.0,
                 lo_open=True, hi_open=True, nonzero=True),),
    "shell": (_f("thickness", "厚度", lo=0.0, lo_open=True),),
    "fillet": (_f("radius", "半径", lo=0.0, lo_open=True),),
    "chamfer": (_f("distance", "距离", lo=0.0, lo_open=True),),
    # R106/B-1: a sketch body is rebuilt from its sketch, so the height is the
    # one number worth editing here (the curves come from the sketch itself)
    "sketch": (_f("height", "拉伸高度", lo=0.0, lo_open=True),),
}


@dataclass
class Feature:
    op: str
    params: Dict[str, Any] = field(default_factory=dict)
    # R104/A-1: the rigid pose that was in effect when this feature was created.
    # A selector is resolved in the body's current frame, so a feature recorded
    # *after* a move/mate must be replayed on the posed base - otherwise a
    # rotation would send the selector to the wrong face.
    pose: List[tuple] = field(default_factory=list)

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
    # R103: memo of the last replay verdict.  The structure tree asks whether a
    # body's history still reproduces its shape on *every* rebuild, and a replay
    # costs ~35 ms for three features (R103 measurement) - the memo keeps the
    # tree cheap while recomputing whenever the shape or a parameter changed.
    _verdict: dict = field(default_factory=dict, compare=False, repr=False)

    def signature(self) -> str:
        """Stable text of the parameter set (cache key ingredient)."""
        return json.dumps(self.as_dict(), sort_keys=True, default=str)

    def cached_verdict(self, shape, scale: float, compute):
        """Return compute() unless (shape identity, parameters, scale) is unchanged."""
        sig = (float(scale), self.signature())
        cache = self._verdict
        if cache.get("shape") is shape and cache.get("sig") == sig:
            return cache["value"]
        value = compute()
        self._verdict = {"shape": shape, "sig": sig, "value": value}
        return value

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
            if f.pose:
                shape = apply_pose(shape, f.pose)   # R104/A-1
            shape = _apply_one(shape, f, scale)
        return shape

    def as_dict(self) -> List[dict]:
        out = []
        for f in self.features:
            d = {"op": f.op, "params": dict(f.params)}
            if f.pose:
                d["pose"] = [list(op) for op in f.pose]
            out.append(d)
        return out

    @classmethod
    def from_dict(cls, data) -> "FeatureStack":
        return cls([Feature(d["op"], dict(d.get("params", {})),
                            [tuple(op) for op in (d.get("pose") or [])])
                    for d in data or []])

    def editable(self) -> List[dict]:
        """The (feature, parameter) pairs a user may change after the fact."""
        out: List[dict] = []
        for i, f in enumerate(self.features):
            for field in EDIT_SCHEMA.get(f.op, ()):
                if field.param not in f.params:
                    continue
                out.append({"index": i, "op": f.op, "feature": f.label(),
                            "param": field.param, "label": field.label,
                            "unit": field.unit, "value": f.params[field.param],
                            "integer": field.integer})
        return out

    def set_param(self, index: int, param: str, value):
        """Validated single-parameter edit: (old, None) or (None, reason).

        Nothing is mutated when a reason is returned, so a caller can report the
        refusal and keep the stack exactly as it was.
        """
        if not (0 <= index < len(self.features)):
            return None, "特征序号越界：%s" % index
        feature = self.features[index]
        field = next((x for x in EDIT_SCHEMA.get(feature.op, ())
                      if x.param == param), None)
        if field is None:
            return None, "%s 不支持参数 %s" % (feature.op, param)
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None, "%s 不是数字：%r" % (field.label, value)
        err = field.check(v)
        if err:
            return None, err
        old = feature.params.get(param)
        feature.params[param] = int(round(v)) if field.integer else v
        try:
            return float(old), None
        except (TypeError, ValueError):
            return None, None


def _sketch_curves(raw):
    """Normalise stored sketch curves (JSON turns tuples into lists)."""
    out = []
    for c in raw or []:
        if not c:
            continue
        kind = c[0]
        if kind in ("rect",):
            out.append((kind, tuple(c[1]), tuple(c[2])))
        elif kind in ("circle",):
            out.append((kind, tuple(c[1]), float(c[2])))
        elif kind == "line":
            out.append((kind, tuple(c[1]), tuple(c[2])))
        elif kind == "poly":
            out.append((kind, [tuple(p) for p in c[1]]))
        else:
            out.append(tuple(c))
    return out


def _apply_one(shape, feature: Feature, scale: float):
    op = feature.op
    p = feature.params
    if op == "sketch":
        # R106/B-1: a sketch body has no meaningful base - the sketch *is* the
        # feature.  The curves travel with the feature (so a reloaded project
        # replays the same body) and sketch_id keeps the live link for edits.
        from scdm import sketch as S
        axes = S.sketch_axes(p.get("plane", "xy"), tuple(p.get("origin") or (0, 0, 0)),
                             tuple(p.get("normal") or (0, 0, 1)),
                             tuple(p.get("xdir") or (1, 0, 0)))
        h = float(p.get("height", 10.0)) / scale
        if h <= 0:
            raise ValueError("草图拉伸高度必须大于 0")
        return S.extrude_sketch(_sketch_curves(p.get("curves")), h, axes=axes)
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
    if op == "gusset":
        # P295: forming feature - triangular added material on the face
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.gusset(shape, face,
                        float(p.get("length", 5.0)) / scale,
                        float(p.get("height", 3.0)) / scale,
                        float(p.get("thickness", 1.0)) / scale)
    if op == "tab":
        # P295: forming feature - rectangular local protrusion on the face
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.tab(shape, face,
                     float(p.get("length", 5.0)) / scale,
                     float(p.get("width", 3.0)) / scale,
                     float(p.get("height", 1.0)) / scale)
    if op == "junction":
        # P303: sheet-metal junction relief / bridge at a face corner
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        w = p.get("width")
        return K.junction(shape, face, float(p.get("size", 4.0)) / scale,
                          mode=p.get("mode", "release"),
                          width=(None if w is None else float(w) / scale))
    if op == "cross_break":
        # P353: sheet-metal cross-break on a face
        face = resolve_face(shape, p.get("selector", {}))
        if face is None:
            return shape
        return K.cross_break(shape, face,
                             float(p.get("length", 10.0)) / scale,
                             float(p.get("width", 2.0)) / scale,
                             float(p.get("depth", 0.3)) / scale,
                             kind=p.get("kind", "v"))
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
    if op in ("beam", "beam_polyline"):
        # P283/P291: body-creating features - the section is rebuilt from the
        # params (mm), so a stack rebuilds the same member against any base
        from scdm import beams as BEAMS
        dims = {k: float(v) / scale for k, v in p.items()
                if k in ("h", "b", "tw", "tf", "a", "t", "d")}
        if op == "beam_polyline":
            return BEAMS.beam_along(
                p.get("profile", "i"),
                tuple(float(v) / scale for v in p.get("p0", (0.0, 0.0, 0.0))),
                tuple(float(v) / scale for v in p.get("p1", (0.0, 0.0, 1.0))),
                **dims)
        return BEAMS.beam(p.get("profile", "i"),
                          float(p.get("length", 200.0)) / scale, **dims)
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

def apply_pose(shape, pose):
    """Apply a rigid pose (R103/A-1) to a shape, in list order.

    Entries: `("translate", (x, y, z))`, `("rotate", origin, axis, angle_rad)`,
    `("mirror", origin, normal)`.  A body's base shape carries the same pose as
    the body itself, so `base + stack` keeps reproducing the live shape after a
    move/rotate — the invariant the feature edit loop needs.
    """
    for op in pose or ():
        if not op:
            continue
        kind = op[0]
        if kind == "translate":
            shape = K.translate(shape, tuple(float(v) for v in op[1]))
        elif kind == "rotate":
            shape = K.rotate(shape, tuple(float(v) for v in op[1]),
                             tuple(float(v) for v in op[2]), float(op[3]))
        elif kind == "mirror":
            shape = K.mirror(shape, tuple(float(v) for v in op[1]),
                             tuple(float(v) for v in op[2]))
        elif kind == "matrix":
            # R104/A-1: a mate or an alignment computed a rigid transform
            shape = K.apply_mat4(shape, op[1])
    return shape


def replay_mismatch(rebuilt, current) -> Optional[str]:
    """Why `rebuilt` differs from `current` (None = they agree).

    The independent yardstick of the edit loop (rule 87): a feature stack is only
    allowed to drive a parameter edit when replaying it reproduces the body that
    is actually in the document.  Face count first (cheap), then volume, then the
    bounding box for non-solid shapes.
    """
    try:
        fa = len(K.explore(rebuilt, "face"))
        fb = len(K.explore(current, "face"))
    except Exception as exc:
        return "面枚举失败：%s" % exc
    if fa != fb:
        return "面数 %d != %d" % (fa, fb)
    va = vb = 0.0
    try:
        va, vb = float(K.volume(rebuilt)), float(K.volume(current))
    except Exception:
        pass
    if va > 0.0 or vb > 0.0:
        ref = max(abs(va), abs(vb), 1e-18)
        if abs(va - vb) / ref > 1e-6:
            return "体积 %.9g != %.9g" % (va, vb)
    # R104: the bounding box is checked even for solids.  Volume and face count
    # are both translation-invariant, so without this an unrecorded *move* would
    # look consistent - and the next parameter edit would silently jump the body
    # home.  Tolerance: 1 nm + 1 ppm of the model size.
    try:
        la, ha = K._vertex_bbox(rebuilt)
        lb, hb = K._vertex_bbox(current)
    except Exception:
        return None
    span = max(max(abs(float(v)) for v in (la + ha + lb + hb)), 1e-12)
    tol = 1e-9 + 1e-6 * span
    for i in range(3):
        if abs(la[i] - lb[i]) > tol or abs(ha[i] - hb[i]) > tol:
            return "包围盒不一致"
    return None


def parse_edit_lines(text, body_ids=None):
    """Parse the feature-parameter block of the parameter dialog.

    Line grammar (whitespace separated; '`#`' is accepted before the index)::

        B1 0 diameter = 8
        B1 #1 depth = 0

    Blank lines and lines starting with '#' or '//' are ignored (that is where the
    dialog puts "this body cannot be replayed" notes).  The body may be omitted
    only when the document has exactly one body.  Returns (edits, errors) with
    human-readable, line-numbered errors.
    """
    edits: List[dict] = []
    errors: List[str] = []
    ids = [str(i) for i in (body_ids or [])]
    for n, raw in enumerate((text or "").splitlines(), 1):
        ln = raw.strip()
        if not ln or ln.startswith("#") or ln.startswith("//"):
            continue
        if "=" not in ln:
            errors.append("第 %d 行缺 '='：%s" % (n, ln))
            continue
        lhs, rhs = ln.split("=", 1)
        toks = lhs.replace("#", " ").split()
        if len(toks) == 3:
            body, idx_s, param = toks
        elif len(toks) == 2 and len(ids) == 1:
            body, idx_s, param = ids[0], toks[0], toks[1]
        elif len(toks) == 2:
            errors.append("第 %d 行缺实体（格式：B1 0 diameter = 8）：%s" % (n, ln))
            continue
        else:
            errors.append("第 %d 行格式不对：%s" % (n, ln))
            continue
        try:
            index = int(idx_s)
        except ValueError:
            errors.append("第 %d 行特征序号不是整数：%s" % (n, idx_s))
            continue
        edits.append({"body": body, "index": index, "param": param,
                      "value": rhs.strip(), "line": n})
    return edits, errors


def apply_edits(kdoc, edits, scale: float = 1000.0) -> List[dict]:
    """Apply parsed edits through `KernelDoc.edit_feature` (one report each)."""
    out: List[dict] = []
    for e in edits:
        rep = kdoc.edit_feature(e["body"], e["index"], e["param"], e["value"], scale)
        rep["line"] = e.get("line")
        out.append(rep)
    return out


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

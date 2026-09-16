"""Session geometry store: named OCCT bodies + snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from scdm import kernel as K
from scdm.features import (FeatureHistory, FeatureStack, apply_pose,
                            replay_mismatch)

Vec3 = Tuple[float, float, float]


def _safe_volume(shape) -> Optional[float]:
    """Volume in kernel units, or None when the shape has no volume (R102)."""
    try:
        return float(K.volume(shape))
    except Exception:
        return None


@dataclass
class KBody:
    id: str
    name: str
    shape: Any
    color: Vec3 = (0.62, 0.66, 0.70)
    visible: bool = True
    layer: str = "默认"
    # R102/P0-1: the un-featured shape that a feature stack replays onto,
    # captured when the body enters the document. None means "unknown" and makes
    # a parameter edit refuse instead of guessing (e.g. a legacy project file
    # that stored the history but not the base, or a body changed after the last
    # recorded feature).
    base_shape: Any = None
    # R103/A-1: rigid transforms applied to the body since the base was captured.
    # The base gets the same pose at replay time, so moving a body does not break
    # the feature-edit invariant.
    base_pose: List[tuple] = field(default_factory=list)


@dataclass
class Sketch:
    id: str
    name: str
    plane: str = "xy"  # xy|zx|yz|custom
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # custom plane only
    normal: Tuple[float, float, float] = (0.0, 0.0, 1.0)   # custom plane only
    xdir: Tuple[float, float, float] = (1.0, 0.0, 0.0)     # custom plane only
    curves: List[tuple] = field(default_factory=list)  # ('line',p1,p2)|('rect',p1,p2)|('circle',c,r)|('poly',pts)
    construction: List[tuple] = field(default_factory=list)
    # P21: applied solver constraints, e.g. ('h', i, j, None) / ('dist', i, j, d)
    constraints: List[tuple] = field(default_factory=list)


@dataclass
class Component:
    """Assembly component: a named group of bodies with anchored/lock state."""
    id: str
    name: str
    body_ids: List[str] = field(default_factory=list)
    anchored: bool = False
    visible: bool = True
    lightweight: bool = False
    explosion: Optional[tuple] = None   # (dx, dy, dz) applied explosion offset
    transform: Optional[tuple] = None   # pending 4x4 pose from mate solving
    # lightweight bodies are drawn as a bounding-box wireframe (no full tessellation)

    def lightweight_body_ids(self) -> set:
        return set(self.body_ids) if self.lightweight else set()


@dataclass
class Configuration:
    """P23: a named assembly state (component visibility / body suppression)."""
    id: str
    name: str
    hidden_components: List[str] = field(default_factory=list)
    suppressed_bodies: List[str] = field(default_factory=list)
    transforms: Dict[str, tuple] = field(default_factory=dict)
    # P331: the configuration also owns a PROPERTY snapshot (material + custom
    # fields per body) and BOM quantities
    properties: Dict[str, dict] = field(default_factory=dict)
    quantities: Dict[str, int] = field(default_factory=dict)


def _replay_shape(doc, body, base, stack, scale):
    """base -> features -> trailing pose (R104/A-1 order).

    Features carry the pose they were recorded under, so the sequence is exactly
    the sequence of operations the user performed: transform, feature,
    transform, feature, ..., final transform.
    """
    shape = stack.apply(base, scale)
    pose = getattr(body, "base_pose", None)
    return apply_pose(shape, pose) if pose else shape


class KernelDoc:
    def __init__(self):
        self.bodies: List[KBody] = []
        self.sketches: List[Sketch] = []
        self.components: List[Component] = []
        self.mates: List[dict] = []   # {"type", "a": comp_id, "b": comp_id,
        #                               "value", "angle", "slide"}
        self.parametrics: List[Any] = []  # scdm.params.Parametric
        self.features: Dict[str, FeatureStack] = {}   # P5: per-body feature history
        self.instances: List[dict] = []   # P8: placed copies of a source body
        self.document_features = FeatureHistory()   # P22: multi-body features
        self.configurations: List[Configuration] = []   # P23: assembly states
        self.active_configuration: Optional[str] = None
        self.import_warnings: List[str] = []   # P30: import degradation notes
        # P47: machine-readable version of the same facts, for the GUI report
        # ({"parts", "failed_parts": [(index, name)], "unbuilt_faces",
        #   "dropped_faces", "mesh_bodies": [names], "fatal": str|None})
        self.import_report: dict = {}
        self.weldments: List[Any] = []    # P291: beam/weldment groups
        self.properties: Dict[str, Any] = {}   # P319: body id -> PartProperties
        # P323: session-only mesh artifacts (derived, rule 77: never persisted;
        # recompute on demand, only the REPORT leaves the session)
        self.meshes: Dict[str, Any] = {}
        self.param_table = None           # scdm.params.ParamTable (optional)
        # R110/A-5: the sketch the user was last editing - persisted with the
        # project so resolve_active() points at it again after a reload
        self.active_sketch: Optional[str] = None
        self.sim = None                   # scdm.simprep.SimModel (H8)
        self.named: List[dict] = []  # named selections: {"name": str, "items": [(kind,id)]}
        self.groups: List[dict] = []  # user groups: same shape as named
        self._n = 1
        self._sk = 1
        self._c = 1

    def add_parametric(self, parametric, scale: float = 1000.0) -> KBody:
        """Build the parametric body now and register it for parameter edits."""
        body = self.add_body(parametric.build(scale), name=parametric.body_name)
        parametric.body_id = body.id
        self.parametrics.append(parametric)
        self.features.setdefault(body.id, FeatureStack())
        return body

    def rebuild_parametric(self, parametric, scale: float = 1000.0) -> Optional[KBody]:
        """Re-run a parametric's builder into its body."""
        bid = getattr(parametric, "body_id", None)
        body = self.body_by_id(bid) if bid else None
        if body is None:
            return self.add_parametric(parametric, scale)
        shape = parametric.build(scale)
        stack = self.features.get(body.id)
        if stack is not None and len(stack):
            shape = stack.apply(shape, scale)   # P5: replay the feature history
        pose = getattr(body, "base_pose", None)
        if pose:                                # R104/A-1: trailing pose last
            shape = apply_pose(shape, pose)
        body.shape = shape
        return body

    # ---- P5: feature history -------------------------------------------
    def feature_stack(self, body_id: str) -> FeatureStack:
        """The (possibly empty) feature history attached to a body."""
        return self.features.setdefault(body_id, FeatureStack())

    # ---- P319: part properties (material + custom fields) ---------------
    def part_properties(self, body_id: str):
        """The body's properties, created on first use (default material)."""
        from scdm.materials import PartProperties
        p = self.properties.get(body_id)
        if p is None:
            p = PartProperties()
            self.properties[body_id] = p
        return p

    def set_material(self, body_id: str, material: str):
        """Set the body's material; returns the properties object."""
        from scdm.materials import PartProperties
        old = self.properties.get(body_id)
        p = PartProperties(material=material,
                           custom=dict(old.custom) if old is not None else {})
        self.properties[body_id] = p
        return p

    def record_feature(self, body_id: str, op: str, **params) -> None:
        """Append a replayable feature to a body's history.

        R104/A-1: the pose that is in effect *now* belongs to this feature (its
        selector was resolved in the posed frame), so it is moved from the body
        onto the feature and the body's trailing pose starts empty again.
        """
        feature = self.feature_stack(body_id).add(op, **params)
        body = self.body_by_id(body_id)
        if body is not None and getattr(body, "base_pose", None):
            feature.pose = [tuple(op) for op in body.base_pose]
            body.base_pose = []

    def clear_features(self, body_id: str) -> None:
        self.features.pop(body_id, None)


    # ---- R102/P0-1: feature parameter edits ------------------------------
    def _stack_len(self, body_id: str) -> int:
        stack = self.features.get(body_id)
        return len(stack) if stack is not None else 0

    def _base_shape(self, body, scale: float = 1000.0):
        """The shape a replay must start from.

        A parametric body replays from its *builder* (that is the live
        definition, and it is what `rebuild_parametric` already does); every
        other body replays from the base captured when it entered the document.
        """
        base = None
        for p in self.parametrics:
            if getattr(p, "body_id", None) == body.id:
                try:
                    base = p.build(scale)
                except Exception:
                    return None
                break
        if base is None:
            base = body.base_shape
        return base
    # NOTE (R104/A-1): the *trailing* pose is applied AFTER the feature stack
    # (see replay_body), because a feature's selector lives in the frame it was
    # recorded in - applying a rotation to the base first would move the
    # selector to another face.

    # ---- R103/A-1: rigid transforms keep the replay invariant ------------
    def _transform_body(self, body_id: str, op: tuple):
        """Apply one rigid op to the body *and* remember it for the base."""
        body = self.body_by_id(body_id)
        if body is None:
            return None
        body.shape = apply_pose(body.shape, [op])
        poses = getattr(body, "base_pose", None)
        if poses is None:
            body.base_pose = poses = []
        poses.append(op)
        return body

    def translate_body(self, body_id: str, vec):
        """Move a body by a vector, keeping its feature history replayable."""
        return self._transform_body(
            body_id, ("translate", tuple(float(v) for v in vec)))

    def rotate_body(self, body_id: str, origin, axis, angle_rad: float):
        """Rotate a body about an axis, keeping its history replayable."""
        return self._transform_body(
            body_id, ("rotate", tuple(float(v) for v in origin),
                      tuple(float(v) for v in axis), float(angle_rad)))

    def mirror_body(self, body_id: str, origin, normal):
        """Mirror a body in place, keeping its history replayable."""
        return self._transform_body(
            body_id, ("mirror", tuple(float(v) for v in origin),
                      tuple(float(v) for v in normal)))

    # ---- R104/A-1 + P1-1: mates and alignments as replayable poses -------
    def _component_of(self, body_id: str) -> str:
        """The component that owns a body, or the body id when it is loose."""
        for c in self.components:
            if body_id in c.body_ids:
                return c.id
        return body_id

    def pose_body(self, body_id: str, ops):
        """Apply a rigid pose (a list of apply_pose ops) and remember it."""
        body = self.body_by_id(body_id)
        if body is None:
            return None
        body.shape = apply_pose(body.shape, ops)
        poses = getattr(body, "base_pose", None)
        if poses is None:
            body.base_pose = poses = []
        poses.extend(ops)
        return body

    def align_body(self, body_id: str, kind: str, moving_face, target_face):
        """Face-flush / axis-align a body and record the transform (A-1).

        The transform itself comes from the kernel (`align_faces_matrix` /
        `align_axes_matrix`), so the pose that is remembered is the *same*
        matrix the shape got - a replay reproduces the aligned body.
        """
        if kind == "axes":
            m = K.align_axes_matrix(moving_face, target_face)
        elif kind == "faces":
            m = K.align_faces_matrix(moving_face, target_face)
        else:
            raise ValueError("未知对齐类型：%s" % kind)
        return self.pose_body(body_id, [("matrix", m)])

    def pair_dof_used(self, a: str, b: str) -> int:
        """Degrees of freedom already fixed by the mates of this pair (P1-1).

        Counted from `mates.DOFS` (the single source): a mate that leaves D
        degrees of freedom fixes 6 - D.
        """
        from scdm import mates as MATES
        key = {a, b}
        used = 0
        for m in self.mates:
            if {m.get("a"), m.get("b")} == key:
                used += 6 - int(MATES.DOFS.get(m.get("type"), 6))
        return used

    def add_mate(self, mtype, a, b, value=0.0, angle=0.0, slide=0.0):
        """Register a mate; refuses over-constraint with the numbers (P1-1).

        Conservative on purpose: the solver applies one mate at a time, so two
        mates that jointly fix more than six degrees would silently let the
        last one win - that is refused instead.
        """
        from scdm import mates as MATES
        if mtype not in MATES.DOFS:
            return None, "未知配合类型：%s" % mtype
        removes = 6 - int(MATES.DOFS[mtype])
        used = self.pair_dof_used(a, b)
        if used + removes > 6:
            return None, ("过约束：体对 %s/%s 已固定 %d 个自由度，再加 %s（%d 个）超过 6"
                          % (a, b, used, mtype, removes))
        mate = {"type": mtype, "a": a, "b": b, "value": float(value),
                "angle": float(angle), "slide": float(slide)}
        self.mates.append(mate)
        return mate, ""

    def mate_bodies(self, mtype, body_a, face_a, body_b, face_b,
                    value=0.0, angle=0.0, slide=0.0, scale: float = 1000.0) -> dict:
        """Solve one mate between two faces and move `body_b` (P1-1).

        `body_a` / `face_a` is the target, `body_b` / `face_b` the moving side
        (the solver positions B's frame onto A's).  Returns
        {"ok","reason","dof","removes","matrix","mate"}; nothing moves and no
        mate is recorded when the pair would be over-constrained.
        """
        from scdm import mates as MATES
        rep = {"ok": False, "reason": "", "dof": None, "removes": None,
               "matrix": None, "mate": None, "type": mtype}
        if body_a is None or body_b is None or body_a is body_b:
            rep["reason"] = "配合需要不同实体上的两个面"
            return rep
        if mtype not in MATES.DOFS:
            rep["reason"] = "未知配合类型：%s" % mtype
            return rep
        comp_a = self._component_of(body_a.id)
        comp_b = self._component_of(body_b.id)
        mate, why = self.add_mate(mtype, comp_a, comp_b, value=value,
                                  angle=angle, slide=slide)
        if mate is None:
            rep["reason"] = why
            return rep
        try:
            frame_a = MATES.frame_of(face_a)
            frame_b = MATES.frame_of(face_b)
            m = MATES.solve_transform(MATES.Mate(mtype, frame_a, frame_b,
                                                 value=value, angle=angle,
                                                 slide=slide))
        except Exception as exc:
            self.mates.remove(mate)
            rep["reason"] = "求解失败：%s" % exc
            return rep
        self.pose_body(body_b.id, [("matrix", m)])
        rep.update(ok=True, dof=int(MATES.DOFS[mtype]),
                   removes=6 - int(MATES.DOFS[mtype]), matrix=m, mate=mate)
        return rep

    def can_replay(self, body_id: str, scale: float = 1000.0):
        """(ok, reason): can this body's feature history drive a parameter edit?

        The recorded stack must reproduce the body that is actually in the
        document; a body changed after its last recorded feature (boolean,
        import, an unrecorded tool) fails here and the edit is refused with the
        measured difference instead of silently rebuilding a different body.
        """
        body = self.body_by_id(body_id)
        if body is None:
            return False, "未知实体：%s" % body_id
        stack = self.feature_stack(body_id)
        if not len(stack):
            return False, "该实体没有特征历史"
        base = self._base_shape(body, scale)
        if base is None:
            return False, "缺少基准形状（未记录特征前的形状）"

        def _verdict():
            try:
                rebuilt = _replay_shape(self, body, base, stack, scale)
            except Exception as exc:
                return False, "重放失败：%s" % exc
            if rebuilt is None:
                return False, "重放失败：内核返回空形状"
            why = replay_mismatch(rebuilt, body.shape)
            if why:
                return False, "实体与特征历史不一致（%s）" % why
            return True, ""

        # R103: memoised - the tree asks for this on every rebuild
        return stack.cached_verdict(body.shape, scale, _verdict)

    def replay_body(self, body_id: str, scale: float = 1000.0):
        """Rebuild a body from its base shape + feature stack."""
        body = self.body_by_id(body_id)
        if body is None:
            return False, "未知实体：%s" % body_id
        stack = self.feature_stack(body_id)
        if not len(stack):
            return False, "该实体没有特征历史"
        base = self._base_shape(body, scale)
        if base is None:
            return False, "缺少基准形状（未记录特征前的形状）"
        try:
            shape = _replay_shape(self, body, base, stack, scale)
        except Exception as exc:
            return False, "重放失败：%s" % exc
        if shape is None:
            return False, "重放失败：内核返回空形状"
        body.shape = shape
        return True, ""

    def edit_feature(self, body_id: str, index: int, param: str, value,
                     scale: float = 1000.0) -> dict:
        """Change one recorded feature parameter and replay the body.

        Atomic: either the parameter *and* the geometry move together, or
        neither does (a failed replay restores both).  The report carries the
        volume before/after so a caller can check it against a closed form.
        """
        rep = {"ok": False, "body": body_id, "index": index, "param": param,
               "value": value, "old": None, "op": None, "label": "",
               "reason": "", "volume_before": None, "volume_after": None}
        body = self.body_by_id(body_id)
        if body is None:
            rep["reason"] = "未知实体：%s" % body_id
            return rep
        stack = self.feature_stack(body_id)
        if not (0 <= index < len(stack)):
            rep["reason"] = "特征序号越界：%s" % index
            return rep
        feature = stack.features[index]
        rep["op"] = feature.op
        rep["label"] = feature.label()
        ok, why = self.can_replay(body_id, scale)
        if not ok:
            rep["reason"] = why
            return rep
        rep["volume_before"] = _safe_volume(body.shape)
        saved_shape = body.shape
        saved_params = dict(feature.params)
        old, err = stack.set_param(index, param, value)
        if err:
            rep["reason"] = err
            return rep
        rep["old"] = old
        ok, why = self.replay_body(body_id, scale)
        if not ok:
            feature.params.clear()
            feature.params.update(saved_params)
            body.shape = saved_shape
            rep["reason"] = why
            return rep
        rep["ok"] = True
        rep["volume_after"] = _safe_volume(body.shape)
        return rep

    # ---- P23: assembly configurations -----------------------------------
    def add_configuration(self, name: Optional[str] = None,
                          hidden_components=None, suppressed_bodies=None,
                          transforms=None, properties=None,
                          quantities=None) -> Configuration:
        cid = "CFG%d" % (len(self.configurations) + 1)
        cfg = Configuration(cid, name or ("配置%d" % (len(self.configurations) + 1)),
                            list(hidden_components or []),
                            list(suppressed_bodies or []),
                            dict(transforms or {}),
                            {k: dict(v) for k, v in (properties or {}).items()},
                            {k: int(v) for k, v in (quantities or {}).items()})
        self.configurations.append(cfg)
        return cfg

    def capture_configuration(self, name: Optional[str] = None) -> Configuration:
        """Snapshot the CURRENT visibility/suppression/attribute state.

        P331: the snapshot includes every body's part properties (material +
        custom fields) and a BOM quantity of 1, so a configuration is a full
        state, not just a visibility set.
        """
        from scdm.materials import PartProperties
        cfg = self.add_configuration(name)
        for c in self.components:
            if not c.visible:
                cfg.hidden_components.append(c.id)
        for b in self.bodies:
            if not b.visible:
                cfg.suppressed_bodies.append(b.id)
            # a configuration is a FULL state: every body gets a property
            # snapshot (default material when unset) and a quantity
            p = self.properties.get(b.id) or PartProperties()
            cfg.properties[b.id] = p.to_dict()
            cfg.quantities[b.id] = 1
        return cfg

    # ---- P331: configuration-driven attributes and BOM -------------------
    def set_config_property(self, ref: str, body_id: str, material=None,
                            custom=None) -> Configuration:
        """Override a body's part properties INSIDE a configuration."""
        from scdm.materials import PartProperties
        cfg = self.configuration_by(ref)
        if cfg is None:
            raise ValueError("未知配置：%s" % ref)
        if self.body_by_id(body_id) is None:
            raise ValueError("未知实体：%s" % body_id)
        base = cfg.properties.get(body_id)
        # read the live properties WITHOUT creating them (part_properties would
        # materialise a default entry as a side effect of an override)
        cur = (PartProperties.from_dict(base) if base
               else (self.properties.get(body_id) or PartProperties()))
        fresh = PartProperties(material=material or cur.material,
                               custom=dict(cur.custom if custom is None
                                           else custom))
        cfg.properties[body_id] = fresh.to_dict()
        return cfg

    def set_config_quantity(self, ref: str, body_id: str, qty: int) -> Configuration:
        """BOM quantity of a body inside a configuration (0 = not counted)."""
        cfg = self.configuration_by(ref)
        if cfg is None:
            raise ValueError("未知配置：%s" % ref)
        if self.body_by_id(body_id) is None:
            raise ValueError("未知实体：%s" % body_id)
        q = int(qty)
        if q < 0:
            raise ValueError("数量不能为负：%s" % qty)
        cfg.quantities[body_id] = q
        return cfg

    def properties_for(self, ref: Optional[str] = None) -> Dict[str, Any]:
        """body_id -> PartProperties with the configuration's overrides applied."""
        from scdm.materials import PartProperties
        out = {b.id: (self.properties.get(b.id) or PartProperties())
               for b in self.bodies}
        if ref is None:
            return out
        cfg = self.configuration_by(ref)
        if cfg is None:
            raise ValueError("未知配置：%s" % ref)
        for bid, data in cfg.properties.items():
            if bid in out:
                out[bid] = PartProperties.from_dict(data)
        return out

    def bom(self, ref: Optional[str] = None, scale: float = 1000.0) -> List[dict]:
        """P331: BOM rows for a configuration (None = the live state)."""
        from scdm import materials as MAT
        cfg = self.configuration_by(ref) if ref is not None else None
        if ref is not None and cfg is None:
            raise ValueError("未知配置：%s" % ref)
        return MAT.bom_rows(self.bodies, self.properties_for(ref), scale,
                            quantities=(dict(cfg.quantities) if cfg else None))

    def config_issues(self, ref: str) -> List[dict]:
        """Dangling references inside a configuration (deleted bodies)."""
        cfg = self.configuration_by(ref)
        if cfg is None:
            raise ValueError("未知配置：%s" % ref)
        live = {b.id for b in self.bodies}
        out = [{"body_id": bid, "kind": "property"}
               for bid in cfg.properties if bid not in live]
        out += [{"body_id": bid, "kind": "quantity"}
                for bid in cfg.quantities if bid not in live]
        return sorted(out, key=lambda d: (d["body_id"], d["kind"]))

    def prune_config(self, ref: str) -> int:
        """Drop dangling references; returns how many were removed."""
        cfg = self.configuration_by(ref)
        if cfg is None:
            raise ValueError("未知配置：%s" % ref)
        live = {b.id for b in self.bodies}
        removed = 0
        for store in (cfg.properties, cfg.quantities):
            for bid in [k for k in store if k not in live]:
                del store[bid]
                removed += 1
        return removed

    def configuration_by(self, ref: str) -> Optional[Configuration]:
        for c in self.configurations:
            if c.id == ref or c.name == ref:
                return c
        return None

    def apply_configuration(self, ref: str) -> int:
        """Apply a named configuration; returns how many objects changed."""
        cfg = self.configuration_by(ref)
        if cfg is None:
            return 0
        changed = 0
        hidden = set(cfg.hidden_components)
        for c in self.components:
            vis = c.id not in hidden
            if c.visible != vis:
                changed += 1
            c.visible = vis
        # P331: the property snapshot travels with the configuration
        from scdm.materials import PartProperties
        for bid, data in cfg.properties.items():
            if self.body_by_id(bid) is None:
                continue                      # dangling reference: skip, do not crash
            fresh = PartProperties.from_dict(data)
            if self.properties.get(bid) != fresh:
                changed += 1
            self.properties[bid] = fresh
        suppressed = set(cfg.suppressed_bodies)
        for b in self.bodies:
            vis = b.id not in suppressed
            if b.visible != vis:
                changed += 1
            b.visible = vis
        for cid, mat in cfg.transforms.items():
            comp = self.component_by_id(cid)
            if comp is not None:
                comp.transform = tuple(mat)
                changed += 1
        self.active_configuration = cfg.id
        return changed

    # ---- P22: document-level (multi-body) feature history ----------------
    def record_doc_feature(self, op: str, inputs, **params):
        """Append a whole-body feature (pattern/mirror/combine/split)."""
        return self.document_features.add(op, inputs, **params)

    def replay_document(self, scale: float = 1000.0, apply: bool = False):
        """Rebuild parametric bases + per-body features + doc features.

        Returns the live shape list; with apply=True the bodies are replaced
        (names and ids are regenerated, order preserved).
        """
        bases = []
        names = []
        if self.parametrics:
            for p in self.parametrics:
                shape = p.build(scale)
                stack = self.features.get(getattr(p, "body_id", ""))
                if stack is not None and len(stack):
                    shape = stack.apply(shape, scale)
                bases.append(shape)
                names.append(p.body_name)
        else:
            for b in self.bodies:
                shape = b.shape
                stack = self.features.get(b.id)
                if stack is not None and len(stack):
                    shape = stack.apply(shape, scale)
                bases.append(shape)
                names.append(b.name)
        shapes = self.document_features.replay(bases, scale)
        if apply:
            self.bodies = []
            for i, sh in enumerate(shapes):
                nm = names[i] if i < len(names) else "特征体%d" % (i + 1)
                self.add_body(sh, name=nm)
        return shapes

    @property
    def notes(self) -> List[dict]:
        """Viewport note annotations (H8 markup notes projected + legacy)."""
        out = list(getattr(self, "_legacy_notes", []))
        sim = getattr(self, "sim", None)
        if sim is not None:
            out += [{"text": m.text, "pos": m.point} for m in sim.markups]
        return out

    @notes.setter
    def notes(self, value):
        """Accept legacy pickled note dicts; migrated into sim.markups."""
        self._legacy_notes = list(value or [])
        if self._legacy_notes and self.sim is None:
            from scdm.simprep import SimModel
            self.sim = SimModel()
        for nd in self._legacy_notes:
            self.sim.add_markup(nd.get("text", ""),
                                tuple(nd.get("pos") or (0, 0, 0)))
        self._legacy_notes = []

    def add_component(self, name: Optional[str] = None, body_ids: Optional[List[str]] = None) -> Component:
        cid = f"C{self._c}"
        self._c += 1
        comp = Component(id=cid, name=name or f"组件 {self._c - 1}",
                         body_ids=list(body_ids or []))
        self.components.append(comp)
        return comp

    def component_by_id(self, cid: str) -> Optional[Component]:
        for c in self.components:
            if c.id == cid:
                return c
        return None

    def remove_component(self, cid: str) -> Optional[Component]:
        c = self.component_by_id(cid)
        if c:
            self.components.remove(c)
        return c

    def bodies_of_component(self, cid: str) -> List[KBody]:
        c = self.component_by_id(cid)
        if c is None:
            return []
        return [b for b in self.bodies if b.id in c.body_ids]

    def add_body(self, shape, name: Optional[str] = None, color: Vec3 = (0.62, 0.66, 0.70)) -> KBody:
        bid = f"B{self._n}"
        self._n += 1
        body = KBody(id=bid, name=name or f"实体 {self._n - 1}", shape=shape,
                     color=color, base_shape=shape)
        self.bodies.append(body)
        return body

    def add_sketch(self, plane: str = "xy", name: Optional[str] = None) -> Sketch:
        sid = f"S{self._sk}"
        self._sk += 1
        sk = Sketch(id=sid, name=name or f"草图 {self._sk - 1}", plane=plane)
        self.sketches.append(sk)
        return sk

    def body_by_id(self, bid: str) -> Optional[KBody]:
        for b in self.bodies:
            if b.id == bid:
                return b
        return None

    def remove(self, bid: str) -> Optional[KBody]:
        b = self.body_by_id(bid)
        if b:
            self.bodies.remove(b)
        # P8: drop instance links that referenced (or were placed as) this body
        self.instances = [i for i in self.instances
                          if i.get("body_id") != bid and i.get("source") != bid]
        return b

    # ---- P8: same-part instances ---------------------------------------
    def add_instance(self, source_body_id: str, transform=None,
                     name: Optional[str] = None) -> Optional[KBody]:
        """Place a copy of a source body (the part definition) at a transform.

        The copy is a full body; the link back to the source is what lets
        sync_instances() propagate a later edit to every placement.
        """
        src = self.body_by_id(source_body_id)
        if src is None:
            return None
        shape = (K.apply_mat4(src.shape, transform) if transform is not None
                 else K.copy_shape(src.shape))
        body = self.add_body(shape, name=name or (src.name + " 实例"))
        self.instances.append({
            "id": f"I{len(self.instances) + 1}", "source": source_body_id,
            "body_id": body.id, "transform": transform, "name": body.name})
        return body

    def instances_of(self, source_body_id: str) -> List[dict]:
        """Every placement derived from a source body."""
        return [i for i in self.instances if i.get("source") == source_body_id]

    def sync_instances(self, source_body_id: str) -> int:
        """Re-derive every instance of a source body from its current shape."""
        src = self.body_by_id(source_body_id)
        if src is None:
            return 0
        n = 0
        for inst in self.instances_of(source_body_id):
            b = self.body_by_id(inst["body_id"])
            if b is None:
                continue
            b.shape = (K.apply_mat4(src.shape, inst["transform"])
                       if inst.get("transform") is not None
                       else K.copy_shape(src.shape))
            n += 1
        return n


    def snapshot(self):
        """Undo/redo state: body shapes *and* the modelling history (R102).

        Callers treat this as an opaque token.  The dict form exists because
        undoing a *parameter* edit must restore the recorded parameters together
        with the geometry: a stack that describes the old shape while the body
        shows the new one would be a lie (and would make the next edit refuse).
        A legacy list of 5-tuples is still accepted by `restore`.
        """
        if not K.available():
            return {"bodies": [], "features": {}, "bases": {}, "poses": {},
                    "mates": []}
        return {
            "bodies": [(b.id, b.name, K.dumps_brep(b.shape), b.color, b.visible)
                       for b in self.bodies],
            "features": {bid: st.as_dict()
                         for bid, st in self.features.items() if len(st)},
            "bases": {b.id: K.dumps_brep(b.base_shape) for b in self.bodies
                      if b.base_shape is not None and self._stack_len(b.id)},
            "poses": {b.id: [list(op) for op in b.base_pose] for b in self.bodies
                      if getattr(b, "base_pose", None) and self._stack_len(b.id)},
            # R104/P1-1: the mate list is the DOF budget bookkeeping, so an undo
            # has to take it back together with the geometry
            "mates": [dict(m) for m in self.mates],
        }

    def restore(self, snap) -> None:
        if isinstance(snap, dict):
            rows = snap.get("bodies") or []
            feats = snap.get("features") or {}
            bases = snap.get("bases") or {}
            poses = snap.get("poses") or {}
            mates = snap.get("mates") or []
        else:                      # legacy: [(id, name, brep, color, visible)]
            rows, feats, bases, poses = list(snap or []), {}, {}, {}
            mates = []
        self.bodies = []
        max_n = 1
        for bid, name, blob, color, vis in rows:
            sh = K.loads_brep(blob)
            base = K.loads_brep(bases[bid]) if bid in bases else None
            self.bodies.append(KBody(id=bid, name=name, shape=sh, color=color,
                                     visible=vis, base_shape=base,
                                     base_pose=[tuple(op) for op in poses.get(bid, [])]))
            try:
                max_n = max(max_n, int(bid[1:]) + 1)
            except Exception:
                pass
        self._n = max_n
        self.features = {bid: FeatureStack.from_dict(data)
                         for bid, data in feats.items()}
        if isinstance(snap, dict):
            self.mates = [dict(m) for m in mates]

    def compound(self):
        if not self.bodies:
            return None
        if len(self.bodies) == 1:
            return self.bodies[0].shape
        return K.compound([b.shape for b in self.bodies])

"""Session geometry store: named OCCT bodies + snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from scdm import kernel as K
from scdm.features import FeatureHistory, FeatureStack

Vec3 = Tuple[float, float, float]


@dataclass
class KBody:
    id: str
    name: str
    shape: Any
    color: Vec3 = (0.62, 0.66, 0.70)
    visible: bool = True
    layer: str = "默认"


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
        """Append a replayable feature to a body's history."""
        self.feature_stack(body_id).add(op, **params)

    def clear_features(self, body_id: str) -> None:
        self.features.pop(body_id, None)

    # ---- P23: assembly configurations -----------------------------------
    def add_configuration(self, name: Optional[str] = None,
                          hidden_components=None, suppressed_bodies=None,
                          transforms=None) -> Configuration:
        cid = "CFG%d" % (len(self.configurations) + 1)
        cfg = Configuration(cid, name or ("配置%d" % (len(self.configurations) + 1)),
                            list(hidden_components or []),
                            list(suppressed_bodies or []),
                            dict(transforms or {}))
        self.configurations.append(cfg)
        return cfg

    def capture_configuration(self, name: Optional[str] = None) -> Configuration:
        """Snapshot the CURRENT visibility/suppression state as a configuration."""
        cfg = self.add_configuration(name)
        for c in self.components:
            if not c.visible:
                cfg.hidden_components.append(c.id)
        for b in self.bodies:
            if not b.visible:
                cfg.suppressed_bodies.append(b.id)
        return cfg

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
        body = KBody(id=bid, name=name or f"实体 {self._n - 1}", shape=shape, color=color)
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

    def snapshot(self) -> List[tuple]:
        if not K.available():
            return []
        return [
            (b.id, b.name, K.dumps_brep(b.shape), b.color, b.visible)
            for b in self.bodies
        ]

    def restore(self, snap: List[tuple]) -> None:
        self.bodies = []
        max_n = 1
        for bid, name, blob, color, vis in snap:
            sh = K.loads_brep(blob)
            self.bodies.append(KBody(id=bid, name=name, shape=sh, color=color, visible=vis))
            try:
                max_n = max(max_n, int(bid[1:]) + 1)
            except Exception:
                pass
        self._n = max_n

    def compound(self):
        if not self.bodies:
            return None
        if len(self.bodies) == 1:
            return self.bodies[0].shape
        return K.compound([b.shape for b in self.bodies])

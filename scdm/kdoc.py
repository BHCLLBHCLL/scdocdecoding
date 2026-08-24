"""Session geometry store: named OCCT bodies + snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from scdm import kernel as K

Vec3 = Tuple[float, float, float]


@dataclass
class KBody:
    id: str
    name: str
    shape: Any
    color: Vec3 = (0.62, 0.66, 0.70)
    visible: bool = True


@dataclass
class Sketch:
    id: str
    name: str
    plane: str = "xy"  # xy|zx|yz
    curves: List[tuple] = field(default_factory=list)  # ('line',p1,p2)|('rect',p1,p2)|('circle',c,r)
    construction: List[tuple] = field(default_factory=list)


class KernelDoc:
    def __init__(self):
        self.bodies: List[KBody] = []
        self.sketches: List[Sketch] = []
        self._n = 1
        self._sk = 1

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
        return b

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

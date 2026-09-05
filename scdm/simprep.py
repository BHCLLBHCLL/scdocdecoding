"""H8: Simulation-prep / Markup data model.

Loads, supports (fixtures), contacts and 3D-markup notes are DATA objects
attached to bodies/faces — the ANSYS solve happens elsewhere, but the
objects must live in the document and persist (io_project pickle).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Vec3 = Tuple[float, float, float]

LOAD_TYPES = ("force", "pressure", "torque")
SUPPORT_TYPES = ("fixed", "pin", "roller")


@dataclass
class Load:
    """Force (N) / pressure (MPa) applied on a body face."""
    id: str
    kind: str                     # LOAD_TYPES
    body_id: str
    face_index: int
    vector: Vec3 = (0.0, 0.0, -100.0)   # direction*magnitude (force)
    magnitude: float = 0.0              # pressure/torque scalar

    def describe(self) -> str:
        if self.kind == "force":
            return (f"力 {self.magnitude:g}N @ 面{self.face_index} "
                    f"({self.vector[0]:g},{self.vector[1]:g},{self.vector[2]:g})")
        return f"{self.kind} {self.magnitude:g} @ 面{self.face_index}"


@dataclass
class Support:
    """Support (fixture) on a body face."""
    id: str
    kind: str                     # SUPPORT_TYPES
    body_id: str
    face_index: int

    def describe(self) -> str:
        return f"{self.kind} @ 面{self.face_index}"


@dataclass
class Contact:
    """Bonded/no-separation contact pair between two faces."""
    id: str
    kind: str                     # "bonded", "no_separation"
    body_a: str
    face_a: int
    body_b: str
    face_b: int

    def describe(self) -> str:
        return (f"{self.kind}: {self.body_a}/面{self.face_a} ↔ "
                f"{self.body_b}/面{self.face_b}")


@dataclass
class MarkupNote:
    """3D-markup note: text anchored at a world point with a camera view."""
    id: str
    text: str
    point: Vec3
    camera: Optional[dict] = None   # {"pos","focal","up"} — restored view


@dataclass
class SimModel:
    """All simulation-prep objects of a document."""
    loads: List[Load] = field(default_factory=list)
    supports: List[Support] = field(default_factory=list)
    contacts: List[Contact] = field(default_factory=list)
    markups: List[MarkupNote] = field(default_factory=list)
    _n: int = 0

    def _next_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def add_load(self, kind: str, body_id: str, face_index: int,
                 vector: Vec3 = (0, 0, -100), magnitude: float = 0.0) -> Load:
        ld = Load(self._next_id("L"), kind, body_id, face_index,
                  vector, magnitude)
        self.loads.append(ld)
        return ld

    def add_support(self, kind: str, body_id: str, face_index: int) -> Support:
        sp = Support(self._next_id("S"), kind, body_id, face_index)
        self.supports.append(sp)
        return sp

    def add_contact(self, kind: str, body_a: str, face_a: int,
                    body_b: str, face_b: int) -> Contact:
        ct = Contact(self._next_id("CT"), kind, body_a, face_a,
                     body_b, face_b)
        self.contacts.append(ct)
        return ct

    def add_markup(self, text: str, point: Vec3,
                   camera: Optional[dict] = None) -> MarkupNote:
        mk = MarkupNote(self._next_id("M"), text, point, camera)
        self.markups.append(mk)
        return mk

    def summary(self) -> str:
        return (f"载荷 {len(self.loads)}、支撑 {len(self.supports)}、"
                f"接触 {len(self.contacts)}、标记 {len(self.markups)}")

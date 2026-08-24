"""Selection set and topology filters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Sel = Tuple[str, str]  # (kind, id)  kind in body|face|edge|vertex|plane|origin


@dataclass
class SelectionModel:
    allow_vertex: bool = True
    allow_edge: bool = True
    allow_face: bool = True
    allow_body: bool = True
    allow_component: bool = True
    snap_grid: bool = False
    snap_end: bool = True
    snap_mid: bool = True
    items: List[Sel] = field(default_factory=list)

    def clear(self) -> None:
        self.items.clear()

    def set_one(self, kind: str, sid: str) -> None:
        self.items = [(kind, sid)]

    def toggle(self, kind: str, sid: str) -> None:
        key = (kind, sid)
        if key in self.items:
            self.items.remove(key)
        else:
            self.items.append(key)

    def primary(self) -> Optional[Sel]:
        return self.items[0] if self.items else None

    def allows(self, kind: str) -> bool:
        return {
            "vertex": self.allow_vertex,
            "edge": self.allow_edge,
            "face": self.allow_face,
            "body": self.allow_body,
            "component": self.allow_component,
            "plane": True,
            "origin": True,
        }.get(kind, True)

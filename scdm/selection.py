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
    snap_coin: bool = False    # P19: 重合 - snap to existing sketch anchors
    # R112/A-2: the snap radius in millimetres (world units).  The same number
    # is the weld tolerance, so "it snapped" and "it welded" cannot disagree
    snap_radius_mm: float = 5.0
    # R112/A-2: welding is a *repair* tolerance, not a drawing aid.  Snapping a
    # corner and welding two profiles are different questions: a 5mm weld
    # tolerance merges profiles 2mm apart (measured), so this stays its own
    # number with the historic 0.1mm default
    weld_tol_mm: float = 0.1
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

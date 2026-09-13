"""P299/R55: 图纸标注 —— 引线（leader）与形位公差框（GD&T）。

Annotations are DRAWING objects: they never touch the model.  Their anchor is a
view point snapped through `scdm.snaptools` exactly like a dimension handle, and
they leave the building through the sheet export (SVG/DXF) instead of becoming
geometry - which is why the acceptance asserts BOTH halves: the anchor lands on
the closed-form target, and the model's volume/bbox does not move.

Unlike a dimension (one degree of freedom: the offset along its normal), an
annotation anchor is a FREE 2D point (rule 69: snap the degree of freedom the
model actually has - here the 2D point, there the scalar offset).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]

GD_T_SYMBOLS = ("position", "flatness", "straightness", "circularity",
                "parallelism", "perpendicularity", "angularity",
                "concentricity", "symmetry", "profile", "runout")

GD_T_GLYPHS = {
    "position": "⌖", "flatness": "⏥", "straightness": "⏤", "circularity": "○",
    "parallelism": "∥", "perpendicularity": "⊥", "angularity": "∠",
    "concentricity": "◎", "symmetry": "⌯", "profile": "⌒", "runout": "↗",
}


def _pt(p) -> Point:
    return (float(p[0]), float(p[1]))


@dataclass
class Leader:
    """P299: 引线标注 —— 箭头锚点 +（可选）折点 + 文本。"""

    view: str
    anchor: Point
    text: str = ""
    elbow: Optional[Point] = None
    tail: float = 0.015            # 水平尾段长度（视图坐标，米）

    def validate(self) -> "Leader":
        if not str(self.text).strip():
            raise ValueError("引线标注必须有文字")
        if float(self.tail) < 0:
            raise ValueError("引线尾段长度不能为负")
        self.anchor = _pt(self.anchor)
        if self.elbow is not None:
            self.elbow = _pt(self.elbow)
        return self

    def points(self) -> List[Point]:
        """引线折线：锚点 →（折点）→ 尾端。"""
        self.validate()
        end = self.elbow if self.elbow is not None else self.anchor
        return ([self.anchor] + ([self.elbow] if self.elbow is not None else [])
                + [(end[0] + float(self.tail), end[1])])

    def text_at(self) -> Point:
        p = self.points()[-1]
        return (p[0], p[1] + 0.002)

    def move_to(self, p) -> None:
        """整体平移：折点保持与锚点的相对位置（拖动只改标注，不改几何）。"""
        p = _pt(p)
        dx = p[0] - self.anchor[0]
        dy = p[1] - self.anchor[1]
        self.anchor = p
        if self.elbow is not None:
            self.elbow = (self.elbow[0] + dx, self.elbow[1] + dy)

    def to_dict(self) -> Dict:
        self.validate()
        return {"kind": "leader", "view": self.view, "anchor": list(self.anchor),
                "text": str(self.text),
                "elbow": (list(self.elbow) if self.elbow is not None else None),
                "tail": float(self.tail)}

    @classmethod
    def from_dict(cls, data) -> "Leader":
        elbow = data.get("elbow")
        return cls(view=data.get("view", ""), anchor=tuple(data.get("anchor") or (0, 0)),
                   text=data.get("text", ""),
                   elbow=(tuple(elbow) if elbow is not None else None),
                   tail=data.get("tail", 0.015)).validate()


@dataclass
class GdtFrame:
    """P299: 形位公差框 —— 符号 / 公差值 / 基准。"""

    view: str
    anchor: Point
    symbol: str = "position"
    value: float = 0.05            # mm（与尺寸标注同单位）
    datums: List[str] = field(default_factory=list)
    width: float = 0.028           # 框尺寸（视图坐标，米）
    height: float = 0.009

    def validate(self) -> "GdtFrame":
        sym = str(self.symbol).lower()
        if sym not in GD_T_SYMBOLS:
            raise ValueError("形位公差符号未知：%s（可选 %s）"
                             % (self.symbol, "/".join(GD_T_SYMBOLS)))
        self.symbol = sym
        self.value = float(self.value)
        if self.value <= 0:
            raise ValueError("形位公差值必须为正")
        self.datums = [str(d).strip() for d in (self.datums or []) if str(d).strip()]
        if any(len(d) > 3 for d in self.datums):
            raise ValueError("基准代号过长（最多 3 个字符）")
        if float(self.width) <= 0 or float(self.height) <= 0:
            raise ValueError("形位公差框尺寸必须为正")
        self.anchor = _pt(self.anchor)
        return self

    def label(self) -> str:
        sym = GD_T_GLYPHS.get(self.symbol, self.symbol)
        txt = "%s Ø%g" % (sym, self.value)
        if self.datums:
            txt += " " + " ".join(self.datums)
        return txt

    def corners(self) -> List[Point]:
        """框的四角（锚点是框的左下角）。"""
        self.validate()
        x0, y0 = self.anchor
        x1, y1 = x0 + float(self.width), y0 + float(self.height)
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def move_to(self, p) -> None:
        self.anchor = _pt(p)

    def to_dict(self) -> Dict:
        self.validate()
        return {"kind": "gdt", "view": self.view, "anchor": list(self.anchor),
                "symbol": self.symbol, "value": self.value,
                "datums": list(self.datums), "width": float(self.width),
                "height": float(self.height)}

    @classmethod
    def from_dict(cls, data) -> "GdtFrame":
        return cls(view=data.get("view", ""),
                   anchor=tuple(data.get("anchor") or (0, 0)),
                   symbol=data.get("symbol", "position"),
                   value=data.get("value", 0.05),
                   datums=list(data.get("datums") or []),
                   width=data.get("width", 0.028),
                   height=data.get("height", 0.009)).validate()


def annotation_geometry(a):
    """(segments, text, text_at) in view coordinates for any annotation."""
    if isinstance(a, Leader):
        pts = a.points()
        return (list(zip(pts, pts[1:])), str(a.text), a.text_at())
    c = a.corners()
    segs = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    label = a.label()
    return (segs, label, (c[0][0] + 0.002, c[0][1] + float(a.height) * 0.72))


def annotation_layer(a) -> str:
    return "NOTE" if isinstance(a, Leader) else "GDT"


def from_dict(data):
    """Rebuild whichever annotation `data` describes."""
    if str(data.get("kind", "")).lower() == "gdt":
        return GdtFrame.from_dict(data)
    return Leader.from_dict(data)

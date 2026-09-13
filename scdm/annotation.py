"""P299/P307: 图纸标注 —— 引线（leader）、形位公差框（GD&T）、基准符号（datum）。

Annotations are DRAWING objects: they never touch the model.  Their anchor is a
view point snapped through `scdm.snaptools` exactly like a dimension handle, and
they leave the building through the sheet export (SVG/DXF) instead of becoming
geometry - which is why the acceptance asserts BOTH halves: the anchor lands on
the closed-form target, and the model's volume/bbox does not move.

P307 adds the second batch: arrow styles (solid/open/none) with a closed-form
arrow head, text height, composite (multi-row) tolerance frames with internal
cell dividers, and datum symbols (A/B/C, optionally a datum target).  Every
style field rides through `to_dict/from_dict` so the sheet reopens identical.
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

ARROW_STYLES = ("solid", "open", "none")

ARROW_LENGTH = 2.5        # 相对字高
ARROW_HALF_WIDTH = 0.8


def _pt(p) -> Point:
    return (float(p[0]), float(p[1]))


def _unit(dx: float, dy: float) -> Point:
    n = (dx * dx + dy * dy) ** 0.5
    if n < 1e-15:
        return (-1.0, 0.0)
    return (dx / n, dy / n)


@dataclass
class Leader:
    """P299/P307: 引线标注 —— 箭头锚点 +（可选）折点 + 文本 + 样式。"""

    view: str
    anchor: Point
    text: str = ""
    elbow: Optional[Point] = None
    tail: float = 0.015            # 水平尾段长度（视图坐标，米）
    arrow: str = "solid"           # solid | open | none
    text_height: float = 0.0025    # 字高（视图坐标，米）

    def __post_init__(self):
        self.validate()            # fail fast: styles are part of the contract

    def validate(self) -> "Leader":
        if not str(self.text).strip():
            raise ValueError("引线标注必须有文字")
        if float(self.tail) < 0:
            raise ValueError("引线尾段长度不能为负")
        if str(self.arrow).lower() not in ARROW_STYLES:
            raise ValueError("引线箭头样式未知：%s（可选 %s）"
                             % (self.arrow, "/".join(ARROW_STYLES)))
        self.arrow = str(self.arrow).lower()
        if float(self.text_height) <= 0:
            raise ValueError("字高必须为正")
        self.text_height = float(self.text_height)
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

    def arrow_head(self) -> List[Point]:
        """闭式箭头：solid 为三角形（首点=锚点），open 为两条倒钩，none 为空。"""
        self.validate()
        if self.arrow == "none":
            return []
        pts = self.points()
        tip = pts[0]
        nxt = pts[1] if len(pts) > 1 else (tip[0] + self.tail, tip[1])
        ux, uy = _unit(nxt[0] - tip[0], nxt[1] - tip[1])
        L = ARROW_LENGTH * self.text_height
        W = ARROW_HALF_WIDTH * self.text_height
        base = (tip[0] + ux * L, tip[1] + uy * L)
        px, py = -uy, ux
        left = (base[0] + px * W, base[1] + py * W)
        right = (base[0] - px * W, base[1] - py * W)
        if self.arrow == "solid":
            return [tip, left, right]
        return [left, tip, right]          # open: a two-barb polyline

    def text_at(self) -> Point:
        p = self.points()[-1]
        return (p[0], p[1] + self.text_height)

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
                "tail": float(self.tail), "arrow": self.arrow,
                "text_height": self.text_height}

    @classmethod
    def from_dict(cls, data) -> "Leader":
        elbow = data.get("elbow")
        return cls(view=data.get("view", ""),
                   anchor=tuple(data.get("anchor") or (0, 0)),
                   text=data.get("text", ""),
                   elbow=(tuple(elbow) if elbow is not None else None),
                   tail=data.get("tail", 0.015),
                   arrow=data.get("arrow", "solid"),
                   text_height=data.get("text_height", 0.0025)).validate()


@dataclass
class GdtFrame:
    """P299/P307: 形位公差框 —— 符号 / 公差值 / 基准；P307 支持复合（多行）。"""

    view: str
    anchor: Point
    symbol: str = "position"
    value: float = 0.05            # mm（与尺寸标注同单位）
    datums: List[str] = field(default_factory=list)
    width: float = 0.028           # 单格宽（视图坐标，米）
    height: float = 0.009          # 单行高
    extra_rows: List[Dict] = field(default_factory=list)   # 复合公差：后续行

    def __post_init__(self):
        self.validate()

    def _row(self, row: Dict) -> Tuple[str, float, List[str]]:
        sym = str(row.get("symbol", self.symbol)).lower()
        if sym not in GD_T_SYMBOLS:
            raise ValueError("形位公差符号未知：%s（可选 %s）"
                             % (row.get("symbol"), "/".join(GD_T_SYMBOLS)))
        val = float(row.get("value", self.value))
        if val <= 0:
            raise ValueError("形位公差值必须为正")
        ds = [str(d).strip() for d in (row.get("datums") or []) if str(d).strip()]
        for d in ds:
            if len(d) > 3:
                raise ValueError("基准代号过长（最多 3 个字符）")
        return sym, val, ds

    def rows(self) -> List[Tuple[str, float, List[str]]]:
        """每一行 (符号, 公差值, 基准表) —— 复合公差就是多行。"""
        out = [self._row({"symbol": self.symbol, "value": self.value,
                          "datums": self.datums})]
        for row in self.extra_rows:
            out.append(self._row(row))
        return out

    def row_label(self, sym: str, val: float, datums: List[str]) -> str:
        txt = "%s Ø%g" % (GD_T_GLYPHS.get(sym, sym), val)
        if datums:
            txt += " " + " ".join(datums)
        return txt

    def label(self) -> str:
        sym, val, ds = self.rows()[0]
        return self.row_label(sym, val, ds)

    def labels(self) -> List[str]:
        return [self.row_label(*r) for r in self.rows()]

    def validate(self) -> "GdtFrame":
        self.rows()                       # 逐行校验（含复合行）
        if float(self.width) <= 0 or float(self.height) <= 0:
            raise ValueError("形位公差框尺寸必须为正")
        self.anchor = _pt(self.anchor)
        return self

    def corners(self) -> List[Point]:
        """框的四角（锚点是左下角；复合公差按行数加高）。"""
        self.validate()
        x0, y0 = self.anchor
        x1 = x0 + float(self.width)
        y1 = y0 + float(self.height) * len(self.rows())
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def dividers(self) -> List[Tuple[Point, Point]]:
        """行分隔线（复合公差）+ 行内单元格分隔线（符号 | 公差 | 基准）。"""
        self.validate()
        x0, y0 = self.anchor
        x1 = x0 + float(self.width)
        rows = self.rows()
        out: List[Tuple[Point, Point]] = []
        for i in range(1, len(rows)):
            y = y0 + float(self.height) * i
            out.append(((x0, y), (x1, y)))
        for i, (_s, _v, ds) in enumerate(rows):
            ya = y0 + float(self.height) * i
            yb = ya + float(self.height)
            # real frames carry symbol | tolerance | datum cells: the datum
            # cell only exists when the row HAS a datum
            xs = x0 + float(self.width) * (0.34 if ds else 0.45)
            out.append(((xs, ya), (xs, yb)))
            if ds:
                xd = x0 + float(self.width) * 0.68
                out.append(((xd, ya), (xd, yb)))
        return out

    def move_to(self, p) -> None:
        self.anchor = _pt(p)

    def to_dict(self) -> Dict:
        self.validate()
        return {"kind": "gdt", "view": self.view, "anchor": list(self.anchor),
                "symbol": self.symbol, "value": self.value,
                "datums": list(self.datums), "width": float(self.width),
                "height": float(self.height),
                "extra_rows": [dict(r) for r in self.extra_rows]}

    @classmethod
    def from_dict(cls, data) -> "GdtFrame":
        return cls(view=data.get("view", ""),
                   anchor=tuple(data.get("anchor") or (0, 0)),
                   symbol=data.get("symbol", "position"),
                   value=data.get("value", 0.05),
                   datums=list(data.get("datums") or []),
                   width=data.get("width", 0.028),
                   height=data.get("height", 0.009),
                   extra_rows=[dict(r) for r in (data.get("extra_rows") or [])]
                   ).validate()


@dataclass
class Datum:
    """P307: 基准符号 —— 引线 + 字母框（A/B/C），可作基准目标。"""

    view: str
    anchor: Point
    label: str = "A"
    target: bool = False               # 基准目标（点/线/面）
    target_size: float = 0.006         # 目标标记尺寸（视图坐标，米）
    tail: float = 0.012
    box: float = 0.008                 # 字母框边长

    def __post_init__(self):
        self.validate()

    def validate(self) -> "Datum":
        lab = str(self.label).strip()
        if not lab or len(lab) > 3 or not lab.replace("-", "").isalnum():
            raise ValueError("基准代号非法（1–3 个字母/数字）：%r" % self.label)
        self.label = lab.upper()
        for name, v in (("引线长度", self.tail), ("框边长", self.box)):
            if float(v) <= 0:
                raise ValueError("基准%s必须为正" % name)
        if float(self.target_size) <= 0:
            raise ValueError("基准目标尺寸必须为正")
        self.tail = float(self.tail)
        self.box = float(self.box)
        self.target_size = float(self.target_size)
        self.anchor = _pt(self.anchor)
        return self

    def _elbow(self) -> Point:
        return (self.anchor[0] + self.tail * 0.7, self.anchor[1] + self.tail * 0.7)

    def points(self) -> List[Point]:
        """引线：锚点 → 斜折点 → 尾端（字母框画在尾端）。"""
        self.validate()
        el = self._elbow()
        return [self.anchor, el, (el[0] + self.tail * 0.6, el[1])]

    def target_mark(self) -> List[Point]:
        """基准目标标记：以锚点为中心的正三角（闭式）。"""
        self.validate()
        if not self.target:
            return []
        r = self.target_size / 2.0
        return [(self.anchor[0], self.anchor[1] + r),
                (self.anchor[0] - r, self.anchor[1] - r),
                (self.anchor[0] + r, self.anchor[1] - r)]

    def box_corners(self) -> List[Point]:
        self.validate()
        p = self.points()[-1]
        x0, y0 = p[0], p[1] - self.box / 2.0
        return [(x0, y0), (x0 + self.box, y0),
                (x0 + self.box, y0 + self.box), (x0, y0 + self.box)]

    def text_at(self) -> Point:
        c = self.box_corners()[0]
        return (c[0] + self.box * 0.28, c[1] + self.box * 0.72)

    def move_to(self, p) -> None:
        self.anchor = _pt(p)

    def to_dict(self) -> Dict:
        self.validate()
        return {"kind": "datum", "view": self.view, "anchor": list(self.anchor),
                "label": self.label, "target": bool(self.target),
                "target_size": self.target_size, "tail": self.tail,
                "box": self.box}

    @classmethod
    def from_dict(cls, data) -> "Datum":
        return cls(view=data.get("view", ""),
                   anchor=tuple(data.get("anchor") or (0, 0)),
                   label=data.get("label", "A"),
                   target=bool(data.get("target", False)),
                   target_size=data.get("target_size", 0.006),
                   tail=data.get("tail", 0.012),
                   box=data.get("box", 0.008)).validate()


def annotation_geometry(a):
    """(segments, text, text_at, style) in view coordinates for any annotation.

    P307: the style dict carries the drawing attributes (arrow style, text
    height, layer) so both exporters can reproduce the look without knowing the
    annotation classes.
    """
    if isinstance(a, Leader):
        a.validate()
        pts = a.points()
        segs = list(zip(pts, pts[1:]))
        head = a.arrow_head()
        if a.arrow == "solid" and len(head) == 3:
            segs += [(head[0], head[1]), (head[1], head[2]),
                     (head[2], head[0])]
        elif len(head) == 3:                    # open barbs
            segs += [(head[0], head[1]), (head[1], head[2])]
        return (segs, str(a.text), a.text_at(),
                {"arrow": a.arrow, "text_height": a.text_height,
                 "layer": "NOTE", "filled": a.arrow == "solid"})
    if isinstance(a, Datum):
        a.validate()
        pts = a.points()
        segs = list(zip(pts, pts[1:]))
        c = a.box_corners()
        segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
        mark = a.target_mark()
        if len(mark) == 3:
            segs += [(mark[0], mark[1]), (mark[1], mark[2]),
                     (mark[2], mark[0])]
        return (segs, a.label, a.text_at(),
                {"arrow": "solid" if a.target else "none",
                 "text_height": a.box * 0.7, "layer": "DATUM",
                 "filled": bool(a.target)})
    a.validate()
    c = a.corners()
    segs = [(c[i], c[(i + 1) % 4]) for i in range(4)] + list(a.dividers())
    labels = a.labels()
    text = " / ".join(labels) if len(labels) > 1 else labels[0]
    at = (c[0][0] + 0.002, c[0][1] + float(a.height) * 0.72)
    return (segs, text, at,
            {"arrow": "none", "text_height": float(a.height) * 0.55,
             "layer": "GDT", "filled": False, "rows": len(labels)})


def annotation_layer(a) -> str:
    if isinstance(a, Leader):
        return "NOTE"
    if isinstance(a, Datum):
        return "DATUM"
    return "GDT"


def from_dict(data):
    """Rebuild whichever annotation `data` describes."""
    kind = str(data.get("kind", "")).lower()
    if kind == "gdt":
        return GdtFrame.from_dict(data)
    if kind == "datum":
        return Datum.from_dict(data)
    return Leader.from_dict(data)

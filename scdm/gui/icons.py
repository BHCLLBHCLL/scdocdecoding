"""Original CAD ribbon glyphs: isometric solids + sketch line-art (not SpaceClaim assets)."""
from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QIcon, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF, QRadialGradient,
)

_CACHE = {}

# Isometric body palettes
BLUE = ("#D3E7F6", "#8FB4D0", "#5C88A9", "#35536C")
ORANGE = ("#FFE4C4", "#FFB24D", "#E65100", "#8D4A12")
GREEN = ("#CDE9D0", "#7CBC80", "#3D9144", "#2E5D32")
TEAL = ("#C8ECEC", "#6DBFBF", "#2A8A8A", "#1F5C5C")
STEEL = ("#E6EDF2", "#A7B6C2", "#6D7E8C", "#3E4E5A")

SKETCH = QColor("#2D9A55")
NODE = QColor("#F57C00")
INK = QColor("#3A4A58")
RED = QColor("#C62828")
AXIS_R = QColor("#D32F2F")
AXIS_G = QColor("#388E3C")
AXIS_B = QColor("#1976D2")


def _qc(color):
    if color is None:
        return None
    return color if isinstance(color, QColor) else QColor(color)


class _G:
    def __init__(self, painter: QPainter, size: int):
        self.p = painter
        self.s = float(size)
        m = size * 0.08
        self.x0 = m
        self.y0 = m
        self.w = size - 2 * m
        self.h = size - 2 * m
        self.sw = max(1.35, size * 0.065)

    def pt(self, fx, fy) -> QPointF:
        return QPointF(self.x0 + fx * self.w, self.y0 + fy * self.h)

    def xy(self, fx, fy):
        return (self.x0 + fx * self.w, self.y0 + fy * self.h)

    def rect(self, fx, fy, fw, fh) -> QRectF:
        return QRectF(self.x0 + fx * self.w, self.y0 + fy * self.h, fw * self.w, fh * self.h)

    def stroke(self, color=None, w=None, dash=False):
        pe = QPen(_qc(color) or INK)
        pe.setWidthF(w if w is not None else self.sw)
        pe.setCapStyle(Qt.RoundCap)
        pe.setJoinStyle(Qt.RoundJoin)
        if dash:
            pe.setStyle(Qt.DashLine)
            pe.setDashPattern([2.2, 2.0])
        self.p.setPen(pe)
        self.p.setBrush(Qt.NoBrush)

    def fill(self, color, outline=None, w=None):
        if outline is not None:
            pe = QPen(_qc(outline))
            pe.setWidthF(w if w is not None else max(1.0, self.sw * 0.55))
            pe.setJoinStyle(Qt.RoundJoin)
            pe.setCapStyle(Qt.RoundCap)
            self.p.setPen(pe)
        else:
            self.p.setPen(Qt.NoPen)
        if color is None:
            self.p.setBrush(Qt.NoBrush)
        else:
            self.p.setBrush(QBrush(_qc(color)))

    def line(self, a, b):
        self.p.drawLine(self.pt(*a), self.pt(*b))

    def polygon(self, pts):
        self.p.drawPolygon(QPolygonF([self.pt(x, y) for x, y in pts]))

    def ellipse(self, fx, fy, fw, fh):
        self.p.drawEllipse(self.rect(fx, fy, fw, fh))

    def rounded(self, fx, fy, fw, fh, rad=0.08):
        self.p.drawRoundedRect(self.rect(fx, fy, fw, fh), rad * self.w, rad * self.h)

    def node(self, fx, fy, r=0.07, color=None):
        self.fill(color or NODE)
        self.ellipse(fx - r, fy - r, r * 2, r * 2)

    def arrow(self, tail, head, color=None, scale=1.0):
        col = _qc(color) if color is not None else AXIS_B
        self.stroke(col, self.sw * (1.05 if self.s >= 40 else 1.0))
        t, h = self.pt(*tail), self.pt(*head)
        self.p.drawLine(t, h)
        dx, dy = h.x() - t.x(), h.y() - t.y()
        length = max((dx * dx + dy * dy) ** 0.5, 1.0)
        ux, uy = dx / length, dy / length
        ah = max(3.2, self.s * 0.13 * scale)
        px, py = -uy, ux
        self.fill(col)
        self.p.drawPolygon(QPolygonF([
            h,
            QPointF(h.x() - ux * ah + px * ah * 0.42, h.y() - uy * ah + py * ah * 0.42),
            QPointF(h.x() - ux * ah - px * ah * 0.42, h.y() - uy * ah - py * ah * 0.42),
        ]))

    def iso(self, cx, cy, s=1.0, pal=BLUE, lift=0.0):
        """Unit cube in isometric view. Returns corner fn and face polygons."""
        top, right, left, edge = pal
        sx, sy, sz = 0.30 * s, 0.155 * s, 0.30 * s
        cy = cy - lift * sz

        def c(x, y, z):
            px = cx + (x - y) * sx
            py = cy + (x + y) * (sy * 0.92) - z * sz
            return (px, py)

        faces = {
            "right": [c(1, 0, 0), c(1, 1, 0), c(1, 1, 1), c(1, 0, 1)],
            "left": [c(0, 1, 0), c(1, 1, 0), c(1, 1, 1), c(0, 1, 1)],
            "top": [c(0, 0, 1), c(1, 0, 1), c(1, 1, 1), c(0, 1, 1)],
        }
        ew = max(1.0, self.sw * 0.5)
        self.fill(right, edge, ew)
        self.polygon(faces["right"])
        self.fill(left, edge, ew)
        self.polygon(faces["left"])
        self.fill(top, edge, ew)
        self.polygon(faces["top"])
        return c, faces

    def cursor(self, fx=0.62, fy=0.42):
        self.fill(QColor("#1A1A1A"))
        self.polygon([
            (fx, fy), (fx, fy + 0.46), (fx + 0.14, fy + 0.32),
            (fx + 0.26, fy + 0.56), (fx + 0.36, fy + 0.50),
            (fx + 0.22, fy + 0.28), (fx + 0.42, fy + 0.28),
        ])
        self.fill(QColor("#FAFAFA"))
        self.polygon([
            (fx + 0.04, fy + 0.08), (fx + 0.04, fy + 0.38), (fx + 0.14, fy + 0.28),
            (fx + 0.22, fy + 0.46), (fx + 0.28, fy + 0.42),
            (fx + 0.18, fy + 0.26), (fx + 0.34, fy + 0.26),
        ])


def _doc(g, fx=0.22, fy=0.12, folded=True):
    g.fill("#FFFDF7", INK, g.sw * 0.55)
    g.polygon([(fx, fy + 0.08), (fx, fy + 0.78), (fx + 0.56, fy + 0.78),
               (fx + 0.56, fy + 0.28), (fx + 0.34, fy + 0.08)])
    if folded:
        g.fill("#EEF2F5", INK, g.sw * 0.45)
        g.polygon([(fx + 0.34, fy + 0.08), (fx + 0.34, fy + 0.28), (fx + 0.56, fy + 0.28)])


def _draw(g: _G, key: str):
    if key in ("select", "sel"):
        g.iso(0.38, 0.58, 0.95, BLUE)
        g.cursor(0.52, 0.28)
    elif key == "pull":
        c, _ = g.iso(0.46, 0.70, 0.88, BLUE)
        g.fill(GREEN[0], GREEN[3], g.sw * 0.5)
        g.polygon([c(0, 0, 1.45), c(1, 0, 1.45), c(1, 1, 1.45), c(0, 1, 1.45)])
        g.arrow((0.46, 0.42), (0.46, 0.06), AXIS_G, 1.1)
    elif key == "move":
        g.iso(0.50, 0.58, 0.62, ORANGE)
        g.arrow((0.50, 0.48), (0.50, 0.06), AXIS_G)
        g.arrow((0.50, 0.58), (0.88, 0.72), AXIS_R)
        g.arrow((0.50, 0.58), (0.12, 0.72), AXIS_B)
    elif key == "fill":
        c, faces = g.iso(0.46, 0.66, 0.88, BLUE)
        g.fill("#EEF3F7", INK, g.sw * 0.45)
        g.polygon(faces["top"])
        g.fill(TEAL[0], TEAL[3], g.sw * 0.55)
        g.polygon([c(-0.05, -0.05, 1.35), c(0.95, -0.05, 1.35),
                   c(0.95, 0.95, 1.35), c(-0.05, 0.95, 1.35)])
        g.arrow((0.55, 0.22), (0.48, 0.40), QColor(TEAL[2]), 0.75)
    elif key == "replace":
        g.iso(0.34, 0.62, 0.72, BLUE)
        g.iso(0.64, 0.52, 0.72, ORANGE)
    elif key == "combine":
        g.iso(0.36, 0.60, 0.78, BLUE)
        g.iso(0.62, 0.66, 0.78, ORANGE)
    elif key in ("split", "splitf"):
        c, _ = g.iso(0.48, 0.60, 0.92, BLUE)
        g.fill(QColor(230, 120, 40, 170), RED, g.sw * 0.55)
        g.polygon([c(-0.15, 0.5, -0.08), c(1.15, 0.5, -0.08),
                   c(1.15, 0.5, 1.18), c(-0.15, 0.5, 1.18)])
    elif key == "cut":
        _doc(g, 0.14, 0.10)
        g.stroke(RED, g.sw * 1.15)
        g.line((0.22, 0.22), (0.86, 0.82))
        g.line((0.78, 0.18), (0.18, 0.78))
    elif key == "copy":
        g.fill("#E8EEF3", INK, g.sw * 0.5)
        g.rounded(0.10, 0.28, 0.52, 0.58, 0.05)
        g.fill("#FFFDF7", INK, g.sw * 0.55)
        g.rounded(0.32, 0.12, 0.54, 0.60, 0.05)
        g.stroke(SKETCH, g.sw * 0.7)
        g.line((0.44, 0.32), (0.72, 0.32))
        g.line((0.44, 0.46), (0.68, 0.46))
    elif key == "paste":
        g.fill("#CFD8DC", INK, g.sw * 0.5)
        g.rounded(0.28, 0.08, 0.44, 0.18, 0.08)
        g.fill("#FFFDF7", INK, g.sw * 0.55)
        g.rounded(0.16, 0.20, 0.68, 0.70, 0.06)
        g.stroke(SKETCH, g.sw * 0.75)
        g.line((0.30, 0.40), (0.70, 0.40))
        g.line((0.30, 0.54), (0.62, 0.54))
        g.line((0.30, 0.68), (0.56, 0.68))
    elif key == "new":
        _doc(g, 0.22, 0.08)
        g.fill(AXIS_B)
        g.rounded(0.58, 0.58, 0.30, 0.30, 0.06)
        g.stroke(QColor("#FFFFFF"), max(1.4, g.sw))
        g.line((0.73, 0.64), (0.73, 0.82))
        g.line((0.64, 0.73), (0.82, 0.73))
    elif key == "open":
        g.fill("#F4C06A", QColor("#C47A12"), g.sw * 0.5)
        g.polygon([(0.10, 0.38), (0.10, 0.84), (0.88, 0.84), (0.80, 0.38)])
        g.fill("#E8A23A")
        g.polygon([(0.12, 0.20), (0.42, 0.20), (0.52, 0.38), (0.12, 0.38)])
    elif key in ("save", "saveas"):
        g.fill("#1E88E5", QColor("#1565C0"), g.sw * 0.45)
        g.rounded(0.14, 0.12, 0.72, 0.76, 0.08)
        g.fill("#E3F2FD")
        g.rect(0.30, 0.12, 0.40, 0.26)
        g.fill("#FFFFFF")
        g.rect(0.26, 0.48, 0.48, 0.32)
        if key == "saveas":
            g.stroke(QColor("#FFFFFF"), g.sw * 0.8)
            g.line((0.70, 0.22), (0.86, 0.08))
    elif key == "undo":
        g.stroke(QColor("#6A3D9A"), g.sw * 1.2)
        path = QPainterPath(g.pt(0.80, 0.34))
        path.arcTo(g.rect(0.16, 0.18, 0.66, 0.66), 35, 235)
        g.p.drawPath(path)
        g.arrow((0.24, 0.42), (0.08, 0.20), QColor("#6A3D9A"))
    elif key == "redo":
        g.stroke(QColor("#6A3D9A"), g.sw * 1.2)
        path = QPainterPath(g.pt(0.20, 0.34))
        path.arcTo(g.rect(0.16, 0.18, 0.66, 0.66), 145, -235)
        g.p.drawPath(path)
        g.arrow((0.76, 0.42), (0.92, 0.20), QColor("#6A3D9A"))
    elif key == "spin":
        g.iso(0.50, 0.58, 0.62, BLUE)
        g.stroke(AXIS_B, g.sw * 1.05)
        path = QPainterPath()
        path.arcMoveTo(g.rect(0.10, 0.22, 0.80, 0.42), 20)
        path.arcTo(g.rect(0.10, 0.22, 0.80, 0.42), 20, 220)
        g.p.drawPath(path)
        g.arrow((0.18, 0.40), (0.12, 0.22), AXIS_B, 0.85)
    elif key == "pan":
        g.iso(0.50, 0.56, 0.50, BLUE)
        g.arrow((0.50, 0.40), (0.50, 0.08), AXIS_B, 0.8)
        g.arrow((0.50, 0.68), (0.50, 0.92), AXIS_B, 0.8)
        g.arrow((0.38, 0.58), (0.10, 0.70), AXIS_B, 0.8)
        g.arrow((0.62, 0.58), (0.90, 0.70), AXIS_B, 0.8)
    elif key == "zoom":
        g.iso(0.34, 0.40, 0.42, BLUE)
        g.stroke(INK, g.sw * 1.15)
        g.ellipse(0.28, 0.22, 0.50, 0.50)
        g.line((0.68, 0.68), (0.90, 0.90))
        g.stroke(AXIS_B, g.sw)
        g.line((0.40, 0.47), (0.66, 0.47))
        g.line((0.53, 0.34), (0.53, 0.60))
    elif key == "fit":
        g.iso(0.50, 0.56, 0.70, BLUE)
        g.stroke(AXIS_B, g.sw * 1.05)
        g.line((0.08, 0.22), (0.08, 0.08))
        g.line((0.08, 0.08), (0.24, 0.08))
        g.line((0.76, 0.08), (0.92, 0.08))
        g.line((0.92, 0.08), (0.92, 0.22))
        g.line((0.08, 0.78), (0.08, 0.92))
        g.line((0.08, 0.92), (0.24, 0.92))
        g.line((0.76, 0.92), (0.92, 0.92))
        g.line((0.92, 0.92), (0.92, 0.78))
    elif key == "prev":
        g.fill(AXIS_B)
        g.polygon([(0.70, 0.16), (0.22, 0.50), (0.70, 0.84)])
    elif key == "home":
        g.iso(0.50, 0.70, 0.55, BLUE)
        g.fill(AXIS_B)
        g.polygon([(0.50, 0.06), (0.90, 0.40), (0.10, 0.40)])
    elif key == "iso":
        g.iso(0.50, 0.56, 1.05, BLUE)
    elif key == "viewx":
        c, faces = g.iso(0.50, 0.56, 1.0, STEEL)
        g.fill(QColor("#E57373"), RED, g.sw * 0.5)
        g.polygon(faces["right"])
    elif key == "viewy":
        c, faces = g.iso(0.50, 0.56, 1.0, STEEL)
        g.fill(QColor("#81C784"), AXIS_G, g.sw * 0.5)
        g.polygon(faces["left"])
    elif key == "viewz":
        c, faces = g.iso(0.50, 0.56, 1.0, STEEL)
        g.fill(QColor("#64B5F6"), AXIS_B, g.sw * 0.5)
        g.polygon(faces["top"])
    elif key == "line":
        g.stroke(SKETCH, g.sw * 1.25)
        g.line((0.12, 0.80), (0.88, 0.16))
        g.node(0.12, 0.80)
        g.node(0.88, 0.16)
    elif key == "tangent":
        g.stroke(SKETCH, g.sw * 1.1)
        g.ellipse(0.08, 0.28, 0.54, 0.54)
        g.stroke(SKETCH, g.sw * 1.2)
        g.line((0.16, 0.22), (0.94, 0.22))
        g.node(0.42, 0.22)
    elif key == "rect":
        g.stroke(SKETCH, g.sw * 1.15)
        g.rounded(0.14, 0.22, 0.72, 0.56, 0.02)
        g.node(0.14, 0.22)
        g.node(0.86, 0.78)
    elif key == "rect3":
        g.stroke(SKETCH, g.sw * 1.1)
        g.polygon([(0.16, 0.74), (0.38, 0.18), (0.88, 0.34), (0.66, 0.88)])
        for fx, fy in ((0.16, 0.74), (0.38, 0.18), (0.88, 0.34)):
            g.node(fx, fy, 0.06)
    elif key == "circle":
        g.stroke(SKETCH, g.sw * 1.2)
        g.ellipse(0.14, 0.14, 0.72, 0.72)
        g.node(0.50, 0.50, 0.06)
        g.node(0.86, 0.50, 0.055)
    elif key == "circle3":
        g.stroke(SKETCH, g.sw * 1.1)
        g.ellipse(0.14, 0.16, 0.72, 0.72)
        for fx, fy in ((0.26, 0.30), (0.74, 0.28), (0.56, 0.82)):
            g.node(fx, fy, 0.06)
    elif key == "ellipse":
        g.stroke(SKETCH, g.sw * 1.15)
        g.ellipse(0.08, 0.28, 0.84, 0.48)
        g.node(0.50, 0.52, 0.055)
    elif key == "spline":
        g.stroke(SKETCH, g.sw * 1.15)
        path = QPainterPath(g.pt(0.08, 0.74))
        path.cubicTo(g.pt(0.28, 0.06), g.pt(0.64, 0.94), g.pt(0.92, 0.26))
        g.p.drawPath(path)
        g.node(0.08, 0.74)
        g.node(0.92, 0.26)
    elif key == "point":
        g.stroke(SKETCH, g.sw * 0.8)
        g.line((0.50, 0.10), (0.50, 0.34))
        g.line((0.50, 0.66), (0.50, 0.90))
        g.line((0.10, 0.50), (0.34, 0.50))
        g.line((0.66, 0.50), (0.90, 0.50))
        g.node(0.50, 0.50, 0.11)
    elif key == "const":
        g.stroke(QColor("#7A8A96"), g.sw * 1.05, dash=True)
        g.line((0.12, 0.80), (0.88, 0.18))
    elif key == "offset":
        g.stroke(QColor("#90A4AE"), g.sw, dash=True)
        g.rounded(0.14, 0.32, 0.48, 0.48, 0.02)
        g.stroke(SKETCH, g.sw * 1.15)
        g.rounded(0.34, 0.14, 0.50, 0.50, 0.02)
    elif key == "layout":
        g.stroke(SKETCH, g.sw)
        g.rounded(0.10, 0.16, 0.80, 0.68, 0.03)
        g.line((0.50, 0.16), (0.50, 0.84))
        g.line((0.10, 0.50), (0.90, 0.50))
    elif key == "grid":
        g.stroke(SKETCH, g.sw * 0.75)
        for t in (0.18, 0.50, 0.82):
            g.line((t, 0.12), (t, 0.88))
            g.line((0.12, t), (0.88, t))
    elif key == "mode_sketch":
        g.fill("#FFFDF7", SKETCH, g.sw * 0.6)
        g.rounded(0.12, 0.16, 0.76, 0.68, 0.04)
        g.stroke(SKETCH, g.sw * 1.1)
        g.line((0.22, 0.72), (0.42, 0.34))
        g.line((0.42, 0.34), (0.78, 0.54))
        g.node(0.42, 0.34, 0.06)
    elif key == "mode_section":
        g.iso(0.50, 0.58, 0.95, BLUE)
        g.fill(QColor(80, 180, 180, 150), QColor(TEAL[3]), g.sw * 0.5)
        g.polygon([(0.18, 0.42), (0.82, 0.28), (0.82, 0.78), (0.18, 0.88)])
    elif key == "mode_3d":
        g.iso(0.50, 0.56, 1.08, BLUE)
    elif key == "dim":
        g.stroke(SKETCH, g.sw * 0.85)
        g.line((0.18, 0.16), (0.18, 0.84))
        g.line((0.82, 0.16), (0.82, 0.84))
        g.arrow((0.22, 0.50), (0.78, 0.50), AXIS_B, 0.85)
        g.arrow((0.78, 0.50), (0.22, 0.50), AXIS_B, 0.85)
    elif key == "hv":
        g.stroke(SKETCH, g.sw * 1.15)
        g.line((0.14, 0.80), (0.86, 0.80))
        g.line((0.50, 0.14), (0.50, 0.80))
        g.node(0.50, 0.80, 0.06)
    elif key == "coin":
        g.stroke(SKETCH, g.sw)
        g.ellipse(0.14, 0.14, 0.44, 0.44)
        g.ellipse(0.42, 0.42, 0.44, 0.44)
        g.node(0.50, 0.50, 0.07)
    elif key == "tan":
        g.stroke(SKETCH, g.sw * 1.1)
        g.ellipse(0.08, 0.30, 0.50, 0.50)
        g.line((0.18, 0.20), (0.94, 0.20))
        g.node(0.36, 0.20, 0.06)
    elif key == "eq":
        g.stroke(SKETCH, g.sw * 1.25)
        g.line((0.16, 0.36), (0.84, 0.36))
        g.line((0.16, 0.64), (0.84, 0.64))
    elif key == "par":
        g.stroke(SKETCH, g.sw * 1.15)
        g.line((0.20, 0.82), (0.46, 0.14))
        g.line((0.54, 0.82), (0.80, 0.14))
    elif key == "fix":
        g.stroke(INK, g.sw)
        g.line((0.50, 0.10), (0.50, 0.46))
        g.node(0.50, 0.50, 0.10, AXIS_B)
        g.stroke(INK, g.sw * 0.9)
        g.line((0.20, 0.78), (0.80, 0.78))
        g.line((0.28, 0.70), (0.20, 0.90))
        g.line((0.50, 0.70), (0.50, 0.90))
        g.line((0.72, 0.70), (0.80, 0.90))
    elif key == "pattern":
        for i, (fx, fy) in enumerate(((0.16, 0.22), (0.50, 0.22), (0.16, 0.58), (0.50, 0.58))):
            pal = BLUE if i == 0 else STEEL
            g.iso(fx + 0.14, fy + 0.18, 0.38, pal)
    elif key == "mirror":
        g.iso(0.30, 0.58, 0.62, BLUE)
        g.stroke(QColor("#90A4AE"), g.sw * 0.85, dash=True)
        g.line((0.50, 0.08), (0.50, 0.92))
        g.iso(0.70, 0.58, 0.62, STEEL)
    elif key == "project":
        g.stroke(SKETCH, g.sw)
        g.ellipse(0.28, 0.08, 0.44, 0.32)
        g.iso(0.50, 0.78, 0.70, BLUE)
        g.arrow((0.50, 0.38), (0.50, 0.58), AXIS_B, 0.8)
    elif key == "shell":
        c, faces = g.iso(0.50, 0.56, 1.0, BLUE)
        g.fill("#F7FAFC", INK, g.sw * 0.45)
        g.polygon([c(0.22, 0.22, 1.01), c(0.78, 0.22, 1.01),
                   c(0.78, 0.78, 1.01), c(0.22, 0.78, 1.01)])
    elif key == "blend":
        g.stroke(INK, g.sw * 1.15)
        path = QPainterPath(g.pt(0.14, 0.16))
        path.lineTo(g.pt(0.14, 0.58))
        path.quadTo(g.pt(0.14, 0.86), g.pt(0.46, 0.86))
        path.lineTo(g.pt(0.88, 0.86))
        g.p.drawPath(path)
        g.stroke(AXIS_G, g.sw * 0.9, dash=True)
        g.line((0.14, 0.58), (0.14, 0.86))
        g.line((0.14, 0.86), (0.46, 0.86))
    elif key == "chamfer":
        g.stroke(INK, g.sw * 1.15)
        g.p.drawPolyline(QPolygonF([g.pt(0.14, 0.14), g.pt(0.14, 0.58),
                                    g.pt(0.42, 0.86), g.pt(0.88, 0.86)]))
        g.stroke(QColor(ORANGE[2]), g.sw)
        g.line((0.14, 0.58), (0.42, 0.86))
    elif key == "draft":
        g.fill(BLUE[0], INK, g.sw * 0.5)
        g.polygon([(0.30, 0.12), (0.70, 0.12), (0.86, 0.88), (0.14, 0.88)])
        g.stroke(AXIS_G, g.sw * 0.9, dash=True)
        g.line((0.30, 0.12), (0.14, 0.88))
    elif key == "offace":
        g.iso(0.50, 0.72, 0.85, BLUE, lift=0)
        c, _ = g.iso(0.50, 0.42, 0.85, TEAL)
        g.arrow((0.50, 0.52), (0.50, 0.28), AXIS_G, 0.85)
    elif key == "plane":
        g.fill(QColor(100, 140, 210, 90), AXIS_B, g.sw * 0.6)
        g.polygon([(0.10, 0.62), (0.42, 0.16), (0.92, 0.28), (0.58, 0.80)])
        g.stroke(AXIS_B, g.sw * 0.7)
        g.line((0.42, 0.16), (0.42, 0.08))
    elif key == "origin":
        g.arrow((0.22, 0.78), (0.90, 0.78), AXIS_R)
        g.arrow((0.22, 0.78), (0.22, 0.10), AXIS_G)
        g.arrow((0.22, 0.78), (0.08, 0.92), AXIS_B, 0.75)
        g.fill(QColor("#FFFFFF"), INK)
        g.ellipse(0.14, 0.70, 0.16, 0.16)
    elif key == "axis":
        g.stroke(AXIS_B, g.sw * 1.2)
        g.line((0.20, 0.84), (0.80, 0.16))
        g.node(0.20, 0.84, 0.07, AXIS_B)
        g.node(0.80, 0.16, 0.07, AXIS_B)
    elif key == "cyl":
        g.fill(ORANGE[1], ORANGE[3], g.sw * 0.5)
        body = QPainterPath()
        body.moveTo(g.pt(0.22, 0.24))
        body.lineTo(g.pt(0.22, 0.72))
        body.arcTo(g.rect(0.22, 0.62, 0.56, 0.24), 180, 180)
        body.lineTo(g.pt(0.78, 0.24))
        body.arcTo(g.rect(0.22, 0.12, 0.56, 0.24), 0, -180)
        g.p.drawPath(body)
        g.fill(ORANGE[2], ORANGE[3], g.sw * 0.5)
        g.ellipse(0.22, 0.62, 0.56, 0.24)
        g.fill(ORANGE[0], ORANGE[3], g.sw * 0.5)
        g.ellipse(0.22, 0.12, 0.56, 0.24)
    elif key == "sphere":
        rg = QRadialGradient(g.pt(0.38, 0.36), g.w * 0.55)
        rg.setColorAt(0.0, QColor("#FFE8C8"))
        rg.setColorAt(1.0, QColor("#E65100"))
        g.p.setPen(QPen(QColor(ORANGE[3]), max(1.0, g.sw * 0.55)))
        g.p.setBrush(QBrush(rg))
        g.ellipse(0.12, 0.12, 0.76, 0.76)
        g.stroke(QColor("#BF360C"), g.sw * 0.7)
        g.ellipse(0.12, 0.36, 0.76, 0.28)
    elif key == "helix":
        g.stroke(ORANGE[2], g.sw * 1.15)
        path = QPainterPath(g.pt(0.22, 0.86))
        path.cubicTo(g.pt(0.88, 0.72), g.pt(0.12, 0.50), g.pt(0.80, 0.36))
        path.cubicTo(g.pt(0.98, 0.26), g.pt(0.22, 0.16), g.pt(0.50, 0.08))
        g.p.drawPath(path)
    elif key == "comp":
        g.iso(0.36, 0.48, 0.62, BLUE)
        g.iso(0.62, 0.66, 0.62, ORANGE)
    elif key == "face":
        g.fill(BLUE[0], INK, g.sw * 0.55)
        g.polygon([(0.14, 0.30), (0.78, 0.14), (0.88, 0.72), (0.20, 0.86)])
    elif key == "edge":
        c, _ = g.iso(0.50, 0.58, 0.85, STEEL)
        g.stroke(AXIS_B, g.sw * 1.4)
        g.p.drawLine(g.pt(*c(1, 0, 0)), g.pt(*c(1, 0, 1)))
    elif key == "vert":
        g.iso(0.50, 0.60, 0.80, STEEL)
        g.node(0.68, 0.32, 0.09, AXIS_B)
    elif key == "shaded":
        g.iso(0.50, 0.56, 1.05, BLUE)
        g.stroke(INK, g.sw * 0.7)
    elif key == "shaded2":
        g.iso(0.50, 0.56, 1.05, BLUE)
    elif key == "wire":
        sx, sy, sz = 0.32, 0.165, 0.32
        cx, cy = 0.50, 0.56

        def wc(x, y, z):
            return (cx + (x - y) * sx, cy + (x + y) * sy * 0.92 - z * sz)

        g.stroke(INK, g.sw * 0.95)
        for a, b in (
            ((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (1, 1, 0)), ((1, 1, 0), (0, 1, 0)),
            ((0, 1, 0), (0, 0, 0)), ((0, 0, 1), (1, 0, 1)), ((1, 0, 1), (1, 1, 1)),
            ((1, 1, 1), (0, 1, 1)), ((0, 1, 1), (0, 0, 1)), ((0, 0, 0), (0, 0, 1)),
            ((1, 0, 0), (1, 0, 1)), ((1, 1, 0), (1, 1, 1)), ((0, 1, 0), (0, 1, 1)),
        ):
            g.line(wc(*a), wc(*b))
    elif key == "transp":
        g.iso(0.50, 0.56, 1.0, BLUE)
        g.fill(QColor(255, 255, 255, 110))
        g.ellipse(0.22, 0.22, 0.56, 0.56)
    elif key == "sil":
        g.stroke(INK, g.sw * 1.15)
        path = QPainterPath(g.pt(0.16, 0.82))
        path.quadTo(g.pt(0.16, 0.14), g.pt(0.50, 0.14))
        path.quadTo(g.pt(0.84, 0.14), g.pt(0.84, 0.82))
        g.p.drawPath(path)
    elif key == "sect":
        g.iso(0.50, 0.58, 0.95, BLUE)
        g.fill(QColor(42, 138, 138, 140), TEAL[3])
        g.polygon([(0.16, 0.40), (0.84, 0.26), (0.84, 0.78), (0.16, 0.88)])
    elif key == "measure":
        g.iso(0.28, 0.62, 0.55, BLUE)
        g.iso(0.72, 0.48, 0.40, ORANGE)
        g.arrow((0.40, 0.42), (0.70, 0.28), AXIS_B, 0.75)
    elif key == "mass":
        g.iso(0.50, 0.58, 0.95, STEEL)
        g.stroke(QColor("#6A3D9A"), g.sw)
        g.ellipse(0.32, 0.08, 0.36, 0.22)
    elif key == "rev":
        g.iso(0.50, 0.58, 0.80, BLUE)
        g.stroke(RED, g.sw * 1.1)
        path = QPainterPath()
        path.arcMoveTo(g.rect(0.12, 0.12, 0.76, 0.76), -20)
        path.arcTo(g.rect(0.12, 0.12, 0.76, 0.76), -20, 200)
        g.p.drawPath(path)
    elif key == "smooth":
        g.stroke(TEAL[2], g.sw * 1.2)
        path = QPainterPath(g.pt(0.08, 0.72))
        path.cubicTo(g.pt(0.32, 0.08), g.pt(0.68, 0.92), g.pt(0.92, 0.28))
        g.p.drawPath(path)
    elif key == "reduce":
        g.iso(0.32, 0.50, 0.70, BLUE)
        g.iso(0.70, 0.64, 0.42, STEEL)
    elif key in ("solid", "box"):
        g.iso(0.50, 0.56, 1.08, ORANGE)
    elif key == "stitch":
        g.stroke(SKETCH, g.sw)
        g.polygon([(0.12, 0.30), (0.40, 0.18), (0.44, 0.78), (0.16, 0.86)])
        g.polygon([(0.56, 0.22), (0.86, 0.16), (0.90, 0.74), (0.60, 0.82)])
        g.stroke(AXIS_B, g.sw * 0.85)
        g.line((0.40, 0.44), (0.60, 0.40))
        g.line((0.42, 0.60), (0.62, 0.56))
    elif key == "gaps":
        g.iso(0.30, 0.58, 0.62, BLUE)
        g.iso(0.74, 0.58, 0.62, ORANGE)
    elif key == "script":
        g.fill("#FFFDF7", INK, g.sw * 0.5)
        g.rounded(0.16, 0.08, 0.68, 0.84, 0.05)
        g.stroke(AXIS_B, g.sw * 1.05)
        g.p.drawPolyline(QPolygonF([g.pt(0.34, 0.32), g.pt(0.22, 0.50), g.pt(0.34, 0.68)]))
        g.p.drawPolyline(QPolygonF([g.pt(0.66, 0.32), g.pt(0.78, 0.50), g.pt(0.66, 0.68)]))
    elif key == "rec":
        g.fill("#ECEFF1", INK, g.sw * 0.5)
        g.rounded(0.12, 0.22, 0.76, 0.56, 0.10)
        g.fill(RED)
        g.ellipse(0.36, 0.36, 0.28, 0.28)
    elif key == "gear":
        g.stroke(INK, g.sw * 1.05)
        g.ellipse(0.30, 0.30, 0.40, 0.40)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            g.line((0.50 + 0.20 * math.cos(rad), 0.50 + 0.20 * math.sin(rad)),
                   (0.50 + 0.42 * math.cos(rad), 0.50 + 0.42 * math.sin(rad)))
        g.fill("#CFD8DC")
        g.ellipse(0.40, 0.40, 0.20, 0.20)
    elif key == "render":
        g.iso(0.46, 0.62, 0.80, BLUE)
        rg = QRadialGradient(g.pt(0.72, 0.22), g.w * 0.22)
        rg.setColorAt(0, QColor("#FFF59D"))
        rg.setColorAt(1, QColor("#FFC107"))
        g.p.setPen(Qt.NoPen)
        g.p.setBrush(QBrush(rg))
        g.ellipse(0.60, 0.08, 0.28, 0.28)
    elif key == "recent":
        g.stroke(AXIS_B, g.sw * 1.15)
        g.ellipse(0.14, 0.14, 0.72, 0.72)
        g.line((0.50, 0.28), (0.50, 0.52))
        g.line((0.50, 0.52), (0.70, 0.64))
    elif key == "close":
        g.stroke(RED, g.sw * 1.35)
        g.line((0.22, 0.22), (0.78, 0.78))
        g.line((0.78, 0.22), (0.22, 0.78))
    elif key == "recover":
        g.stroke(TEAL[2], g.sw * 1.15)
        g.ellipse(0.16, 0.16, 0.68, 0.68)
        g.arrow((0.78, 0.40), (0.62, 0.16), TEAL[2])
    elif key == "print":
        g.fill("#90A4AE", INK, g.sw * 0.5)
        g.rounded(0.12, 0.34, 0.76, 0.38, 0.06)
        g.fill("#FFFFFF", INK, g.sw * 0.45)
        g.rect(0.28, 0.12, 0.44, 0.26)
        g.rect(0.28, 0.58, 0.44, 0.28)
    elif key == "image":
        g.fill("#E8F1FA", AXIS_B, g.sw * 0.5)
        g.rounded(0.12, 0.16, 0.76, 0.68, 0.05)
        g.fill("#FFD54F")
        g.ellipse(0.22, 0.26, 0.20, 0.20)
        g.fill(AXIS_B)
        g.polygon([(0.26, 0.76), (0.46, 0.42), (0.60, 0.58), (0.72, 0.46), (0.88, 0.76)])
    elif key == "export":
        _doc(g, 0.10, 0.16)
        g.arrow((0.52, 0.48), (0.90, 0.16), AXIS_G)
    elif key == "exit":
        g.fill("#E3F2FD", AXIS_B, g.sw * 0.5)
        g.rounded(0.12, 0.16, 0.52, 0.68, 0.06)
        g.arrow((0.40, 0.50), (0.90, 0.50), RED)
    elif key == "note":
        g.fill("#FFF8E1", INK, g.sw * 0.5)
        g.rounded(0.18, 0.10, 0.64, 0.80, 0.04)
        g.stroke(INK, g.sw * 0.7)
        g.line((0.30, 0.32), (0.70, 0.32))
        g.line((0.30, 0.48), (0.70, 0.48))
        g.line((0.30, 0.64), (0.58, 0.64))
    elif key == "list":
        for fy in (0.22, 0.46, 0.70):
            g.node(0.18, fy + 0.06, 0.055, AXIS_B)
            g.stroke(INK, g.sw * 0.85)
            g.line((0.30, fy + 0.06), (0.88, fy + 0.06))
    elif key == "check":
        # magnifier with a red tick over a small solid
        g.iso(0.36, 0.62, 0.60, GREEN)
        g.stroke(INK)
        g.fill(None)
        g.ellipse(0.44, 0.10, 0.46, 0.46)
        g.stroke(RED, g.sw * 1.4)
        g.line((0.55, 0.33), (0.63, 0.42))
        g.line((0.63, 0.42), (0.79, 0.22))
        g.stroke(INK)
    else:
        g.iso(0.50, 0.56, 0.90, STEEL)


def _render(key: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    _draw(_G(p, size), key)
    p.end()
    return pm


def make_icon(key: str, size: int = 32) -> QIcon:
    cache_key = (key, size)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    icon = QIcon()
    icon.addPixmap(_render(key, size))
    hi = size * 2
    if hi != size:
        icon.addPixmap(_render(key, hi))
    _CACHE[cache_key] = icon
    return icon

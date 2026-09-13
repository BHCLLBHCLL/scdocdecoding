"""QPainter vector icons in the cabdecoding / hmdecoding style.

Filled 2D shapes, round strokes, Material-ish palettes — original art,
not ANSYS / SpaceClaim / KeyShot assets.
"""
from __future__ import annotations

import math

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
    QPolygon, QPolygonF,
)

_CACHE: dict = {}


def _pen(color, w=1.55):
    pe = QPen(QColor(color))
    pe.setWidthF(w)
    pe.setJoinStyle(Qt.RoundJoin)
    pe.setCapStyle(Qt.RoundCap)
    return pe


def _pw(size, base=1.55):
    # Match cabdecoding (~1.6) / hmdecoding (~1.5) weight at toolbar sizes.
    return max(1.35, base * size / 20.0)


def _poly(p, pts, fill, edge, w):
    p.setPen(_pen(edge, w))
    p.setBrush(QBrush(QColor(fill)))
    p.drawPolygon(QPolygon([QPoint(int(x), int(y)) for x, y in pts]))


def _iso(p, r, top="#90caf9", left="#64b5f6", right="#42a5f5", edge="#1565c0", w=1.35):
    """Simple 3-face isometric cube (hmdecoding / cabdecoding)."""
    cx, cy = r.center().x(), r.center().y()
    p.setPen(_pen(edge, max(w, 1.25)))
    p.setBrush(QBrush(QColor(top)))
    p.drawPolygon(QPolygon([
        QPoint(int(cx), int(r.top())),
        QPoint(int(r.right()), int(cy - r.height() * 0.12)),
        QPoint(int(cx), int(cy + r.height() * 0.08)),
        QPoint(int(r.left()), int(cy - r.height() * 0.12)),
    ]))
    p.setBrush(QBrush(QColor(left)))
    p.drawPolygon(QPolygon([
        QPoint(int(r.left()), int(cy - r.height() * 0.12)),
        QPoint(int(cx), int(cy + r.height() * 0.08)),
        QPoint(int(cx), int(r.bottom())),
        QPoint(int(r.left()), int(r.bottom() - r.height() * 0.18)),
    ]))
    p.setBrush(QBrush(QColor(right)))
    p.drawPolygon(QPolygon([
        QPoint(int(cx), int(cy + r.height() * 0.08)),
        QPoint(int(r.right()), int(cy - r.height() * 0.12)),
        QPoint(int(r.right()), int(r.bottom() - r.height() * 0.18)),
        QPoint(int(cx), int(r.bottom())),
    ]))


def _arrow(p, x0, y0, x1, y1, color, w, head=0.28):
    p.setPen(_pen(color, w))
    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    dx, dy = x1 - x0, y1 - y0
    L = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / L, dy / L
    ah = max(3.0, L * head)
    px, py = -uy, ux
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(color)))
    p.drawPolygon(QPolygonF([
        QPointF(x1, y1),
        QPointF(x1 - ux * ah + px * ah * 0.45, y1 - uy * ah + py * ah * 0.45),
        QPointF(x1 - ux * ah - px * ah * 0.45, y1 - uy * ah - py * ah * 0.45),
    ]))


def _node(p, x, y, rad, fill="#ff9800", edge="#e65100"):
    p.setPen(_pen(edge, 1.0))
    p.setBrush(QBrush(QColor(fill)))
    p.drawEllipse(QPointF(x, y), rad, rad)


def _folder(p, r, tab="#f4c542", body="#ffd966", edge="#2e75b6", w=1.2):
    p.setPen(_pen(edge, w))
    p.setBrush(QBrush(QColor(tab)))
    p.drawRoundedRect(QRectF(r.left(), r.top(), r.width() * 0.46,
                             r.height() * 0.30), 1.4, 1.4)
    p.setBrush(QBrush(QColor(body)))
    p.drawRoundedRect(QRectF(r.left(), r.top() + r.height() * 0.22,
                             r.width(), r.height() * 0.70), 1.6, 1.6)


def _doc(p, r, w):
    p.setPen(_pen("#455a64", w))
    p.setBrush(QBrush(QColor("#fff")))
    p.drawRoundedRect(r, 1.5, 1.5)
    p.setBrush(QBrush(QColor("#eceff1")))
    p.drawPolygon(QPolygon([
        QPoint(int(r.right() - r.width() * 0.38), int(r.top())),
        QPoint(int(r.right()), int(r.top() + r.height() * 0.38)),
        QPoint(int(r.right() - r.width() * 0.38),
               int(r.top() + r.height() * 0.38)),
    ]))


def _text(p, r, s, color="#0d47a1", scale=0.5):
    p.setPen(_pen(color, 1.0))
    p.setFont(QFont("Segoe UI", max(6, int(r.height() * scale)), QFont.Bold))
    p.drawText(r.toRect(), Qt.AlignCenter, s)


# ---------------------------------------------------------------------------

def _draw(p: QPainter, r: QRectF, key: str, size: int):
    w = _pw(size)
    cx, cy = r.center().x(), r.center().y()
    L, T, Rgt, B = r.left(), r.top(), r.right(), r.bottom()
    rw, rh = r.width(), r.height()

    if key in ("select", "sel"):
        p.setPen(_pen("#37474f", w))
        path = QPainterPath()
        path.moveTo(L + 1, T + 1)
        path.lineTo(L + 1, B - 2)
        path.lineTo(L + rw * 0.35, T + rh * 0.55)
        path.lineTo(L + rw * 0.55, B - 2)
        path.lineTo(Rgt - 1, T + rh * 0.35)
        path.closeSubpath()
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawPath(path)

    elif key == "pull":
        _iso(p, r.adjusted(0, rh * 0.12, 0, 0), w=w)
        _arrow(p, cx, cy - rh * 0.02, cx, T + 1, "#2e7d32", w * 1.15, 0.32)

    elif key == "move":
        _arrow(p, cx, cy, Rgt - 1, cy, "#c62828", w * 1.1)
        _arrow(p, cx, cy, cx, T + 1, "#2e7d32", w * 1.1)
        _arrow(p, cx, cy, L + rw * 0.12, B - 1, "#1565c0", w * 1.1, 0.34)
        p.setPen(_pen("#fff", 0.8))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawEllipse(QPointF(cx, cy), max(2.2, size * 0.09), max(2.2, size * 0.09))

    elif key == "fill":
        _iso(p, r, top="#b2dfdb", left="#80cbc4", right="#4db6ac",
             edge="#00695c", w=w)
        p.setPen(_pen("#00695c", w))
        p.setBrush(QBrush(QColor("#e0f2f1")))
        p.drawPolygon(QPolygon([
            QPoint(int(cx), int(T + rh * 0.02)),
            QPoint(int(Rgt - 1), int(cy - rh * 0.22)),
            QPoint(int(cx), int(cy - rh * 0.04)),
            QPoint(int(L + 1), int(cy - rh * 0.22)),
        ]))

    elif key == "replace":
        box = QRectF(L, T + rh * 0.18, rw * 0.62, rh * 0.62)
        _iso(p, box, w=w)
        p.setPen(_pen("#ef6c00", w))
        p.setBrush(QBrush(QColor("#ffcc80")))
        p.drawRoundedRect(QRectF(L + rw * 0.38, T, rw * 0.60, rh * 0.58), 2, 2)

    elif key == "combine":
        _iso(p, QRectF(L, T + rh * 0.08, rw * 0.62, rh * 0.78), w=w)
        _iso(p, QRectF(L + rw * 0.32, T + rh * 0.22, rw * 0.66, rh * 0.74),
             top="#ffcc80", left="#ffb74d", right="#ffa726", edge="#ef6c00", w=w)

    elif key in ("split", "splitf"):
        _iso(p, r, w=w)
        p.setPen(_pen("#c62828", w * 1.35))
        p.drawLine(QPointF(L + 1, T + rh * 0.68), QPointF(Rgt - 1, T + rh * 0.28))

    elif key == "cut":
        _doc(p, r.adjusted(0, 0, -rw * 0.08, 0), w)
        p.setPen(_pen("#c62828", w * 1.45))
        p.drawLine(QPoint(int(L + 1), int(T + 1)), QPoint(int(Rgt - 1), int(B - 1)))
        p.drawLine(QPoint(int(Rgt - 1), int(T + 1)), QPoint(int(L + 1), int(B - 1)))

    elif key == "copy":
        p.setPen(_pen("#546e7a", w))
        p.setBrush(QBrush(QColor("#cfd8dc")))
        p.drawRoundedRect(QRectF(L, T + rh * 0.18, rw * 0.62, rh * 0.70), 2, 2)
        p.setBrush(QBrush(QColor("#fff")))
        p.drawRoundedRect(QRectF(L + rw * 0.22, T, rw * 0.72, rh * 0.72), 2, 2)

    elif key == "paste":
        p.setPen(_pen("#546e7a", w))
        p.setBrush(QBrush(QColor("#90a4ae")))
        p.drawRoundedRect(QRectF(L + rw * 0.22, T, rw * 0.56, rh * 0.22), 2, 2)
        p.setBrush(QBrush(QColor("#fffde7")))
        p.drawRoundedRect(QRectF(L, T + rh * 0.16, rw, rh * 0.78), 2, 2)
        p.setPen(_pen("#2e7d32", w * 0.9))
        for i in range(3):
            y = T + rh * (0.40 + i * 0.16)
            p.drawLine(QPointF(L + rw * 0.18, y), QPointF(Rgt - rw * 0.22, y))

    elif key == "new":
        _doc(p, r, w)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        badge = QRectF(L + rw * 0.52, T + rh * 0.52, rw * 0.46, rh * 0.46)
        p.drawEllipse(badge)
        p.setPen(_pen("#fff", w * 1.1))
        p.drawLine(QPointF(badge.center().x(), badge.top() + 3),
                   QPointF(badge.center().x(), badge.bottom() - 3))
        p.drawLine(QPointF(badge.left() + 3, badge.center().y()),
                   QPointF(badge.right() - 3, badge.center().y()))

    elif key == "open":
        _folder(p, r, w=w)

    elif key in ("save", "saveas"):
        p.setPen(_pen("#1f4e79", w))
        p.setBrush(QBrush(QColor("#5b9bd5")))
        p.drawRoundedRect(r, 2, 2)
        p.setBrush(QBrush(QColor("#fff")))
        p.drawRect(QRectF(L + rw * 0.22, T, rw * 0.56, rh * 0.36))
        p.setBrush(QBrush(QColor("#eaf2fb")))
        p.drawRoundedRect(QRectF(L + rw * 0.18, T + rh * 0.48,
                                 rw * 0.64, rh * 0.40), 1, 1)
        if key == "saveas":
            _arrow(p, Rgt - rw * 0.28, T + rh * 0.28, Rgt - 1, T + 1, "#fff", w)

    elif key == "undo":
        p.setPen(_pen("#1565c0", w * 1.45))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), 40 * 16, 250 * 16)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygon([
            QPoint(int(L), int(cy)),
            QPoint(int(L + rw * 0.32), int(cy - rh * 0.28)),
            QPoint(int(L + rw * 0.32), int(cy + rh * 0.08)),
        ]))

    elif key == "redo":
        p.setPen(_pen("#1565c0", w * 1.45))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), 250 * 16, 250 * 16)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygon([
            QPoint(int(Rgt), int(cy)),
            QPoint(int(Rgt - rw * 0.32), int(cy - rh * 0.28)),
            QPoint(int(Rgt - rw * 0.32), int(cy + rh * 0.08)),
        ]))

    elif key == "spin":
        p.setPen(_pen("#6a1b9a", w * 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r.adjusted(2, 2, -2, -2))
        p.drawLine(QPoint(int(cx), int(T + 2)), QPoint(int(cx), int(cy)))
        p.setBrush(QBrush(QColor("#8e24aa")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - 2.4, cy - 2.4, 4.8, 4.8))

    elif key == "pan":
        p.setPen(_pen("#37474f", w * 1.15))
        p.drawLine(QPoint(int(L + 1), int(cy)), QPoint(int(Rgt - 1), int(cy)))
        p.drawLine(QPoint(int(cx), int(T + 1)), QPoint(int(cx), int(B - 1)))
        _arrow(p, cx, cy, Rgt - 1, cy, "#37474f", w * 0.9, 0.22)
        _arrow(p, cx, cy, L + 1, cy, "#37474f", w * 0.9, 0.22)
        _arrow(p, cx, cy, cx, T + 1, "#37474f", w * 0.9, 0.22)
        _arrow(p, cx, cy, cx, B - 1, "#37474f", w * 0.9, 0.22)

    elif key == "zoom":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#bbdefb")))
        circ = r.adjusted(0, 0, -rw * 0.22, -rh * 0.22)
        p.drawEllipse(circ)
        p.setPen(_pen("#1565c0", w * 1.45))
        p.drawLine(QPoint(int(circ.right() - 1), int(circ.bottom() - 1)),
                   QPoint(int(Rgt), int(B)))
        p.setPen(_pen("#1565c0", w))
        p.drawLine(QPointF(circ.center().x() - circ.width() * 0.22, circ.center().y()),
                   QPointF(circ.center().x() + circ.width() * 0.22, circ.center().y()))
        p.drawLine(QPointF(circ.center().x(), circ.center().y() - circ.height() * 0.22),
                   QPointF(circ.center().x(), circ.center().y() + circ.height() * 0.22))

    elif key == "fit":
        p.setPen(_pen("#37474f", w * 1.15))
        p.setBrush(Qt.NoBrush)
        s = rw * 0.28
        for x, y, sx, sy in (
            (L, T, 1, 1), (Rgt, T, -1, 1),
            (L, B, 1, -1), (Rgt, B, -1, -1),
        ):
            p.drawLine(QPoint(int(x), int(y)), QPoint(int(x + sx * s), int(y)))
            p.drawLine(QPoint(int(x), int(y)), QPoint(int(x), int(y + sy * s)))
        p.setBrush(QBrush(QColor("#90a4ae")))
        p.drawEllipse(r.adjusted(rw * 0.28, rh * 0.28, -rw * 0.28, -rh * 0.28))

    elif key == "prev":
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(QPolygon([
            QPoint(int(Rgt - rw * 0.12), int(T + rh * 0.12)),
            QPoint(int(L + rw * 0.12), int(cy)),
            QPoint(int(Rgt - rw * 0.12), int(B - rh * 0.12)),
        ]))

    elif key == "home":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawPolygon(QPolygon([
            QPoint(int(cx), int(T + 1)),
            QPoint(int(Rgt - 1), int(T + rh * 0.42)),
            QPoint(int(Rgt - rw * 0.18), int(T + rh * 0.42)),
            QPoint(int(Rgt - rw * 0.18), int(B - 1)),
            QPoint(int(L + rw * 0.18), int(B - 1)),
            QPoint(int(L + rw * 0.18), int(T + rh * 0.42)),
            QPoint(int(L + 1), int(T + rh * 0.42)),
        ]))

    elif key == "iso":
        _iso(p, r, w=w)

    elif key == "viewx":
        p.setPen(_pen("#c62828", w))
        p.setBrush(QBrush(QColor("#ef9a9a")))
        p.drawRect(r.adjusted(2, 2, -2, -2))
        _text(p, r, "X", "#b71c1c", 0.48)

    elif key == "viewy":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(QBrush(QColor("#a5d6a7")))
        p.drawRect(r.adjusted(1, rh * 0.22, -1, -rh * 0.22))
        _text(p, r, "Y", "#1b5e20", 0.48)

    elif key == "viewz":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawRect(r.adjusted(rw * 0.18, 1, -rw * 0.18, -1))
        _text(p, r, "Z", "#0d47a1", 0.48)

    elif key == "line":
        p.setPen(_pen("#2e7d32", w * 1.25))
        p.drawLine(QPoint(int(L + 1), int(B - 2)), QPoint(int(Rgt - 1), int(T + 2)))
        _node(p, L + 2, B - 2, max(2.0, size * 0.08))
        _node(p, Rgt - 2, T + 2, max(2.0, size * 0.08))

    elif key == "tangent":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(L, T + rh * 0.22, rw * 0.58, rh * 0.58))
        p.setPen(_pen("#2e7d32", w * 1.15))
        p.drawLine(QPointF(L + rw * 0.08, T + rh * 0.18),
                   QPointF(Rgt - 1, T + rh * 0.18))
        _node(p, L + rw * 0.42, T + rh * 0.18, max(2.0, size * 0.07))

    elif key == "rect":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, rh * 0.12, -1, -rh * 0.08), 1.5, 1.5)
        _node(p, L + 2, T + rh * 0.12, max(2.0, size * 0.07))
        _node(p, Rgt - 2, B - rh * 0.08, max(2.0, size * 0.07))

    elif key == "rect3":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        pts = [(0.16, 0.74), (0.38, 0.18), (0.88, 0.34), (0.66, 0.88)]
        p.drawPolygon(QPolygon([
            QPoint(int(L + fx * rw), int(T + fy * rh)) for fx, fy in pts
        ]))
        for fx, fy in pts[:3]:
            _node(p, L + fx * rw, T + fy * rh, max(1.8, size * 0.065))

    elif key == "circle":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r.adjusted(1, 1, -1, -1))
        _node(p, cx, cy, max(2.0, size * 0.07))
        _node(p, Rgt - 2, cy, max(1.8, size * 0.06))

    elif key == "circle3":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r.adjusted(1, 1, -1, -1))
        for fx, fy in ((0.28, 0.28), (0.78, 0.30), (0.58, 0.82)):
            _node(p, L + fx * rw, T + fy * rh, max(1.8, size * 0.065))

    elif key == "ellipse":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r.adjusted(0, rh * 0.18, 0, -rh * 0.18))
        _node(p, cx, cy, max(2.0, size * 0.07))

    elif key == "spline":
        p.setPen(_pen("#2e7d32", w * 1.1))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(L + 1, B - rh * 0.18))
        path.cubicTo(QPointF(L + rw * 0.28, T + 1),
                     QPointF(L + rw * 0.68, B - 1),
                     QPointF(Rgt - 1, T + rh * 0.22))
        p.drawPath(path)
        _node(p, L + 1, B - rh * 0.18, max(2.0, size * 0.07))
        _node(p, Rgt - 1, T + rh * 0.22, max(2.0, size * 0.07))

    elif key == "point":
        p.setPen(_pen("#2e7d32", w * 0.9))
        p.drawLine(QPointF(cx, T + 1), QPointF(cx, T + rh * 0.32))
        p.drawLine(QPointF(cx, B - rh * 0.32), QPointF(cx, B - 1))
        p.drawLine(QPointF(L + 1, cy), QPointF(L + rw * 0.32, cy))
        p.drawLine(QPointF(Rgt - rw * 0.32, cy), QPointF(Rgt - 1, cy))
        _node(p, cx, cy, max(2.6, size * 0.11))

    elif key == "const":
        pe = _pen("#78909c", w)
        pe.setStyle(Qt.DashLine)
        pe.setDashPattern([2.4, 2.0])
        p.setPen(pe)
        p.drawLine(QPoint(int(L + 1), int(B - 2)), QPoint(int(Rgt - 1), int(T + 2)))

    elif key == "offset":
        pe = _pen("#90a4ae", w)
        pe.setStyle(Qt.DashLine)
        p.setPen(pe)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0, rh * 0.22, -rw * 0.28, 0), 1.5, 1.5)
        p.setPen(_pen("#2e7d32", w))
        p.drawRoundedRect(r.adjusted(rw * 0.22, 0, 0, -rh * 0.22), 1.5, 1.5)

    elif key == "layout":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 2, 2)
        p.drawLine(QPointF(cx, T + 1), QPointF(cx, B - 1))
        p.drawLine(QPointF(L + 1, cy), QPointF(Rgt - 1, cy))

    elif key == "grid":
        p.setPen(_pen("#2e7d32", w * 0.85))
        for t in (0.18, 0.50, 0.82):
            p.drawLine(QPointF(L + t * rw, T + 1), QPointF(L + t * rw, B - 1))
            p.drawLine(QPointF(L + 1, T + t * rh), QPointF(Rgt - 1, T + t * rh))

    elif key == "mode_sketch":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(QBrush(QColor("#e8f5e9")))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(_pen("#2e7d32", w * 1.05))
        p.drawLine(QPointF(L + rw * 0.18, B - rh * 0.22),
                   QPointF(L + rw * 0.42, T + rh * 0.28))
        p.drawLine(QPointF(L + rw * 0.42, T + rh * 0.28),
                   QPointF(Rgt - rw * 0.16, T + rh * 0.52))
        _node(p, L + rw * 0.42, T + rh * 0.28, max(2.0, size * 0.07))

    elif key == "mode_section":
        _iso(p, r, w=w)
        p.setPen(_pen("#00838f", w))
        p.setBrush(QBrush(QColor(0, 151, 167, 120)))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.08), int(T + rh * 0.42)),
            QPoint(int(Rgt - 1), int(T + rh * 0.22)),
            QPoint(int(Rgt - 1), int(B - rh * 0.12)),
            QPoint(int(L + rw * 0.08), int(B - rh * 0.04)),
        ]))

    elif key == "mode_3d":
        _iso(p, r, w=w)

    elif key == "dim":
        p.setPen(_pen("#2e7d32", w * 0.9))
        p.drawLine(QPointF(L + rw * 0.16, T + 1), QPointF(L + rw * 0.16, B - 1))
        p.drawLine(QPointF(Rgt - rw * 0.16, T + 1), QPointF(Rgt - rw * 0.16, B - 1))
        _arrow(p, L + rw * 0.20, cy, Rgt - rw * 0.20, cy, "#1565c0", w)
        _arrow(p, Rgt - rw * 0.20, cy, L + rw * 0.20, cy, "#1565c0", w)

    elif key == "hv":
        p.setPen(_pen("#2e7d32", w * 1.1))
        p.drawLine(QPointF(L + 1, B - rh * 0.18), QPointF(Rgt - 1, B - rh * 0.18))
        p.drawLine(QPointF(cx, T + 1), QPointF(cx, B - rh * 0.18))
        _node(p, cx, B - rh * 0.18, max(2.0, size * 0.07))

    elif key == "coin":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(L, T, rw * 0.58, rh * 0.58))
        p.drawEllipse(QRectF(L + rw * 0.38, T + rh * 0.38, rw * 0.58, rh * 0.58))
        _node(p, cx, cy, max(2.0, size * 0.07))

    elif key == "tan":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(L, T + rh * 0.28, rw * 0.54, rh * 0.54))
        p.drawLine(QPointF(L + rw * 0.10, T + rh * 0.16),
                   QPointF(Rgt - 1, T + rh * 0.16))
        _node(p, L + rw * 0.36, T + rh * 0.16, max(2.0, size * 0.07))

    elif key == "eq":
        p.setPen(_pen("#2e7d32", w * 1.25))
        p.drawLine(QPointF(L + rw * 0.12, T + rh * 0.36),
                   QPointF(Rgt - rw * 0.12, T + rh * 0.36))
        p.drawLine(QPointF(L + rw * 0.12, T + rh * 0.64),
                   QPointF(Rgt - rw * 0.12, T + rh * 0.64))

    elif key == "par":
        p.setPen(_pen("#2e7d32", w * 1.15))
        p.drawLine(QPointF(L + rw * 0.18, B - 2), QPointF(L + rw * 0.42, T + 2))
        p.drawLine(QPointF(L + rw * 0.56, B - 2), QPointF(L + rw * 0.80, T + 2))

    elif key == "fix":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#42a5f5")))
        p.drawEllipse(QRectF(cx - rw * 0.16, T + rh * 0.08, rw * 0.32, rh * 0.32))
        p.setPen(_pen("#37474f", w))
        p.drawLine(QPointF(cx, T + rh * 0.40), QPointF(cx, T + rh * 0.62))
        p.drawLine(QPointF(L + rw * 0.18, B - rh * 0.18),
                   QPointF(Rgt - rw * 0.18, B - rh * 0.18))
        p.drawLine(QPointF(L + rw * 0.22, T + rh * 0.62),
                   QPointF(L + rw * 0.12, B - 1))
        p.drawLine(QPointF(cx, T + rh * 0.62), QPointF(cx, B - 1))
        p.drawLine(QPointF(Rgt - rw * 0.22, T + rh * 0.62),
                   QPointF(Rgt - rw * 0.12, B - 1))

    elif key == "pattern":
        cell = min(rw, rh) * 0.38
        for i, (fx, fy) in enumerate(((0.08, 0.08), (0.54, 0.08),
                                      (0.08, 0.54), (0.54, 0.54))):
            box = QRectF(L + fx * rw, T + fy * rh, cell, cell)
            if i == 0:
                _iso(p, box, w=max(1.0, w * 0.85))
            else:
                _iso(p, box, top="#cfd8dc", left="#b0bec5", right="#90a4ae",
                     edge="#546e7a", w=max(1.0, w * 0.85))

    elif key == "mirror":
        _iso(p, QRectF(L, T + rh * 0.08, rw * 0.46, rh * 0.84), w=w)
        pe = _pen("#90a4ae", w)
        pe.setStyle(Qt.DashLine)
        p.setPen(pe)
        p.drawLine(QPointF(cx, T + 1), QPointF(cx, B - 1))
        _iso(p, QRectF(L + rw * 0.50, T + rh * 0.08, rw * 0.48, rh * 0.84),
             top="#cfd8dc", left="#b0bec5", right="#90a4ae", edge="#546e7a", w=w)

    elif key == "project":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(L + rw * 0.22, T, rw * 0.56, rh * 0.36))
        _iso(p, QRectF(L + rw * 0.12, T + rh * 0.32, rw * 0.76, rh * 0.66), w=w)
        _arrow(p, cx, T + rh * 0.34, cx, T + rh * 0.52, "#1565c0", w, 0.4)

    elif key == "shell":
        _iso(p, r, w=w)
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#e3f2fd")))
        p.drawPolygon(QPolygon([
            QPoint(int(cx), int(T + rh * 0.16)),
            QPoint(int(Rgt - rw * 0.22), int(cy - rh * 0.04)),
            QPoint(int(cx), int(cy + rh * 0.08)),
            QPoint(int(L + rw * 0.22), int(cy - rh * 0.04)),
        ]))

    elif key == "blend":
        p.setPen(_pen("#37474f", w * 1.1))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(L + 2, T + 2))
        path.lineTo(QPointF(L + 2, T + rh * 0.55))
        path.quadTo(QPointF(L + 2, B - 2), QPointF(L + rw * 0.48, B - 2))
        path.lineTo(QPointF(Rgt - 2, B - 2))
        p.drawPath(path)
        pe = _pen("#2e7d32", w * 0.9)
        pe.setStyle(Qt.DashLine)
        p.setPen(pe)
        p.drawLine(QPointF(L + 2, T + rh * 0.55), QPointF(L + 2, B - 2))
        p.drawLine(QPointF(L + 2, B - 2), QPointF(L + rw * 0.48, B - 2))

    elif key == "chamfer":
        p.setPen(_pen("#37474f", w * 1.1))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([
            QPointF(L + 2, T + 2), QPointF(L + 2, T + rh * 0.52),
            QPointF(L + rw * 0.42, B - 2), QPointF(Rgt - 2, B - 2),
        ]))
        p.setPen(_pen("#ef6c00", w * 1.1))
        p.drawLine(QPointF(L + 2, T + rh * 0.52), QPointF(L + rw * 0.42, B - 2))

    elif key == "draft":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.28), int(T + 1)),
            QPoint(int(Rgt - rw * 0.28), int(T + 1)),
            QPoint(int(Rgt - 1), int(B - 1)),
            QPoint(int(L + 1), int(B - 1)),
        ]))

    elif key == "offace":
        _iso(p, QRectF(L + rw * 0.08, T + rh * 0.28, rw * 0.84, rh * 0.70), w=w)
        p.setPen(_pen("#00838f", w))
        p.setBrush(QBrush(QColor(128, 222, 234, 160)))
        p.drawPolygon(QPolygon([
            QPoint(int(cx), int(T + 1)),
            QPoint(int(Rgt - 2), int(T + rh * 0.28)),
            QPoint(int(cx), int(T + rh * 0.42)),
            QPoint(int(L + 2), int(T + rh * 0.28)),
        ]))
        _arrow(p, cx, T + rh * 0.48, cx, T + rh * 0.22, "#2e7d32", w, 0.4)

    elif key == "plane":
        p.setPen(_pen("#0277bd", w))
        p.setBrush(QBrush(QColor("#81d4fa")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.08), int(B - 1)),
            QPoint(int(L + rw * 0.35), int(T + 1)),
            QPoint(int(Rgt - 1), int(T + 1)),
            QPoint(int(Rgt - rw * 0.27), int(B - 1)),
        ]))

    elif key == "origin":
        _arrow(p, L + rw * 0.18, B - rh * 0.18, Rgt - 1, B - rh * 0.18, "#c62828", w)
        _arrow(p, L + rw * 0.18, B - rh * 0.18, L + rw * 0.18, T + 1, "#2e7d32", w)
        _arrow(p, L + rw * 0.18, B - rh * 0.18, L + 1, B - 1, "#1565c0", w, 0.36)
        p.setPen(_pen("#37474f", 1.0))
        p.setBrush(QBrush(QColor("#fff")))
        p.drawEllipse(QPointF(L + rw * 0.18, B - rh * 0.18),
                      max(2.2, size * 0.08), max(2.2, size * 0.08))

    elif key == "axis":
        p.setPen(_pen("#1565c0", w * 1.2))
        p.drawLine(QPoint(int(L + 1), int(B - 2)), QPoint(int(Rgt - 1), int(T + 2)))
        _node(p, L + 2, B - 2, max(2.0, size * 0.08), "#42a5f5", "#1565c0")
        _node(p, Rgt - 2, T + 2, max(2.0, size * 0.08), "#42a5f5", "#1565c0")

    elif key == "cyl":
        p.setPen(_pen("#00695c", w))
        p.setBrush(QBrush(QColor("#80cbc4")))
        p.drawEllipse(QRectF(L + 2, T, rw - 4, rh * 0.28))
        p.drawRect(QRectF(L + 2, T + rh * 0.14, rw - 4, rh * 0.60))
        p.drawEllipse(QRectF(L + 2, B - rh * 0.28, rw - 4, rh * 0.28))
        p.setBrush(QBrush(QColor("#b2dfdb")))
        p.drawEllipse(QRectF(L + 2, T, rw - 4, rh * 0.28))

    elif key == "sphere":
        p.setPen(_pen("#ad1457", w))
        p.setBrush(QBrush(QColor("#f48fb1")))
        p.drawEllipse(r)
        p.setPen(_pen("#880e4f", w * 0.8))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(L, T + rh * 0.32, rw, rh * 0.36))

    elif key == "helix":
        p.setPen(_pen("#ef6c00", w * 1.15))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(L + rw * 0.18, B - 2))
        path.cubicTo(QPointF(Rgt - 2, B - rh * 0.28),
                     QPointF(L + 2, T + rh * 0.48),
                     QPointF(Rgt - rw * 0.18, T + rh * 0.28))
        path.cubicTo(QPointF(Rgt - 1, T + rh * 0.16),
                     QPointF(L + rw * 0.22, T + rh * 0.12),
                     QPointF(cx, T + 2))
        p.drawPath(path)

    elif key == "comp":
        _iso(p, QRectF(L, T, rw * 0.62, rh * 0.62), w=w)
        _iso(p, QRectF(L + rw * 0.32, T + rh * 0.28, rw * 0.66, rh * 0.70),
             top="#ffcc80", left="#ffb74d", right="#ffa726", edge="#ef6c00", w=w)

    elif key == "face":
        p.setPen(_pen("#0277bd", w))
        p.setBrush(QBrush(QColor("#81d4fa")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.10), int(T + rh * 0.28)),
            QPoint(int(L + rw * 0.78), int(T + 2)),
            QPoint(int(Rgt - 1), int(B - rh * 0.18)),
            QPoint(int(L + rw * 0.16), int(B - 1)),
        ]))

    elif key == "edge":
        _iso(p, r, top="#cfd8dc", left="#b0bec5", right="#90a4ae",
             edge="#546e7a", w=w)
        p.setPen(_pen("#1565c0", w * 1.4))
        p.drawLine(QPointF(Rgt - rw * 0.08, T + rh * 0.22),
                   QPointF(cx, B - 2))

    elif key == "vert":
        _iso(p, r, top="#cfd8dc", left="#b0bec5", right="#90a4ae",
             edge="#546e7a", w=w)
        _node(p, cx, T + rh * 0.18, max(2.4, size * 0.09), "#42a5f5", "#1565c0")

    elif key in ("shaded", "shaded2"):
        _iso(p, r, w=w)
        if key == "shaded":
            p.setPen(_pen("#1a237e", w * 0.75))
            p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(cx, T), QPointF(cx, B))
            p.drawLine(QPointF(L, cy - rh * 0.12), QPointF(cx, cy + rh * 0.08))
            p.drawLine(QPointF(Rgt, cy - rh * 0.12), QPointF(cx, cy + rh * 0.08))

    elif key == "wire":
        p.setPen(_pen("#1a237e", w))
        p.setBrush(Qt.NoBrush)
        cx2, cy2 = cx, cy
        p.drawPolygon(QPolygon([
            QPoint(int(cx2), int(T)),
            QPoint(int(Rgt), int(cy2 - rh * 0.12)),
            QPoint(int(cx2), int(cy2 + rh * 0.08)),
            QPoint(int(L), int(cy2 - rh * 0.12)),
        ]))
        p.drawPolygon(QPolygon([
            QPoint(int(L), int(cy2 - rh * 0.12)),
            QPoint(int(cx2), int(cy2 + rh * 0.08)),
            QPoint(int(cx2), int(B)),
            QPoint(int(L), int(B - rh * 0.18)),
        ]))
        p.drawPolygon(QPolygon([
            QPoint(int(cx2), int(cy2 + rh * 0.08)),
            QPoint(int(Rgt), int(cy2 - rh * 0.12)),
            QPoint(int(Rgt), int(B - rh * 0.18)),
            QPoint(int(cx2), int(B)),
        ]))

    elif key == "transp":
        _iso(p, r, top="#bbdefb", left="#90caf9", right="#64b5f6",
             edge="#1565c0", w=w)
        p.setPen(_pen("#fff", w * 0.9))
        p.setBrush(QBrush(QColor(255, 255, 255, 140)))
        p.drawEllipse(r.adjusted(rw * 0.22, rh * 0.22, -rw * 0.22, -rh * 0.22))

    elif key == "sil":
        p.setPen(_pen("#37474f", w * 1.15))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(L + rw * 0.12, B - 2))
        path.quadTo(QPointF(L + rw * 0.12, T + 2), QPointF(cx, T + 2))
        path.quadTo(QPointF(Rgt - rw * 0.12, T + 2), QPointF(Rgt - rw * 0.12, B - 2))
        p.drawPath(path)

    elif key == "sect":
        _iso(p, r, w=w)
        p.setPen(_pen("#c62828", w * 1.35))
        p.drawLine(QPointF(L + 1, T + rh * 0.70), QPointF(Rgt - 1, T + rh * 0.28))

    elif key == "measure":
        p.setPen(_pen("#6a1b9a", w * 1.15))
        p.drawLine(QPoint(int(L), int(B - 2)), QPoint(int(Rgt), int(T + 2)))
        p.drawLine(QPoint(int(L), int(B - 5)), QPoint(int(L), int(B)))
        p.drawLine(QPoint(int(Rgt), int(T)), QPoint(int(Rgt), int(T + 5)))

    elif key == "mass":
        _iso(p, r, top="#cfd8dc", left="#b0bec5", right="#90a4ae",
             edge="#455a64", w=w)
        p.setPen(_pen("#6a1b9a", w))
        p.setBrush(QBrush(QColor("#ce93d8")))
        p.drawEllipse(QRectF(cx - rw * 0.18, T, rw * 0.36, rh * 0.28))

    elif key == "rev":
        p.setPen(_pen("#c62828", w * 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), -20 * 16, 220 * 16)
        _iso(p, r.adjusted(rw * 0.18, rh * 0.18, -rw * 0.18, -rh * 0.08),
             w=max(1.0, w * 0.85))

    elif key == "smooth":
        p.setPen(_pen("#00838f", w * 1.2))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(L + 1, B - rh * 0.22))
        path.cubicTo(QPointF(L + rw * 0.32, T + 1),
                     QPointF(L + rw * 0.68, B - 1),
                     QPointF(Rgt - 1, T + rh * 0.22))
        p.drawPath(path)

    elif key == "reduce":
        _iso(p, QRectF(L, T, rw * 0.62, rh * 0.62), w=w)
        _iso(p, QRectF(L + rw * 0.42, T + rh * 0.42, rw * 0.52, rh * 0.52),
             top="#cfd8dc", left="#b0bec5", right="#90a4ae", edge="#546e7a", w=w)

    elif key in ("solid", "box"):
        _iso(p, r, top="#ffcc80", left="#ffb74d", right="#ffa726",
             edge="#ef6c00", w=w)

    elif key == "stitch":
        p.setPen(_pen("#2e7d32", w))
        p.setBrush(QBrush(QColor("#a5d6a7")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + 1), int(T + rh * 0.28)),
            QPoint(int(L + rw * 0.40), int(T + rh * 0.12)),
            QPoint(int(L + rw * 0.44), int(B - rh * 0.12)),
            QPoint(int(L + rw * 0.08), int(B - 1)),
        ]))
        p.setBrush(QBrush(QColor("#81c784")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.56), int(T + rh * 0.16)),
            QPoint(int(Rgt - 1), int(T + 2)),
            QPoint(int(Rgt - 1), int(B - rh * 0.16)),
            QPoint(int(L + rw * 0.58), int(B - 2)),
        ]))
        p.setPen(_pen("#1565c0", w))
        p.drawLine(QPointF(L + rw * 0.40, cy - 2), QPointF(L + rw * 0.58, cy - 4))
        p.drawLine(QPointF(L + rw * 0.42, cy + 6), QPointF(L + rw * 0.60, cy + 4))

    elif key == "gaps":
        _iso(p, QRectF(L, T + rh * 0.08, rw * 0.44, rh * 0.84), w=w)
        _iso(p, QRectF(L + rw * 0.56, T + rh * 0.08, rw * 0.44, rh * 0.84),
             top="#ffcc80", left="#ffb74d", right="#ffa726", edge="#ef6c00", w=w)

    elif key == "script":
        p.setPen(_pen("#37474f", w))
        p.setBrush(QBrush(QColor("#fffde7")))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(_pen("#1565c0", w * 1.1))
        p.drawPolyline(QPolygonF([
            QPointF(L + rw * 0.32, T + rh * 0.28),
            QPointF(L + rw * 0.18, cy),
            QPointF(L + rw * 0.32, B - rh * 0.28),
        ]))
        p.drawPolyline(QPolygonF([
            QPointF(Rgt - rw * 0.32, T + rh * 0.28),
            QPointF(Rgt - rw * 0.18, cy),
            QPointF(Rgt - rw * 0.32, B - rh * 0.28),
        ]))

    elif key == "rec":
        p.setPen(_pen("#455a64", w))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawRoundedRect(r.adjusted(0, rh * 0.16, 0, -rh * 0.16), 3, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#c62828")))
        p.drawEllipse(r.adjusted(rw * 0.28, rh * 0.28, -rw * 0.28, -rh * 0.28))

    elif key == "gear":
        p.setPen(_pen("#455a64", w))
        p.setBrush(QBrush(QColor("#90a4ae")))
        path = QPainterPath()
        path.addEllipse(QRectF(cx - rw * 0.22, cy - rh * 0.22, rw * 0.44, rh * 0.44))
        p.drawPath(path)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            p.drawLine(QPointF(cx + rw * 0.22 * math.cos(rad),
                               cy + rh * 0.22 * math.sin(rad)),
                       QPointF(cx + rw * 0.44 * math.cos(rad),
                               cy + rh * 0.44 * math.sin(rad)))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawEllipse(QRectF(cx - rw * 0.10, cy - rh * 0.10, rw * 0.20, rh * 0.20))

    elif key == "render":
        _iso(p, r.adjusted(0, rh * 0.12, -rw * 0.08, 0), w=w)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#ffc107")))
        p.drawEllipse(QRectF(L + rw * 0.58, T, rw * 0.38, rh * 0.38))

    elif key == "recent":
        p.setPen(_pen("#1565c0", w * 1.15))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r)
        p.drawLine(QPointF(cx, T + rh * 0.22), QPointF(cx, cy))
        p.drawLine(QPointF(cx, cy), QPointF(L + rw * 0.72, T + rh * 0.68))

    elif key == "close":
        p.setPen(_pen("#c62828", w * 1.4))
        p.drawLine(QPoint(int(L + 1), int(T + 1)), QPoint(int(Rgt - 1), int(B - 1)))
        p.drawLine(QPoint(int(Rgt - 1), int(T + 1)), QPoint(int(L + 1), int(B - 1)))

    elif key == "done":
        p.setPen(_pen("#2e7d32", w * 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([
            QPointF(L + rw * 0.12, cy),
            QPointF(L + rw * 0.38, B - rh * 0.18),
            QPointF(Rgt - rw * 0.10, T + rh * 0.18),
        ]))

    elif key == "recover":
        p.setPen(_pen("#00838f", w * 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), 40 * 16, 280 * 16)
        _arrow(p, Rgt - rw * 0.18, T + rh * 0.38, L + rw * 0.68, T + 2, "#00838f", w, 0.4)

    elif key == "print":
        p.setPen(_pen("#455a64", w))
        p.setBrush(QBrush(QColor("#90a4ae")))
        p.drawRoundedRect(QRectF(L, T + rh * 0.28, rw, rh * 0.42), 2, 2)
        p.setBrush(QBrush(QColor("#fff")))
        p.drawRect(QRectF(L + rw * 0.22, T, rw * 0.56, rh * 0.34))
        p.drawRect(QRectF(L + rw * 0.18, T + rh * 0.58, rw * 0.64, rh * 0.34))

    elif key == "image":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#e3f2fd")))
        p.drawRoundedRect(r, 2, 2)
        p.setBrush(QBrush(QColor("#ffd54f")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(L + rw * 0.12, T + rh * 0.14, rw * 0.28, rh * 0.28))
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.18), int(B - 2)),
            QPoint(int(L + rw * 0.42), int(T + rh * 0.42)),
            QPoint(int(L + rw * 0.58), int(T + rh * 0.58)),
            QPoint(int(L + rw * 0.74), int(T + rh * 0.40)),
            QPoint(int(Rgt - 2), int(B - 2)),
        ]))

    elif key == "export":
        _doc(p, r.adjusted(0, 0, -rw * 0.18, 0), w)
        _arrow(p, cx, cy, Rgt - 1, T + rh * 0.12, "#2e7d32", w * 1.15)

    elif key == "exit":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#e3f2fd")))
        p.drawRoundedRect(QRectF(L, T + rh * 0.08, rw * 0.58, rh * 0.84), 2, 2)
        _arrow(p, L + rw * 0.36, cy, Rgt - 1, cy, "#c62828", w * 1.15)

    elif key == "note":
        p.setPen(_pen("#f9a825", w))
        p.setBrush(QBrush(QColor("#fff8e1")))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(_pen("#6d4c41", w * 0.85))
        for i in range(3):
            y = T + rh * (0.30 + i * 0.18)
            p.drawLine(QPointF(L + rw * 0.18, y),
                       QPointF(Rgt - rw * (0.18 if i < 2 else 0.36), y))

    elif key == "list":
        for i, fy in enumerate((0.22, 0.50, 0.78)):
            _node(p, L + rw * 0.14, T + fy * rh, max(1.8, size * 0.06),
                  "#42a5f5", "#1565c0")
            p.setPen(_pen("#455a64", w * 0.9))
            p.drawLine(QPointF(L + rw * 0.28, T + fy * rh),
                       QPointF(Rgt - 2, T + fy * rh))

    elif key == "params":
        for fy, kx in ((0.28, 0.62), (0.50, 0.32), (0.72, 0.70)):
            p.setPen(_pen("#455a64", w))
            p.drawLine(QPointF(L + 2, T + fy * rh), QPointF(Rgt - 2, T + fy * rh))
            p.setPen(_pen("#1565c0", 1.0))
            p.setBrush(QBrush(QColor("#42a5f5")))
            p.drawEllipse(QPointF(L + kx * rw, T + fy * rh),
                          max(2.4, size * 0.08), max(2.4, size * 0.08))

    elif key == "check":
        _iso(p, QRectF(L, T + rh * 0.22, rw * 0.70, rh * 0.76),
             top="#a5d6a7", left="#81c784", right="#66bb6a", edge="#2e7d32", w=w)
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#bbdefb")))
        mag = QRectF(L + rw * 0.38, T, rw * 0.48, rh * 0.48)
        p.drawEllipse(mag)
        p.setPen(_pen("#1565c0", w * 1.3))
        p.drawLine(QPointF(mag.right() - 1, mag.bottom() - 1),
                   QPointF(Rgt, B - rh * 0.12))

    elif key == "load":
        p.setPen(_pen("#e53935", w))
        p.setBrush(QBrush(QColor("#ef9a9a")))
        p.drawPolygon(QPolygon([
            QPoint(int(cx), int(T + 1)),
            QPoint(int(Rgt - 1), int(B - rh * 0.18)),
            QPoint(int(L + 1), int(B - rh * 0.18)),
        ]))
        p.setPen(_pen("#b71c1c", w))
        p.drawLine(QPointF(cx, T + rh * 0.28), QPointF(cx, B - rh * 0.28))

    elif key == "support":
        p.setPen(_pen("#455a64", w))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawRect(QRectF(L + rw * 0.18, T, rw * 0.64, rh * 0.22))
        p.setBrush(QBrush(QColor("#b0bec5")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.22), int(T + rh * 0.22)),
            QPoint(int(Rgt - rw * 0.22), int(T + rh * 0.22)),
            QPoint(int(Rgt - rw * 0.08), int(B - 1)),
            QPoint(int(L + rw * 0.08), int(B - 1)),
        ]))

    elif key == "contact":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawRoundedRect(QRectF(L, T + rh * 0.12, rw * 0.58, rh * 0.76), 2, 2)
        p.setBrush(QBrush(QColor("#ffcc80")))
        p.setPen(_pen("#ef6c00", w))
        p.drawRoundedRect(QRectF(L + rw * 0.42, T + rh * 0.12, rw * 0.56, rh * 0.76), 2, 2)

    elif key == "report":
        p.setPen(_pen("#1565c0", w))
        p.setBrush(QBrush(QColor("#e3f2fd")))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(_pen("#1565c0", w * 0.9))
        for i in range(3):
            y = T + rh * (0.30 + i * 0.20)
            p.drawLine(QPointF(L + rw * 0.18, y), QPointF(Rgt - rw * 0.18, y))

    elif key == "thick":
        p.setPen(_pen("#0277bd", w))
        p.setBrush(QBrush(QColor("#81d4fa")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.08), int(B - rh * 0.28)),
            QPoint(int(L + rw * 0.32), int(T + rh * 0.18)),
            QPoint(int(Rgt - 1), int(T + rh * 0.18)),
            QPoint(int(Rgt - rw * 0.22), int(B - rh * 0.28)),
        ]))
        p.setBrush(QBrush(QColor("#4fc3f7")))
        p.drawPolygon(QPolygon([
            QPoint(int(L + rw * 0.08), int(B - rh * 0.28)),
            QPoint(int(Rgt - rw * 0.22), int(B - rh * 0.28)),
            QPoint(int(Rgt - rw * 0.22), int(B - 1)),
            QPoint(int(L + rw * 0.08), int(B - 1)),
        ]))

    elif key == "untrim":
        p.setPen(_pen("#0277bd", w))
        p.setBrush(QBrush(QColor("#b3e5fc")))
        p.drawRoundedRect(r, 2, 2)
        pe = _pen("#0277bd", w)
        pe.setStyle(Qt.DashLine)
        p.setPen(pe)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r.adjusted(rw * 0.18, rh * 0.18, -rw * 0.18, -rh * 0.18))

    elif key == "extend":
        p.setPen(_pen("#2e7d32", w * 1.15))
        p.drawLine(QPointF(L + 1, B - rh * 0.28), QPointF(cx, T + rh * 0.22))
        pe = _pen("#2e7d32", w)
        pe.setStyle(Qt.DashLine)
        p.setPen(pe)
        p.drawLine(QPointF(cx, T + rh * 0.22), QPointF(Rgt - 1, T + 2))
        _arrow(p, cx, T + rh * 0.22, Rgt - 1, T + 2, "#2e7d32", w, 0.4)

    elif key == "patch":
        p.setPen(_pen("#0277bd", w))
        p.setBrush(QBrush(QColor("#81d4fa")))
        p.drawRoundedRect(r.adjusted(0, rh * 0.18, 0, -rh * 0.08), 2, 2)
        p.setBrush(QBrush(QColor("#4fc3f7")))
        p.drawEllipse(QRectF(L + rw * 0.28, T, rw * 0.44, rh * 0.44))

    elif key == "bend":
        p.setPen(_pen("#ef6c00", w * 1.15))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(L + 1, B - rh * 0.18))
        path.lineTo(QPointF(L + rw * 0.42, B - rh * 0.18))
        path.quadTo(QPointF(L + rw * 0.62, B - rh * 0.18),
                    QPointF(L + rw * 0.62, T + rh * 0.42))
        path.lineTo(QPointF(L + rw * 0.62, T + 2))
        p.drawPath(path)
        p.setPen(_pen("#bf360c", w))
        p.setBrush(QBrush(QColor("#ffcc80")))
        p.drawRect(QRectF(L + 1, B - rh * 0.34, rw * 0.42, rh * 0.28))

    elif key == "unfold":
        p.setPen(_pen("#ef6c00", w))
        p.setBrush(QBrush(QColor("#ffe0b2")))
        p.drawRoundedRect(r.adjusted(0, rh * 0.22, 0, -rh * 0.22), 2, 2)
        p.setPen(_pen("#ef6c00", w * 0.85))
        p.drawLine(QPointF(L + rw * 0.33, T + rh * 0.22),
                   QPointF(L + rw * 0.33, B - rh * 0.22))
        p.drawLine(QPointF(L + rw * 0.66, T + rh * 0.22),
                   QPointF(L + rw * 0.66, B - rh * 0.22))

    elif key == "rip":
        p.setPen(_pen("#ef6c00", w))
        p.setBrush(QBrush(QColor("#ffcc80")))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(_pen("#c62828", w * 1.25))
        p.drawLine(QPointF(cx, T + 2), QPointF(cx, B - 2))

    elif key == "corner":
        p.setPen(_pen("#ef6c00", w * 1.1))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([
            QPointF(L + 2, T + 2), QPointF(L + 2, B - 2), QPointF(Rgt - 2, B - 2),
        ]))
        p.setPen(_pen("#1565c0", w))
        p.drawArc(int(L + 2), int(cy - rh * 0.08), int(rw * 0.55), int(rh * 0.55),
                  0 * 16, 90 * 16)

    elif key == "jog":
        p.setPen(_pen("#ef6c00", w * 1.15))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([
            QPointF(L + 1, B - 2),
            QPointF(L + rw * 0.32, B - 2),
            QPointF(L + rw * 0.32, T + rh * 0.28),
            QPointF(Rgt - rw * 0.22, T + rh * 0.28),
            QPointF(Rgt - rw * 0.22, T + 2),
        ]))

    else:
        p.setPen(_pen("#555", w))
        p.setBrush(QBrush(QColor("#dde3ea")))
        p.drawRoundedRect(r, 3, 3)


def _render(key: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    # Slightly fuller glyph than size//10 — closer to cab/hm toolbar density.
    m = max(1, size // 12)
    rect = QRectF(m, m, size - 2 * m, size - 2 * m)
    _draw(painter, rect, key, size)
    painter.end()
    return pm


def make_icon(key: str, size: int = 22) -> QIcon:
    cache_key = (key, size)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    icon = QIcon()
    # Draw at 2× then scale down for sharper edges on crisp DPI (cab wizard trick).
    hi = max(size * 2, 48)
    big = _render(key, hi)
    if hi == size:
        icon.addPixmap(big)
    else:
        scaled = big.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon.addPixmap(scaled)
        icon.addPixmap(big)  # HiDPI device pixel ratio
    _CACHE[cache_key] = icon
    return icon

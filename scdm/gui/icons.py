"""Programmatic ribbon icons (no SpaceClaim assets)."""
from __future__ import annotations

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QFont, QBrush

_CACHE = {}

_PALETTE = {
    "new": "#5B9BD5", "open": "#5B9BD5", "save": "#2E7D32", "saveas": "#2E7D32",
    "undo": "#6A1B9A", "redo": "#6A1B9A", "paste": "#F9A825", "cut": "#C62828",
    "copy": "#F9A825", "spin": "#455A64", "pan": "#455A64", "zoom": "#455A64",
    "fit": "#1565C0", "prev": "#455A64", "home": "#1565C0", "iso": "#1565C0",
    "viewx": "#C62828", "viewy": "#2E7D32", "viewz": "#1565C0",
    "line": "#37474F", "tangent": "#37474F", "rect": "#37474F", "rect3": "#37474F",
    "circle": "#37474F", "circle3": "#37474F", "ellipse": "#37474F",
    "spline": "#37474F", "point": "#37474F", "const": "#90A4AE",
    "offset": "#37474F", "layout": "#37474F", "grid": "#37474F",
    "mode_sketch": "#6A1B9A", "mode_section": "#00838F", "mode_3d": "#1565C0",
    "select": "#1565C0", "pull": "#2E7D32", "move": "#EF6C00", "fill": "#00838F",
    "replace": "#6A1B9A", "combine": "#C62828", "split": "#C62828", "splitf": "#C62828",
    "dim": "#1565C0", "hv": "#37474F", "coin": "#37474F", "tan": "#37474F",
    "eq": "#37474F", "par": "#37474F", "fix": "#37474F",
    "pattern": "#6A1B9A", "mirror": "#6A1B9A", "project": "#37474F",
    "shell": "#00838F", "blend": "#2E7D32", "chamfer": "#2E7D32", "draft": "#2E7D32",
    "offace": "#2E7D32", "plane": "#90A4AE", "origin": "#C62828", "axis": "#1565C0",
    "cyl": "#EF6C00", "sphere": "#EF6C00", "helix": "#EF6C00", "comp": "#5D4037",
    "face": "#90A4AE", "edge": "#37474F", "vert": "#212121",
    "shaded": "#90A4AE", "shaded2": "#B0BEC5", "wire": "#37474F", "transp": "#90CAF9",
    "sil": "#37474F", "sect": "#00838F", "measure": "#1565C0", "mass": "#6A1B9A",
    "rev": "#C62828", "smooth": "#00838F", "reduce": "#EF6C00", "solid": "#5D4037",
    "box": "#5D4037", "stitch": "#2E7D32", "gaps": "#C62828",
    "script": "#37474F", "rec": "#C62828", "gear": "#546E7A", "render": "#6A1B9A",
    "recent": "#5B9BD5", "close": "#C62828", "recover": "#00838F", "print": "#455A64",
    "image": "#1565C0", "export": "#2E7D32", "exit": "#C62828", "note": "#37474F",
    "list": "#37474F", "sel": "#1565C0",
}

_GLYPH = {
    "new": "N+", "open": "Op", "save": "Sv", "saveas": "SA", "undo": "Un",
    "redo": "Re", "paste": "Ps", "cut": "Ct", "copy": "Cp", "spin": "Sp",
    "pan": "Pn", "zoom": "Zm", "fit": "Fit", "prev": "<", "home": "H",
    "iso": "Iso", "viewx": "X", "viewy": "Y", "viewz": "Z", "line": "/",
    "tangent": "~", "rect": "[]", "rect3": "R3", "circle": "O", "circle3": "O3",
    "ellipse": "()", "spline": "S~", "point": ".", "const": "- -", "offset": "Off",
    "layout": "Ly", "grid": "#", "mode_sketch": "2D", "mode_section": "Sc",
    "mode_3d": "3D", "select": "Sel", "pull": "Pul", "move": "Mov", "fill": "Fil",
    "replace": "Rep", "combine": "U", "split": "SpB", "splitf": "SpF", "dim": "Dim",
    "hv": "H/V", "coin": "Coin", "tan": "Tan", "eq": "=", "par": "Par", "fix": "Pin",
    "pattern": "Pat", "mirror": "Mir", "project": "Prj", "shell": "Sh",
    "blend": "R", "chamfer": "C", "draft": "Dr", "offace": "OfF", "plane": "Pl",
    "origin": "XYZ", "axis": "Ax", "cyl": "Cyl", "sphere": "Sph", "helix": "Hx",
    "comp": "Cmp", "face": "Fc", "edge": "Ed", "vert": "Vt", "shaded": "ShE",
    "shaded2": "Sh", "wire": "Wf", "transp": "Tr", "sil": "Sil", "sect": "Sec",
    "measure": "Mea", "mass": "m", "rev": "Rev", "smooth": "Sm", "reduce": "Rd",
    "solid": "Sol", "box": "Box", "stitch": "St", "gaps": "Gp", "script": "Py",
    "rec": "Rec", "gear": "Opt", "render": "Rnd", "recent": "Rec", "close": "X",
    "recover": "Rc", "print": "Pr", "image": "Img", "export": "Ex", "exit": "Exi",
    "note": "Nt", "list": "Lst", "sel": "Sel",
}


def make_icon(key: str, size: int = 32) -> QIcon:
    cache_key = (key, size)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color = QColor(_PALETTE.get(key, "#607D8B"))
    margin = max(1, size // 16)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(color))
    p.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, 4, 4)
    p.setPen(QPen(QColor("#FFFFFF")))
    font = QFont("Segoe UI", max(6, size // 4 - 1))
    font.setBold(True)
    p.setFont(font)
    text = _GLYPH.get(key, key[:2])
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, text)
    p.end()
    icon = QIcon(pm)
    _CACHE[cache_key] = icon
    return icon

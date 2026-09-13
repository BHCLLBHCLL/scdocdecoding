"""P48: drawing sheet preview with draggable dimension handles.

The 3D viewport has no drawing surface, so the sheet is previewed on a plain
QWidget canvas: the projected view polylines, the dimension lines and one
drag handle per dimension.  Dragging a handle only rewrites Dimension.offset -
the measured value and the model are untouched - and the very same Dimension
objects are then handed to svg_sheet/write_dxf, so the export follows the drag.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

BG = QColor(252, 252, 250)
VIEW = QColor(60, 66, 76)
DIM = QColor(176, 0, 0)
STALE = QColor(204, 102, 0)
HANDLE = QColor(214, 158, 20)
HANDLE_HOT = QColor(255, 196, 40)


class SheetCanvas(QWidget):
    """View polylines + draggable dimension handles, in view coordinates (m)."""

    changed = pyqtSignal()

    def __init__(self, views, dims, parent=None):
        super().__init__(parent)
        self.views = list(views or [])
        self.dims = list(dims or [])
        self.scale = 1000.0        # px per metre
        self.ox = 20.0
        self.oy = 20.0
        self.hot = -1              # handle under the cursor / being dragged
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self._recompute()

    # -- geometry ---------------------------------------------------------
    def _bounds(self):
        xs, ys = [], []
        for _name, polys in self.views:
            for poly in polys:
                for p in poly:
                    xs.append(p[0])
                    ys.append(p[1])
        for d in self.dims:
            for p in (d.a, d.b) + d.line():
                xs.append(p[0])
                ys.append(p[1])
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def _recompute(self):
        b = self._bounds()
        if b is None:
            return
        w = max(1, self.width() - 40)
        h = max(1, self.height() - 40)
        span_x = max(1e-9, b[2] - b[0])
        span_y = max(1e-9, b[3] - b[1])
        self.scale = min(w / span_x, h / span_y)
        self.ox = 20.0 - b[0] * self.scale + (w - span_x * self.scale) / 2.0
        self.oy = 20.0 - b[1] * self.scale + (h - span_y * self.scale) / 2.0

    def to_px(self, x, y) -> QPointF:
        """View coordinates (metres) -> widget pixels (y flipped)."""
        return QPointF(self.ox + x * self.scale,
                       self.height() - (self.oy + y * self.scale))

    def to_view(self, px, py) -> Tuple[float, float]:
        """Widget pixels -> view coordinates (metres)."""
        return ((px - self.ox) / self.scale,
                ((self.height() - py) - self.oy) / self.scale)

    def handle_px(self, index: int) -> QPointF:
        (hx, hy) = self.dims[index].handle_point()
        return self.to_px(hx, hy)

    # -- interaction (also the test surface: no Qt events needed) ----------
    def pick(self, px, py, tol: float = 12.0) -> int:
        """Index of the dimension handle within tol pixels, else -1."""
        best, best_d = -1, tol
        for i in range(len(self.dims)):
            p = self.handle_px(i)
            d = ((p.x() - px) ** 2 + (p.y() - py) ** 2) ** 0.5
            if d <= best_d:
                best, best_d = i, d
        return best

    def drag_handle(self, index: int, px, py) -> float:
        """Move handle `index` to a pixel position; returns the new offset."""
        if not (0 <= index < len(self.dims)):
            return 0.0
        (vx, vy) = self.to_view(px, py)
        value = self.dims[index].drag_to((vx, vy))
        self.hot = index
        self.update()
        self.changed.emit()
        return value

    def mousePressEvent(self, ev):
        i = self.pick(ev.x(), ev.y())
        if i >= 0:
            self.hot = i
            self.update()

    def mouseMoveEvent(self, ev):
        if self.hot >= 0 and (ev.buttons() & Qt.LeftButton):
            self.drag_handle(self.hot, ev.x(), ev.y())
            return
        i = self.pick(ev.x(), ev.y())
        if i != self.hot:
            self.hot = i
            self.update()

    def mouseReleaseEvent(self, ev):
        self.update()

    def resizeEvent(self, ev):
        self._recompute()

    # -- painting ---------------------------------------------------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        p.setRenderHint(QPainter.Antialiasing, True)
        for name, polys in self.views:
            p.setPen(QPen(VIEW, 1.2))
            for poly in polys:
                pts = [self.to_px(q[0], q[1]) for q in poly]
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
            if polys:
                p.setPen(QPen(VIEW, 1.0))
                p.setFont(QFont('', 8))
                p.drawText(self.to_px(*polys[0][0]) + QPointF(4, -4), name)
        for i, d in enumerate(self.dims):
            colour = STALE if getattr(d, 'stale', False) else DIM
            p.setPen(QPen(colour, 1.4))
            (p1, p2) = d.line()
            a, b = self.to_px(*p1), self.to_px(*p2)
            p.drawLine(a, b)
            t = self.to_px(*d.text_at())
            txt = '%.1f' % d.value_mm + ('?' if getattr(d, 'stale', False) else '')
            p.setFont(QFont('', 9))
            p.drawText(t + QPointF(3, -3), txt)
            hp = self.handle_px(i)
            p.setBrush(HANDLE_HOT if i == self.hot else HANDLE)
            p.setPen(QPen(QColor(120, 84, 0), 1.0))
            p.drawEllipse(hp, 5.0, 5.0)
        p.end()


class SheetDialog(QDialog):
    """P48: preview a view with its dimensions and export the dragged state."""

    def __init__(self, views, dims, title='图纸尺寸', parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.views = list(views or [])
        self.canvas = SheetCanvas(self.views, dims, self)
        self.hint = QLabel('拖动黄色手柄移动尺寸线（只改偏移，不改标注值）')
        self.hint.setStyleSheet('color:#555')
        lay = QVBoxLayout(self)
        lay.addWidget(self.hint)
        lay.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.btn_svg = QPushButton('导出 SVG')
        self.btn_dxf = QPushButton('导出 DXF')
        self.btn_close = QPushButton('关闭')
        for b in (self.btn_svg, self.btn_dxf, self.btn_close):
            row.addWidget(b)
        lay.addLayout(row)
        self.btn_svg.clicked.connect(self.export_svg)
        self.btn_dxf.clicked.connect(self.export_dxf)
        self.btn_close.clicked.connect(self.reject)
        self.last_path: Optional[str] = None

    def export_svg(self) -> Optional[str]:
        fn, _ = QFileDialog.getSaveFileName(self, '导出图纸', 'sheet.svg',
                                           'SVG (*.svg)')
        if not fn:
            return None
        if not fn.lower().endswith('.svg'):
            fn += '.svg'
        from scdm import drawing as D
        D.svg_sheet(self.views, fn, dimensions=self.canvas.dims)
        self.last_path = fn
        return fn

    def export_dxf(self) -> Optional[str]:
        fn, _ = QFileDialog.getSaveFileName(self, '导出 DXF', 'sheet.dxf',
                                           'DXF (*.dxf)')
        if not fn:
            return None
        if not fn.lower().endswith('.dxf'):
            fn += '.dxf'
        from scdm import drawing as D
        D.write_dxf(self.views, fn, dimensions=self.canvas.dims)
        self.last_path = fn
        return fn
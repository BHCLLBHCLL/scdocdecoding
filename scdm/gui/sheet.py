"""P48/P287: 图纸预览画布——可拖动尺寸手柄 + 多选/吸附/撤销。

The 3D viewport has no drawing surface, so the sheet is previewed on a plain
QWidget canvas: the projected view polylines, the dimension lines and one drag
handle per dimension.  Dragging only rewrites `Dimension.offset` - the measured
value and the model are untouched - and the very same Dimension objects are then
handed to svg_sheet/write_dxf, so the export follows the drag.

P287 (R52) adds the second batch of dimension editing:
  * multi-select - Ctrl+click appends/toggles, a rubber band selects a region,
    and dragging one handle moves the whole selection by the same vector;
  * snapping - endpoints / midpoints / intersections of the view geometry and an
    optional grid (scdm.snaptools); a snap lands exactly on the target;
  * undo / redo - Ctrl+Z / Ctrl+Y over offset snapshots (scdm.history), so a
    group drag is undone in one step.

Everything below `# -- interaction` is callable without Qt events, which is how
the tests drive it (press/move/release only translate pixels into these calls).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from scdm import history as HISTORY
from scdm import snaptools as SNAP

BG = QColor(252, 252, 250)
VIEW = QColor(60, 66, 76)
DIM = QColor(176, 0, 0)
STALE = QColor(204, 102, 0)
HANDLE = QColor(214, 158, 20)
HANDLE_HOT = QColor(255, 196, 40)
HANDLE_SEL = QColor(0, 132, 96)
BAND = QColor(0, 110, 180, 60)
SNAP_MARK = QColor(0, 110, 180)


class SheetCanvas(QWidget):
    """View polylines + draggable dimension handles, in view coordinates (m)."""

    changed = pyqtSignal()

    def __init__(self, views, dims, parent=None, grid: float = 0.0,
                 snap_tol_px: float = 8.0):
        super().__init__(parent)
        self.views = list(views or [])
        self.dims = list(dims or [])
        self.scale = 1000.0        # px per metre
        self.ox = 20.0
        self.oy = 20.0
        self.hot = -1              # handle under the cursor / being dragged
        self.selected: List[int] = []          # P287: multi-selection
        self.snap = SNAP.SnapIndex(self.views, grid=grid)
        self.snap_enabled = True
        self.snap_tol_px = float(snap_tol_px)
        self.last_snap = ""                    # kind of the last snap ("", end, ...)
        self.undo = HISTORY.History(limit=100)
        self._band = None                      # rubber band in pixels
        self._drag_from = None
        self._undo_pushed = False
        self.setFocusPolicy(Qt.StrongFocus)
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
        self._size = (self.width(), self.height())

    def _sync(self):
        """Re-fit when the widget size changed without a resize event yet (a
        hidden widget resized before its first show, which is how the tests and
        the dialog constructor drive it)."""
        if getattr(self, "_size", None) != (self.width(), self.height()):
            self._recompute()

    def to_px(self, x, y) -> QPointF:
        """View coordinates (metres) -> widget pixels (y flipped)."""
        self._sync()
        return QPointF(self.ox + x * self.scale,
                       self.height() - (self.oy + y * self.scale))

    def to_view(self, px, py) -> Tuple[float, float]:
        """Widget pixels -> view coordinates (metres)."""
        self._sync()
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

    def select(self, index: int, append: bool = False) -> List[int]:
        """Select a handle; `append` (Ctrl) toggles it in the set."""
        if 0 <= index < len(self.dims):
            if append:
                if index in self.selected:
                    self.selected.remove(index)
                else:
                    self.selected.append(index)
            else:
                self.selected = [index]
        elif not append:
            self.selected = []
        self.update()
        return list(self.selected)

    def box_select(self, x0, y0, x1, y1, append: bool = False) -> List[int]:
        """Rubber band: every handle inside the pixel rectangle."""
        lo = (min(x0, x1), min(y0, y1))
        hi = (max(x0, x1), max(y0, y1))
        hits = []
        for i in range(len(self.dims)):
            p = self.handle_px(i)
            if lo[0] <= p.x() <= hi[0] and lo[1] <= p.y() <= hi[1]:
                hits.append(i)
        if append:
            for i in hits:
                if i not in self.selected:
                    self.selected.append(i)
        else:
            self.selected = hits
        self.update()
        return list(self.selected)

    def snap_offset(self, dim, vx, vy, tol=None):
        """Snap the dimension LINE, not the free handle point.

        Dimension.offset is a distance along the normal, so a dimension line can
        only slide perpendicular to what it measures.  The snapped offset is the
        one whose line passes EXACTLY through a nearby endpoint / midpoint /
        crossing (offset = (p - a) . n), or the nearest grid node; a snap kind of
        '' means nothing was near and no grid was asked for.
        """
        if not self.snap_enabled:
            return dim.offset_for_point((vx, vy)), ""
        if tol is None:
            tol = self.snap_tol_px / max(self.scale, 1e-9)
        raw = dim.offset_for_point((vx, vy))
        (ax, ay) = dim.a
        (nx, ny) = dim.normal()
        best = None
        for (x, y, kind) in self.snap.targets:
            off = (x - ax) * nx + (y - ay) * ny
            d = abs(off - raw)
            if d > tol:
                continue
            key = (d, SNAP.PRIORITY.get(kind, 9), off)
            if best is None or key < best[0]:
                best = (key, off, kind)
        if best is not None:
            return best[1], best[2]
        if self.snap.grid > 0:
            g = self.snap.grid
            return round(raw / g) * g, "grid"
        return raw, ""

    def begin_drag(self, index: int, px, py) -> None:
        """Start a drag; the undo snapshots are taken on the first move and on
        end_drag, so the stack always holds the current state as its top."""
        if index >= 0 and index not in self.selected:
            self.selected = [index]
        self._drag_from = (px, py)
        self._undo_pushed = False
        self.hot = index

    def end_drag(self) -> None:
        """Close a drag: push the resulting state (one undo step per drag)."""
        if self.undo.current() != self.offsets():
            self.undo.push(self.offsets())
        self._undo_pushed = False
        self._drag_from = None

    def drag_handle(self, index: int, px, py) -> float:
        """Move the selection so handle `index` lands on the (snapped) point.

        The whole selection moves by the same view vector, so a group keeps its
        relative layout; only offsets change, never the measured values.
        """
        if not (0 <= index < len(self.dims)):
            return 0.0
        if index not in self.selected:
            self.selected = [index]
        if not self._undo_pushed:
            if self.undo.current() != self.offsets():
                self.undo.push(self.offsets())
            self._undo_pushed = True
        (vx, vy) = self.to_view(px, py)
        dim = self.dims[index]
        before = dim.handle_point()
        offset, kind = self.snap_offset(dim, vx, vy)
        dim.offset = offset
        after = dim.handle_point()
        delta = (after[0] - before[0], after[1] - before[1])
        for i in self.selected:
            if i == index:
                continue
            h = self.dims[i].handle_point()
            self.dims[i].drag_to((h[0] + delta[0], h[1] + delta[1]))
        self.last_snap = kind
        self.hot = index
        self.update()
        self.changed.emit()
        return dim.offset

    # -- undo / redo (offset snapshots - exact, no geometry involved) ------
    def offsets(self) -> List[float]:
        return [float(d.offset) for d in self.dims]

    def set_offsets(self, values) -> None:
        for d, v in zip(self.dims, values):
            d.offset = float(v)
        self.update()
        self.changed.emit()

    def undo_last(self) -> bool:
        snap = self.undo.undo()
        if snap is None:
            return False
        self.set_offsets(snap)
        return True

    def redo_last(self) -> bool:
        snap = self.undo.redo()
        if snap is None:
            return False
        self.set_offsets(snap)
        return True

    def rebuild_targets(self) -> None:
        """Re-read the snap targets after the drawing changed."""
        self.snap.rebuild(self.views)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        i = self.pick(ev.x(), ev.y())
        if i >= 0 and (ev.modifiers() & Qt.ControlModifier):
            self.select(i, append=True)
            return
        if i >= 0:
            self.begin_drag(i, ev.x(), ev.y())
            self.update()
            return
        self._band = (ev.x(), ev.y(), ev.x(), ev.y())
        self.update()

    def mouseMoveEvent(self, ev):
        if self._band is not None:
            self._band = (self._band[0], self._band[1], ev.x(), ev.y())
            self.update()
            return
        if self.hot >= 0 and (ev.buttons() & Qt.LeftButton):
            self.drag_handle(self.hot, ev.x(), ev.y())
            return
        i = self.pick(ev.x(), ev.y())
        if i != self.hot:
            self.hot = i
            self.update()

    def mouseReleaseEvent(self, ev):
        if self._band is not None:
            (x0, y0, x1, y1) = self._band
            self._band = None
            self.box_select(x0, y0, x1, y1,
                            append=bool(ev.modifiers() & Qt.ControlModifier))
        elif self._drag_from is not None:
            self.end_drag()
        self.update()

    def keyPressEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier and ev.key() == Qt.Key_Z:
            self.undo_last()
            return
        if ev.modifiers() & Qt.ControlModifier and ev.key() == Qt.Key_Y:
            self.redo_last()
            return
        super().keyPressEvent(ev)

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
            if i in self.selected:
                p.setBrush(HANDLE_SEL)
            else:
                p.setBrush(HANDLE_HOT if i == self.hot else HANDLE)
            p.setPen(QPen(QColor(120, 84, 0), 1.0))
            p.drawEllipse(hp, 5.0, 5.0)
        if self._band is not None:
            (x0, y0, x1, y1) = self._band
            p.setBrush(BAND)
            p.setPen(QPen(SNAP_MARK, 1.0, Qt.DashLine))
            p.drawRect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
        p.end()


class SheetDialog(QDialog):
    """P48/P287: preview a view with its dimensions and export the dragged state."""

    def __init__(self, views, dims, title='图纸尺寸', parent=None, grid: float = 0.001):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.views = list(views or [])
        self.canvas = SheetCanvas(self.views, dims, self, grid=grid)
        self.hint = QLabel('拖动黄色手柄移动尺寸线（只改偏移，不改标注值）；'
                           'Ctrl 追加选择 / 框选成组移动；'
                           '端点·中点·交点·1 mm 网格自动吸附；Ctrl+Z 撤销、Ctrl+Y 重做')
        self.hint.setStyleSheet('color:#555')
        lay = QVBoxLayout(self)
        lay.addWidget(self.hint)
        lay.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.btn_undo = QPushButton('撤销')
        self.btn_redo = QPushButton('重做')
        self.btn_svg = QPushButton('导出 SVG')
        self.btn_dxf = QPushButton('导出 DXF')
        self.btn_close = QPushButton('关闭')
        for b in (self.btn_undo, self.btn_redo, self.btn_svg, self.btn_dxf,
                  self.btn_close):
            row.addWidget(b)
        lay.addLayout(row)
        self.btn_undo.clicked.connect(self.canvas.undo_last)
        self.btn_redo.clicked.connect(self.canvas.redo_last)
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
        fn, _ = QFileDialog.getSaveFileName(self, '导出图纸', 'sheet.dxf',
                                           'DXF (*.dxf)')
        if not fn:
            return None
        if not fn.lower().endswith('.dxf'):
            fn += '.dxf'
        from scdm import drawing as D
        D.write_dxf(self.views, fn, dimensions=self.canvas.dims)
        self.last_path = fn
        return fn

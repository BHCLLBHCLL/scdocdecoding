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
NOTE_GDT = QColor(0, 130, 70)
NOTE_DATUM = QColor(170, 102, 0)


class SheetCanvas(QWidget):
    """View polylines + draggable dimension handles, in view coordinates (m)."""

    changed = pyqtSignal()

    def __init__(self, views, dims, parent=None, grid: float = 0.0,
                 snap_tol_px: float = 8.0, annotations=None):
        super().__init__(parent)
        self.views = list(views or [])
        self.dims = list(dims or [])
        self.notes = list(annotations or [])   # P299: leader / GD&T annotations
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
        self.hot_note = -1                     # annotation under the cursor
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
        if self.undo.current() != self.state():
            self.undo.push(self.state())
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
            if self.undo.current() != self.state():
                self.undo.push(self.state())
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

    # -- annotations (P299: free 2D anchors, unlike the 1-DOF dimensions) --
    def pick_annotation(self, px, py, tol: float = 12.0) -> int:
        """Index of the annotation anchor within tol pixels, else -1."""
        best, best_d = -1, tol
        for i, a in enumerate(self.notes):
            p = self.to_px(*a.anchor)
            d = ((p.x() - px) ** 2 + (p.y() - py) ** 2) ** 0.5
            if d <= best_d:
                best, best_d = i, d
        return best

    def snap_free_point(self, vx, vy):
        """Snap a FREE 2D point: an annotation anchor has both degrees of
        freedom, so it snaps to the nearest target point (a dimension only has
        the scalar offset along its normal - rule 69)."""
        if not self.snap_enabled:
            return (vx, vy), ""
        return self.snap.snap((vx, vy), self.snap_tol_px / max(self.scale, 1e-9))

    def begin_annotation_drag(self, index: int, px, py) -> None:
        self.hot_note = index
        self._drag_from = (px, py)
        self._undo_pushed = False

    def drag_annotation(self, index: int, px, py):
        """Move an annotation anchor to the (snapped) pixel point."""
        if not (0 <= index < len(self.notes)):
            return None
        if not self._undo_pushed:
            if self.undo.current() != self.state():
                self.undo.push(self.state())
            self._undo_pushed = True
        (vx, vy) = self.to_view(px, py)
        (sx, sy), kind = self.snap_free_point(vx, vy)
        self.notes[index].move_to((sx, sy))
        self.last_snap = kind
        self.hot_note = index
        self.update()
        self.changed.emit()
        return self.notes[index].anchor

    # -- undo / redo (offset + annotation snapshots - exact, no geometry) --
    def offsets(self) -> List[float]:
        return [float(d.offset) for d in self.dims]

    def set_offsets(self, values) -> None:
        for d, v in zip(self.dims, values):
            d.offset = float(v)
        self.update()
        self.changed.emit()

    def state(self):
        """Everything a drag can change: dimension offsets + annotations."""
        return {"offsets": self.offsets(),
                "notes": [a.to_dict() for a in self.notes]}

    def set_state(self, state) -> None:
        from scdm.annotation import from_dict
        if isinstance(state, dict):
            self.set_offsets(state.get("offsets") or [])
            self.notes = [from_dict(d) for d in (state.get("notes") or [])]
        else:                       # a bare offset list (pre-P299 snapshot)
            self.set_offsets(state)
        self.update()
        self.changed.emit()

    def undo_last(self) -> bool:
        snap = self.undo.undo()
        if snap is None:
            return False
        self.set_state(snap)
        return True

    def redo_last(self) -> bool:
        snap = self.undo.redo()
        if snap is None:
            return False
        self.set_state(snap)
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
        j = self.pick_annotation(ev.x(), ev.y())
        if j >= 0:
            self.begin_annotation_drag(j, ev.x(), ev.y())
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
        if self.hot_note >= 0 and (ev.buttons() & Qt.LeftButton):
            self.drag_annotation(self.hot_note, ev.x(), ev.y())
            return
        i = self.pick(ev.x(), ev.y())
        j = self.pick_annotation(ev.x(), ev.y()) if i < 0 else -1
        if i != self.hot or j != self.hot_note:
            self.hot, self.hot_note = i, j
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
            from scdm.drawing import dim_text
            txt = dim_text(d)            # P352: same label as the exports
            p.setFont(QFont('', 9))
            p.drawText(t + QPointF(3, -3), txt)
            hp = self.handle_px(i)
            if i in self.selected:
                p.setBrush(HANDLE_SEL)
            else:
                p.setBrush(HANDLE_HOT if i == self.hot else HANDLE)
            p.setPen(QPen(QColor(120, 84, 0), 1.0))
            p.drawEllipse(hp, 5.0, 5.0)
        for i, a in enumerate(self.notes):
            from scdm.annotation import annotation_geometry
            segs, text, at, style = annotation_geometry(a)
            layer = style.get("layer", "NOTE")
            colour = {"NOTE": SNAP_MARK, "GDT": NOTE_GDT,
                      "DATUM": NOTE_DATUM}.get(layer, SNAP_MARK)
            if i == self.hot_note:
                colour = HANDLE_HOT
            p.setPen(QPen(colour, 1.3))
            for q1, q2 in segs:
                p.drawLine(self.to_px(*q1), self.to_px(*q2))
            px_h = max(6.0, min(16.0, style.get("text_height", 0.003) * self.scale))
            p.setFont(QFont('', int(px_h)))
            p.drawText(self.to_px(*at), text)
        if self._band is not None:
            (x0, y0, x1, y1) = self._band
            p.setBrush(BAND)
            p.setPen(QPen(SNAP_MARK, 1.0, Qt.DashLine))
            p.drawRect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
        p.end()


class SheetDialog(QDialog):
    """P48/P287: preview a view with its dimensions and export the dragged state."""

    def __init__(self, views, dims, title='图纸尺寸', parent=None,
                 grid: float = 0.001, annotations=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.views = list(views or [])
        self.canvas = SheetCanvas(self.views, dims, self, grid=grid,
                                  annotations=annotations)
        self.hint = QLabel('拖动黄色手柄移动尺寸线（只改偏移，不改标注值）；'
                           'Ctrl 追加选择 / 框选成组移动；'
                           '端点·中点·交点·1 mm 网格自动吸附；'
                           '引线/公差框可拖动（标注不入几何）；Ctrl+Z 撤销、Ctrl+Y 重做')
        self.hint.setStyleSheet('color:#555')
        lay = QVBoxLayout(self)
        lay.addWidget(self.hint)
        lay.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.btn_note = QPushButton('加引线')
        self.btn_datum = QPushButton('加基准')
        self.btn_chain = QPushButton('尺寸链')
        row.addWidget(self.btn_note)
        row.addWidget(self.btn_datum)
        row.addWidget(self.btn_chain)
        self.btn_undo = QPushButton('撤销')
        self.btn_redo = QPushButton('重做')
        self.btn_svg = QPushButton('导出 SVG')
        self.btn_dxf = QPushButton('导出 DXF')
        self.btn_close = QPushButton('关闭')
        for b in (self.btn_undo, self.btn_redo, self.btn_svg, self.btn_dxf,
                  self.btn_close):
            row.addWidget(b)
        lay.addLayout(row)
        self.btn_note.clicked.connect(self.prompt_leader)
        self.btn_datum.clicked.connect(self.prompt_datum)
        self.btn_chain.clicked.connect(self.prompt_chain)
        self.btn_undo.clicked.connect(self.canvas.undo_last)
        self.btn_redo.clicked.connect(self.canvas.redo_last)
        self.btn_svg.clicked.connect(self.export_svg)
        self.btn_dxf.clicked.connect(self.export_dxf)
        self.btn_close.clicked.connect(self.reject)
        self.last_path: Optional[str] = None

    def add_leader(self, text: str, anchor=None, view=None, arrow: str = "solid",
                   text_height: float = 0.0025):
        """P299/P307: mount a leader annotation; the anchor snaps to a target."""
        from scdm.annotation import Leader
        if not str(text or '').strip():
            raise ValueError("引线标注必须有文字")
        note = Leader(view=self._note_view(view), anchor=self._note_anchor(anchor),
                      text=str(text), arrow=arrow, text_height=text_height)
        self._mount_note(note)
        return note

    def add_chain_total(self, mode: str = "worst"):
        """P352: 把当前尺寸串成链，并把总尺寸（含叠加公差）挂到图上。

        Returns the total Dimension, or None when the run is not a chain (the
        caller gets the verdict text through the status bar, not an exception).
        """
        from scdm import dimchain as DC
        try:
            verdict = DC.check_chain(self.canvas.dims)
            total = DC.chain_dimension(self.canvas.dims, mode=mode)
        except ValueError:
            return None
        self.canvas.undo.push(self.canvas.state())
        self.canvas.dims.append(total)
        self.canvas.update()
        self.canvas.changed.emit()
        self._chain_text = DC.describe(verdict)
        return total

    def add_chain_labels(self, gap_mm: float = 8.0):
        """R90/P422: 极值/统计两条总尺寸并列 + 一条链线（同一链）。

        Returns the dict from dimchain.chain_annotations, or None when the run
        is not a chain; the verdict text still reaches the status bar.
        """
        from scdm import dimchain as DC
        try:
            verdict = DC.check_chain(self.canvas.dims)
            made = DC.chain_annotations(self.canvas.dims, gap_mm=gap_mm)
        except ValueError:
            return None
        self.canvas.undo.push(self.canvas.state())
        self.canvas.dims.extend([made["worst"], made["rss"]])
        self.canvas.notes.append(made["line"])
        self.canvas.update()
        self.canvas.changed.emit()
        self._chain_text = DC.describe(verdict)
        return made

    def chain_text(self) -> str:
        """The last chain verdict, one line (rule 84: same wording everywhere)."""
        return getattr(self, "_chain_text", "")

    def add_datum(self, label: str = "A", anchor=None, view=None,
                  target: bool = False):
        """P307: mount a datum symbol (A/B/C, optionally a datum target)."""
        from scdm.annotation import Datum
        note = Datum(view=self._note_view(view), anchor=self._note_anchor(anchor),
                     label=label, target=target)
        self._mount_note(note)
        return note

    def _note_view(self, view) -> str:
        return view or (self.canvas.views[0][0] if self.canvas.views else "")

    def _note_anchor(self, anchor):
        if anchor is not None:
            return tuple(anchor)
        t = self.canvas.snap.targets
        return (t[0][0], t[0][1]) if t else (0.0, 0.0)

    def _mount_note(self, note):
        self.canvas.undo.push(self.canvas.state())
        self.canvas.notes.append(note)
        self.canvas.update()
        self.canvas.changed.emit()

    def prompt_leader(self):
        """Button path: ask for the text, then add_leader()."""
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, '引线标注', '文字')
        if not ok:
            return None
        try:
            return self.add_leader(text)
        except ValueError:
            return None

    def prompt_datum(self):
        """Button path: ask for the datum letter, then add_datum()."""
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, '基准符号', '基准代号', text='A')
        if not ok:
            return None
        try:
            return self.add_datum(text)
        except ValueError:
            return None

    def prompt_chain(self):
        """Button path: total the chain and show the verdict in the hint line."""
        total = self.add_chain_total()
        if total is None:
            self.hint.setText("尺寸链不成立：尺寸不连续或方向不一致"
                              "（" + self.chain_text() + "）")
            return None
        self.hint.setText(self.chain_text() + "；已挂总尺寸 " + "%.1f" % total.value_mm
                          + (" ±%.3g" % total.tol if total.tol > 0 else ""))
        return total

    def export_svg(self) -> Optional[str]:
        fn, _ = QFileDialog.getSaveFileName(self, '导出图纸', 'sheet.svg',
                                           'SVG (*.svg)')
        if not fn:
            return None
        if not fn.lower().endswith('.svg'):
            fn += '.svg'
        from scdm import drawing as D
        D.svg_sheet(self.views, fn, dimensions=self.canvas.dims,
                    annotations=self.canvas.notes)
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
        D.write_dxf(self.views, fn, dimensions=self.canvas.dims,
                    annotations=self.canvas.notes)
        self.last_path = fn
        return fn

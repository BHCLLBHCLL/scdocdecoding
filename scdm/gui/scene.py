"""VTK scene: tessellated bodies, gizmo, picking, display styles."""
from __future__ import annotations

import numpy as np

import vtk
from vtk.util import numpy_support

from scdm.document import Session

BG = (0.96, 0.96, 0.96)
SELECT = (1.0, 0.35, 0.1)
PRE = (1.0, 0.78, 0.16)
BASE = (0.62, 0.66, 0.70)


class CadStyle(vtk.vtkInteractorStyleTrackballCamera):
    """LMB select, MMB rotate, Shift+MMB pan, RMB context, wheel zoom.

    When drag_start_cb/drag_end_cb are set, an LMB press starts a drag gesture:
    the click_cb fires only if the button is released without moving (plain click);
    otherwise drag_move_cb streams pixel deltas and drag_end_cb fires once with the
    total delta. Used by Pull/Move for interactive drag preview.
    """

    def __init__(self):
        super().__init__()
        self.click_cb = None
        self.right_cb = None
        self.drag_start_cb = None   # callable() at LMB down
        self.drag_move_cb = None    # callable(dx, dy) during drag
        self.drag_end_cb = None     # callable(total_dx, total_dy) at release
        self._drag_start = None
        self._dragging = False
        self._last = None

    def OnLeftButtonDown(self):
        iren = self.GetInteractor()
        if iren and self.drag_start_cb:
            self._drag_start = iren.GetEventPosition()
            self._last = self._drag_start
            self._dragging = True
            self.drag_start_cb()
            return
        if self.click_cb:
            self.click_cb()

    def OnMouseMove(self):
        iren = self.GetInteractor()
        if self._dragging and iren and self.drag_move_cb:
            pos = iren.GetEventPosition()
            self.drag_move_cb(pos[0] - self._last[0], pos[1] - self._last[1])
            self._last = pos
            return
        vtk.vtkInteractorStyleTrackballCamera.OnMouseMove(self)

    def OnLeftButtonUp(self):
        if self._dragging and self.drag_end_cb:
            iren = self.GetInteractor()
            pos = iren.GetEventPosition() if iren else self._drag_start
            self.drag_end_cb(pos[0] - self._drag_start[0], pos[1] - self._drag_start[1])
            self._dragging = False
            return
        vtk.vtkInteractorStyleTrackballCamera.OnLeftButtonUp(self)

    def OnMiddleButtonDown(self):
        iren = self.GetInteractor()
        if iren is not None and iren.GetShiftKey():
            vtk.vtkInteractorStyleTrackballCamera.OnMiddleButtonDown(self)
        else:
            vtk.vtkInteractorStyleTrackballCamera.OnLeftButtonDown(self)

    def OnMiddleButtonUp(self):
        vtk.vtkInteractorStyleTrackballCamera.OnMiddleButtonUp(self)
        vtk.vtkInteractorStyleTrackballCamera.OnLeftButtonUp(self)

    def OnRightButtonDown(self):
        if self.right_cb:
            self.right_cb()


class Scene:
    def __init__(self, vtk_widget):
        self.vtk_widget = vtk_widget
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(*BG)
        self.renderer.GradientBackgroundOff()
        self.renderer.GetActiveCamera().ParallelProjectionOn()
        vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self.style = CadStyle()
        vtk_widget.GetRenderWindow().GetInteractor().SetInteractorStyle(self.style)
        vtk_widget.Initialize()
        vtk_widget.Start()

        self._face_actors = {}
        self._edge_actor = None
        self._vert_actor = None
        self._sketch_actor = None
        self._sketch_pts_actor = None
        self._preview_actor = None
        self._highlight = []
        self._origin_actor = None
        self._plane_actors = {}
        self._grid_actor = None
        self._silhouette_actor = None
        self._gizmo = None
        self._install_gizmo()
        self._install_origin()
        self._install_planes()
        self._reset_empty_camera()

        self._click_n = 0
        self._click_actor = None
        self._click_t = 0.0

    def _install_gizmo(self):
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(1.0, 1.0, 1.0)
        _style_axes(axes, world=False)
        gizmo = vtk.vtkOrientationMarkerWidget()
        gizmo.SetOrientationMarker(axes)
        gizmo.SetInteractor(self.vtk_widget.GetRenderWindow().GetInteractor())
        gizmo.SetViewport(0.0, 0.0, 0.11, 0.11)
        try:
            gizmo.SetOutlineColor(0.72, 0.72, 0.72)
        except Exception:
            pass
        gizmo.SetEnabled(1)
        gizmo.InteractiveOff()
        self._gizmo = gizmo

    def _install_origin(self):
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(0.012, 0.012, 0.012)
        _style_axes(axes, world=True)
        self.renderer.AddActor(axes)
        self._origin_actor = axes
        self._origin_labels = []
        length = 0.012
        for text, pos, color in (
            ("X", (length * 1.15, 0.0, 0.0), (0.78, 0.22, 0.18)),
            ("Y", (0.0, length * 1.15, 0.0), (0.20, 0.55, 0.22)),
            ("Z", (0.0, 0.0, length * 1.15), (0.18, 0.36, 0.75)),
        ):
            lab = _axis_label(text, pos, color)
            if lab is None:
                continue
            self.renderer.AddActor(lab)
            self._origin_labels.append(lab)

    def _install_planes(self):
        specs = {
            "xy": ((1, 0, 0), (0, 1, 0), (0.72, 0.74, 0.86)),
            "zx": ((1, 0, 0), (0, 0, 1), (0.86, 0.72, 0.72)),
            "yz": ((0, 1, 0), (0, 0, 1), (0.72, 0.84, 0.72)),
        }
        for key, (ax1, ax2, col) in specs.items():
            src = vtk.vtkPlaneSource()
            src.SetOrigin(-0.018, -0.018, 0)
            src.SetPoint1(0.018, -0.018, 0)
            src.SetPoint2(-0.018, 0.018, 0)
            if key == "zx":
                src.SetNormal(0, 1, 0)
            elif key == "yz":
                src.SetNormal(1, 0, 0)
            else:
                src.SetNormal(0, 0, 1)
            src.Update()
            m = vtk.vtkPolyDataMapper()
            m.SetInputConnection(src.GetOutputPort())
            a = vtk.vtkActor()
            a.SetMapper(m)
            a.GetProperty().SetColor(*col)
            a.GetProperty().SetOpacity(0.14)
            a.SetVisibility(0)
            _exclude_from_bounds(a)
            self.renderer.AddActor(a)
            self._plane_actors[key] = a

    def render(self):
        self.renderer.GetRenderWindow().Render()

    def clear_bodies(self):
        for act in list(self._highlight):
            self._restore(act)
        self._highlight.clear()
        for act in (self._edge_actor, self._vert_actor):
            if act:
                self.renderer.RemoveActor(act)
        for act in list(self._face_actors.values()):
            self.renderer.RemoveActor(act)
        self._face_actors.clear()
        self._edge_actor = None
        self._vert_actor = None
        for act in (self._sketch_actor, self._sketch_pts_actor):
            if act:
                self.renderer.RemoveActor(act)
        self._sketch_actor = None
        self._sketch_pts_actor = None
        for act in getattr(self, "_light_actors", []):
            self.renderer.RemoveActor(act)
        self._light_actors = []
        if self._silhouette_actor:
            self.renderer.RemoveActor(self._silhouette_actor)
        self._silhouette_actor = None
        self.clear_preview()

    def build(self, session: Session):
        self.clear_bodies()
        kdoc = getattr(session, "kdoc", None)
        if kdoc is not None and getattr(kdoc, "bodies", None):
            self._build_kdoc(session)
            return
        data = session.data
        if not data or data.get("fac") is None or self.renderer is None:
            self.render()
            return
        fac = data["fac"]
        model = data["model"]
        render_rgb = None
        if data.get("render"):
            for view in data["render"]:
                for it in view.get("items", []):
                    for b in it.get("bodies", []):
                        if b.get("rgb"):
                            render_rgb = [c / 255.0 for c in b["rgb"]]
                            break
        base = render_rgb or list(BASE)
        for fnode in fac.faces:
            pts = np.array([c.position for c in fnode.corners], dtype=np.float64)
            tris = []
            for a, b, c in fnode.triangles:
                if max(a, b, c) < len(fnode.corners):
                    tris.append([a, b, c])
            if not len(pts) or not tris:
                continue
            pd = _polys(pts, tris)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(pd)
            act = vtk.vtkActor()
            act.SetMapper(mapper)
            act.GetProperty().SetColor(*base)
            act.GetProperty().SetDiffuse(0.8)
            act.GetProperty().SetSpecular(0.2)
            act.GetProperty().SetAmbient(0.2)
            act._base_color = list(base)
            act._base_opacity = 1.0
            act._node_id = fnode.node_id
            self.renderer.AddActor(act)
            self._face_actors[fnode.node_id] = act
        if model is not None:
            lines, verts = [], []
            for ed in model.of_kind("edge"):
                ep = model.edge_endpoints(ed)
                if ep:
                    lines.append([list(ep[0]), list(ep[1])])
                    verts.append(list(ep[0]))
                    verts.append(list(ep[1]))
            if lines:
                self._edge_actor = _lines_actor(lines, (0.12, 0.12, 0.15), 1.4)
                self.renderer.AddActor(self._edge_actor)
            if verts:
                self._vert_actor = _points_actor(verts, (0.05, 0.05, 0.05), 6)
                self.renderer.AddActor(self._vert_actor)
        self.apply_visibility(session)
        self.apply_style(session.style)
        self.fit()

    def _build_kdoc(self, session: Session):
        from scdm.kernel import tessellate_faces
        kdoc = session.kdoc
        light_ids = set()
        for comp in getattr(kdoc, "components", []):
            light_ids |= comp.lightweight_body_ids()
        lines, verts = [], []
        pds = []
        self._light_actors = []
        for body in kdoc.bodies:
            if not body.visible:
                continue
            if body.id in light_ids:
                self._add_lightweight_body(body)
                continue
            try:
                faces = tessellate_faces(body.shape, deflection=max(0.0005, 0.02 / max(session.scale, 1)))
            except Exception:
                continue
            col = list(body.color)
            for fd in faces:
                pts = np.array(fd["vertices"], dtype=np.float64)
                tris = fd["triangles"]
                if len(pts) == 0 or not tris:
                    continue
                pd = _polys(pts, tris)
                pds.append(pd)
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputData(pd)
                act = vtk.vtkActor()
                act.SetMapper(mapper)
                act.GetProperty().SetColor(*col)
                act.GetProperty().SetDiffuse(0.8)
                act.GetProperty().SetSpecular(0.2)
                act.GetProperty().SetAmbient(0.2)
                act._base_color = list(col)
                act._base_opacity = 1.0
                key = f"{body.id}:{fd['index']}"
                act._node_id = key
                act._body_id = body.id
                act._face_i = fd['index']
                act._normal = fd["normal"]
                act._center = fd["center"]
                self.renderer.AddActor(act)
                self._face_actors[key] = act
                for a, b, c in tris:
                    for u, v in ((a, b), (b, c), (c, a)):
                        lines.append([list(pts[u]), list(pts[v])])
                        verts.append(list(pts[u]))
        if lines:
            self._edge_actor = _lines_actor(lines, (0.12, 0.12, 0.15), 1.2)
            self.renderer.AddActor(self._edge_actor)
        if verts:
            self._vert_actor = _points_actor(verts, (0.05, 0.05, 0.05), 5)
            self.renderer.AddActor(self._vert_actor)
        self._build_silhouette(pds)
        self._build_sketches(kdoc)
        self.apply_visibility(session)
        self.apply_style(session.style)
        self.fit()

    def _build_silhouette(self, pds):
        """Feature-edge overlay for the shaded model (gfx.silhouette)."""
        self._silhouette_actor = None
        if not pds:
            return
        app = vtk.vtkAppendPolyData()
        for pd in pds:
            app.AddInputData(pd)
        app.Update()
        fe = vtk.vtkFeatureEdges()
        fe.SetInputData(app.GetOutput())
        fe.BoundaryEdgesOff()
        fe.ManifoldEdgesOff()
        fe.NonManifoldEdgesOff()
        fe.FeatureEdgesOn()
        fe.SetFeatureAngle(30.0)
        fe.Update()
        if fe.GetOutput().GetNumberOfCells() == 0:
            return
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(fe.GetOutputPort())
        act = vtk.vtkActor()
        act.SetMapper(mapper)
        act.GetProperty().SetColor(0.08, 0.08, 0.12)
        act.GetProperty().SetLineWidth(1.6)
        act.SetVisibility(0)  # off until session.show_silhouette
        _exclude_from_bounds(act)
        self.renderer.AddActor(act)
        self._silhouette_actor = act

    def _add_lightweight_body(self, body):
        """Draw a lightweight body as a bounding-box wireframe (no tessellation)."""
        from scdm import additive as A
        lo, hi = A.shape_bbox(body.shape)
        def pt(x, y, z):
            return [x, y, z]
        c = [pt(lo[0], lo[1], lo[2]), pt(hi[0], lo[1], lo[2]), pt(hi[0], hi[1], lo[2]),
             pt(lo[0], hi[1], lo[2]), pt(lo[0], lo[1], hi[0] * 0 + hi[2]),
             pt(hi[0], lo[1], hi[2]), pt(hi[0], hi[1], hi[2]), pt(lo[0], hi[1], hi[2])]
        segs = [(c[0], c[1]), (c[1], c[2]), (c[2], c[3]), (c[3], c[0]),
                (c[4], c[5]), (c[5], c[6]), (c[6], c[7]), (c[7], c[4]),
                (c[0], c[4]), (c[1], c[5]), (c[2], c[6]), (c[3], c[7])]
        act = _lines_actor([[list(a), list(b)] for a, b in segs],
                           tuple(body.color), 1.8)
        self.renderer.AddActor(act)
        self._light_actors.append(act)

    def _build_sketches(self, kdoc):
        """Render sketch curves as on-plane 2D line/polygon actors."""
        import math as _math
        segs, pts = [], []
        for sk in getattr(kdoc, "sketches", []):
            for c in sk.curves:
                if c[0] == "rect":
                    x0, y0 = c[1][0], c[1][1]
                    x1, y1 = c[2][0], c[2][1]
                    loop = [(x0, y0, c[1][2]), (x1, y0, c[1][2]),
                            (x1, y1, c[1][2]), (x0, y1, c[1][2]), (x0, y0, c[1][2])]
                    for a, b in zip(loop, loop[1:]):
                        segs.append([list(a), list(b)])
                elif c[0] == "line":
                    segs.append([list(c[1]), list(c[2])])
                elif c[0] == "circle":
                    cx, cy, cz = c[1]
                    r = c[2]
                    ring = [(cx + r * _math.cos(t), cy + r * _math.sin(t), cz)
                            for t in [_math.tau * i / 32 for i in range(32)]]
                    ring.append(ring[0])
                    for a, b in zip(ring, ring[1:]):
                        segs.append([list(a), list(b)])
                elif c[0] == "point":
                    pts.append(list(c[1]))
            for c in getattr(sk, "construction", []):
                if c and c[0] in ("line",):
                    segs.append([list(c[1]), list(c[2])])
        if segs:
            self._sketch_actor = _lines_actor(segs, (0.10, 0.30, 0.65), 2.2)
            self.renderer.AddActor(self._sketch_actor)
        if pts:
            self._sketch_pts_actor = _points_actor(pts, (0.10, 0.30, 0.65), 8)
            self.renderer.AddActor(self._sketch_pts_actor)

    def show_preview(self, shape, color=PRE, opacity=0.45):
        """Show a translucent orange preview of a candidate shape (not committed)."""
        from scdm.kernel import tessellate_faces
        self.clear_preview()
        try:
            faces = tessellate_faces(shape, deflection=0.001)
        except Exception:
            return
        app = vtk.vtkAppendPolyData()
        for fd in faces:
            pts = np.array(fd["vertices"], dtype=np.float64)
            if len(pts) == 0 or not fd["triangles"]:
                continue
            app.AddInputData(_polys(pts, fd["triangles"]))
        if app.GetTotalNumberOfInputConnections() == 0:
            return
        app.Update()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(app.GetOutputPort())
        act = vtk.vtkActor()
        act.SetMapper(mapper)
        act.GetProperty().SetColor(*color)
        act.GetProperty().SetOpacity(opacity)
        act.GetProperty().SetDiffuse(0.9)
        act.GetProperty().SetSpecular(0.2)
        act.GetProperty().SetAmbient(0.2)
        self._preview_actor = act
        self.renderer.AddActor(act)
        self.render()

    def clear_preview(self):
        if self._preview_actor is not None:
            self.renderer.RemoveActor(self._preview_actor)
            self._preview_actor = None
            self.render()

    def apply_visibility(self, session: Session):
        face_on = session.show_faces and session.style != "wire"
        for a in self._face_actors.values():
            a.SetVisibility(1 if face_on else 0)
        if self._edge_actor:
            hide_edges = session.style == "shaded"
            self._edge_actor.SetVisibility(1 if session.show_edges and not hide_edges else 0)
        if self._vert_actor:
            self._vert_actor.SetVisibility(1 if session.show_vertices else 0)
        if self._origin_actor:
            vis = 1 if session.show_axes else 0
            self._origin_actor.SetVisibility(vis)
            for lab in getattr(self, "_origin_labels", []):
                lab.SetVisibility(vis)
        for a in self._plane_actors.values():
            a.SetVisibility(1 if session.show_planes else 0)
        if self._silhouette_actor:
            self._silhouette_actor.SetVisibility(
                1 if getattr(session, "show_silhouette", False) else 0)
        self.update_grid(session)
        self.render()

    def update_grid(self, session: Session):
        """Sketch grid on the active sketch's plane (session.show_grid)."""
        if self._grid_actor is not None:
            self.renderer.RemoveActor(self._grid_actor)
            self._grid_actor = None
        if not getattr(session, "show_grid", False):
            self.render()
            return
        sketches = getattr(getattr(session, "kdoc", None), "sketches", [])
        plane = sketches[-1].plane if sketches else "xy"
        ext, n = 0.02, 10
        step = 2 * ext / n

        def w(u, v):
            if plane == "zx":
                return (u, 0.0, v)
            if plane == "yz":
                return (0.0, u, v)
            return (u, v, 0.0)

        lines = []
        for i in range(n + 1):
            t = -ext + i * step
            lines.append([list(w(t, -ext)), list(w(t, ext))])
            lines.append([list(w(-ext, t)), list(w(ext, t))])
        self._grid_actor = _lines_actor(lines, (0.62, 0.68, 0.78), 1.0)
        _exclude_from_bounds(self._grid_actor)
        self.renderer.AddActor(self._grid_actor)
        self.render()

    def apply_style(self, style: str):
        for a in self._face_actors.values():
            prop = a.GetProperty()
            if style == "wire":
                a.SetVisibility(0)
            elif style == "transp":
                a.SetVisibility(1)
                prop.SetOpacity(0.35)
            elif style == "shaded":
                a.SetVisibility(1)
                prop.SetOpacity(getattr(a, "_base_opacity", 1.0))
            else:
                a.SetVisibility(1)
                prop.SetOpacity(getattr(a, "_base_opacity", 1.0))
        if self._edge_actor:
            hide_edges = style == "shaded"
            self._edge_actor.SetVisibility(0 if hide_edges else 1)
        self.render()

    def _restore(self, actor):
        if actor is None:
            return
        col = getattr(actor, "_base_color", None)
        if col:
            actor.GetProperty().SetColor(*col)
        actor.GetProperty().SetOpacity(getattr(actor, "_base_opacity", 1.0))

    def highlight_actors(self, actors):
        for a in self._highlight:
            self._restore(a)
        self._highlight = [a for a in actors if a is not None]
        for a in self._highlight:
            a.GetProperty().SetColor(*SELECT)
            a.GetProperty().SetOpacity(0.85)
        self.render()

    def highlight_nodes(self, node_ids):
        self.highlight_actors([self._face_actors.get(n) for n in node_ids])

    def highlight_all_faces(self):
        self.highlight_actors(list(self._face_actors.values()))

    def pick_actor(self):
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        x, y = iren.GetEventPosition()
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        for a in self._face_actors.values():
            picker.AddPickList(a)
        picker.PickFromListOn()
        picker.Pick(x, y, 0, self.renderer)
        actor = picker.GetActor()
        world = picker.GetPickPosition() if actor else None
        return actor, world

    def _reset_empty_camera(self):
        cam = self.renderer.GetActiveCamera()
        cam.ParallelProjectionOn()
        cam.SetFocalPoint(0.0, 0.0, 0.0)
        cam.SetPosition(0.05, -0.065, 0.045)
        cam.SetViewUp(0.0, 0.0, 1.0)
        cam.SetParallelScale(0.042)
        self.renderer.ResetCameraClippingRange()

    def fit(self):
        if not self._face_actors:
            self._reset_empty_camera()
            self.render()
            return
        self.renderer.ResetCamera()
        cam = self.renderer.GetActiveCamera()
        try:
            cam.Zoom(0.92)
        except Exception:
            pass
        self.renderer.ResetCameraClippingRange()
        self.render()

    def store_camera(self):
        cam = self.renderer.GetActiveCamera()
        return (cam.GetPosition(), cam.GetFocalPoint(), cam.GetViewUp(),
                cam.GetParallelScale())

    def restore_camera(self, snap):
        if not snap:
            return
        cam = self.renderer.GetActiveCamera()
        cam.SetPosition(*snap[0])
        cam.SetFocalPoint(*snap[1])
        cam.SetViewUp(*snap[2])
        cam.SetParallelScale(snap[3])
        self.render()

    def plane_view(self, axis: str, scale: float, negative=False):
        cam = self.renderer.GetActiveCamera()
        d = max(scale, 20.0) * 1.2
        s = -1 if negative else 1
        if axis == "x":
            cam.SetPosition(s * d, 0, 0)
            cam.SetViewUp(0, 0, 1)
        elif axis == "y":
            cam.SetPosition(0, s * d, 0)
            cam.SetViewUp(0, 0, 1)
        else:
            cam.SetPosition(0, 0, s * d)
            cam.SetViewUp(0, 1, 0)
        cam.SetFocalPoint(0, 0, 0)
        cam.ParallelProjectionOn()
        if self._face_actors:
            self.renderer.ResetCamera()
        else:
            self._reset_empty_camera()
        self.render()

    def iso_view(self, scale: float):
        cam = self.renderer.GetActiveCamera()
        d = max(scale, 20.0) * 1.2
        cam.SetPosition(d, d, d)
        cam.SetViewUp(0, 0, 1)
        cam.SetFocalPoint(0, 0, 0)
        cam.ParallelProjectionOn()
        if self._face_actors:
            self.renderer.ResetCamera()
        else:
            self._reset_empty_camera()
        self.render()

    def export_png(self, path: str):
        w2i = vtk.vtkWindowToImageFilter()
        w2i.SetInput(self.renderer.GetRenderWindow())
        w2i.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.Write()


def _axis_label(text, pos, color):
    """Screen-sized axis letter that does not blow up with camera fit."""
    try:
        lab = vtk.vtkBillboardTextActor3D()
        lab.SetInput(text)
        lab.SetPosition(*pos)
        tp = lab.GetTextProperty()
        tp.SetFontFamilyToArial()
        tp.SetFontSize(13)
        tp.BoldOff()
        tp.ItalicOff()
        tp.ShadowOff()
        tp.SetColor(*color)
        tp.SetJustificationToCentered()
        tp.SetVerticalJustificationToCentered()
        _exclude_from_bounds(lab)
        return lab
    except Exception:
        return None


def _exclude_from_bounds(prop):
    try:
        prop.UseBoundsOff()
    except Exception:
        pass


def _style_axes(axes, world=False):
    try:
        axes.SetShaftTypeToCylinder()
        axes.SetNormalizedShaftLength(0.82, 0.82, 0.82)
        axes.SetNormalizedTipLength(0.18, 0.18, 0.18)
        if world:
            axes.SetCylinderRadius(0.018)
            axes.SetConeRadius(0.05)
        else:
            axes.SetCylinderRadius(0.02)
            axes.SetConeRadius(0.06)
        for getter, rgb in (
            (axes.GetXAxisShaftProperty, (0.82, 0.22, 0.20)),
            (axes.GetYAxisShaftProperty, (0.22, 0.62, 0.28)),
            (axes.GetZAxisShaftProperty, (0.20, 0.38, 0.78)),
            (axes.GetXAxisTipProperty, (0.82, 0.22, 0.20)),
            (axes.GetYAxisTipProperty, (0.22, 0.62, 0.28)),
            (axes.GetZAxisTipProperty, (0.20, 0.38, 0.78)),
        ):
            try:
                getter().SetColor(*rgb)
            except Exception:
                pass
    except Exception:
        pass
    if world:
        try:
            axes.AxisLabelsOff()
        except Exception:
            try:
                axes.SetAxisLabels(0)
            except Exception:
                pass
        _exclude_from_bounds(axes)
        return
    colors = ((0.78, 0.18, 0.18), (0.18, 0.55, 0.22), (0.16, 0.34, 0.72))
    getters = (
        axes.GetXAxisCaptionActor2D,
        axes.GetYAxisCaptionActor2D,
        axes.GetZAxisCaptionActor2D,
    )
    for getter, color in zip(getters, colors):
        try:
            cap = getter()
        except Exception:
            continue
        try:
            cap.SetWidth(0.08)
            cap.SetHeight(0.04)
        except Exception:
            pass
        try:
            ta = cap.GetTextActor()
            ta.SetTextScaleModeToNone()
        except Exception:
            pass
        try:
            tp = cap.GetCaptionTextProperty()
            tp.ShadowOff()
            tp.BoldOff()
            tp.ItalicOff()
            tp.SetFontFamilyToArial()
            tp.SetFontSize(11)
            tp.SetColor(*color)
            try:
                tp.SetBackgroundOpacity(0.0)
            except Exception:
                pass
        except Exception:
            pass


def _polys(pts, tris):
    pd = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_support.numpy_to_vtk(pts, deep=True))
    pd.SetPoints(vp)
    conn = np.column_stack([np.full(len(tris), 3, dtype=np.int64), tris]).reshape(-1)
    arr = vtk.vtkCellArray()
    arr.SetCells(len(tris), numpy_support.numpy_to_vtkIdTypeArray(conn, deep=True))
    pd.SetPolys(arr)
    return pd


def _lines_actor(segments, color, width):
    pts, conn = [], []
    for a, b in segments:
        base = len(pts)
        pts.append(a)
        pts.append(b)
        conn.append([2, base, base + 1])
    pd = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_support.numpy_to_vtk(np.array(pts, dtype=np.float64), deep=True))
    pd.SetPoints(vp)
    c = np.array(conn, dtype=np.int64).reshape(-1)
    arr = vtk.vtkCellArray()
    arr.SetCells(len(segments), numpy_support.numpy_to_vtkIdTypeArray(c, deep=True))
    pd.SetLines(arr)
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(pd)
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetLineWidth(width)
    a.GetProperty().SetAmbient(1.0)
    a.GetProperty().LightingOff()
    return a


def _points_actor(vpts, color, size):
    pd = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_support.numpy_to_vtk(np.array(vpts, dtype=np.float64), deep=True))
    pd.SetPoints(vp)
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(pd)
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetPointSize(size)
    a.GetProperty().SetAmbient(1.0)
    a.GetProperty().LightingOff()
    return a

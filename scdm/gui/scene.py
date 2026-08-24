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
    """LMB select, MMB rotate, Shift+MMB pan, RMB context, wheel zoom."""

    def __init__(self):
        super().__init__()
        self.click_cb = None
        self.right_cb = None

    def OnLeftButtonDown(self):
        if self.click_cb:
            self.click_cb()

    def OnLeftButtonUp(self):
        return

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
        self._highlight = []
        self._origin_actor = None
        self._plane_actors = {}
        self._gizmo = None
        self._install_gizmo()
        self._install_origin()
        self._install_planes()

        self._click_n = 0
        self._click_actor = None
        self._click_t = 0.0

    def _install_gizmo(self):
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(1.0, 1.0, 1.0)
        try:
            axes.SetNormalizedShaftLength(0.85, 0.85, 0.85)
            axes.SetNormalizedTipLength(0.15, 0.15, 0.15)
        except Exception:
            pass
        gizmo = vtk.vtkOrientationMarkerWidget()
        gizmo.SetOrientationMarker(axes)
        gizmo.SetInteractor(self.vtk_widget.GetRenderWindow().GetInteractor())
        gizmo.SetViewport(0.0, 0.0, 0.16, 0.16)
        gizmo.SetEnabled(1)
        gizmo.InteractiveOff()
        self._gizmo = gizmo

    def _install_origin(self):
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(0.02, 0.02, 0.02)
        axes.SetShaftTypeToCylinder()
        self.renderer.AddActor(axes)
        self._origin_actor = axes

    def _install_planes(self):
        specs = {
            "xy": ((1, 0, 0), (0, 1, 0), (0.7, 0.7, 0.9)),
            "zx": ((1, 0, 0), (0, 0, 1), (0.9, 0.7, 0.7)),
            "yz": ((0, 1, 0), (0, 0, 1), (0.7, 0.9, 0.7)),
        }
        for key, (ax1, ax2, col) in specs.items():
            src = vtk.vtkPlaneSource()
            src.SetOrigin(-0.03, -0.03, 0)
            src.SetPoint1(0.03, -0.03, 0)
            src.SetPoint2(-0.03, 0.03, 0)
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
            a.GetProperty().SetOpacity(0.18)
            a.SetVisibility(0)
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
        lines, verts = [], []
        for body in kdoc.bodies:
            if not body.visible:
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
                act._face_i = fd["index"]
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
        self.apply_visibility(session)
        self.apply_style(session.style)
        self.fit()

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
            self._origin_actor.SetVisibility(1 if session.show_axes else 0)
        for a in self._plane_actors.values():
            a.SetVisibility(1 if session.show_planes else 0)
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

    def fit(self):
        self.renderer.ResetCamera()
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
        self.renderer.ResetCamera()
        self.render()

    def iso_view(self, scale: float):
        cam = self.renderer.GetActiveCamera()
        d = max(scale, 20.0) * 1.2
        cam.SetPosition(d, d, d)
        cam.SetViewUp(0, 0, 1)
        cam.SetFocalPoint(0, 0, 0)
        cam.ParallelProjectionOn()
        self.renderer.ResetCamera()
        self.render()

    def export_png(self, path: str):
        w2i = vtk.vtkWindowToImageFilter()
        w2i.SetInput(self.renderer.GetRenderWindow())
        w2i.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.Write()


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

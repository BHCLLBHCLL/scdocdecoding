"""VTK scene: tessellated bodies, gizmo, picking, display styles."""
from __future__ import annotations

import math

import numpy as np

import vtk
from vtk.util import numpy_support

from scdm.document import Session

BG = (0.97, 0.97, 0.975)
BG2 = (0.91, 0.92, 0.935)
SELECT = (1.0, 0.45, 0.08)
PRE = (1.0, 0.78, 0.16)
BASE = (0.62, 0.66, 0.70)
GOLD = (1.0, 0.80, 0.12)
GOLD_DIM = (1.0, 0.86, 0.42)


class CadStyle(vtk.vtkInteractorStyleUser):
    """Bare style + callback holder for Scene's interactor-level handlers.

    LMB select/tool drag, MMB rotate, Shift+MMB pan, RMB context, wheel zoom
    are implemented in Scene's observer handlers (see below).  A bare
    vtkInteractorStyleUser is used because C++->Python virtual dispatch of
    interactor-style overrides does not fire in some vtk builds: a python
    subclass of the trackball style silently falls through to the C++
    default (clicks would camera-rotate and every callback would be dead).
    """

    def __init__(self):
        super().__init__()
        self.click_cb = None
        self.right_cb = None
        self.drag_start_cb = None   # callable() at LMB down
        self.drag_move_cb = None    # callable(dx, dy) during drag
        self.drag_end_cb = None     # callable(total_dx, total_dy) at release


class Scene:
    # -- interactor-level input handlers ----------------------------------
    # (see CadStyle docstring: these replace the style's virtual overrides)
    ROTATE_DEG_PER_PX = 0.5
    ZOOM_STEP = 1.1
    # World-origin triad length as a fraction of camera ParallelScale
    # (half the viewport height in world units) so on-screen size tracks
    # the window, not the imported model bounds.
    ORIGIN_VIEW_FRAC = 0.22

    def _on_iren_left_down(self, o, e):
        if self.style.drag_start_cb:
            self._drag_active = True
            self._drag_origin = o.GetEventPosition()
            self._drag_last = self._drag_origin
            self.style.drag_start_cb()
        elif self.style.click_cb:
            self.style.click_cb()

    def _on_iren_move(self, o, e):
        if self._drag_active and self.style.drag_move_cb:
            pos = o.GetEventPosition()
            self.style.drag_move_cb(pos[0] - self._drag_last[0],
                                    pos[1] - self._drag_last[1])
            self._drag_last = pos
            return
        if self._cam_mode is not None:
            pos = o.GetEventPosition()
            dx = pos[0] - self._cam_last[0]
            dy = pos[1] - self._cam_last[1]
            self._cam_last = pos
            self._camera_move(dx, dy)

    def _on_iren_left_up(self, o, e):
        if self._drag_active:
            self._drag_active = False
            if self.style.drag_end_cb:
                pos = o.GetEventPosition()
                self.style.drag_end_cb(pos[0] - self._drag_origin[0],
                                       pos[1] - self._drag_origin[1])

    def _on_iren_middle_down(self, o, e):
        self._cam_mode = "pan" if o.GetShiftKey() else "rotate"
        self._cam_last = o.GetEventPosition()

    def _on_iren_middle_up(self, o, e):
        self._cam_mode = None

    def _on_iren_right_down(self, o, e):
        if self.style.right_cb:
            self.style.right_cb()

    def _on_iren_wheel(self, o, e, factor):
        cam = self.renderer.GetActiveCamera()
        if cam.GetParallelProjection():
            cam.SetParallelScale(cam.GetParallelScale() / factor)
        else:
            cam.Dolly(factor)
        self.render()

    def _camera_move(self, dx, dy):
        """Grab-the-model trackball (MMB) / pan (Shift+MMB) in pixels.

        VTK Azimuth(+): camera walks right, the model appears to spin right.
        CAD convention is the opposite — the model follows the cursor — so
        azimuth uses -dx. Pan Y is likewise inverted so dragging up moves
        the model up.
        """
        cam = self.renderer.GetActiveCamera()
        if self._cam_mode == "rotate":
            cam.Azimuth(-dx * self.ROTATE_DEG_PER_PX)
            cam.Elevation(-dy * self.ROTATE_DEG_PER_PX)
            cam.OrthogonalizeViewUp()
        else:
            _, vh = self.renderer.GetRenderWindow().GetSize()
            k = 2.0 * cam.GetParallelScale() / max(vh, 1)
            d = cam.GetDirectionOfProjection()
            up = cam.GetViewUp()
            right = (d[1] * up[2] - d[2] * up[1],
                     d[2] * up[0] - d[0] * up[2],
                     d[0] * up[1] - d[1] * up[0])
            fp = cam.GetFocalPoint()
            p = cam.GetPosition()
            shift = (right[0] * -dx * k + up[0] * -dy * k,
                     right[1] * -dx * k + up[1] * -dy * k,
                     right[2] * -dx * k + up[2] * -dy * k)
            cam.SetFocalPoint(fp[0] + shift[0], fp[1] + shift[1],
                              fp[2] + shift[2])
            cam.SetPosition(p[0] + shift[0], p[1] + shift[1],
                            p[2] + shift[2])
        self.render()

    def __init__(self, vtk_widget):
        self.preserve_camera = False   # sketch mode: keep the plane view
        self.vtk_widget = vtk_widget
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(*BG)
        self.renderer.SetBackground2(*BG2)
        self.renderer.GradientBackgroundOn()
        self.renderer.GetActiveCamera().ParallelProjectionOn()
        rw = vtk_widget.GetRenderWindow()
        rw.AddRenderer(self.renderer)
        try:
            rw.LineSmoothingOn()
            rw.PointSmoothingOn()
        except Exception:
            pass
        self.style = CadStyle()
        vtk_widget.GetRenderWindow().GetInteractor().SetInteractorStyle(self.style)
        _iren = vtk_widget.GetRenderWindow().GetInteractor()
        # Custom input runs on interactor-level observers: C++->Python
        # virtual dispatch of interactor-style overrides does not fire in
        # some vtk builds (CadStyle.OnLeftButtonDown etc. would never run),
        # while interactor observers and explicit base-class calls always
        # do.  The C++ trackball style stays for the wheel (zoom).
        self._drag_active = False
        self._drag_origin = (0, 0)
        self._drag_last = (0, 0)
        self._cam_mode = None  # None | "rotate" | "pan"
        _iren.AddObserver("LeftButtonPressEvent", self._on_iren_left_down,
                          10.0)
        _iren.AddObserver("LeftButtonReleaseEvent", self._on_iren_left_up,
                          10.0)
        _iren.AddObserver("MouseMoveEvent", self._on_iren_move, 10.0)
        _iren.AddObserver("MiddleButtonPressEvent", self._on_iren_middle_down,
                          10.0)
        _iren.AddObserver("MiddleButtonReleaseEvent", self._on_iren_middle_up,
                          10.0)
        _iren.AddObserver("RightButtonPressEvent", self._on_iren_right_down,
                          10.0)
        _iren.AddObserver("MouseWheelForwardEvent",
                          lambda o, e: self._on_iren_wheel(o, e, self.ZOOM_STEP),
                          10.0)
        _iren.AddObserver("MouseWheelBackwardEvent",
                          lambda o, e: self._on_iren_wheel(
                              o, e, 1.0 / self.ZOOM_STEP), 10.0)
        vtk_widget.Initialize()
        vtk_widget.Start()

        self._face_actors = {}
        self._edge_actor = None
        self._vert_actor = None
        self._sketch_actor = None
        self._sketch_pts_actor = None
        self._preview_actor = None
        self._preview_hidden = []
        self._highlight = []
        self._origin_actor = None
        self._plane_actors = {}
        self._grid_actor = None
        self._silhouette_actor = None
        self._section_axis = None
        self._note_actors = []
        self._edge_topo_actor = None
        self._vert_topo_actor = None
        self._edge_cell_map = []
        self._vert_cell_map = []
        self._edge_segments = {}
        self._vertex_pos = {}
        self._sel_edge_actor = None
        self._sel_vert_actor = None
        self._measure_actors = []
        self._section_widget = None
        self._gizmo = None
        self._handle_actors = []
        self._handle_label = None
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
        _style_axes(axes, world=False, hairline=False)
        hub = _sphere_actor(0.08, (0.94, 0.94, 0.95), opacity=1.0, spec=0.55)
        asm = vtk.vtkPropAssembly()
        asm.AddPart(axes)
        asm.AddPart(hub)
        gizmo = vtk.vtkOrientationMarkerWidget()
        gizmo.SetOrientationMarker(asm)
        gizmo.SetInteractor(self.vtk_widget.GetRenderWindow().GetInteractor())
        # ~16% of the viewport, inset from the corner.
        gizmo.SetViewport(0.012, 0.012, 0.172, 0.172)
        try:
            gizmo.SetOutlineColor(*BG)
        except Exception:
            pass
        for getter in ("GetOutlineProperty", "GetBorderProperty"):
            try:
                getattr(gizmo, getter)().SetOpacity(0.0)
            except Exception:
                pass
        gizmo.SetEnabled(1)
        gizmo.InteractiveOff()
        self._gizmo = gizmo

    def _origin_length(self):
        """World length of the origin triad for the current camera."""
        cam = self.renderer.GetActiveCamera()
        if cam.GetParallelProjection():
            half_h = cam.GetParallelScale()
        else:
            dist = abs(cam.GetDistance())
            half_h = dist * math.tan(math.radians(cam.GetViewAngle()) * 0.5)
        return max(1e-9, half_h * self.ORIGIN_VIEW_FRAC)

    def _sync_origin_scale(self):
        """Keep the world origin a constant fraction of the viewport."""
        asm = getattr(self, "_origin_actor", None)
        if asm is None:
            return
        length = self._origin_length()
        base = getattr(self, "_origin_base_length", 1.0) or 1.0
        scale = length / base
        prev = getattr(self, "_origin_scale", None)
        if prev is not None and abs(prev - scale) < 1e-9:
            return
        self._origin_scale = scale
        try:
            asm.SetScale(scale, scale, scale)
        except Exception:
            pass
        tip = length * 1.20
        for lab, pos in zip(
            getattr(self, "_origin_labels", []),
            ((tip, 0.0, 0.0), (0.0, tip, 0.0), (0.0, 0.0, tip)),
        ):
            try:
                lab.SetPosition(*pos)
            except Exception:
                pass

    def _install_origin(self):
        # Unit-length triad; world scale is applied in _sync_origin_scale.
        self._origin_base_length = 1.0
        asm = _make_triad(1.0, cone_frac=0.22, hub_frac=0.07, tube=True)
        _exclude_from_bounds(asm)
        self.renderer.AddActor(asm)
        self._origin_actor = asm
        self._origin_labels = []
        for text, pos, color in (
            ("X", (1.20, 0.0, 0.0), (0.82, 0.18, 0.14)),
            ("Y", (0.0, 1.20, 0.0), (0.16, 0.58, 0.24)),
            ("Z", (0.0, 0.0, 1.20), (0.14, 0.34, 0.80)),
        ):
            lab = _axis_label(text, pos, color, size=13, shadow=True)
            if lab is None:
                continue
            self.renderer.AddActor(lab)
            self._origin_labels.append(lab)
        self._sync_origin_scale()

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
        self._sync_origin_scale()
        self.renderer.GetRenderWindow().Render()

    def clear_bodies(self):
        self.disable_section_widget()
        self.clear_handles()
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
        for act in getattr(self, "_note_actors", []):
            self.renderer.RemoveActor(act)
        self._note_actors = []
        for attr in ("_edge_topo_actor", "_vert_topo_actor",
                     "_sel_edge_actor", "_sel_vert_actor"):
            act = getattr(self, attr, None)
            if act:
                self.renderer.RemoveActor(act)
            setattr(self, attr, None)
        self._edge_cell_map = []
        self._vert_cell_map = []
        self._edge_segments = {}
        self._vertex_pos = {}
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
        if self.preserve_camera:
            self.renderer.ResetCameraClippingRange()
            self.render()
        else:
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
        self._build_topo(kdoc)
        self._build_silhouette(pds)
        self._build_sketches(kdoc)
        self._build_notes(kdoc)
        self.apply_visibility(session)
        self.apply_style(session.style)
        self.set_section(getattr(session, "section_axis", None))
        if self.preserve_camera:
            self.renderer.ResetCameraClippingRange()
            self.render()
        else:
            self.fit()

    def model_bounds(self):
        acts = list(self._face_actors.values())
        if not acts:
            return None
        b = list(acts[0].GetBounds())
        for a in acts[1:]:
            ab = a.GetBounds()
            b[0] = min(b[0], ab[0]); b[1] = max(b[1], ab[1])
            b[2] = min(b[2], ab[2]); b[3] = max(b[3], ab[3])
            b[4] = min(b[4], ab[4]); b[5] = max(b[5], ab[5])
        return tuple(b)

    def set_section(self, axis):
        """Static section: clip the shaded model through its centre (None=off)."""
        self._section_axis = axis
        planes = []
        if axis:
            b = self.model_bounds()
            if b:
                nx, ny, nz = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
                pl = vtk.vtkPlane()
                pl.SetNormal(nx, ny, nz)
                pl.SetOrigin((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0,
                             (b[4] + b[5]) / 2.0)
                planes.append(pl)
        for a in self._face_actors.values():
            m = a.GetMapper()
            m.RemoveAllClippingPlanes()
            for pl in planes:
                m.AddClippingPlane(pl)
        self.render()

    def enable_section_widget(self):
        """Interactive section: draggable implicit-plane widget clipping the model."""
        self.disable_section_widget()
        b = self.model_bounds()
        if not b:
            return False
        try:
            w = vtk.vtkImplicitPlaneWidget()
        except Exception:
            return False
        pl = w.GetPlane()
        pl.SetOrigin((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, (b[4] + b[5]) / 2.0)
        pl.SetNormal(1.0, 0.0, 0.0)
        w.SetInteractor(self.vtk_widget.GetRenderWindow().GetInteractor())
        w.SetPlaceFactor(1.25)
        w.PlaceWidget(b)
        w.AddObserver("InteractionEvent", lambda obj, ev: self.render())
        w.On()
        self._section_widget = w
        for a in self._face_actors.values():
            a.GetMapper().AddClippingPlane(pl)
        self.render()
        return True

    def disable_section_widget(self):
        w = getattr(self, "_section_widget", None)
        if w is not None:
            try:
                w.Off()
            except Exception:
                pass
            self._section_widget = None
        for a in self._face_actors.values():
            a.GetMapper().RemoveAllClippingPlanes()
        self.render()

    def _build_topo(self, kdoc):
        """Pickable B-rep edges (polylines) and vertices for the whole kdoc.

        Cell k of the edges actor maps to (body_id, edge_index); the same mapping
        is stored for vertices so picks resolve to edge:/vertex: node ids. Edges
        are de-duplicated across orientation repeats via endpoint keys.
        """
        from scdm import kernel as K
        pts_all, cells, ecmap, esegs = [], [], [], {}
        vpts, vcmap, vpos = [], [], {}
        seen_e, seen_v = set(), set()
        for body in kdoc.bodies:
            if not body.visible:
                continue
            try:
                edges = K.explore(body.shape, "edge")
            except Exception:
                edges = []
            for i, e in enumerate(edges):
                p = K.edge_polyline(e, deflection=max(1e-6, 0.01 / 1000.0))
                if len(p) < 2:
                    continue
                k = (round(p[0][0] * 1e5), round(p[0][1] * 1e5), round(p[0][2] * 1e5),
                     round(p[-1][0] * 1e5), round(p[-1][1] * 1e5), round(p[-1][2] * 1e5))
                if k in seen_e:
                    continue
                seen_e.add(k)
                ei = len(cells)  # canonical display-edge index (cell id)
                pids = []
                for q in p:
                    pids.append(len(pts_all))
                    pts_all.append(list(q))
                cells.append([len(pids)] + pids)
                esegs[(body.id, ei)] = [[list(a), list(b)] for a, b in zip(p, p[1:])]
                ecmap.append((body.id, ei))
            try:
                vs = K.explore(body.shape, "vertex")
            except Exception:
                vs = []
            for i, v in enumerate(vs):
                try:
                    p = K.vertex_point(v)
                except Exception:
                    continue
                k = (round(p[0] * 1e5), round(p[1] * 1e5), round(p[2] * 1e5))
                if k in seen_v:
                    continue
                seen_v.add(k)
                vi = len(vpts)
                vpos[(body.id, vi)] = p
                vpts.append(list(p))
                vcmap.append((body.id, vi))
        if cells:
            self._edge_topo_actor = _polylines_actor(pts_all, cells, (0.12, 0.12, 0.15), 1.4)
            self.renderer.AddActor(self._edge_topo_actor)
            self._edge_actor = self._edge_topo_actor
            self._edge_cell_map = ecmap
            self._edge_segments = esegs
        if vpts:
            self._vert_topo_actor = _vertices_actor(vpts, (0.05, 0.05, 0.05), 6)
            self.renderer.AddActor(self._vert_topo_actor)
            self._vert_actor = self._vert_topo_actor
            self._vert_cell_map = vcmap
            self._vertex_pos = vpos

    def _build_notes(self, kdoc):
        """Viewport text annotations anchored at world positions."""
        for note in getattr(kdoc, "notes", []):
            lab = _axis_label(note.get("text", ""),
                              tuple(note.get("pos") or (0, 0, 0)),
                              (0.55, 0.25, 0.10))
            if lab is not None:
                self.renderer.AddActor(lab)
                self._note_actors.append(lab)

    def focal_point(self):
        return tuple(self.renderer.GetActiveCamera().GetFocalPoint())

    PLANE_NORMALS = {"xy": (0, 0, 1), "zx": (0, 1, 0), "yz": (1, 0, 0)}

    def plane_point(self, plane):
        """World point where the click ray meets the sketch plane.

        `plane` is a named datum plane ('xy'|'zx'|'yz') or a sketch axes tuple
        (origin, u, v, n) for custom planes.
        """
        from scdm import sketch as S
        if isinstance(plane, str):
            origin, _u, _v, n = S.sketch_axes(plane)
        else:
            origin, _u, _v, n = plane
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        x, y = iren.GetEventPosition()
        picker = vtk.vtkWorldPointPicker()
        picker.Pick(x, y, 0, self.renderer)
        wp = picker.GetPickPosition()
        cam = self.renderer.GetActiveCamera()
        pos = cam.GetPosition()
        d = (wp[0] - pos[0], wp[1] - pos[1], wp[2] - pos[2])
        denom = d[0] * n[0] + d[1] * n[1] + d[2] * n[2]
        if abs(denom) < 1e-12:
            return None
        t = -((pos[0] - origin[0]) * n[0] + (pos[1] - origin[1]) * n[1]
              + (pos[2] - origin[2]) * n[2]) / denom
        if t <= 0:
            return None
        return (pos[0] + d[0] * t, pos[1] + d[1] * t, pos[2] + d[2] * t)

    def normal_view(self, origin, normal, up, scale):
        """Camera looking straight at a plane (origin along normal, up = in-plane)."""
        cam = self.renderer.GetActiveCamera()
        d = max(scale, 20.0) * 1.2
        cam.SetPosition(origin[0] + normal[0] * d, origin[1] + normal[1] * d,
                        origin[2] + normal[2] * d)
        cam.SetFocalPoint(*origin)
        cam.SetViewUp(*up)
        self.renderer.ResetCameraClippingRange()
        self.render()

    def show_measure(self, text, p1, p2=None):
        """Measurement annotation: optional connector line + billboard label."""
        self.clear_measure()
        mid = p1
        if p2 is not None:
            self._measure_actors.append(
                _lines_actor([[list(p1), list(p2)]], (0.85, 0.45, 0.10), 2.0))
            mid = [(p1[k] + p2[k]) / 2.0 for k in range(3)]
        lab = _axis_label(text, mid, (0.85, 0.45, 0.10))
        if lab is not None:
            self._measure_actors.append(lab)
        for a in self._measure_actors:
            self.renderer.AddActor(a)
        self.render()

    def clear_measure(self):
        for a in self._measure_actors:
            self.renderer.RemoveActor(a)
        self._measure_actors = []
        self.render()

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
        """Render sketch curves as on-plane 2D line/polygon actors.

        Curve coords are plane-local (u, v), mapped through the sketch's axes
        (named datum plane or custom origin/normal/xdir).
        """
        import math as _math
        from scdm import sketch as S
        segs, pts = [], []
        for sk in getattr(kdoc, "sketches", []):
            axes = S.sketch_axes(sk.plane, sk.origin, sk.normal, sk.xdir)

            def wpt(p, _ax=axes):
                return list(S.axes_to_world(_ax, float(p[0]), float(p[1])))
            for c in sk.curves:
                if c[0] == "poly":
                    ring = [wpt(p) for p in c[1]]
                    if ring[0] != ring[-1]:
                        ring.append(ring[0])
                    for a, b in zip(ring, ring[1:]):
                        segs.append([list(a), list(b)])
                elif c[0] == "rect":
                    x0, y0 = c[1][0], c[1][1]
                    x1, y1 = c[2][0], c[2][1]
                    loop = [wpt((x0, y0)), wpt((x1, y0)), wpt((x1, y1)),
                            wpt((x0, y1)), wpt((x0, y0))]
                    for a, b in zip(loop, loop[1:]):
                        segs.append([list(a), list(b)])
                elif c[0] == "line":
                    segs.append([list(wpt(c[1])), list(wpt(c[2]))])
                elif c[0] == "circle":
                    cx, cy = c[1][0], c[1][1]
                    r = c[2]
                    ring = [wpt((cx + r * _math.cos(t), cy + r * _math.sin(t)))
                            for t in [_math.tau * i / 32 for i in range(32)]]
                    ring.append(ring[0])
                    for a, b in zip(ring, ring[1:]):
                        segs.append([list(a), list(b)])
                elif c[0] == "point":
                    pts.append(list(wpt(c[1])))
            for c in getattr(sk, "construction", []):
                if c and c[0] == "line":
                    segs.append([list(wpt(c[1])), list(wpt(c[2]))])
                elif c and c[0] == "poly":
                    ring = [wpt(p) for p in c[1]]
                    for a, b in zip(ring, ring[1:]):
                        segs.append([list(a), list(b)])
        if segs:
            self._sketch_actor = _lines_actor(segs, (0.10, 0.30, 0.65), 2.2)
            self.renderer.AddActor(self._sketch_actor)
        if pts:
            self._sketch_pts_actor = _points_actor(pts, (0.10, 0.30, 0.65), 8)
            self.renderer.AddActor(self._sketch_pts_actor)

    def show_preview(self, shape, color=PRE, opacity=0.55, hide_body_id=None):
        """Show a translucent orange preview of a candidate shape (not committed)."""
        from scdm.kernel import tessellate_faces
        if self._preview_actor is not None:
            self.renderer.RemoveActor(self._preview_actor)
            self._preview_actor = None
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
        if hide_body_id and not self._preview_hidden:
            hidden = []
            for a in self._face_actors.values():
                if getattr(a, "_body_id", None) == hide_body_id:
                    hidden.append((a, a.GetVisibility()))
                    a.SetVisibility(0)
            self._preview_hidden = hidden
        self.render()

    def clear_preview(self):
        if self._preview_actor is not None:
            self.renderer.RemoveActor(self._preview_actor)
            self._preview_actor = None
        for a, vis in getattr(self, "_preview_hidden", []):
            try:
                a.SetVisibility(vis)
            except Exception:
                pass
        self._preview_hidden = []
        self.render()

    def handle_length(self):
        cam = self.renderer.GetActiveCamera()
        return max(0.005, cam.GetParallelScale() * 0.22)

    def world_to_display(self, xyz):
        """VTK display coords (origin at bottom-left of the render window)."""
        self.renderer.SetWorldPoint(xyz[0], xyz[1], xyz[2], 1.0)
        self.renderer.WorldToDisplay()
        d = self.renderer.GetDisplayPoint()
        return d[0], d[1]

    def clear_handles(self):
        for a in list(getattr(self, "_handle_actors", [])):
            self.renderer.RemoveActor(a)
        self._handle_actors = []
        if getattr(self, "_handle_label", None) is not None:
            self.renderer.RemoveActor(self._handle_label)
            self._handle_label = None

    def show_pull_handles(self, origin, normal, length=None, distance_mm=None):
        """Gold bidirectional arrows along a face normal (Pull manipulator)."""
        self.clear_handles()
        n = _norm3(normal)
        if n is None:
            return
        L = length if length is not None else self.handle_length()
        pos = _make_arrow(origin, n, L, GOLD, 0.92)
        neg = _make_arrow(origin, (-n[0], -n[1], -n[2]), L * 0.72, GOLD_DIM, 0.42)
        for a in (pos, neg):
            if a is None:
                continue
            _exclude_from_bounds(a)
            self.renderer.AddActor(a)
            self._handle_actors.append(a)
        if distance_mm is not None:
            tip = (origin[0] + n[0] * L * 1.08,
                   origin[1] + n[1] * L * 1.08,
                   origin[2] + n[2] * L * 1.08)
            lab = _axis_label(f"{distance_mm:.2f} mm", tip, (0.42, 0.28, 0.04),
                              size=13, shadow=True)
            if lab is not None:
                self.renderer.AddActor(lab)
                self._handle_label = lab
        self.render()

    def show_move_handles(self, origin, length=None):
        """RGB triad manipulator at a body origin (Move)."""
        self.clear_handles()
        L = length if length is not None else self.handle_length() * 0.9
        asm = _make_triad(L, cone_frac=0.22, hub_frac=0.07, tube=True)
        _exclude_from_bounds(asm)
        self.renderer.AddActor(asm)
        self._handle_actors.append(asm)
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
        from scdm import sketch as S
        if self._grid_actor is not None:
            self.renderer.RemoveActor(self._grid_actor)
            self._grid_actor = None
        if not getattr(session, "show_grid", False):
            self.render()
            return
        sketches = getattr(getattr(session, "kdoc", None), "sketches", [])
        sk = sketches[-1] if sketches else None
        axes = S.sketch_axes(sk.plane, sk.origin, sk.normal, sk.xdir) \
            if sk is not None else S.sketch_axes("xy")
        ext, n = 0.02, 10
        step = 2 * ext / n
        lines = []
        for i in range(n + 1):
            t = -ext + i * step
            lines.append([list(S.axes_to_world(axes, t, -ext)),
                          list(S.axes_to_world(axes, t, ext))])
            lines.append([list(S.axes_to_world(axes, -ext, t)),
                          list(S.axes_to_world(axes, ext, t))])
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
        face_ids = [n for n in node_ids if n in self._face_actors]
        self.highlight_actors([self._face_actors.get(n) for n in face_ids])
        self._highlight_topo(node_ids)

    def _highlight_topo(self, node_ids):
        """Orange overlays for selected B-rep edges / vertices."""
        for a in (self._sel_edge_actor, self._sel_vert_actor):
            if a:
                self.renderer.RemoveActor(a)
        self._sel_edge_actor = self._sel_vert_actor = None
        esegs, vpts = [], []
        for n in node_ids:
            parts = str(n).split(":")
            if len(parts) == 3 and parts[0] == "edge":
                segs = self._edge_segments.get((parts[1], int(parts[2])))
                if segs:
                    esegs.extend(segs)
            elif len(parts) == 3 and parts[0] == "vertex":
                p = self._vertex_pos.get((parts[1], int(parts[2])))
                if p:
                    vpts.append(list(p))
        if esegs:
            self._sel_edge_actor = _lines_actor(esegs, SELECT, 2.8)
            self.renderer.AddActor(self._sel_edge_actor)
        if vpts:
            self._sel_vert_actor = _vertices_actor(vpts, SELECT, 9)
            self.renderer.AddActor(self._sel_vert_actor)
        self.render()

    def highlight_all_faces(self):
        self.highlight_actors(list(self._face_actors.values()))

    def pick_detail(self, allow=("face", "edge", "vertex")):
        """Priority pick: faces, then B-rep edges, then vertices.

        Returns (kind, actor, node_id, world). node_id is 'B1:2' for faces,
        'edge:B1:3' / 'vertex:B1:1' for topo picks (cell id -> body/index map).
        """
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        x, y = iren.GetEventPosition()

        def _pick(actors):
            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.005)
            for a in actors:
                picker.AddPickList(a)
            picker.PickFromListOn()
            picker.Pick(x, y, 0, self.renderer)
            a = picker.GetActor()
            return a, picker.GetCellId(), (
                picker.GetPickPosition() if a else None)

        if "face" in allow:
            a, _cid, world = _pick(list(self._face_actors.values()))
            if a is not None:
                return ("face", a, getattr(a, "_node_id", None), world)
        if "edge" in allow and self._edge_topo_actor:
            a, cid, world = _pick([self._edge_topo_actor])
            if a is not None and 0 <= cid < len(self._edge_cell_map):
                bid, ei = self._edge_cell_map[cid]
                return ("edge", a, f"edge:{bid}:{ei}", world)
        if "vertex" in allow and self._vert_topo_actor:
            a, cid, world = _pick([self._vert_topo_actor])
            if a is not None and 0 <= cid < len(self._vert_cell_map):
                bid, vi = self._vert_cell_map[cid]
                return ("vertex", a, f"vertex:{bid}:{vi}", world)
        return (None, None, None, None)

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
        self._sync_origin_scale()

    def fit_to_bodies(self, body_ids):
        """Reset the camera to the combined bounds of the given bodies."""
        want = set(body_ids)
        acts = [a for k, a in self._face_actors.items()
                if k.split(":")[0] in want]
        if not acts:
            return
        b = list(acts[0].GetBounds())
        for a in acts[1:]:
            ab = a.GetBounds()
            b[0] = min(b[0], ab[0]); b[1] = max(b[1], ab[1])
            b[2] = min(b[2], ab[2]); b[3] = max(b[3], ab[3])
            b[4] = min(b[4], ab[4]); b[5] = max(b[5], ab[5])
        self.renderer.ResetCamera(tuple(b))
        self.renderer.ResetCameraClippingRange()
        self.render()

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

    def render_image(self, scale=1, bg=None, show_edges=None):
        """Grab the current viewport as a QImage (print / render entry).

        scale > 1 renders at a larger window size for anti-aliased supersampling;
        bg overrides the background colour; show_edges forces the edge overlay.
        """
        from PyQt5.QtGui import QImage
        from vtk.util.numpy_support import vtk_to_numpy
        rw = self.vtk_widget.GetRenderWindow()
        old_size = rw.GetSize()
        old_bg = self.renderer.GetBackground()
        edge_vis = self._edge_actor.GetVisibility() if self._edge_actor else 0
        try:
            if bg is not None:
                self.renderer.SetBackground(*bg)
            if show_edges is not None and self._edge_actor:
                self._edge_actor.SetVisibility(1 if show_edges else 0)
            if scale != 1:
                rw.SetSize(old_size[0] * scale, old_size[1] * scale)
            self.render()
            w2i = vtk.vtkWindowToImageFilter()
            w2i.SetInput(rw)
            w2i.Update()
            img = w2i.GetOutput()
            dims = img.GetDimensions()
            arr = vtk_to_numpy(img.GetPointData().GetScalars())
            arr = np.flipud(arr.reshape(dims[1], dims[0], -1))
        finally:
            if scale != 1:
                rw.SetSize(*old_size)
            self.renderer.SetBackground(*old_bg)
            if show_edges is not None and self._edge_actor:
                self._edge_actor.SetVisibility(edge_vis)
            self.render()
        fmt = QImage.Format_RGBA8888 if arr.shape[2] == 4 else QImage.Format_RGB888
        return QImage(arr.copy(), dims[0], dims[1], dims[0] * arr.shape[2], fmt)


def _axis_label(text, pos, color, size=12, shadow=False):
    """Screen-sized label that does not blow up with camera fit."""
    try:
        lab = vtk.vtkBillboardTextActor3D()
        lab.SetInput(text)
        lab.SetPosition(*pos)
        tp = lab.GetTextProperty()
        tp.SetFontFamilyToArial()
        tp.SetFontSize(int(size))
        tp.BoldOff()
        tp.ItalicOff()
        if shadow:
            tp.ShadowOn()
        else:
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


def _norm3(v):
    L = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if L < 1e-12:
        return None
    return (v[0] / L, v[1] / L, v[2] / L)


def _tube_actor(p0, p1, radius, color, opacity=1.0):
    src = vtk.vtkLineSource()
    src.SetPoint1(*p0)
    src.SetPoint2(*p1)
    tube = vtk.vtkTubeFilter()
    tube.SetInputConnection(src.GetOutputPort())
    tube.SetRadius(max(radius, 1e-12))
    tube.SetNumberOfSides(20)
    tube.CappingOn()
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(tube.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    prop = a.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetAmbient(0.35)
    prop.SetDiffuse(0.65)
    prop.SetSpecular(0.35)
    prop.SetSpecularPower(22)
    return a


def _line_actor(p0, p1, color, width):
    src = vtk.vtkLineSource()
    src.SetPoint1(*p0)
    src.SetPoint2(*p1)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(src.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    prop = a.GetProperty()
    prop.SetColor(*color)
    prop.SetLineWidth(width)
    prop.LightingOff()
    prop.SetAmbient(1.0)
    try:
        prop.SetRenderLinesAsTubes(False)
    except Exception:
        pass
    return a


def _cone_actor(direction, tip, height, radius, color, opacity=1.0):
    n = _norm3(direction)
    if n is None:
        return None
    src = vtk.vtkConeSource()
    src.SetResolution(28)
    src.SetHeight(height)
    src.SetRadius(radius)
    src.SetDirection(*n)
    src.SetCenter(tip[0] - n[0] * height * 0.5,
                  tip[1] - n[1] * height * 0.5,
                  tip[2] - n[2] * height * 0.5)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(src.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    prop = a.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetAmbient(0.35)
    prop.SetDiffuse(0.65)
    prop.SetSpecular(0.4)
    prop.SetSpecularPower(24)
    return a


def _sphere_actor(radius, color, opacity=1.0, spec=0.45):
    src = vtk.vtkSphereSource()
    src.SetRadius(radius)
    src.SetThetaResolution(28)
    src.SetPhiResolution(20)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(src.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    prop = a.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetAmbient(0.4)
    prop.SetDiffuse(0.55)
    prop.SetSpecular(spec)
    prop.SetSpecularPower(28)
    return a


def _make_triad(length, line_width=1.8, cone_frac=0.22, hub_frac=0.07,
                tube=True):
    """RGB triad with conical arrowheads and a pale hub."""
    asm = vtk.vtkAssembly()
    colors = ((0.90, 0.20, 0.16), (0.18, 0.64, 0.28), (0.16, 0.38, 0.86))
    dirs = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    cone_h = length * cone_frac
    cone_r = length * (0.075 if tube else 0.028)
    hub_r = length * hub_frac
    shaft_r = length * 0.028
    for d, col in zip(dirs, colors):
        tip = (d[0] * length, d[1] * length, d[2] * length)
        shaft = (d[0] * (length - cone_h), d[1] * (length - cone_h),
                 d[2] * (length - cone_h))
        if tube:
            shaft_act = _tube_actor((0.0, 0.0, 0.0), shaft, shaft_r, col)
        else:
            shaft_act = _line_actor((0.0, 0.0, 0.0), shaft, col, line_width)
        cone = _cone_actor(d, tip, cone_h, cone_r, col)
        asm.AddPart(shaft_act)
        if cone is not None:
            asm.AddPart(cone)
    hub = _sphere_actor(hub_r, (0.94, 0.94, 0.95), opacity=1.0, spec=0.55)
    asm.AddPart(hub)
    return asm


def _make_arrow(origin, direction, length, color, opacity=0.9):
    n = _norm3(direction)
    if n is None or length <= 0:
        return None
    asm = vtk.vtkAssembly()
    cone_h = length * 0.28
    tip = (origin[0] + n[0] * length,
           origin[1] + n[1] * length,
           origin[2] + n[2] * length)
    shaft = (origin[0] + n[0] * (length - cone_h),
             origin[1] + n[1] * (length - cone_h),
             origin[2] + n[2] * (length - cone_h))
    line = _line_actor(origin, shaft, color, 2.4)
    line.GetProperty().SetOpacity(opacity)
    cone = _cone_actor(n, tip, cone_h, length * 0.07, color, opacity)
    asm.AddPart(line)
    if cone is not None:
        asm.AddPart(cone)
    return asm


def _style_axes(axes, world=False, hairline=False):
    try:
        axes.SetShaftTypeToCylinder()
        try:
            axes.SetCylinderResolution(18)
            axes.SetConeResolution(24)
        except Exception:
            pass
        if hairline:
            axes.SetNormalizedShaftLength(0.80, 0.80, 0.80)
            axes.SetNormalizedTipLength(0.20, 0.20, 0.20)
            axes.SetCylinderRadius(0.04)
            axes.SetConeRadius(0.38)
        elif world:
            axes.SetNormalizedShaftLength(0.78, 0.78, 0.78)
            axes.SetNormalizedTipLength(0.22, 0.22, 0.22)
            axes.SetCylinderRadius(0.04)
            axes.SetConeRadius(0.40)
        else:
            # Corner orientation marker: VTK ConeRadius is relative to the
            # unit cone (default 0.4), then scaled by NormalizedTipLength.
            axes.SetNormalizedShaftLength(0.74, 0.74, 0.74)
            axes.SetNormalizedTipLength(0.26, 0.26, 0.26)
            axes.SetCylinderRadius(0.048)
            axes.SetConeRadius(0.45)
        for getter, rgb in (
            (axes.GetXAxisShaftProperty, (0.90, 0.20, 0.16)),
            (axes.GetYAxisShaftProperty, (0.18, 0.64, 0.28)),
            (axes.GetZAxisShaftProperty, (0.16, 0.38, 0.86)),
            (axes.GetXAxisTipProperty, (0.90, 0.20, 0.16)),
            (axes.GetYAxisTipProperty, (0.18, 0.64, 0.28)),
            (axes.GetZAxisTipProperty, (0.16, 0.38, 0.86)),
        ):
            try:
                p = getter()
                p.SetColor(*rgb)
                p.SetAmbient(0.35)
                p.SetDiffuse(0.65)
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
    colors = ((0.82, 0.16, 0.14), (0.14, 0.56, 0.24), (0.14, 0.34, 0.80))
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
            cap.SetWidth(0.14)
            cap.SetHeight(0.055)
        except Exception:
            pass
        try:
            ta = cap.GetTextActor()
            ta.SetTextScaleModeToNone()
        except Exception:
            pass
        try:
            tp = cap.GetCaptionTextProperty()
            tp.ShadowOn()
            tp.BoldOff()
            tp.ItalicOff()
            tp.SetFontFamilyToArial()
            tp.SetFontSize(16)
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


def _vertices_actor(vpts, color, size):
    """Points with vertex cells so each point is individually pickable."""
    pd = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_support.numpy_to_vtk(np.array(vpts, dtype=np.float64), deep=True))
    pd.SetPoints(vp)
    n = len(vpts)
    c = np.hstack([np.ones((n, 1), dtype=np.int64),
                   np.arange(n, dtype=np.int64)[:, None]]).reshape(-1)
    arr = vtk.vtkCellArray()
    arr.SetCells(n, numpy_support.numpy_to_vtkIdTypeArray(c, deep=True))
    pd.SetVerts(arr)
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(pd)
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetPointSize(size)
    a.GetProperty().SetAmbient(1.0)
    a.GetProperty().LightingOff()
    return a


def _polylines_actor(points, cells, color, width):
    """Lines from explicit polyline cells; cell k == cells[k] (pickable per edge)."""
    pd = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_support.numpy_to_vtk(np.array(points, dtype=np.float64), deep=True))
    pd.SetPoints(vp)
    flat = []
    for cell in cells:
        flat.extend(cell)
    arr = vtk.vtkCellArray()
    arr.SetCells(len(cells), numpy_support.numpy_to_vtkIdTypeArray(
        np.array(flat, dtype=np.int64), deep=True))
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

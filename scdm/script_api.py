"""H7: SpaceClaim-flavoured scripting API facade.

A thin pythonic subset of the SpaceClaim IronPython API over the project's
kernel/document so recorded/user scripts read naturally:

    from scdm.script_api import ScriptSession
    s = ScriptSession(kdoc)
    part = s.GetRootPart()
    body = s.DesignBody(K.make_box(0.01, 0.01, 0.01), "B1")
    s.SetParameter("width", 20.0)
    s.SetParameter("height", "width * 2")
    s.RebuildAll()
    bodies = part.GetBodies()

Selection-aware ops (Pull/Move/Combine) are exposed through the same
kitchen-knife style as the GUI handlers.
"""
from __future__ import annotations

from typing import List, Optional

from scdm import kernel as K
from scdm.params import ParamTable, eval_expr


class DesignBody:
    """Wrapper mirroring SpaceClaim's DesignBody (name + shape handle)."""

    def __init__(self, kbody):
        self._kb = kbody

    @property
    def Name(self) -> str:
        return self._kb.name

    @property
    def Shape(self):
        return self._kb.shape

    @property
    def Volume(self) -> float:
        return K.volume(self._kb.shape)

    def GetFaces(self) -> List:
        return K.explore(self._kb.shape, "face")

    def GetEdges(self) -> List:
        return K.explore(self._kb.shape, "edge")


class RootPart:
    """Mirrors SpaceClaim's root part (body container)."""

    def __init__(self, kdoc):
        self._doc = kdoc

    def GetBodies(self) -> List[DesignBody]:
        return [DesignBody(b) for b in self._doc.bodies]


class ScriptSession:
    """Facade over a KernelDoc + scale."""

    def __init__(self, kdoc, scale: float = 1000.0):
        self.kdoc = kdoc
        self.scale = scale
        if self.kdoc.param_table is None:
            self.kdoc.param_table = ParamTable()

    # -- structure ----------------------------------------------------
    def GetRootPart(self) -> RootPart:
        return RootPart(self.kdoc)

    def DesignBody(self, shape, name: str = "Body") -> DesignBody:
        b = self.kdoc.add_body(shape, name=name)
        return DesignBody(b)

    def GetBodyByName(self, name: str) -> Optional[DesignBody]:
        for b in self.kdoc.bodies:
            if b.name == name:
                return DesignBody(b)
        return None

    # -- parameters -----------------------------------------------------
    def SetParameter(self, name: str, expr) -> None:
        self.kdoc.param_table.set(name, expr)

    def GetParameter(self, name: str) -> float:
        return self.kdoc.param_table.get(name)

    def RebuildAll(self) -> None:
        """Re-run every parametric body against the current table."""
        for p in self.kdoc.parametrics:
            self.kdoc.rebuild_parametric(p, self.scale)

    # -- primitives -------------------------------------------------------
    def AddBox(self, w: float, h: float, d: float,
               origin=(0.0, 0.0, 0.0), name: str = "Box") -> DesignBody:
        s = self.scale
        return DesignBody(self.kdoc.add_body(
            K.make_box(w / s, h / s, d / s, origin=tuple(o / s for o in origin)),
            name=name))

    def AddCylinder(self, r: float, h: float,
                    origin=(0.0, 0.0, 0.0), name: str = "Cylinder") -> DesignBody:
        s = self.scale
        return DesignBody(self.kdoc.add_body(
            K.make_cylinder(r / s, h / s,
                            origin=tuple(o / s for o in origin)), name=name))

    def AddSphere(self, r: float, origin=(0.0, 0.0, 0.0),
                  name: str = "Sphere") -> DesignBody:
        s = self.scale
        return DesignBody(self.kdoc.add_body(
            K.make_sphere(r / s, origin=tuple(o / s for o in origin)),
            name=name))

    # -- modelling ------------------------------------------------------
    def CombineIntersect(self, a: DesignBody, b: DesignBody) -> DesignBody:
        a._kb.shape = K.common(a._kb.shape, b._kb.shape)
        self.kdoc.remove_body(b._kb.id) if hasattr(
            self.kdoc, "remove_body") else None
        return a

    def CombineSubtract(self, a: DesignBody, b: DesignBody) -> DesignBody:
        a._kb.shape = K.cut(a._kb.shape, b._kb.shape)
        return a

    def CombineUnite(self, a: DesignBody, b: DesignBody) -> DesignBody:
        a._kb.shape = K.fuse(a._kb.shape, b._kb.shape)
        return a

    def MoveBody(self, body: DesignBody, dx: float, dy: float, dz: float):
        s = self.scale
        body._kb.shape = K.translate(
            body._kb.shape, (dx / s, dy / s, dz / s))
        return body

    def FilletEdges(self, body: DesignBody, radius_mm: float,
                    edge_indices=None):
        s = self.scale
        edges = K.explore(body._kb.shape, "edge")
        use = [edges[i] for i in (edge_indices or range(len(edges)))]
        body._kb.shape = K.fillet_edges(body._kb.shape, radius_mm / s, use)
        return body

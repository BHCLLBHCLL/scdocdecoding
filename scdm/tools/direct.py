"""Concrete direct-modeling tools (SpaceClaim Edit group).

Each tool is a small state machine operating on a session's KernelDoc + a picked
context + option dict. They are GUI-agnostic (unit-testable) and mirror the
SpaceClaim 2019 Edit semantics:
  Pull -> extrude/offset a face       (BRepPrimAPI_MakePrism + boolean)
  Move -> transform a body (copy)     (BRepBuilderAPI_Transform)
  Fill -> remove a face and heal      (BRepAlgoAPI_Defeaturing)
  Combine -> fuse / cut / common      (BRepAlgoAPI_Fuse|Cut|Common)
  Split -> cut a body by a plane      (BRepAlgoAPI_Splitter)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scdm import kernel as K


class ToolError(RuntimeError):
    pass


class DirectTool:
    """Base for a direct-modeling tool."""

    id: str = ""
    name: str = ""
    hud: str = ""

    def apply(self, ses, ctx: Dict[str, Any], opts: Dict[str, Any]) -> str:
        raise NotImplementedError


def _scale(ses) -> float:
    return getattr(ses, "scale", 1000.0) or 1000.0


def _body(ses, body_id: Optional[str]):
    kdoc = ses.kdoc
    if body_id is not None:
        b = kdoc.body_by_id(body_id)
        if b:
            return b
    # fall back to first selected body or first body
    return kdoc.bodies[0] if kdoc.bodies else None


def _dist(opts: Dict[str, Any], default_mm: float, ses) -> float:
    d = opts.get("distance", default_mm)
    return float(d) / _scale(ses)


class SelectTool(DirectTool):
    id = "tool.select"
    name = "选择"
    hud = "单击选择对象；双击选环边；三击选实体"

    def apply(self, ses, ctx, opts):
        return self.hud


class PullTool(DirectTool):
    id = "tool.pull"
    name = "拉动"
    hud = "拉动：选择面后再次单击，沿法向挤出 5mm"

    def apply(self, ses, ctx, opts):
        body = _body(ses, ctx.get("body_id"))
        if body is None:
            raise ToolError("拉动需要内核实体")
        faces = K.explore(body.shape, "face")
        fi = ctx.get("face_i")
        if fi is None or fi >= len(faces):
            raise ToolError("请选择一个面")
        d = _dist(opts, 5.0, ses)
        if opts.get("symmetric"):
            body.shape = K.pull_face_symmetric(body.shape, faces[fi], d)
            verb = f"对称拉动 {d * _scale(ses):.0f}mm"
        else:
            body.shape = K.pull_face(body.shape, faces[fi], d)
            verb = f"拉动 {d * _scale(ses):.0f}mm"
        return verb


class MoveTool(DirectTool):
    id = "tool.move"
    name = "移动"
    hud = "移动：选择实体后单击，沿 X 平移 10mm；选项可复制"

    def apply(self, ses, ctx, opts):
        body = _body(ses, ctx.get("body_id"))
        if body is None:
            raise ToolError("移动需要内核实体")
        axis = opts.get("axis") or (1.0, 0.0, 0.0)
        d = _dist(opts, 10.0, ses)
        vec = (axis[0] * d, axis[1] * d, axis[2] * d)
        if opts.get("copy"):
            ses.kdoc.add_body(K.translate(body.shape, vec),
                              name=body.name + " 副本")
            svc = f"复制 + 移动 {d * _scale(ses):.0f}mm"
        else:
            body.shape = K.translate(body.shape, vec)
            svc = f"移动 {d * _scale(ses):.0f}mm"
        return svc


class FillTool(DirectTool):
    id = "tool.fill"
    name = "填充"
    hud = "填充：选择要移除并愈合的面后单击"

    def apply(self, ses, ctx, opts):
        body = _body(ses, ctx.get("body_id"))
        if body is None:
            raise ToolError("填充需要内核实体")
        faces = K.explore(body.shape, "face")
        fi = ctx.get("face_i")
        if fi is None or fi >= len(faces):
            raise ToolError("请选择一个要去除的面")
        body.shape = K.fill_faces(body.shape, [faces[fi]])
        return "已填充"


class CombineTool(DirectTool):
    id = "tool.combine"
    name = "合并"
    hud = "合并：先选目标体，再选刀具体"

    def apply(self, ses, ctx, opts):
        ids = [sid for sid in ctx.get("sel_ids", [])]
        kdoc = ses.kdoc
        if len(ids) < 2:
            ids = [b.id for b in kdoc.bodies[:2]]
        if len(ids) < 2:
            raise ToolError("合并需要两个实体")
        a = kdoc.body_by_id(ids[0])
        b = kdoc.body_by_id(ids[1])
        if a is None or b is None:
            raise ToolError("合并的实体不存在")
        mode = opts.get("mode", "fuse")
        if mode == "cut":
            a.shape = K.cut(a.shape, b.shape)
        elif mode == "common":
            a.shape = K.common(a.shape, b.shape)
        else:
            a.shape = K.fuse(a.shape, b.shape)
        kdoc.remove(b.id)
        return f"合并 ({mode})"


class SplitTool(DirectTool):
    id = "tool.split_body"
    name = "分割实体"
    hud = "分割：沿面或平面切体"

    def apply(self, ses, ctx, opts):
        body = _body(ses, ctx.get("body_id"))
        if body is None:
            raise ToolError("分割需要内核实体")
        c = K.cog(body.shape)
        if ctx.get("face_i") is not None:
            faces = K.explore(body.shape, "face")
            fi = ctx["face_i"]
            if fi < len(faces):
                _n, cc = K.face_normal_center(faces[fi])
                origin = cc
                normal = _n
            else:
                origin, normal = c, (1.0, 0.0, 0.0)
        else:
            origin, normal = c, (1.0, 0.0, 0.0)
        if opts.get("normal"):
            normal = opts["normal"]
        if opts.get("origin"):
            origin = opts["origin"]
        parts = K.split_by_plane(body.shape, origin, normal)
        kdoc = ses.kdoc
        kdoc.remove(body.id)
        for i, sh in enumerate(parts, 1):
            kdoc.add_body(sh, name=f"{body.name} 段{i}")
        return "已分割实体"


TOOLS: Dict[str, DirectTool] = {
    t.id: t for t in (
        SelectTool(), PullTool(), MoveTool(), FillTool(), CombineTool(), SplitTool(),
    )
}


def get_tool(tool_id: str) -> Optional[DirectTool]:
    return TOOLS.get(tool_id)

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


def _plane_offset(n1, c1, n2, c2) -> float:
    """Signed offset along n1 from plane(n1,c1) to the parallel plane(n2,c2)."""
    denom = n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]
    if abs(denom) < 1e-9:
        raise ToolError("两面不平行")
    return ((c2[0] - c1[0]) * n2[0] + (c2[1] - c1[1]) * n2[1]
            + (c2[2] - c1[2]) * n2[2]) / denom


class PullTool(DirectTool):
    id = "tool.pull"
    name = "拉动"
    hud = "拉动：选面后单击挤出；选项可设距离/对称/复制/到面"

    def apply(self, ses, ctx, opts):
        body = _body(ses, ctx.get("body_id"))
        if body is None:
            raise ToolError("拉动需要内核实体")
        faces = K.explore(body.shape, "face")
        fi = ctx.get("face_i")
        if fi is None or fi >= len(faces):
            raise ToolError("请选择一个面")
        d = _dist(opts, 5.0, ses)
        face = faces[fi]
        if opts.get("to_face") and ctx.get("to_face_target"):
            n1, c1 = K.face_normal_center(face)
            t = ctx["to_face_target"]
            d = _plane_offset(n1, c1, t["normal"], t["center"])
            if abs(d) < 1e-9:
                raise ToolError("到面：目标面与拉动面重合")
        if opts.get("copy"):
            if opts.get("symmetric"):
                pulled = K.pull_face_symmetric(body.shape, face, d)
            else:
                pulled = K.pull_face(body.shape, face, d)
            ses.kdoc.add_body(pulled, name=body.name + " 拉动副本")
            return f"复制拉动 {d * _scale(ses):.1f}mm"
        if opts.get("symmetric"):
            body.shape = K.pull_face_symmetric(body.shape, face, d)
            return f"对称拉动 {d * _scale(ses):.1f}mm"
        body.shape = K.pull_face(body.shape, face, d)
        return f"拉动 {d * _scale(ses):.1f}mm"


class MoveTool(DirectTool):
    id = "tool.move"
    name = "移动"
    hud = "移动：选实体后单击沿轴平移；选项可设距离/复制/到点/到面"

    def apply(self, ses, ctx, opts):
        body = _body(ses, ctx.get("body_id"))
        if body is None:
            raise ToolError("移动需要内核实体")
        d = _dist(opts, 10.0, ses)
        axis = opts.get("axis") or (1.0, 0.0, 0.0)
        if opts.get("to_point") and ctx.get("pick_point"):
            p = ctx["pick_point"]
            c = K.cog(body.shape)
            vec = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
            how = "到点"
        elif opts.get("to_face") and ctx.get("pick_face"):
            n2, c2 = ctx["pick_face"]["normal"], ctx["pick_face"]["center"]
            best, bd = None, None
            for f in K.explore(body.shape, "face"):
                n1, c1 = K.face_normal_center(f)
                if abs(n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]) < 0.999:
                    continue  # only parallel faces can land on the target plane
                dd = sum((c1[k] - c2[k]) ** 2 for k in range(3))
                if bd is None or dd < bd:
                    bd, best = dd, (n1, c1)
            if best is None:
                raise ToolError("到面：实体上没有与目标面平行的面")
            n1, c1 = best
            dist = _plane_offset(n1, c1, n2, c2)
            if abs(dist) < 1e-9:
                raise ToolError("到面：目标面与源面重合")
            vec = (n1[0] * dist, n1[1] * dist, n1[2] * dist)
            how = "到面"
        else:
            vec = (axis[0] * d, axis[1] * d, axis[2] * d)
            how = f"{d * _scale(ses):.1f}mm"
        if opts.get("copy"):
            ses.kdoc.add_body(K.translate(body.shape, vec),
                              name=body.name + " 副本")
            return f"复制 + 移动（{how}）"
        body.shape = K.translate(body.shape, vec)
        return f"移动（{how}）"


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

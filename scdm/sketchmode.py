"""R105: the sketch / solid mode boundary.

SpaceClaim keeps an explicit boundary between sketching and solid modelling: a
dedicated *Edit Sketch* ribbon tab appears, entering and leaving is one click (or
Esc), and Pull turns the sketch into a body and leaves the mode.  This module owns
the policy half of that boundary so it can be tested without Qt:

* @plan(cmd_id, mode)@ - what happens to a command issued *inside* sketch mode:
  run it, leave sketch mode first, or refuse with a reason;
* @SketchSession@ - the active sketch, the plane it was created on, and whether
  that plane can still be trusted (a sketch on a face whose body was modified is
  *stale*, and drawing on the wrong plane is worse than refusing);
* @extrude_active()@ - the bridge: the active sketch becomes a body, with the
  same circle fallback the GUI used to carry inline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from scdm import kernel as K

MODE_SOLID = "solid"
MODE_SKETCH = "sketch"

#: commands that live on the sketch side of the boundary
SKETCH_COMMANDS = frozenset({
    "mode.sketch", "mode.3d", "mode.section", "create.project",
})
SKETCH_PREFIXES = ("sketch.", "con.")

#: mode-neutral commands (navigation, display, selection, files, measurement)
NEUTRAL_PREFIXES = ("view.", "show.", "style.", "gfx.", "edit.", "file.",
                    "measure.", "mode.", "tools.", "wb.", "markup.")

#: the bridge: Pull extrudes the active sketch, and *that* ends the mode
BRIDGE_COMMANDS = frozenset({"tool.pull"})


@dataclass(frozen=True)
class Plan:
    """What to do with a command issued in the current mode."""
    kind: str          # run | exit_then_run | refuse
    reason: str = ""

    @property
    def exits(self) -> bool:
        return self.kind == "exit_then_run"


def is_sketch_command(cmd_id: str) -> bool:
    return bool(cmd_id) and (cmd_id in SKETCH_COMMANDS
                             or cmd_id.startswith(SKETCH_PREFIXES))


def is_neutral(cmd_id: str) -> bool:
    return bool(cmd_id) and cmd_id.startswith(NEUTRAL_PREFIXES)


def plan(cmd_id: str, mode: str) -> Plan:
    """The boundary in one place (R105).

    In sketch mode a solid command is not refused - it *leaves* the mode and then
    runs, which is what makes the switch smooth: one click, no dead state.  The
    reason string is what the status bar shows.
    """
    if mode != MODE_SKETCH or not cmd_id:
        return Plan("run")
    if (is_sketch_command(cmd_id) or is_neutral(cmd_id)
            or cmd_id in BRIDGE_COMMANDS):
        return Plan("run")
    return Plan("exit_then_run", "已退出草图模式：%s" % cmd_id)


def find_sketch(kdoc, sketch_id: str):
    for sk in getattr(kdoc, "sketches", []) or []:
        if sk.id == sketch_id:
            return sk
    return None


def resolve_active(kdoc, session: Optional["SketchSession"] = None):
    """The sketch an operation should use: (sketch, reason)."""
    if session is not None:
        sk = find_sketch(kdoc, session.sketch_id)
        if sk is not None:
            return sk, ""
    sks = list(getattr(kdoc, "sketches", []) or [])
    if not sks:
        return None, "没有草图：先用草图工具画一个轮廓"
    if len(sks) == 1:
        return sks[0], ""
    return None, "有 %d 个草图：请先在结构树里双击要编辑的草图" % len(sks)


@dataclass
class SketchSession:
    """The active sketch plus the plane source it was created from."""
    sketch_id: str
    plane: str = "xy"
    axes: Optional[tuple] = None
    source: str = "datum"          # datum | face | custom | section
    source_body: Optional[str] = None
    source_normal: Optional[Tuple[float, float, float]] = None
    source_point: Optional[Tuple[float, float, float]] = None

    def label(self) -> str:
        return {"xy": "XY", "zx": "ZX", "yz": "YZ"}.get(self.plane, "自定义平面")

    def stale(self, kdoc, tol: float = 1e-6) -> Optional[str]:
        """Why the sketch plane can no longer be trusted (None = fine).

        Only face-anchored sketches can go stale: the datum planes never move.
        The check is geometric (a face with the same normal lying in the same
        plane), not index based, so a rebuild that renumbers faces is fine.
        """
        if find_sketch(kdoc, self.sketch_id) is None:
            return "草图已不存在（被删除或工程被重载）"
        if self.source != "face":
            return None
        body = kdoc.body_by_id(self.source_body) if self.source_body else None
        if body is None:
            return "草图所依附的实体已不存在"
        if self.source_point is None or self.source_normal is None:
            return None
        n, o = self.source_normal, self.source_point
        for f in K.explore(body.shape, "face"):
            try:
                fn, fc = K.face_normal_center(f)
            except Exception:
                continue
            if abs(abs(sum(fn[i] * n[i] for i in range(3))) - 1.0) > 1e-6:
                continue
            if abs(sum((fc[i] - o[i]) * n[i] for i in range(3))) <= tol:
                return None
        return "草图所在平面已改变（原面被移动或删除）"


def extrude_active(kdoc, height_mm: float, scale: float = 1000.0,
                   session: Optional[SketchSession] = None,
                   name: str = "拉伸") -> Dict[str, Any]:
    """Turn the active sketch into bodies (the Pull bridge, R105).

    Returns {"ok", "reason", "bodies", "sketch", "volume", "height_mm"}.  The
    caller leaves sketch mode when ok is True - the geometry work and the mode
    change stay separate so both halves are testable.
    """
    from scdm import sketch as S
    out: Dict[str, Any] = {"ok": False, "reason": "", "bodies": [],
                           "sketch": None, "volume": 0.0,
                           "height_mm": float(height_mm)}
    sk, why = resolve_active(kdoc, session)
    if sk is None:
        out["reason"] = why
        return out
    if session is not None and session.sketch_id == sk.id:
        stale = session.stale(kdoc)
        if stale:
            out["reason"] = stale
            return out
    if not sk.curves:
        out["reason"] = "草图没有曲线"
        return out
    h = float(height_mm) / float(scale)
    if h <= 0:
        out["reason"] = "拉伸高度必须大于 0"
        return out
    axes = S.sketch_axes(sk.plane, sk.origin, sk.normal, sk.xdir)
    made = []
    try:
        solid = S.extrude_sketch(sk.curves, h, axes=axes)
        made.append(kdoc.add_body(solid, name=name))
    except Exception as exc:
        # circles -> cylinders along the sketch normal (the old inline fallback)
        for c in sk.curves:
            if c[0] == "circle":
                center, r = c[1], c[2]
                origin = S.axes_to_world(axes, center[0], center[1])
                made.append(kdoc.add_body(
                    K.make_cylinder(r, h, origin=origin, axis=axes[3]),
                    name=name + "圆"))
        if not made:
            out["reason"] = "草图无闭环：%s" % exc
            return out
    out.update(ok=True, bodies=made, sketch=sk,
               volume=sum(K.volume(b.shape) for b in made))
    return out

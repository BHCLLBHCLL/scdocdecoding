"""R105: the sketch / solid mode boundary.

SpaceClaim keeps an explicit boundary between sketching and solid modelling: a
dedicated *Edit Sketch* ribbon tab appears, entering and leaving is one click (or
Esc), and Pull turns the sketch into a body and leaves the mode.  This module owns
the policy half of that boundary so it can be tested without Qt:

* @plan(cmd_id, mode)@ - what happens to a command issued *inside* sketch mode:
  run it, leave sketch mode first, or refuse with a reason;
* `SketchSession` - the active sketch, the plane it was created on, and whether
  that plane can still be trusted (a sketch on a face whose body was modified is
  *stale*, and drawing on the wrong plane is worse than refusing);
* @extrude_active()@ - the bridge: the active sketch becomes a body, with the
  same circle fallback the GUI used to carry inline.
"""
from __future__ import annotations

import math
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


def loop_curves(loop: tuple) -> list:
    """The canonical curve list of one loop (R107/A-1).

    A feature stores only *its* loop, so a multi-loop sketch produces one
    self-contained body per loop, each replayable on its own.
    """
    if loop and loop[0] == "circle":
        return [("circle", tuple(loop[1]), float(loop[2]))]
    return [("poly", [list(p) for p in (loop[1] if loop else [])])]

#: constraint kinds this module can *drive* (R107/A-3).
#: A circle's size is driven through its centre -> radius-handle distance, which
#: is exactly what the sketch Dimension command creates, so `dist` covers it;
#: `radius` would need the solver's circles mapping and is not offered yet.
DIM_KINDS = ("dist",)


def dimensions(kdoc, sketch_id: str, scale: float = 1000.0) -> List[dict]:
    """The drivable dimensions of a sketch, values in millimetres (R107/A-3)."""
    sk = find_sketch(kdoc, sketch_id)
    if sk is None:
        return []
    out = []
    for i, c in enumerate(getattr(sk, "constraints", []) or []):
        if not c or len(c) < 4 or c[0] not in DIM_KINDS:
            continue
        try:
            v = float(c[3])
        except (TypeError, ValueError):
            continue
        out.append({"index": i, "kind": c[0], "value_mm": v * scale,
                    "label": "距离 %gmm" % (v * scale)})
    return out


def set_dimension(kdoc, sketch_id: str, index: int, value_mm: float,
                  scale: float = 1000.0) -> Dict[str, Any]:
    """Drive one sketch dimension: re-solve and write the points back (A-3).

    Uses the Levenberg-Marquardt solver (not the legacy relaxation) because a
    *driven* dimension has to land on its target tightly - the acceptance is a
    closed-form volume.  Atomic: a solve that misses the target restores both the
    constraint and the curves, so a failed drive never leaves a half-solved
    sketch behind.
    """
    from scdm import sketch as S
    from scdm.sketch_solver import solve_report
    rep: Dict[str, Any] = {"ok": False, "reason": "", "index": index,
                           "old_mm": None, "value_mm": float(value_mm),
                           "label": "", "dof": None, "residual": None}
    sk = find_sketch(kdoc, sketch_id)
    if sk is None:
        rep["reason"] = "草图不存在：%s" % sketch_id
        return rep
    cons = list(getattr(sk, "constraints", []) or [])
    if not (0 <= index < len(cons)):
        rep["reason"] = "标注序号越界：%s" % index
        return rep
    c = list(cons[index])
    if len(c) < 4 or c[0] not in DIM_KINDS:
        rep["reason"] = "该约束不是可驱动尺寸：%s" % (c[0] if c else "?")
        return rep
    try:
        target = float(value_mm) / float(scale or 1.0)
    except (TypeError, ValueError):
        rep["reason"] = "尺寸值不是数字：%r" % (value_mm,)
        return rep
    if target <= 0:
        rep["reason"] = "尺寸必须大于 0"
        return rep
    rep["old_mm"] = float(c[3]) * scale
    rep["label"] = "距离 %gmm" % float(value_mm)
    saved_curves = list(sk.curves)
    saved_cons = list(sk.constraints)
    c[3] = target
    sk.constraints[index] = tuple(c)
    try:
        pts, segs = S.read_points(sk)
        report = solve_report(pts, sk.constraints, segments=segs, max_iter=200)
        rep["dof"] = int(getattr(report, "dof", -1))
        rep["residual"] = float(getattr(report, "max_residual", -1.0))
        # verify the driven dimension itself, not just the solver's own residual
        i, j = int(c[1]), int(c[2])
        if i >= len(pts) or j >= len(pts):
            raise ValueError("尺寸引用的点不存在")
        got = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
        if abs(got - target) > 1e-6 * target + 1e-9:
            raise ValueError("求解未落到目标尺寸（%.6g vs %.6g m）"
                             % (got, target))
        if not getattr(report, "converged", True):
            raise ValueError("求解未收敛：%s" % getattr(report, "message", ""))
        S.write_points(sk, pts)
    except Exception as exc:
        sk.curves = saved_curves
        sk.constraints = saved_cons
        rep["reason"] = str(exc)
        return rep
    rep["ok"] = True
    return rep


def sketch_params(sk, height_mm: float, loop=None, curves=None) -> Dict[str, Any]:
    """The feature payload of a sketch body (R106/B-1, R107/A-1).

    The curves travel with the feature (a reloaded project replays the same body
    without needing the sketch list), `sketch_id` keeps the *live* link so an
    edited sketch can rebuild its bodies, and `loop` is the live-link index of
    the loop this body came from (a body stores only its own loop).
    """
    out = {
        "sketch_id": sk.id,
        "plane": sk.plane,
        "origin": list(sk.origin),
        "normal": list(sk.normal),
        "xdir": list(sk.xdir),
        "curves": [list(c) for c in (sk.curves if curves is None else curves)],
        "height": float(height_mm),
    }
    if loop is not None:
        out["loop"] = int(loop)
    return out


def sync_sketch_bodies(kdoc, sketch_id: Optional[str] = None,
                       scale: float = 1000.0) -> Dict[str, Any]:
    """Re-derive every sketch body from its (possibly edited) sketch.

    This is what makes the sketch a real feature: editing the outline and calling
    this rebuilds the solids, instead of leaving them as orphans of the old
    curves.  Returns {"ok", "reason", "updated", "failed"}.
    """
    out: Dict[str, Any] = {"ok": True, "reason": "", "updated": [], "failed": []}
    for bid, stack in list(getattr(kdoc, "features", {}).items()):
        for f in list(stack.features):
            if f.op != "sketch":
                continue
            sid = f.params.get("sketch_id")
            if sketch_id is not None and sid != sketch_id:
                continue
            sk = find_sketch(kdoc, sid or "")
            if sk is None:
                out["failed"].append((bid, "草图已不存在：%s" % sid))
                continue
            # R107/A-1: a feature owns one loop; the live link follows its index
            idx = f.params.get("loop")
            curves = None
            if idx is not None:
                from scdm import sketch as S
                loops = S.sketch_loops(sk.curves)
                if not (0 <= int(idx) < len(loops)):
                    out["failed"].append(
                        (bid, "草图第 %d 个闭环已不存在" % (int(idx) + 1)))
                    continue
                curves = loop_curves(loops[int(idx)])
            # the new definition is committed only if the replay succeeds -
            # otherwise the feature would describe a body that is not there
            old_params = dict(f.params)
            f.params.update(sketch_params(sk, f.params.get("height", 10.0),
                                          loop=idx, curves=curves))
            ok, why = kdoc.replay_body(bid, scale)
            if ok:
                out["updated"].append(bid)
            else:
                f.params.clear()
                f.params.update(old_params)
                out["failed"].append((bid, why))
    if out["failed"]:
        out["ok"] = False
        out["reason"] = "；".join("%s：%s" % (b, r) for b, r in out["failed"])
    return out


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
    recorded = False
    try:
        # R107/A-1 + A-2: every closed loop becomes its own body (a circle a real
        # cylinder), and each body's feature carries exactly its own loop
        loops = S.sketch_loops(sk.curves)
        if not loops:
            raise ValueError("草图没有闭环（画矩形、圆或闭合线段）")
        for i, loop in enumerate(loops):
            curves = loop_curves(loop)
            solid = S.extrude_loops(curves, h, axes=axes)[0]
            body = kdoc.add_body(
                solid, name=name if len(loops) == 1 else "%s%d" % (name, i + 1))
            # R106/B-1: the sketch becomes the body's feature, so an edited
            # sketch (sync_sketch_bodies) or height (edit_feature) rebuilds it
            kdoc.record_feature(body.id, "sketch",
                                **sketch_params(sk, height_mm, loop=i,
                                                curves=curves))
            made.append(body)
        recorded = True
    except Exception as exc:
        if not made:
            out["reason"] = "草图无闭环：%s" % exc
            return out
    out.update(ok=True, bodies=made, sketch=sk, feature=recorded,
               volume=sum(K.volume(b.shape) for b in made))
    return out

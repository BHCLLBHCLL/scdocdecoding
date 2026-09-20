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
    # R110/A-5: the document remembers the sketch that was being edited
    active = getattr(kdoc, "active_sketch", None)
    if active:
        sk = find_sketch(kdoc, active)
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

#: constraint kinds this module can *drive* (R110/A-1 adds the radius)
DIM_KINDS = ("dist", "radius")

#: human labels per dimension kind
DIM_LABELS = {"dist": "距离", "radius": "半径"}


#: how far apart two sketch endpoints may be and still be welded (R112/A-2).
#: The library default is the historic 0.1 mm; the viewport writes its snap
#: radius here, so snapping and welding are one number (rule 84).
DEFAULT_WELD_TOL_MM = 0.1


def weld_tolerance_mm(kdoc) -> float:
    """The document's weld/snap tolerance in millimetres (R112/A-2)."""
    try:
        v = float(getattr(kdoc, "weld_tol_mm", DEFAULT_WELD_TOL_MM))
    except (TypeError, ValueError):
        return DEFAULT_WELD_TOL_MM
    return v if v > 0.0 else DEFAULT_WELD_TOL_MM


def set_weld_tolerance_mm(kdoc, mm) -> float:
    """Set the document's weld/snap tolerance; returns the value in force."""
    try:
        v = float(mm)
    except (TypeError, ValueError):
        return weld_tolerance_mm(kdoc)
    if v > 0.0:
        kdoc.weld_tol_mm = v
    return weld_tolerance_mm(kdoc)


def _param_namespace(kdoc) -> Dict[str, float]:
    """The document's parameter values, or {} when there is no table."""
    table = getattr(kdoc, "param_table", None)
    if table is None:
        return {}
    try:
        return table.resolve()
    except Exception:
        return {}


def _dim_value_index(c) -> int:
    """Where the driven value sits: (dist, i, j, v) vs (radius, centre, v)."""
    return 2 if (c and c[0] == "radius") else 3


def _expr_reason(cons, raw, exc, extra_names=(), kdoc=None, sk=None) -> str:
    """Why an expression failed, naming the indices that *can* be referenced.

    R111/A-1: ``dimN`` binds to the **constraint index**, and only a ``dist`` or
    ``radius`` row carries a value.  A user who names a geometric row (or a
    stale index) needs that mapping - "unknown parameter" alone is not fixable.
    R113/A-5 adds ``<sketch>_dimN`` for the other sketches, passed in as
    *extra_names* so the list is complete.
    """
    import re
    # R114/A-5: a cross-sketch name is diagnosed before anything else - "unknown
    # parameter S2_dim5" does not tell the user that S2 was deleted
    missing, bad_dim = [], []
    for sid, i in _dim_token_refs(raw):
        if not sid:
            continue
        target = None
        for o in getattr(kdoc, "sketches", []) or []:
            if str(getattr(o, "id", "")) == sid:
                target = o
                break
        if target is None:
            missing.append(sid)
            continue
        ocons = list(getattr(target, "constraints", []) or [])
        if not (0 <= i < len(ocons)) or not ocons[i] or ocons[i][0] not in DIM_KINDS:
            bad_dim.append((sid, i))
    named = sorted({int(m.group(1)) for m in re.finditer(r"\bdim(\d+)\b", str(raw))})
    available = [i for i, c in enumerate(cons) if c and c[0] in DIM_KINDS]
    outside = [n for n in named if not (0 <= n < len(cons))]
    not_dim = [n for n in named
               if 0 <= n < len(cons) and (cons[n] or [""])[0] not in DIM_KINDS]
    head = str(exc)
    if missing:
        # the referenced sketch is gone: name it, and still list what *can* be
        # referenced (R113 discipline: a refusal has to be actionable)
        head = "被引用草图 %s 已不存在" % "、".join(sorted(set(missing)))
    elif bad_dim:
        head = "被引用草图 %s" % "、".join(
            "%s 没有尺寸 #%d" % (sid, i) for sid, i in bad_dim)
    elif not_dim:
        head = "%s 不是尺寸（约束 #%s 是 %s）" % (
            "、".join("dim%d" % n for n in not_dim),
            "、#".join(str(n) for n in not_dim),
            "、".join(str((cons[n] or ["?"])[0]) for n in not_dim))
    elif outside:
        head = "尺寸序号越界：%s（本草图共 %d 条约束）" % (
            "、".join("dim%d" % n for n in outside), len(cons))
    names = ["dim%d" % i for i in available]
    names += ["%s_dim%d" % (s, i) for (s, i) in extra_names]
    tail = "；可引用的尺寸：%s" % ("、".join(names) if names else "无")
    return head + tail


def _dim_token_refs(raw):
    """[(sketch_id | None, constraint index)] named by an expression (R113/A-5).

    ``dim3`` is the current sketch; ``S2_dim3`` is sketch ``S2``.  The underscore
    form keeps every reference a single identifier, so the parameter evaluator
    (and its tests) stay untouched.
    """
    import re
    out = []
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(raw)):
        m = re.match(r"^dim(\d+)$", tok)
        if m:
            out.append((None, int(m.group(1))))
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9]*)_dim(\d+)$", tok)
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


def _foreign_dim_names(kdoc, sk):
    """(sketch_id, index) of the *other* sketches' dimensions (R113/A-5)."""
    out = []
    for other in getattr(kdoc, "sketches", []) or []:
        if other is sk:
            continue
        sid = str(getattr(other, "id", ""))
        for i, c in enumerate(getattr(other, "constraints", []) or []):
            if c and c[0] in DIM_KINDS:
                out.append((sid, i))
    return out


def _dim_value_mm(kdoc, sk, index: int, scale: float, seen=None, entry=None):
    """(value_mm, reason) of one dimension, resolving dimension references.

    R111/A-1: an expression may name another dimension as ``dimN`` (N = the
    constraint index of a ``dist``/``radius`` row of this sketch).
    R113/A-5: ``<sketch_id>_dimN`` names one in another sketch (``S2_dim3``).
    Chains are resolved recursively and a cycle is refused with the indices,
    instead of quietly evaluating to something.
    """
    import re
    from scdm.params import eval_expr
    cons = list(getattr(sk, "constraints", []) or [])
    if not (0 <= index < len(cons)):
        return None, "尺寸序号越界：%s" % index
    c = cons[index]
    if not c or c[0] not in DIM_KINDS:
        return None, "dim%s 不是尺寸" % index
    vi = _dim_value_index(c)
    if len(c) <= vi:
        return None, "dim%s 缺少数值" % index
    raw = c[vi]
    if not isinstance(raw, str):
        try:
            return float(raw) * float(scale or 1000.0), ""
        except (TypeError, ValueError):
            return None, "dim%s 数值非法" % index
    seen = set(seen or ())
    here = (str(getattr(sk, "id", "")), int(index))
    mine = here[0]
    entry = str(entry or mine)          # the sketch the user actually edited

    def label(sid, idx):                # the entry sketch keeps the R111 "#5"
        return "#%d" % idx if sid in (None, entry) else "%s#%d" % (sid, idx)

    if here in seen:
        return None, "尺寸引用存在循环（%s）" % label(*here)
    guard = seen | {here}               # a self reference is a cycle too
    for sid, other in _dim_token_refs(raw):
        target = mine if sid is None else sid
        if (target, other) in guard:
            return None, "尺寸引用存在循环（%s → %s）" % (label(*here),
                                                       label(target, other))
    seen.add(here)
    ns = dict(_param_namespace(kdoc))
    bad: Dict[Any, str] = {}
    ns.update(_dim_refs(kdoc, sk, scale, seen, bad, entry=entry))
    try:
        return float(eval_expr(raw, ns)), ""
    except Exception as exc:
        # a name missing *because of* a cycle in the chain is a cycle, not a typo
        for _k, why in sorted(bad.items(), key=lambda kv: str(kv[0])):
            if "循环" in str(why):
                return None, why
        return None, _expr_reason(cons, raw, exc, _foreign_dim_names(kdoc, sk),
                                  kdoc=kdoc, sk=sk)


def _dim_refs(kdoc, sk, scale: float, seen, bad=None, entry=None,
              want_sketches=()) -> Dict[str, float]:
    """{"dimN" / "<sketch>_dimN": value_mm} for the dimensions (R111 + R113).

    ``dimN`` addresses the *current* sketch (R111/A-1); every sketch is also
    published as ``<sketch_id>_dimN`` so a dimension in one sketch can drive one
    in another (R113/A-5).  A dimension that cannot be resolved is left out of
    the namespace; when *bad* is given its reason is recorded under the
    ``(sketch_id, index)`` key, so a caller can tell a cycle from a plain typo.
    """
    out: Dict[str, float] = {}
    # only the sketches this one actually names are pulled in, so the namespace
    # stays cheap on a document with many sketches (R113/A-5)
    wanted = {str(s) for s in (want_sketches or ())}
    for c in getattr(sk, "constraints", []) or []:
        if not c or c[0] not in DIM_KINDS:
            continue
        vi = _dim_value_index(c)
        if len(c) > vi and isinstance(c[vi], str):
            for sid, _i in _dim_token_refs(c[vi]):
                if sid:
                    wanted.add(sid)
    sks = [sk] + [o for o in (getattr(kdoc, "sketches", []) or [])
                  if o is not sk and str(getattr(o, "id", "")) in wanted]
    for cur in sks:
        cid = str(getattr(cur, "id", ""))
        for i, c in enumerate(getattr(cur, "constraints", []) or []):
            if not c or c[0] not in DIM_KINDS or (cid, i) in seen:
                continue
            mm, why = _dim_value_mm(kdoc, cur, i, scale, seen=seen,
                                    entry=entry)
            if mm is None:
                if bad is not None:
                    bad[(cid, i)] = why
                continue
            if cur is sk:
                out["dim%d" % i] = mm
            out["%s_dim%d" % (cid, i)] = mm
    return out


def _namespace_for(kdoc, sk, scale: float, raw=None) -> Dict[str, float]:
    """Parameter table + ``dimN`` values in mm (R111/A-1, R113/A-5).

    *raw* is the expression about to be resolved, if any: a sketch it names is
    published even when no stored constraint mentions it yet (the first drive of
    a cross-sketch reference has nothing stored to scan).
    """
    ns = dict(_param_namespace(kdoc))
    named = {sid for sid, _i in _dim_token_refs(raw) if sid} if raw else ()
    ns.update(_dim_refs(kdoc, sk, scale, set(), want_sketches=named))
    return ns


def _resolve_value_mm(kdoc, raw, scale: float, sk=None):
    """(target_metres, expression_or_None, reason) for a dimension value.

    A number is millimetres (what the UI and the scripts pass); an expression
    (R110/A-2, e.g. "2*d") is evaluated against the parameter table and the
    sketch's own dimensions (``dimN``, R111/A-1), both in millimetres.
    """
    from scdm.params import eval_expr
    if isinstance(raw, str):
        ns = (_namespace_for(kdoc, sk, scale, raw) if sk is not None
              else _param_namespace(kdoc))
        try:
            mm = float(eval_expr(raw, ns))
        except Exception as exc:
            cons = list(getattr(sk, "constraints", []) or []) if sk is not None else []
            extra = _foreign_dim_names(kdoc, sk) if sk is not None else []
            why = _expr_reason(cons, raw, exc, extra, kdoc=kdoc, sk=sk)
            return None, raw, "表达式无法求值：%s（%s）" % (why, raw)
        return mm / float(scale or 1000.0), raw, ""
    try:
        mm = float(raw)
    except (TypeError, ValueError):
        return None, None, "尺寸值不是数字或表达式：%r" % (raw,)
    return mm / float(scale or 1000.0), None, ""


def _solver_rows(sk, ns, scale: float, report=None) -> list:
    """Constraint rows with expression values resolved to metres (R110/A-2).

    The stored rows keep the expression as written (readable, re-resolvable);
    the solver needs numbers, and its unit is metres.  A row whose expression
    cannot be resolved is **left out** and recorded in `report["skipped"]`
    (R115): a dangling reference constrains nothing, and dropping the row must
    not take the whole DOF report with it.
    """
    from scdm.params import eval_expr
    out = []
    for x in getattr(sk, "constraints", []) or []:
        if x and x[0] in DIM_KINDS:
            vi = _dim_value_index(x)
            if len(x) > vi and isinstance(x[vi], str):
                try:
                    v = float(eval_expr(x[vi], ns)) / float(scale or 1000.0)
                except Exception:
                    if report is not None:
                        report.setdefault("skipped", []).append(str(x[vi]))
                    continue
                y = list(x)
                y[vi] = v
                out.append(tuple(y))
                continue
        out.append(x)
    return out


def dof_report(kdoc, sketch_id: str, scale: float = 1000.0) -> Dict[str, Any]:
    """Solve a *copy* of the sketch and report its degrees of freedom (R111/A-6).

    Read-only on purpose: the points are copied, so asking for the report never
    perturbs the sketch (rule 85 - a measurement must not change the workload).
    """
    from scdm import sketch as S
    from scdm.sketch_solver import solve_report
    out: Dict[str, Any] = {"ok": False, "reason": "", "dof": None,
                           "redundant": None, "conflicting": None,
                           "converged": None, "residual": None,
                           "conflict_cons": (), "redundant_cons": (),
                           "skipped": []}
    sk = find_sketch(kdoc, sketch_id)
    if sk is None:
        out["reason"] = "草图不存在：%s" % sketch_id
        return out
    pts, segs = S.read_points(sk)
    pts = [list(p) for p in pts]              # never write back
    has_radius = any(x and x[0] == "radius" for x in sk.constraints)
    circles = S.read_circles(sk) if has_radius else None
    try:
        skipped: Dict[str, Any] = {}
        rows = _solver_rows(sk, _namespace_for(kdoc, sk, scale), scale,
                            skipped)
        rep = solve_report(pts, rows, segments=segs, circles=circles,
                           max_iter=200)
    except Exception as exc:
        out["reason"] = "求解失败：%s" % exc
        return out
    out.update(ok=True, dof=int(getattr(rep, "dof", -1)),
               redundant=int(getattr(rep, "redundant", -1)),
               conflicting=bool(getattr(rep, "conflicting", False)),
               converged=bool(getattr(rep, "converged", True)),
               residual=float(getattr(rep, "max_residual", -1.0)),
               # R112/A-6: not just "how many" - *which* constraints
               conflict_cons=tuple(getattr(rep, "violated_cons", ()) or ()),
               redundant_cons=tuple(getattr(rep, "redundant_cons", ()) or ()),
               skipped=list(skipped.get("skipped", [])))
    return out


def dimension_marks(kdoc, sketch_id: str, scale: float = 1000.0,
                    solve: bool = True) -> Dict[str, Any]:
    """{index: "冲突" | "冗余"} for the tree (R112/A-6), one solve.

    A conflicting row wins over a redundant one: if it is both violated and
    repeated, "conflict" is what the user has to fix first.
    """
    # R115/A-2: the tree marks *every* sketch's unusable rows, but only the active
    # one is worth an LM solve - the rest get the dangling-row pass alone
    rep = (dof_report(kdoc, sketch_id, scale) if solve
           else {"ok": True, "redundant_cons": (), "conflict_cons": ()})
    marks: Dict[int, str] = {}
    for i in rep.get("redundant_cons", ()) or ():
        marks[int(i)] = "冗余"
    for i in rep.get("conflict_cons", ()) or ():
        marks[int(i)] = "冲突"
    # R114/A-5: a dimension whose expression cannot be resolved (a dangling
    # cross-sketch reference, a typo) is unusable - say so on its row
    for row in dimensions(kdoc, sketch_id, scale):
        if row.get("reason") and int(row["index"]) not in marks:
            marks[int(row["index"])] = "悬空"
    rep["marks"] = marks
    return rep


def conflict_geometry(kdoc, sketch_id: str, scale: float = 1000.0) -> Dict[str, Any]:
    """The UV geometry of the rows the solver could not satisfy (R115/A-1).

    Returns `{"ok", "reason", "cons", "points", "segments", "solve"}` where the
    points and segments are in sketch coordinates, ready for a viewport overlay.
    Kept free of Qt on purpose: the mapping is exactly what a test can check when
    there is no 3D scene (headless runs have none).
    """
    from scdm import sketch as S
    out: Dict[str, Any] = {"ok": False, "reason": "", "cons": [], "points": [],
                           "segments": [], "solve": None}
    sk = find_sketch(kdoc, sketch_id)
    if sk is None:
        out["reason"] = "草图不存在：%s" % sketch_id
        return out
    info = dof_report(kdoc, sketch_id, scale)
    out["solve"] = info
    if not info["ok"]:
        out["reason"] = info["reason"]
        return out
    cons = list(getattr(sk, "constraints", []) or [])
    pts, segs = S.read_points(sk)
    seg_of = {}
    for (i, j) in segs:
        seg_of.setdefault((min(i, j), max(i, j)), (i, j))
    mark_pts: Dict[int, None] = {}
    mark_segs: Dict[Tuple[int, int], None] = {}

    def want_point(i):
        if isinstance(i, int) and 0 <= i < len(pts):
            mark_pts[i] = None

    def want_seg(i, j):
        want_point(i)
        want_point(j)
        key = (min(i, j), max(i, j))
        if key in seg_of:
            mark_segs[key] = None

    marked: Dict[int, None] = {}
    for ci in list(info.get("conflict_cons", ()) or ()) + \
            list(info.get("redundant_cons", ()) or ()):
        if not (0 <= ci < len(cons)) or ci in marked:
            continue
        marked[ci] = None
        c = cons[ci]
        if not c:
            continue
        kind = c[0]
        if kind in ("dist", "h", "v", "coin", "point_on") and len(c) >= 3:
            want_seg(int(c[1]), int(c[2]))
        elif kind == "fixed" and len(c) >= 2:
            want_point(int(c[1]))
        elif kind == "radius" and len(c) >= 2:
            want_point(int(c[1]))
        elif kind in ("equal", "par", "perp") and len(c) >= 3:
            for s in (int(c[1]), int(c[2])):
                if 0 <= s < len(segs):
                    want_seg(int(segs[s][0]), int(segs[s][1]))
        elif kind == "tangent" and len(c) >= 3:
            s = int(c[1])
            if 0 <= s < len(segs):
                want_seg(int(segs[s][0]), int(segs[s][1]))
            want_point(int(c[2]))
        elif kind == "mid" and len(c) >= 3:
            want_point(int(c[1]))
            s = int(c[2])
            if 0 <= s < len(segs):
                want_seg(int(segs[s][0]), int(segs[s][1]))
        out["cons"].append(int(ci))
    out["points"] = [[float(pts[i][0]), float(pts[i][1])] for i in sorted(mark_pts)]
    out["segments"] = [[[float(pts[a][0]), float(pts[a][1])],
                        [float(pts[b][0]), float(pts[b][1])]]
                       for (a, b) in sorted(mark_segs)]
    out["ok"] = True
    return out


def reference_warnings(kdoc, scale: float = 1000.0) -> List[dict]:
    """Dimensions whose expression cannot be resolved (R115/A-2).

    What an open-time health check reports: a dangling cross-sketch reference, a
    typo, a deleted sketch.  One entry per row, with the sketch id and index so
    the message can point at exactly the row to fix.
    """
    out: List[dict] = []
    for sk in getattr(kdoc, "sketches", []) or []:
        sid = str(getattr(sk, "id", ""))
        for row in dimensions(kdoc, sid, scale):
            if row.get("reason"):
                out.append({"sketch": sid, "index": int(row["index"]),
                            "expr": row.get("expr"), "reason": row["reason"]})
    return out


def dimensions(kdoc, sketch_id: str, scale: float = 1000.0) -> List[dict]:
    """The drivable dimensions of a sketch, values in millimetres (R110).

    Distance and radius rows are listed; an expression row also carries its raw
    text, so a UI can show it next to the resolved value.  A numeric row is stored
    in metres (the solver's unit) and an expression in millimetres (the parameter
    table's unit, and ``dimN`` likewise) - the conversion happens here.
    """
    sk = find_sketch(kdoc, sketch_id)
    if sk is None:
        return []
    out = []
    for i, c in enumerate(getattr(sk, "constraints", []) or []):
        if not c or c[0] not in DIM_KINDS:
            continue
        vi = _dim_value_index(c)
        if len(c) <= vi:
            continue
        raw = c[vi]
        expr = raw if isinstance(raw, str) else None
        why = ""
        if expr:
            mm, why = _dim_value_mm(kdoc, sk, i, scale, seen=set())
        else:
            try:
                mm = float(raw) * scale
            except (TypeError, ValueError):
                mm, why = None, "尺寸值不是数字：%r" % (raw,)
        if mm is None:
            # a broken dimension must stay visible (and numbered) in the tree,
            # otherwise its index cannot be fixed from the UI
            out.append({"index": i, "kind": c[0], "value_mm": None, "expr": expr,
                        "reason": why,
                        "label": "%s 无法求值%s" % (DIM_LABELS.get(c[0], c[0]),
                                                  ("（%s）" % expr) if expr else "")})
            continue
        out.append({"index": i, "kind": c[0], "value_mm": mm, "expr": expr,
                    "label": "%s %gmm%s" % (DIM_LABELS.get(c[0], c[0]), mm,
                                            ("（%s）" % expr) if expr else "")})
    return out


def redrive_expressions(kdoc, scale: float = 1000.0) -> Dict[str, Any]:
    """Re-solve every expression dimension after the parameter table changed.

    This is what makes "change d in the parameter dialog" move the sketch (and the
    bodies built from it): the expression stays on the constraint, so it only has
    to be driven again.  A dimension may reference another one (R111/A-1), so the
    pass repeats until the values settle - bounded, because a cycle is refused by
    the resolution itself.
    """
    out: Dict[str, Any] = {"ok": True, "reason": "", "redriven": 0, "failed": []}
    for _pass in range(3):
        changed = False
        for sk in list(getattr(kdoc, "sketches", []) or []):
            for dim in dimensions(kdoc, sk.id, scale):
                if not dim["expr"]:
                    continue
                before = dim["value_mm"]
                rep = set_dimension(kdoc, sk.id, dim["index"], dim["expr"], scale)
                if rep["ok"]:
                    out["redriven"] += 1
                    if abs(rep["value_mm"] - before) > 1e-12:
                        changed = True
                else:
                    out["failed"].append((sk.id, dim["index"], rep["reason"]))
        if not changed:
            break
    if out["failed"]:
        out["ok"] = False
        out["reason"] = "；".join("%s#%s：%s" % f for f in out["failed"])
    return out


def set_dimension(kdoc, sketch_id: str, index: int, value_mm,
                  scale: float = 1000.0) -> Dict[str, Any]:
    """Drive one sketch dimension: re-solve and write the points back (A-3).

    ``value_mm`` is a number in millimetres or an **expression** (R110/A-2) such as
    "2*d", resolved against the document's parameter table; the expression is
    stored on the constraint, so it re-resolves whenever the table changes.

    Uses the Levenberg-Marquardt solver (not the legacy relaxation) because a
    *driven* dimension has to land on its target tightly - the acceptance is a
    closed-form volume.  Atomic: a solve that misses the target restores both the
    constraint and the curves, so a failed drive never leaves a half-solved sketch.
    """
    from scdm import sketch as S
    from scdm.sketch_solver import solve_report
    rep: Dict[str, Any] = {"ok": False, "reason": "", "index": index,
                           "old_mm": None, "value_mm": None, "expr": None,
                           "label": "", "dof": None, "residual": None,
                           "welded": 0, "welded_moved": 0}
    sk = find_sketch(kdoc, sketch_id)
    if sk is None:
        rep["reason"] = "草图不存在：%s" % sketch_id
        return rep
    cons = list(getattr(sk, "constraints", []) or [])
    if not (0 <= index < len(cons)):
        rep["reason"] = "标注序号越界：%s" % index
        return rep
    c = list(cons[index])
    if not c or c[0] not in DIM_KINDS:
        rep["reason"] = "该约束不是可驱动尺寸：%s" % (c[0] if c else "?")
        return rep
    vi = _dim_value_index(c)
    if len(c) <= vi:
        rep["reason"] = "该尺寸约束缺少数值：%s" % (c,)
        return rep
    target, expr, why = _resolve_value_mm(kdoc, value_mm, scale, sk)
    if target is None:
        rep["reason"] = why
        return rep
    if target <= 0:
        rep["reason"] = "尺寸必须大于 0"
        return rep
    old = c[vi]
    rep["old_mm"] = float(old) * scale if not isinstance(old, str) else None
    rep["value_mm"] = target * scale
    rep["expr"] = expr
    rep["label"] = "%s %gmm" % (DIM_LABELS.get(c[0], c[0]), target * scale)
    saved_curves = list(sk.curves)
    # R108/A-1 + R109/A-1: weld touching vertices before solving; the welds are a
    # repair and survive a failed drive, so the constraint snapshot comes after
    weld_report: Dict[str, Any] = {}
    rep["welded"] = int(S.weld_coincident(
        sk, tol=weld_tolerance_mm(kdoc) / float(scale or 1000.0),
                                          report=weld_report))
    rep["welded_moved"] = int(weld_report.get("moved", 0))
    saved_cons = list(sk.constraints)
    c[vi] = expr if expr else target     # keep the expression, else store metres
    sk.constraints[index] = tuple(c)
    if expr:
        # R111/A-1: reject a self reference or a chain that leads back here, and
        # say which two dimensions form the cycle
        probe_mm, probe_why = _dim_value_mm(kdoc, sk, index, scale, seen=set())
        if probe_mm is None and "循环" in (probe_why or ""):
            sk.constraints = saved_cons
            rep["reason"] = probe_why
            return rep
    try:
        pts, segs = S.read_points(sk)
        has_radius = any(x and x[0] == "radius" for x in sk.constraints)
        circles = S.read_circles(sk) if has_radius else None
        report = solve_report(pts, _solver_rows(sk, _namespace_for(kdoc, sk, scale),
                                          scale),
                              segments=segs, circles=circles, max_iter=200)
        rep["dof"] = int(getattr(report, "dof", -1))
        rep["residual"] = float(getattr(report, "max_residual", -1.0))
        i = int(c[1])
        if c[0] == "radius":
            got = float(circles.get(i, 0.0)) if circles else 0.0
        else:
            j = int(c[2])
            if i >= len(pts) or j >= len(pts):
                raise ValueError("尺寸引用的点不存在")
            got = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
        if abs(got - target) > 1e-6 * target + 1e-9:
            raise ValueError("求解未落到目标尺寸（%.6g vs %.6g m）" % (got, target))
        if not getattr(report, "converged", True):
            raise ValueError("求解未收敛：%s" % getattr(report, "message", ""))
        S.write_points(sk, pts, circles=circles)
    except Exception as exc:
        sk.curves = saved_curves
        sk.constraints = saved_cons
        rep["reason"] = str(exc)
        return rep
    rep["ok"] = True
    return rep


def sketch_params(sk, height_mm: float, loop=None, curves=None,
                  mode=None) -> Dict[str, Any]:
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
    if mode:
        out["mode"] = str(mode)          # R108/A-4: one | symmetric | reverse
    return out


def sync_sketch_bodies(kdoc, sketch_id: Optional[str] = None,
                       scale: float = 1000.0) -> Dict[str, Any]:
    """Re-derive every sketch body from its (possibly edited) sketch.

    This is what makes the sketch a real feature: editing the outline and calling
    this rebuilds the solids, instead of leaving them as orphans of the old
    curves.  Returns {"ok", "reason", "updated", "failed"}.
    """
    from scdm import sketch as S          # R109: used for welding before replay
    out: Dict[str, Any] = {"ok": True, "reason": "", "updated": [], "failed": [],
                           "removed": [], "extra_loops": 0}
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
            # R109/A-1: the outline may have been edited a hair apart - weld first
            S.weld_coincident(
                sk, tol=weld_tolerance_mm(kdoc) / float(scale or 1000.0))
            # R107/A-1: a feature owns one loop; the live link follows its index
            idx = f.params.get("loop")
            curves = None
            if idx is not None:
                loops = S.sketch_loops(sk.curves)
                if not (0 <= int(idx) < len(loops)):
                    # R115/A-6: the loop this body was built from no longer
                    # exists, so the body has no defining geometry left - it goes
                    # with it (the undo stack still holds the state before the
                    # sketch edit, so this is recoverable).
                    reason = "草图第 %d 个闭环已不存在" % (int(idx) + 1)
                    kdoc.remove(bid)
                    try:
                        kdoc.features.pop(bid, None)
                    except AttributeError:
                        pass
                    out["removed"].append((bid, reason))
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
    # R112/A-1: a curve-adding edit (mirror / pattern) can leave closed loops
    # with no body yet.  Report them so the UI can say "pull again" instead of
    # silently ignoring the new geometry.
    try:
        per_sketch: Dict[str, int] = {}
        for _bid, stack in list(getattr(kdoc, "features", {}).items()):
            for f in list(stack.features):
                if f.op == "sketch" and f.params.get("sketch_id"):
                    sid = str(f.params.get("sketch_id"))
                    per_sketch[sid] = per_sketch.get(sid, 0) + 1
        extra = 0
        for sid, n in per_sketch.items():
            sk = find_sketch(kdoc, sid)
            if sk is None:
                continue
            extra += max(0, len(S.sketch_loops(sk.curves)) - n)
        out["extra_loops"] = int(extra)
    except Exception:
        out["extra_loops"] = 0
    return out


def _face_plane_distance(face, origin, normal):
    """(signed_distance, reason) from a plane to a face along the normal (A-2).

    "Pull to face" needs a plane parallel to the sketch; anything else is refused
    with the reason rather than extruded to a guessed distance.
    """
    from scdm import kernel as K
    try:
        fn, fc = K.face_normal_center(face)
    except Exception as exc:
        return None, "到面：无法读取目标面（%s）" % exc
    dot = sum(fn[i] * normal[i] for i in range(3))
    if abs(abs(dot) - 1.0) > 1e-6:
        return None, "到面需要与草图平面平行的平面"
    d = sum((fc[i] - origin[i]) * normal[i] for i in range(3))
    if abs(d) < 1e-9:
        return None, "到面：目标面就在草图平面上"
    return d, ""


def extrude_active(kdoc, height_mm: float = 10.0, scale: float = 1000.0,
                   session: Optional[SketchSession] = None,
                   name: str = "拉伸", mode: str = "one",
                   to_face=None) -> Dict[str, Any]:
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
    kdoc.active_sketch = sk.id          # R110/A-5: remembered by the document
    h = float(height_mm) / float(scale)
    if h <= 0:
        out["reason"] = "拉伸高度必须大于 0"
        return out
    axes = S.sketch_axes(sk.plane, sk.origin, sk.normal, sk.xdir)
    if to_face is not None:
        # R111/A-2: the height is the plane-to-face distance and the side of the
        # sketch plane decides the direction - what the GUI used to compute itself
        d, why = _face_plane_distance(to_face, axes[0], axes[3])
        if d is None:
            out["reason"] = why
            return out
        h = abs(d)
        height_mm = h * float(scale)
        mode = "reverse" if d < 0 else "one"
        out["to_face_mm"] = height_mm
    made = []
    recorded = False
    try:
        # R109/A-1: welding first turns "drawn a hair apart" into a real loop
        weld_report: Dict[str, Any] = {}
        out["welded"] = int(S.weld_coincident(
            sk, tol=weld_tolerance_mm(kdoc) / float(scale or 1000.0),
            report=weld_report))
        out["welded_moved"] = int(weld_report.get("moved", 0))
        # R107/A-1 + A-2: every closed loop becomes its own body (a circle a real
        # cylinder), and each body's feature carries exactly its own loop
        loops = S.sketch_loops(sk.curves)
        if not loops:
            gap = S.min_vertex_gap(sk)
            tol_mm = weld_tolerance_mm(kdoc)
            if gap is not None and gap * float(scale) <= max(1.0, 10.0 * tol_mm):
                raise ValueError(
                    "草图没有闭环：最近的两个端点相距 %.3gmm"
                    "（未重合，当前焊接容差 %.3gmm）"
                    % (gap * float(scale), tol_mm))
            raise ValueError("草图没有闭环（画矩形、圆或闭合线段）")
        # R112/A-1: a pull on a sketch that already owns bodies updates them loop
        # by loop and only *creates* the loops that are new.  Without this, the
        # mirror/pattern hint ("pull again") would duplicate the profile that was
        # already built instead of adding the new one.
        mine: Dict[int, Any] = {}
        for bid, stack in list(getattr(kdoc, "features", {}).items()):
            for f in list(stack.features):
                if (f.op == "sketch" and f.params.get("sketch_id") == sk.id
                        and f.params.get("loop") is not None):
                    mine.setdefault(int(f.params["loop"]), (bid, f))
        for i, loop in enumerate(loops):
            curves = loop_curves(loop)
            solid = S.extrude_loops(curves, h, axes=axes)[0]
            # R108/A-4: one | symmetric | reverse - same volume, different seat
            solid = S.place_extrusion(solid, mode, h, axes[3])
            params = sketch_params(sk, height_mm, loop=i, curves=curves,
                                   mode=mode)
            old = mine.get(i)
            if old is not None and kdoc.body_by_id(old[0]) is not None:
                # the loop already has a body: re-derive it in place
                old[1].params.update(params)
                ok, why = kdoc.replay_body(old[0], scale)
                if not ok:
                    raise ValueError("重放失败：%s" % why)
                made.append(kdoc.body_by_id(old[0]))
                continue
            body = kdoc.add_body(
                solid, name=name if len(loops) == 1 else "%s%d" % (name, i + 1))
            # R106/B-1: the sketch becomes the body's feature, so an edited
            # sketch (sync_sketch_bodies) or height (edit_feature) rebuilds it
            kdoc.record_feature(body.id, "sketch", **params)
            made.append(body)
        recorded = True
    except Exception as exc:
        if not made:
            text = str(exc)
            out["reason"] = text if "没有闭环" in text else "草图无闭环：%s" % text
            return out
    out.update(ok=True, bodies=made, sketch=sk, feature=recorded,
               volume=sum(K.volume(b.shape) for b in made))
    return out

"""Whole-document reference health check (R116/A-2).

A sketch dimension can point at a deleted sketch; a mate can point at a deleted
component; a named selection, a group, a configuration or a placed instance can
point at a deleted body.  None of that is a crash - it is a document that no
longer describes what it says, and the user only finds out by tripping over it.

`document_warnings()` walks every id-bearing reference and returns one entry per
dangling reference, with the scope and the id, so an open-time check (or a script)
can say exactly what to fix.  Read-only: it never repairs anything (rule 85).
"""
from __future__ import annotations

import math
from typing import Dict, List


def _body_of(sid: str) -> str:
    """The body id inside any topology id ("B3", "B3:5", "edge:B3:2")."""
    parts = str(sid).split(":")
    for p in parts:
        if p[:1] == "B" and p[1:].isdigit():
            return p
    return parts[0]


def document_warnings(kdoc, scale: float = 1000.0) -> List[dict]:
    """Every reference that points at something deleted (R116/A-2).

    Entry: `{"scope", "id", "reason", "extra"}`.  Scopes: "dimension", "mate",
    "named", "group", "config", "instance".
    """
    out: List[dict] = []
    body_ids = {b.id for b in getattr(kdoc, "bodies", []) or []}
    comp_ids = {c.id for c in getattr(kdoc, "components", []) or []}

    # 1. sketch dimensions (R115) - the expression cannot be resolved
    try:
        from scdm import sketchmode as SKM
        for w in SKM.reference_warnings(kdoc, scale):
            out.append({"scope": "dimension", "id": "%s#%d" % (w["sketch"],
                                                            w["index"]),
                        "reason": w["reason"], "extra": w.get("expr"),
                        "ref": (w["sketch"], int(w["index"]))})
    except Exception:
        pass

    # 2. mates: a and b are component (or body) ids
    for m in getattr(kdoc, "mates", []) or []:
        for side in ("a", "b"):
            cid = m.get(side)
            if cid and cid not in comp_ids and cid not in body_ids:
                out.append({"scope": "mate",
                            "id": "%s/%s.%s" % (m.get("type", "?"), cid, side),
                            "reason": "配合指向已删除的组件 %s" % cid,
                            "extra": m.get("type"),
                            "ref": (cid, side,
                                    m.get("b" if side == "a" else "a"))})

    # 3. named selections and groups: items are (kind, id)
    for scope, key in (("named", "named"), ("group", "groups")):
        for entry in getattr(kdoc, key, []) or []:
            for kind, sid in entry.get("items", []) or []:
                bid = _body_of(sid)
                if str(kind) in ("body", "face", "edge", "vertex",
                                 "component") and bid not in body_ids \
                        and bid not in comp_ids:
                    out.append({"scope": scope,
                                "id": "%s/%s" % (entry.get("name", "?"), sid),
                                "reason": "%s %s 指向已删除的 %s%s" % (
                                    "命名选择" if scope == "named" else "组",
                                    entry.get("name", "?"), bid,
                                    "（导入，只读）" if entry.get("imported")
                                    else ""),
                                "extra": str(kind),
                                "readonly": bool(entry.get("imported")),
                                "ref": (key, str(kind), str(sid),
                                        entry.get("name", ""))})

    # 4. configurations: hidden components, suppressed bodies, transforms and the
    #    property snapshot are all keyed by id
    for cfg in getattr(kdoc, "configurations", []) or []:
        for cid in getattr(cfg, "hidden_components", []) or []:
            if cid not in comp_ids:
                out.append({"scope": "config",
                            "id": "%s/%s" % (cfg.id, cid),
                            "reason": "配置 %s 指向已删除的组件 %s" % (cfg.id, cid),
                            "extra": "hidden",
                            "ref": (cfg.id, "hidden_components", cid)})
        for bid in getattr(cfg, "suppressed_bodies", []) or []:
            if bid not in body_ids:
                out.append({"scope": "config", "id": "%s/%s" % (cfg.id, bid),
                            "reason": "配置 %s 指向已删除的实体 %s" % (cfg.id, bid),
                            "extra": "suppressed",
                            "ref": (cfg.id, "suppressed_bodies", bid)})
        for cid in (getattr(cfg, "transforms", {}) or {}):
            if cid not in comp_ids and cid not in body_ids:
                out.append({"scope": "config", "id": "%s/%s" % (cfg.id, cid),
                            "reason": "配置 %s 的位姿指向已删除的 %s" % (cfg.id, cid),
                            "extra": "transform",
                            "ref": (cfg.id, "transforms", cid)})
        for bid in (getattr(cfg, "properties", {}) or {}):
            if bid not in body_ids:
                out.append({"scope": "config", "id": "%s/%s" % (cfg.id, bid),
                            "reason": "配置 %s 的属性指向已删除的实体 %s" % (cfg.id,
                                                                     bid),
                            "extra": "properties",
                            "ref": (cfg.id, "properties", bid)})

    # 5. placed instances (an ordinary body id link)
    for inst in getattr(kdoc, "instances", []) or []:
        for key in ("body_id", "source"):
            bid = inst.get(key)
            if bid and bid not in body_ids:
                out.append({"scope": "instance",
                            "id": "%s/%s" % (inst.get("id", "?"), bid),
                            "reason": "实例指向已删除的实体 %s" % bid,
                            "extra": key, "ref": (key, bid)})
    return out


def report_text(warnings) -> str:
    """The warnings as one line each, for a script or a dialog (R117/A-2).

    The tree shows the same list; this is the copyable form.  Line count ==
    warning count (plus the header only when there is something to report).
    """
    scope_cn = {"dimension": "尺寸", "mate": "配合", "named": "命名选择",
                "group": "组", "config": "配置", "instance": "实例"}
    if not warnings:
        return ""
    out = ["引用体检：%d 条" % len(warnings)]
    for w in warnings:
        out.append("%s %s：%s" % (scope_cn.get(w["scope"], w["scope"]),
                                  w["id"], w["reason"]))
    return "\n".join(out)


def warning_summary(warnings, limit: int = 2) -> str:
    """One line for the status bar: scopes, ids and the first reasons."""
    scope_cn = {"dimension": "尺寸", "mate": "配合", "named": "命名选择",
                "group": "组", "config": "配置", "instance": "实例"}
    if not warnings:
        return ""
    head = "；".join("%s %s %s" % (scope_cn.get(w["scope"], w["scope"]),
                                   w["id"], w["reason"])
                    for w in warnings[:limit])
    more = "" if len(warnings) <= limit else " 等 %d 处" % len(warnings)
    return "已打开：%d 处引用悬空（%s%s）" % (len(warnings), head, more)


#: which repair actions a dangling reference supports (R118/A-2).  A dimension row
#: cannot simply be dropped - removing a constraint renumbers every later row, so
#: the safe fix is to freeze it at the value the geometry has right now.
FIXES = {"dimension": ("freeze", "retarget"), "mate": ("drop",),
         "named": ("drop",), "group": ("drop",), "config": ("drop",),
         "instance": ("drop",)}

#: what each action does, in the words the review list uses (R119/A-2)
ACTION_TEXT = {"freeze": "冻结为当前值", "retarget": "改指向另一张草图",
               "drop": "删除该悬空项"}


def _freeze_dimension(kdoc, warning, scale: float):
    """Turn an unresolvable dimension into the number the geometry has now."""
    from scdm import sketch as S
    from scdm import sketchmode as SKM
    sid, index = warning["ref"]
    sk = SKM.find_sketch(kdoc, sid)
    if sk is None:
        return False, "草图 %s 已不存在" % sid
    cons = list(getattr(sk, "constraints", []) or [])
    if not (0 <= int(index) < len(cons)):
        return False, "尺寸序号越界：%s" % index
    c = cons[int(index)]
    pts, _segs = S.read_points(sk)
    if c[0] == "radius":
        circles = S.read_circles(sk)
        radius = float(circles.get(int(c[1]), c[2] if len(c) > 2 else 0.0))
        value_mm = radius * float(scale or 1000.0)
    else:
        i, j = int(c[1]), int(c[2])
        if not (0 <= i < len(pts) and 0 <= j < len(pts)):
            return False, "尺寸引用的点不存在"
        value_mm = math.hypot(pts[j][0] - pts[i][0],
                              pts[j][1] - pts[i][1]) * float(scale or 1000.0)
    rep = SKM.set_dimension(kdoc, sid, int(index), value_mm, scale)
    if not rep["ok"]:
        return False, rep["reason"]
    return True, "已冻结为 %.4gmm" % value_mm


def _retarget_dimension(kdoc, warning, to, to_index, scale: float):
    """Point an unresolvable dimension at another sketch (R119/A-1).

    Freezing is blunt - it throws the intent away.  Retargeting keeps it: the row
    keeps its expression form, only the sketch it names changes.  The drive goes
    through `set_dimension`, so a target that cannot be solved is refused and the
    row is rolled back.
    """
    from scdm import sketchmode as SKM
    if not to:
        return False, ("改指向需要给出目标"
                      "（to=\"S2\"、\"S2_dim5\"、\"param:d\" 或 \"expr:2*d\"）")
    if isinstance(to, (tuple, list)) and len(to) == 2:
        # R126/A-11: a pair means "that sketch, that dimension" - the form
        # repair_selected() has always taken from a {id: target} map
        to, to_index = to[0], int(to[1])
    elif isinstance(to, str) and "_dim" in to:
        # ... and the rows store exactly that pair as "S2_dim5", so the string a
        # document lists is itself a target (one grammar, not two)
        head, _, tail = str(to).rpartition("_dim")
        if head and tail.isdigit() and SKM.find_sketch(kdoc, head) is not None:
            to, to_index = head, int(tail)
    sid, index = warning["ref"]
    if str(to).startswith("expr:"):
        # R123/A-2: the target may be an expression, so a dangling row can become
        # "2*d" and keep following the parameter table (cycles are still refused
        # by set_dimension, which is where dimension references are checked)
        expr = str(to).split(":", 1)[1].strip()
        if not expr:
            return False, "算式目标为空（to=\"expr:2*d\"）"
        rep = SKM.set_dimension(kdoc, sid, int(index), expr, scale)
        if not rep["ok"]:
            return False, rep["reason"]
        return True, "已改指向算式 %s（%gmm）" % (expr, rep.get("value_mm") or 0.0)
    if str(to).startswith("param:"):
        # R122/A-3: point the row at a parameter instead of another sketch - the
        # number then comes from the parameter table like any other expression
        name = str(to).split(":", 1)[1].strip()
        table = getattr(kdoc, "param_table", None)
        names = {}
        try:
            names = table.resolve() if table is not None else {}
        except Exception:
            names = {}
        if name not in names:
            return False, "参数表里没有 %s" % (name or "（空名）")
        rep = SKM.set_dimension(kdoc, sid, int(index), name, scale)
        if not rep["ok"]:
            return False, rep["reason"]
        return True, "已改指向参数 %s（%gmm）" % (name, rep.get("value_mm") or 0.0)
    target = SKM.find_sketch(kdoc, str(to))
    if target is None:
        return False, "目标草图 %s 已不存在" % to
    idx = int(index if to_index is None else to_index)
    ocons = list(getattr(target, "constraints", []) or [])
    if not (0 <= idx < len(ocons)) or not ocons[idx] or \
            ocons[idx][0] not in SKM.DIM_KINDS:
        return False, "目标草图 %s 没有尺寸 #%d" % (to, idx)
    expr = "%s_dim%d" % (to, idx)
    rep = SKM.set_dimension(kdoc, sid, int(index), expr, scale)
    if not rep["ok"]:
        return False, rep["reason"]
    return True, "已改指向 %s（%s，%gmm）" % (expr, rep.get("expr") or "",
                                             rep.get("value_mm") or 0.0)


def _drop(kdoc, warning) -> tuple:
    """Remove a dangling entry by value (never by list index)."""
    scope, ref = warning["scope"], warning.get("ref")
    if scope == "mate":
        cid = ref[0]                     # (dangling id, side[, other id])
        for i, m in enumerate(kdoc.mates):
            if cid in (m.get("a"), m.get("b")):
                kdoc.mates.pop(i)
                return True, "已删除指向 %s 的配合" % cid
        return False, "没有找到该配合"
    if scope in ("named", "group"):
        key, kind, sid = ref[0], ref[1], ref[2]
        wanted = ref[3] if len(ref) > 3 else None
        for entry in getattr(kdoc, key, []) or []:
            if wanted is not None and entry.get("name", "") != wanted:
                continue
            items = [it for it in entry.get("items", []) or []
                     if not (str(it[0]) == kind and str(it[1]) == sid)]
            if len(items) != len(entry.get("items", []) or []):
                entry["items"] = items
                return True, "已从 %s 移除 %s" % (entry.get("name", "?"), sid)
        return False, "没有找到该条目"
    if scope == "config":
        cfg_id, field, value = ref
        cfg = kdoc.configuration_by(cfg_id)
        if cfg is None:
            return False, "配置 %s 已不存在" % cfg_id
        if field in ("hidden_components", "suppressed_bodies"):
            seq = [x for x in getattr(cfg, field, []) or [] if x != value]
            setattr(cfg, field, seq)
            return True, "已从配置 %s 移除 %s" % (cfg_id, value)
        table = getattr(cfg, field, None)
        if isinstance(table, dict) and value in table:
            table.pop(value, None)
            return True, "已从配置 %s 移除 %s" % (cfg_id, value)
        return False, "配置 %s 里没有 %s" % (cfg_id, value)
    if scope == "instance":
        key, value = ref
        for i, inst in enumerate(getattr(kdoc, "instances", []) or []):
            if inst.get(key) == value:
                kdoc.instances.pop(i)
                return True, "已删除指向 %s 的实例" % value
        return False, "没有找到该实例"
    return False, "该引用不支持删除"


def repair_warning(kdoc, warning, action: str = "auto", scale: float = 1000.0,
                   to=None, to_index=None):
    """Fix one dangling reference (R118/A-2, R119/A-1).

    Returns `{"ok", "reason", "action", "options"}`.  `action` "auto" picks the
    safe fix for the scope (a dimension is frozen, everything else is dropped);
    "retarget" keeps a dimension's intent by pointing it at `to` instead.  An
    unsupported request is refused *with the list of what would work*, so the
    refusal can be acted on.
    """
    scope = warning.get("scope", "")
    if warning.get("readonly"):
        # R120/A-3: an imported structure belongs to the document it came
        # from - a repair here would rewrite someone else's grouping
        return {"ok": False, "action": "", "options": [],
                "reason": "该引用来自导入结构（只读），不能在这里修"}
    options = list(FIXES.get(scope, ()))
    act = action
    if act in (None, "", "auto"):
        act = options[0] if options else ""
    if act not in options:
        return {"ok": False, "action": act, "options": options,
                "reason": "该引用不能这样修：%s（可用：%s）"
                          % (act or "无", "、".join(options) or "无")}
    if act == "freeze":
        ok, why = _freeze_dimension(kdoc, warning, scale)
    elif act == "retarget":
        ok, why = _retarget_dimension(kdoc, warning, to, to_index, scale)
    else:
        ok, why = _drop(kdoc, warning)
    return {"ok": bool(ok), "action": act, "options": options, "reason": why}


def repair_selected(kdoc, ids=None, scale: float = 1000.0, action="auto",
                    to=None, exclude=None) -> dict:
    """Fix only the warnings named in `ids` (R120/A-1) - or all when None.

    `action` may be one action or a `{scope: action}` map, so "retarget the
    dimensions, drop the rest" is one call.  `to` may be one target for every
    retargeted row or a `{warning id: target}` map (a target is a sketch id, or a
    `(sketch, index)` pair).  Everything not named is left exactly as it was.

    R121/A-1: `exclude` is the other way round - fix everything *except* these.
    That is what unticking a row in a preview means, and the two are refused
    together because "only these" and "all but these" cannot both hold.
    """
    if ids is not None and exclude:
        return {"ok": False, "reason": "不能同时限定「只修这些」和「跳过这些」",
                "fixed": [], "skipped": []}
    wanted = None if ids is None else {str(i) for i in ids}
    skip = {str(i) for i in (exclude or ())}
    out = {"ok": True, "fixed": [], "skipped": []}
    for w in document_warnings(kdoc, scale):
        if wanted is not None and w["id"] not in wanted:
            continue
        if w["id"] in skip:
            continue
        act = (action.get(w.get("scope", ""), "auto")
               if isinstance(action, dict) else action)
        target = to.get(w["id"]) if isinstance(to, dict) else to
        tgt, tix = target, None
        if isinstance(target, (tuple, list)) and len(target) == 2:
            tgt, tix = target
        rep = repair_warning(kdoc, w, act, scale, to=tgt, to_index=tix)
        if rep["ok"]:
            out["fixed"].append((w["id"], rep["reason"]))
        else:
            out["skipped"].append((w["id"], rep["reason"]))
    return out


def repair_plan(kdoc, scale: float = 1000.0, ids=None, exclude=None) -> List[dict]:
    """What `repair_all()` would do, without doing it (R119/A-2).

    One entry per warning: `{"id", "scope", "action", "text"}`.  Reviewing the
    list first is the difference between "the tool fixed my document" and "the
    tool changed my document" - a destructive step deserves a look.
    """
    wanted = None if ids is None else {str(i) for i in ids}
    skip = {str(i) for i in (exclude or ())}
    out: List[dict] = []
    for w in document_warnings(kdoc, scale):
        if wanted is not None and w["id"] not in wanted:
            continue
        if w["id"] in skip:
            continue
        if w.get("readonly"):
            out.append({"id": w["id"], "scope": w.get("scope", ""),
                        "action": "", "text": "只读（导入），跳过"})
            continue
        options = FIXES.get(w.get("scope", ""), ())
        act = options[0] if options else ""
        out.append({"id": w["id"], "scope": w.get("scope", ""),
                    "action": act,
                    "text": ACTION_TEXT.get(act, act or "无法修复")})
    return out


def plan_text(plan) -> str:
    """The plan as one line per entry, for a status bar or a dialog."""
    if not plan:
        return ""
    lines = ["引用修复预览：%d 条" % len(plan)]
    for p in plan:
        lines.append("%s → %s" % (p["id"], p["text"]))
    return "\n".join(lines)


def repair_all(kdoc, scale: float = 1000.0) -> dict:
    """Fix every dangling reference that has a safe fix (R118/A-2).

    Entries are removed *by value*, so repairing one cannot shift the next one
    out from under the loop.  What cannot be fixed is reported, not guessed at.
    """
    return repair_selected(kdoc, None, scale, "auto")

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
                        "reason": w["reason"], "extra": w.get("expr")})
    except Exception:
        pass

    # 2. mates: a and b are component (or body) ids
    for m in getattr(kdoc, "mates", []) or []:
        for side in ("a", "b"):
            cid = m.get(side)
            if cid and cid not in comp_ids and cid not in body_ids:
                out.append({"scope": "mate", "id": "%s.%s" % (m.get("id", "?"),
                                                             side),
                            "reason": "配合指向已删除的组件 %s" % cid,
                            "extra": m.get("type")})

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
                                "reason": "%s %s 指向已删除的 %s" % (
                                    "命名选择" if scope == "named" else "组",
                                    entry.get("name", "?"), bid),
                                "extra": str(kind)})

    # 4. configurations: hidden components, suppressed bodies, transforms and the
    #    property snapshot are all keyed by id
    for cfg in getattr(kdoc, "configurations", []) or []:
        for cid in getattr(cfg, "hidden_components", []) or []:
            if cid not in comp_ids:
                out.append({"scope": "config",
                            "id": "%s/%s" % (cfg.id, cid),
                            "reason": "配置 %s 指向已删除的组件 %s" % (cfg.id, cid),
                            "extra": "hidden"})
        for bid in getattr(cfg, "suppressed_bodies", []) or []:
            if bid not in body_ids:
                out.append({"scope": "config", "id": "%s/%s" % (cfg.id, bid),
                            "reason": "配置 %s 指向已删除的实体 %s" % (cfg.id, bid),
                            "extra": "suppressed"})
        for cid in (getattr(cfg, "transforms", {}) or {}):
            if cid not in comp_ids and cid not in body_ids:
                out.append({"scope": "config", "id": "%s/%s" % (cfg.id, cid),
                            "reason": "配置 %s 的位姿指向已删除的 %s" % (cfg.id, cid),
                            "extra": "transform"})
        for bid in (getattr(cfg, "properties", {}) or {}):
            if bid not in body_ids:
                out.append({"scope": "config", "id": "%s/%s" % (cfg.id, bid),
                            "reason": "配置 %s 的属性指向已删除的实体 %s" % (cfg.id,
                                                                     bid),
                            "extra": "properties"})

    # 5. placed instances (an ordinary body id link)
    for inst in getattr(kdoc, "instances", []) or []:
        for key in ("body_id", "source"):
            bid = inst.get(key)
            if bid and bid not in body_ids:
                out.append({"scope": "instance",
                            "id": "%s/%s" % (inst.get("id", "?"), bid),
                            "reason": "实例指向已删除的实体 %s" % bid,
                            "extra": key})
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

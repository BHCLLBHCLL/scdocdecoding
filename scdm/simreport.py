"""P348/R68: 仿真报告 —— 载荷/支撑/接触清单 + 网格与材料统计。

The report is DERIVED (rule 77): every field is recomputed from the live model,
so the counts equal the model's counts by construction, a material change moves
the reported mass by the density ratio, and a mesh/gate change moves the reported
verdict - no refresh plumbing anywhere.

Blockers are a countable list (each one a named fact), and `ready` is simply
"no blockers" - a report is a decision, so it must say what is missing instead of
just being empty.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

BLOCKER_TEXT = {
    "no_mesh": "没有网格（先运行面网格）",
    "mesh_gate_failed": "网格质量门槛未通过",
    "no_loads": "没有载荷",
    "no_supports": "没有支撑（约束）",
}


def build_report(kdoc, scale: float = 1000.0) -> Dict[str, Any]:
    """The simulation report for a document (raises without a sim model)."""
    sim = getattr(kdoc, "sim", None)
    if sim is None:
        raise ValueError("没有仿真模型：先添加载荷/支撑")
    from scdm import materials as MAT

    loads = [{"id": ld.id, "kind": ld.kind, "body": ld.body_id,
              "face": int(ld.face_index),
              "vector": [float(v) for v in (ld.vector or (0, 0, 0))],
              "magnitude": float(getattr(ld, "magnitude", 0.0) or 0.0)}
             for ld in sim.loads]
    supports = [{"id": sp.id, "kind": sp.kind, "body": sp.body_id,
                 "face": int(sp.face_index)} for sp in sim.supports]
    contacts = [{"id": ct.id, "kind": ct.kind, "body_a": ct.body_a,
                 "face_a": int(ct.face_a), "body_b": ct.body_b,
                 "face_b": int(ct.face_b)} for ct in sim.contacts]
    markups = [{"id": mk.id, "text": mk.text,
                "point": [float(v) for v in (mk.point or (0, 0, 0))]}
               for mk in sim.markups]

    meshes: Dict[str, Any] = {}
    gate_failed = 0
    for body in kdoc.bodies:
        entry = (getattr(kdoc, "meshes", {}) or {}).get(body.id) or {}
        stats = entry.get("stats")
        if not stats:
            continue
        gates = entry.get("gates") or {}
        ok = bool(gates.get("ok", True))
        if not ok:
            gate_failed += 1
        meshes[body.id] = {
            "name": body.name,
            "triangles": int(stats.get("triangles", 0)),
            "vertices": int(stats.get("vertices", 0)),
            "degenerate": int(stats.get("degenerate", 0)),
            "area_rel_error": float(stats.get("area_rel_error", 0.0)),
            "gates_ok": ok,
            "gate_violations": int(gates.get("count", 0)),
        }
    materials = []
    for row in MAT.bom_rows(kdoc.bodies, getattr(kdoc, "properties", {}), scale):
        materials.append({"id": row["id"], "name": row["name"],
                          "material": row["material"],
                          "material_name": row["material_name"],
                          "mass_g": row["mass_g"], "volume_mm3": row["volume_mm3"]})

    blockers: List[str] = []
    if not meshes:
        blockers.append("no_mesh")
    if gate_failed:
        blockers.append("mesh_gate_failed")
    if not loads:
        blockers.append("no_loads")
    if not supports:
        blockers.append("no_supports")
    return {
        "counts": {"loads": len(loads), "supports": len(supports),
                   "contacts": len(contacts), "markups": len(markups),
                   "meshes": len(meshes), "bodies": len(kdoc.bodies)},
        "loads": loads, "supports": supports, "contacts": contacts,
        "markups": markups, "meshes": meshes, "materials": materials,
        "total_mass_g": sum(float(m["mass_g"]) for m in materials),
        "blockers": blockers,
        "blocker_text": [BLOCKER_TEXT.get(b, b) for b in blockers],
        "ready": not blockers,
        "summary": str(sim.summary()),
    }


def report_text(report: Dict[str, Any]) -> str:
    """One status-bar line: counts + readiness."""
    c = report.get("counts") or {}
    state = "就绪" if report.get("ready") else "缺 %d 项" % len(
        report.get("blockers") or [])
    return ("仿真报告：载荷 %d / 支撑 %d / 接触 %d / 标记 %d / 网格体 %d —— %s"
            % (c.get("loads", 0), c.get("supports", 0), c.get("contacts", 0),
               c.get("markups", 0), c.get("meshes", 0), state))


def write_report(path: str, report: Dict[str, Any]) -> str:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def read_report(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

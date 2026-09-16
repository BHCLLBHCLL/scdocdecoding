"""Native session package: zip of JSON + BREP bodies (.scdm).

P22: the manifest now also carries the modelling history (per-body feature
stacks + document-level features), assembly instances and components, so a
saved project reopens with its parametric intent, not just its geometry.
P291 (version 3): beam/weldment groups - shared section, members and weld
symbol metadata - ride along in the same manifest.
"""
from __future__ import annotations

import json
import zipfile
from typing import Any

from scdm import kernel as K
from scdm.features import FeatureHistory, FeatureStack
from scdm.kdoc import Component, KernelDoc


def _has_history(kdoc, bid: str) -> bool:
    stack = getattr(kdoc, "features", {}).get(bid)
    return bool(stack) and len(stack) > 0


def _body_manifest(b, kdoc) -> dict:
    """One manifest body row.  R102: featured bodies also carry their base.

    Without the base a reloaded project could only replay from the *featured*
    shape it stored, which rebuilds a different body; so the base travels with
    the file, and a body whose base is missing is left unknown so that a
    parameter edit refuses instead of guessing.
    """
    row = {"id": b.id, "name": b.name, "color": list(b.color),
           "visible": b.visible,
           "layer": getattr(b, "layer", "默认") or "默认",
           "file": f"bodies/{b.id}.brep"}
    if _has_history(kdoc, b.id) and getattr(b, "base_shape", None) is not None:
        row["base"] = f"bodies/{b.id}.base.brep"
    pose = getattr(b, "base_pose", None)
    if _has_history(kdoc, b.id) and pose:
        row["base_pose"] = [list(op) for op in pose]
    return row


def save_scdm(path: str, kdoc: KernelDoc) -> None:
    manifest = {
        "format": "scdm-session",
        "version": 5,
        "bodies": [_body_manifest(b, kdoc) for b in kdoc.bodies],
        "notes": [{"pos": list(n.get("pos") or (0, 0, 0)), "text": n.get("text", "")}
                  for n in getattr(kdoc, "notes", [])],
        "named": [{"name": n.get("name", ""),
                   "items": [list(it) for it in n.get("items", [])]}
                  for n in getattr(kdoc, "named", [])],
        "groups": [{"name": n.get("name", ""),
                    "items": [list(it) for it in n.get("items", [])]}
                   for n in getattr(kdoc, "groups", [])],
        # R110/A-5: the sketch the user was editing (for resolve_active)
        "active_sketch": getattr(kdoc, "active_sketch", None),
        # R112/A-2: snap radius == weld tolerance (mm), so a reloaded
        # project keeps welding the way the viewport snapped it
        "weld_tol_mm": float(getattr(kdoc, "weld_tol_mm", 0.1)),
        "features": {bid: stack.as_dict()
                     for bid, stack in getattr(kdoc, "features", {}).items()
                     if len(stack)},
        # R106/B-1: sketches are first-class now - a sketch body's live link
        # (sync_sketch_bodies) has to survive a reload.  The feature also carries
        # the curves, so replay works even for a file from before this change.
        "sketches": [{"id": s.id, "name": s.name, "plane": s.plane,
                      "origin": list(s.origin), "normal": list(s.normal),
                      "xdir": list(s.xdir),
                      "curves": [list(c) for c in s.curves],
                      "construction": [list(c) for c in s.construction],
                      "constraints": [list(c) for c in s.constraints]}
                     for s in getattr(kdoc, "sketches", [])],
        "document_features": getattr(kdoc, "document_features",
                                     FeatureHistory()).as_dict(),
        "instances": [dict(i) for i in getattr(kdoc, "instances", [])],
        "components": [{"id": c.id, "name": c.name,
                        "body_ids": list(c.body_ids),
                        "anchored": bool(c.anchored),
                        "visible": bool(c.visible),
                        "lightweight": bool(c.lightweight),
                        "explosion": (list(c.explosion)
                                      if c.explosion is not None else None),
                        "transform": (list(c.transform)
                                      if c.transform is not None else None)}
                       for c in getattr(kdoc, "components", [])],
        "mates": [dict(m) for m in getattr(kdoc, "mates", [])],
        "configurations": [{"id": c.id, "name": c.name,
                            "hidden_components": list(c.hidden_components),
                            "suppressed_bodies": list(c.suppressed_bodies),
                            "transforms": {k: list(v) for k, v in c.transforms.items()},
                            "properties": {k: dict(v) for k, v in
                                           getattr(c, "properties", {}).items()},
                            "quantities": {k: int(v) for k, v in
                                           getattr(c, "quantities", {}).items()}}
                           for c in getattr(kdoc, "configurations", [])],
        "active_configuration": getattr(kdoc, "active_configuration", None),
        # P291: beam/weldment groups (shared section + members + weld symbols)
        "weldments": [w.to_dict() for w in getattr(kdoc, "weldments", [])],
        # P319: part properties (material + custom fields) per body
        "properties": {bid: p.to_dict()
                       for bid, p in getattr(kdoc, "properties", {}).items()},
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for b in kdoc.bodies:
            z.writestr(f"bodies/{b.id}.brep", K.dumps_brep(b.shape))
            if _has_history(kdoc, b.id) and b.base_shape is not None:
                z.writestr(f"bodies/{b.id}.base.brep", K.dumps_brep(b.base_shape))


def load_scdm(path: str) -> KernelDoc:
    doc = KernelDoc()
    with zipfile.ZipFile(path, "r") as z:
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        max_n = 1
        for item in man.get("bodies", []):
            blob = z.read(item["file"])
            sh = K.loads_brep(blob)
            body = doc.add_body(sh, name=item.get("name"), color=tuple(item.get("color") or (0.62, 0.66, 0.70)))
            body.id = item["id"]
            body.visible = bool(item.get("visible", True))
            body.layer = item.get("layer") or "默认"
            # R102: the feature base travels with the file; a featured body
            # without one keeps base_shape = None so replay refuses.
            if item.get("base"):
                try:
                    body.base_shape = K.loads_brep(z.read(item["base"]))
                except Exception:
                    body.base_shape = None
            elif (man.get("features") or {}).get(body.id):
                body.base_shape = None
            body.base_pose = [tuple(op) for op in (item.get("base_pose") or [])]
            try:
                max_n = max(max_n, int(str(body.id)[1:]) + 1)
            except Exception:
                pass
        doc._n = max_n
    doc.active_sketch = man.get("active_sketch")   # R110/A-5
    try:                                        # R112/A-2
        doc.weld_tol_mm = float(man.get("weld_tol_mm", 0.1))
    except (TypeError, ValueError):
        doc.weld_tol_mm = 0.1
    doc.notes = [dict(n) for n in man.get("notes", [])]
    doc.named = [{"name": n.get("name", ""),
                  "items": [tuple(it) for it in n.get("items", [])]}
                 for n in man.get("named", [])]
    doc.groups = [{"name": n.get("name", ""),
                   "items": [tuple(it) for it in n.get("items", [])]}
                  for n in man.get("groups", [])]
    # R106/B-1: sketches (plane / curves / constraints) - a sketch body's live
    # link is only useful when the sketch itself comes back
    doc.sketches = []
    max_sk = 1
    for s in man.get("sketches", []) or []:
        sk = doc.add_sketch(s.get("plane") or "xy", name=s.get("name"))
        sk.id = s.get("id") or sk.id
        sk.origin = tuple(s.get("origin") or (0.0, 0.0, 0.0))
        sk.normal = tuple(s.get("normal") or (0.0, 0.0, 1.0))
        sk.xdir = tuple(s.get("xdir") or (1.0, 0.0, 0.0))
        sk.curves = [tuple(c) for c in (s.get("curves") or [])]
        sk.construction = [tuple(c) for c in (s.get("construction") or [])]
        sk.constraints = [tuple(c) for c in (s.get("constraints") or [])]
        try:
            max_sk = max(max_sk, int(str(sk.id)[1:]) + 1)
        except Exception:
            pass
    doc._sk = max_sk
    # P22: modelling history + assembly state
    doc.features = {bid: FeatureStack.from_dict(data)
                    for bid, data in (man.get("features") or {}).items()}
    doc.document_features = FeatureHistory.from_dict(
        man.get("document_features") or [])
    doc.instances = [dict(i) for i in man.get("instances", [])]
    for c in man.get("components", []):
        comp = Component(id=c.get("id") or "C1", name=c.get("name") or "组件",
                         body_ids=list(c.get("body_ids") or []),
                         anchored=bool(c.get("anchored", False)),
                         visible=bool(c.get("visible", True)),
                         lightweight=bool(c.get("lightweight", False)),
                         explosion=(tuple(c["explosion"])
                                    if c.get("explosion") is not None else None),
                         transform=(tuple(c["transform"])
                                    if c.get("transform") is not None else None))
        doc.components.append(comp)
    doc._c = len(doc.components) + 1
    doc.mates = [dict(m) for m in man.get("mates", [])]
    from scdm import beams as BEAMS
    doc.weldments = [BEAMS.Weldment.from_dict(w)
                     for w in (man.get("weldments") or [])]
    from scdm.materials import PartProperties
    doc.properties = {bid: PartProperties.from_dict(p)
                      for bid, p in (man.get("properties") or {}).items()}
    from scdm.kdoc import Configuration
    doc.configurations = [
        Configuration(c.get("id") or "CFG1", c.get("name") or "配置",
                      list(c.get("hidden_components") or []),
                      list(c.get("suppressed_bodies") or []),
                      {k: tuple(v) for k, v in (c.get("transforms") or {}).items()},
                      {k: dict(v) for k, v in (c.get("properties") or {}).items()},
                      {k: int(v) for k, v in (c.get("quantities") or {}).items()})
        for c in man.get("configurations", [])]
    doc.active_configuration = man.get("active_configuration")
    return doc

"""Native session package: zip of JSON + BREP bodies (.scdm)."""
from __future__ import annotations

import json
import zipfile
from typing import Any

from scdm import kernel as K
from scdm.kdoc import KernelDoc


def save_scdm(path: str, kdoc: KernelDoc) -> None:
    manifest = {
        "format": "scdm-session",
        "version": 1,
        "bodies": [{"id": b.id, "name": b.name, "color": list(b.color), "visible": b.visible,
                    "file": f"bodies/{b.id}.brep"} for b in kdoc.bodies],
        "notes": [{"pos": list(n.get("pos") or (0, 0, 0)), "text": n.get("text", "")}
                  for n in getattr(kdoc, "notes", [])],
        "named": [{"name": n.get("name", ""),
                   "items": [list(it) for it in n.get("items", [])]}
                  for n in getattr(kdoc, "named", [])],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for b in kdoc.bodies:
            z.writestr(f"bodies/{b.id}.brep", K.dumps_brep(b.shape))


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
            try:
                max_n = max(max_n, int(str(body.id)[1:]) + 1)
            except Exception:
                pass
        doc._n = max_n
    doc.notes = [dict(n) for n in man.get("notes", [])]
    doc.named = [{"name": n.get("name", ""),
                  "items": [tuple(it) for it in n.get("items", [])]}
                 for n in man.get("named", [])]
    return doc

"""Rebuild OCCT solids from decoded SAB topology (planar faces first)."""
from __future__ import annotations

from typing import Any, List, Optional

from scdm import kernel as K
from scdm.kdoc import KernelDoc


def import_model(model, color=(0.62, 0.66, 0.70)) -> KernelDoc:
    doc = KernelDoc()
    if model is None or not K.available():
        return doc
    bodies = model.of_kind("body")
    if not bodies:
        # some files may only expose faces
        faces = _faces_from_model(model, None)
        if faces:
            try:
                solid = K.sew_faces(faces)
                doc.add_body(solid, name="实体 1", color=color)
            except K.KernelError:
                pass
        return doc
    for i, body in enumerate(bodies, 1):
        faces = _faces_from_model(model, body)
        if not faces:
            continue
        try:
            solid = K.sew_faces(faces)
            name = model.doc_id_of(body) or f"实体 {i}"
            doc.add_body(solid, name=f"实体 {i}", color=color)
        except K.KernelError:
            continue
    return doc


def _faces_from_model(model, body) -> List[Any]:
    face_ents = model.body_faces(body) if body is not None else model.of_kind("face")
    occ_faces = []
    for face in face_ents:
        polys = model.face_loops_polygons(face)
        if not polys:
            continue
        try:
            occ_faces.append(K.face_from_polygon(polys[0]))
        except K.KernelError:
            continue
    return occ_faces


def import_scdoc_bundle(data: dict) -> KernelDoc:
    model = data.get("model") if data else None
    color = (0.62, 0.66, 0.70)
    render = data.get("render") if data else None
    if render:
        for view in render:
            for it in view.get("items", []):
                for b in it.get("bodies", []):
                    if b.get("rgb"):
                        color = tuple(c / 255.0 for c in b["rgb"])
                        break
    doc = import_model(model, color=color)
    if doc.bodies:
        return doc
    # bbox fallback from facets
    fac = data.get("fac") if data else None
    if fac is not None and getattr(fac, "faces", None):
        xs, ys, zs = [], [], []
        for f in fac.faces:
            for c in f.corners:
                xs.append(c.position[0]); ys.append(c.position[1]); zs.append(c.position[2])
        if xs and K.available():
            dx = max(xs) - min(xs); dy = max(ys) - min(ys); dz = max(zs) - min(zs)
            if min(dx, dy, dz) > 1e-12:
                box = K.make_box(dx, dy, dz, origin=(min(xs), min(ys), min(zs)))
                doc.add_body(box, name="实体 1", color=color)
    return doc

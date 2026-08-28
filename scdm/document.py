"""Session document: wrap scdoc_parser output for the GUI."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from scdm.history import History

from scdoc_parser import document as dmod
from scdoc_parser import facets as fmod
from scdoc_parser import opc, sab, topology
from scdoc_parser.report import parse_renderlist


def load_scdoc(path: str) -> dict:
    """Parse a .scdoc into a GUI/kernel-facing bundle."""
    pkg = opc.parse_package(path)
    doc_part = pkg.find_main_document()
    geom = pkg.find_geometry()
    doc = dmod.parse_document(pkg.read(doc_part)) if doc_part else None
    sf = sab.tokenize(pkg.read(geom[0].name)) if geom else None
    model = topology.SabModel(sf) if sf else None
    fac_pd = None
    fac = None
    render_pd = None
    render = None
    if doc_part:
        for r in pkg.rels_of(doc_part):
            rt = r.rel_type.lower()
            if "bodyfacets" in rt:
                fac_pd = r.target
            elif "renderlist" in rt:
                render_pd = r.target
    if fac_pd:
        fac = fmod.parse_facets(pkg.read(fac_pd))
    if render_pd:
        render = parse_renderlist(pkg.read(render_pd))
    scale = model.sab.unit_scale if model else (doc.units.factor if doc else 1000.0)
    return {
        "path": path,
        "pkg": pkg,
        "doc": doc,
        "model": model,
        "fac": fac,
        "render": render,
        "scale": scale,
        "doc_path": doc_part,
        "geom_path": geom[0].name if geom else None,
        "fac_path": fac_pd,
        "render_path": render_pd,
    }


@dataclass
class Session:
    """One open design (tab)."""
    name: str = "Design1"
    path: Optional[str] = None
    dirty: bool = False
    data: Optional[dict] = None
    show_faces: bool = True
    show_edges: bool = True
    show_vertices: bool = True
    show_planes: bool = False
    show_axes: bool = True
    show_grid: bool = False  # sketch grid on the active sketch plane
    show_silhouette: bool = False  # feature-edge silhouette overlay
    section_axis: Optional[str] = None  # static section clip: None|'x'|'y'|'z'
    style: str = "shaded_edges"  # shaded_edges | shaded | wire | transp
    kdoc: Any = None
    history: History = field(default_factory=History)
    clipboard: Optional[bytes] = None
    saved_views: List[dict] = field(default_factory=list)  # {"name","pos","focal","up","scale"}

    @property
    def scale(self) -> float:
        if self.data and self.data.get("scale"):
            return float(self.data["scale"])
        return 1000.0

    @property
    def design_doc(self) -> Optional[Any]:
        return None if not self.data else self.data.get("doc")

    def title(self) -> str:
        mark = "*" if self.dirty else ""
        return f"{mark}{self.name} - SpaceClaim"

    def body_caption(self, body) -> str:
        doc = self.design_doc
        if doc is not None:
            cap = doc.caption_for(body.id)
            if cap and cap.name:
                return cap.name
        return body.id or "实体"

    def root_caption(self) -> str:
        doc = self.design_doc
        if doc is not None:
            for c in doc.captions:
                if c.type == "Design" or (c.name and not c.subject_id):
                    pass
            # RootCaptionDef typically names the part/design
            if doc.captions:
                root = doc.captions[0]
                if root.name:
                    return root.name
        return self.name

    def layers(self) -> List:
        doc = self.design_doc
        return list(doc.layers) if doc is not None else []

    def units_symbol(self) -> str:
        doc = self.design_doc
        if doc is not None and getattr(doc, "units", None):
            return doc.units.symbol or "mm"
        return "mm"


def new_session(index: int = 1) -> Session:
    from scdm.kdoc import KernelDoc
    ses = Session(name=f"Design{index}", data=None, dirty=False, kdoc=KernelDoc())
    ses.history.push(ses.kdoc.snapshot())
    return ses


def session_from_scdoc(path: str) -> Session:
    data = load_scdoc(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    ses = Session(name=stem, path=path, data=data, dirty=False)
    try:
        from scdm.import_sab import import_scdoc_bundle
        from scdm import kernel as K
        if K.available():
            ses.kdoc = import_scdoc_bundle(data)
            ses.history.push(ses.kdoc.snapshot())
    except Exception:
        ses.kdoc = None
    return ses

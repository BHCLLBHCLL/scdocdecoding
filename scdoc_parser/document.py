"""SpaceClaim document.xml design-tree parser.

document.xml is the parametric design tree; its structure for box.scdoc:

  Document (version 1.520)
  +-- importSource/importPath/importTimestamp
  +-- Design (urn:nom) Id="0:1"
  |   +-- PartDef Id="0:2"
  |       +-- DefaultEdgeTreatmentDef Id="0:13" (blendRadius)
  |       +-- NominalBodyDef Id="0:23"  <- SAB ATTRIB_XACIS_NAME '0:23' points here
  |       |   +-- layerId/color/renderingStyle/fillStyle/finishStyle ...
  |       |   +-- NominalFaceDef x6   Id="0:27".."0:42"  <- face ids in SAB
  |       |   +-- NominalEdgeDef x12  Id="0:45".."0:78"  <- edge ids in SAB
  |       +-- PartSketchCurveContainerDef (urn:sketch) + SketchCurveDef x4
  +-- PresentationDef (urn:presentation) Id="0:5"
  |   +-- AttributeTableDef, LayerDef Id="0:9" (name, color)
  |   +-- RootCaptionDef subjectId="0:2" name="box"      <- part name
  |   +-- CaptionDef subjectId="0:23" name="Solid1"      <- body name
  +-- DocumentSettingsDef (urn:presentation) Id="0:16"
      +-- DocumentUnitsDef Id="0:17" (lengthProperties: MM factor 1000)
      +-- DocumentDetailSettingsDef

The '0:N' Ids are the join keys between the design tree and the ACIS
SAB entity attributes (ATTRIB_XACIS_NAME values).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _text(el: ET.Element, local_name: str) -> Optional[str]:
    """Text of first direct child matching by LOCAL name (namespaces vary)."""
    for child in el:
        if _local(child.tag) == local_name and child.text is not None:
            return child.text.strip()
    return None


def _sub_text(el: ET.Element, parent_name: str, child_name: str) -> Optional[str]:
    for child in el:
        if _local(child.tag) == parent_name:
            return _text(child, child_name)
    return None


def _deep_text(el: ET.Element, local_name: str) -> Optional[str]:
    """Recursive local-name text search (for nested sketch curve params)."""
    for sub in el.iter():
        if sub is not el and _local(sub.tag) == local_name and sub.text and sub.text.strip():
            return sub.text.strip()
    return None


def _floats(text: Optional[str]) -> List[float]:
    if not text:
        return []
    return [float(x) for x in text.replace(',', ' ').split()]


@dataclass
class FaceDef:
    id: str
    props: Dict[str, str] = field(default_factory=dict)


@dataclass
class EdgeDef:
    id: str
    is_reversed: bool = False
    props: Dict[str, str] = field(default_factory=dict)


@dataclass
class BodyDef:
    id: str
    layer_id: Optional[str] = None
    type: Optional[str] = None
    color: Optional[str] = None            # '143, 166, 175'
    rendering_style: Optional[str] = None
    fill_style: Optional[str] = None
    finish_style: Optional[str] = None
    faces: List[FaceDef] = field(default_factory=list)
    edges: List[EdgeDef] = field(default_factory=list)


@dataclass
class SketchCurve:
    id: str
    kind: str = 'line'
    origin: List[float] = field(default_factory=list)
    direction: List[float] = field(default_factory=list)
    interval: List[float] = field(default_factory=list)
    color: Optional[str] = None


@dataclass
class Layer:
    id: str
    name: Optional[str] = None
    color: Optional[str] = None
    visible: bool = True
    locked: bool = False


@dataclass
class Caption:
    id: str
    subject_id: str
    name: str
    type: Optional[str] = None


@dataclass
class Units:
    length_type: str = 'MM'
    factor: float = 1000.0
    symbol: str = 'mm'
    decimal_places: int = 2


@dataclass
class DesignDocument:
    version: Optional[str] = None
    next_id: Optional[str] = None
    import_source: Optional[str] = None
    import_path: Optional[str] = None
    import_timestamp: Optional[str] = None
    design_id: Optional[str] = None
    parts: List[str] = field(default_factory=list)          # PartDef ids
    bodies: List[BodyDef] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=list)
    captions: List[Caption] = field(default_factory=list)
    sketch_curves: List[SketchCurve] = field(default_factory=list)
    units: Units = field(default_factory=Units)
    default_blend_radius: Optional[float] = None

    # -- lookup helpers -----------------------------------------------------
    def caption_for(self, subject_id: str) -> Optional[Caption]:
        for c in self.captions:
            if c.subject_id == subject_id:
                return c
        return None

    def body_by_doc_id(self, doc_id: str) -> Optional[BodyDef]:
        for b in self.bodies:
            if b.id == doc_id:
                return b
        return None


def parse_document(xml_bytes: bytes) -> DesignDocument:
    root = ET.fromstring(xml_bytes)
    doc = DesignDocument()
    doc.version = root.get('version')

    for el in root.iter():
        tag = _local(el.tag)
        if tag == 'nextId' and doc.next_id is None:
            doc.next_id = (el.text or '').strip()
        elif tag == 'importPath':
            doc.import_path = (el.text or '').strip()
        elif tag == 'importSource':
            doc.import_source = (el.text or '').strip()
        elif tag == 'importTimestamp':
            doc.import_timestamp = (el.text or '').strip()
        elif tag == 'Design':
            doc.design_id = el.get('Id')
        elif tag == 'DefaultEdgeTreatmentDef':
            r = _text(el, 'blendRadius')
            if r is not None:
                doc.default_blend_radius = float(r)

    # NominalBodyDef: capture child face/edge defs before flattening
    for body_el in root.iter():
        if _local(body_el.tag) != 'NominalBodyDef':
            continue
        body = BodyDef(id=body_el.get('Id', ''))
        body.layer_id = _text(body_el, 'layerId')
        body.type = _text(body_el, 'type')
        body.color = _text(body_el, 'color')
        body.rendering_style = _text(body_el, 'renderingStyle')
        body.fill_style = _text(body_el, 'fillStyle')
        body.finish_style = _text(body_el, 'finishStyle')
        for child in body_el:
            ctag = _local(child.tag)
            if ctag == 'NominalFaceDef':
                body.faces.append(FaceDef(id=child.get('Id', '')))
            elif ctag == 'NominalEdgeDef':
                rev = (_text(child, 'isReversed') or 'False').lower() == 'true'
                body.edges.append(EdgeDef(id=child.get('Id', ''), is_reversed=rev))
        doc.bodies.append(body)

    for el in root.iter():
        tag = _local(el.tag)
        if tag == 'PartDef':
            doc.parts.append(el.get('Id', ''))
        elif tag == 'LayerDef':
            doc.layers.append(Layer(
                id=el.get('Id', ''),
                name=_text(el, 'name'),
                color=_text(el, 'color'),
                visible=(_text(el, 'visible') or 'True').lower() == 'true',
                locked=(_text(el, 'locked') or 'False').lower() == 'true',
            ))
        elif tag in ('RootCaptionDef', 'CaptionDef'):
            doc.captions.append(Caption(
                id=el.get('Id', ''),
                subject_id=_text(el, 'subjectId') or '',
                name=_text(el, 'name') or '',
                type=_text(el, 'type'),
            ))
        elif tag == 'SketchCurveDef':
            origin = _floats(_deep_text(el, 'origin'))
            direction = _floats(_deep_text(el, 'dir'))
            start = _floats(_deep_text(el, 'start'))
            end = _floats(_deep_text(el, 'end'))
            doc.sketch_curves.append(SketchCurve(
                id=el.get('Id', ''),
                origin=origin,
                direction=direction,
                interval=start + end,
                color=_text(el, 'color'),
            ))
        elif tag == 'DocumentUnitsDef':
            lp = el.find('units/lengthProperties')
            if lp is not None:
                doc.units = Units(
                    length_type=_text(lp, 'type') or 'MM',
                    factor=float(_text(lp, 'factor') or 1000),
                    symbol=_text(lp, 'symbol') or 'mm',
                    decimal_places=int(_text(lp, 'decimalPlaces') or 2),
                )
    return doc
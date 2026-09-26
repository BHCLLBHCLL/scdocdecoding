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
class NamedSelection:
    id: str
    name: str
    selections: List[str] = field(default_factory=list)   # moniker refIds
    section_plane: Optional[dict] = None                  # origin/dirX/dirY


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
    system: str = 'Metric'   # Metric | Imperial (SpaceClaim Document.Units)


@dataclass
class ComponentRef:
    id: str
    source_ref: Optional[str] = None
    transform: Optional[str] = None
    parent_part_id: Optional[str] = None


@dataclass
class DocItem:
    """Generic design-tree item (beam, datum, CS, mesh, drawing sheet, mate)."""
    id: str
    kind: str
    name: Optional[str] = None
    props: Dict[str, str] = field(default_factory=dict)


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
    named: List[NamedSelection] = field(default_factory=list)
    units: Units = field(default_factory=Units)
    default_blend_radius: Optional[float] = None
    components: List[ComponentRef] = field(default_factory=list)
    beams: List[DocItem] = field(default_factory=list)
    mating_conditions: List[DocItem] = field(default_factory=list)
    datum_planes: List[DocItem] = field(default_factory=list)
    coordinate_systems: List[DocItem] = field(default_factory=list)
    meshes: List[DocItem] = field(default_factory=list)
    drawing_sheets: List[DocItem] = field(default_factory=list)
    named_views: List[DocItem] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    sheet_metal: List[DocItem] = field(default_factory=list)
    # PartDef id -> NominalBodyDef ids living directly under that part
    part_body_ids: Dict[str, List[str]] = field(default_factory=dict)

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

    @property
    def part_def_count(self) -> int:
        """Non-root PartDef count (matches SpaceClaim part-template tally)."""
        return max(0, len(self.parts) - 1)

    @property
    def coordinate_system_count(self) -> int:
        """SpaceClaim always exposes the default CS; beam 'Reference' frames
        are serialised as CoordinateSystemDef but not returned by
        GetCoordinateSystems(), so only captioned non-Reference systems
        count as extras.
        """
        extra = 0
        for cs in self.coordinate_systems:
            cap = self.caption_for(cs.id)
            if cap is None:
                continue
            if (cap.name or '') in ('Reference', ''):
                continue
            extra += 1
        return 1 + extra


def _find_local(el: ET.Element, local_name: str) -> Optional[ET.Element]:
    for child in el:
        if _local(child.tag) == local_name:
            return child
    return None


def _units_system(length_type: str) -> str:
    t = (length_type or '').upper()
    if t in ('INCHES', 'INCH', 'FEET', 'FOOT', 'MILS', 'MICROINCHES'):
        return 'Imperial'
    return 'Metric'


def _units_length_symbol(length_type: str, symbol: Optional[str]) -> str:
    """Map SpaceClaim length type / symbol to the corpus `units_length` token."""
    if symbol:
        return symbol
    t = (length_type or '').upper()
    return {
        'MM': 'mm', 'MILLIMETERS': 'mm', 'MILLIMETRE': 'mm', 'MILLIMETRES': 'mm',
        'CM': 'cm', 'CENTIMETERS': 'cm',
        'M': 'm', 'METERS': 'm', 'METRES': 'm',
        'INCHES': 'in', 'INCH': 'in',
        'FEET': 'ft', 'FOOT': 'ft',
    }.get(t, (length_type or 'mm').lower())


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
            pid = el.get('Id', '')
            doc.parts.append(pid)
            body_ids = []
            for child in el:
                if _local(child.tag) == 'NominalBodyDef':
                    body_ids.append(child.get('Id', ''))
            doc.part_body_ids[pid] = body_ids
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
        elif tag == 'NamedSelectionDef':
            sel = NamedSelection(
                id=el.get('Id', ''),
                name=_text(el, 'name') or '',
            )
            # namespace-tolerant: children live under the stored-selection
            # urn, so walk with _local filtering
            in_selections = False
            for sub in el.iter():
                st = _local(sub.tag)
                if st == 'selections':
                    in_selections = True
                    continue
                if st == 'sectionPlane':
                    in_selections = False
                if in_selections and st == 'item' and sub.get('refId'):
                    sel.selections.append(sub.get('refId'))
                if st == 'sectionPlane' and sel.section_plane is None:
                    sel.section_plane = {
                        'origin': _floats(_text(sub, 'origin') or ''),
                        'dirX': _floats(_text(sub, 'dirX') or ''),
                        'dirY': _floats(_text(sub, 'dirY') or ''),
                    }
            doc.named.append(sel)
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
            units_el = _find_local(el, 'units')
            lp = _find_local(units_el, 'lengthProperties') if units_el is not None else None
            if lp is None:
                # namespace-tolerant deep search
                for sub in el.iter():
                    if _local(sub.tag) == 'lengthProperties':
                        lp = sub
                        break
            if lp is not None:
                length_type = _text(lp, 'type') or 'MM'
                symbol = _text(lp, 'symbol') or 'mm'
                doc.units = Units(
                    length_type=length_type,
                    factor=float(_text(lp, 'factor') or 1000),
                    symbol=symbol,
                    decimal_places=int(_text(lp, 'decimalPlaces') or 2),
                    system=_units_system(length_type),
                )
        elif tag == 'ComponentDef':
            source = None
            for sub in el:
                if _local(sub.tag) == 'source':
                    source = sub.get('refId')
                    break
            doc.components.append(ComponentRef(
                id=el.get('Id', ''),
                source_ref=source,
                transform=_text(el, 'trans'),
            ))
        elif tag == 'BeamDef':
            doc.beams.append(DocItem(id=el.get('Id', ''), kind='beam',
                                     name=_text(el, 'name')))
        elif tag == 'MatingConditionDef':
            doc.mating_conditions.append(DocItem(
                id=el.get('Id', ''), kind='mate',
                name=_text(el, 'name') or _text(el, 'type')))
        elif tag == 'DatumDef':
            doc.datum_planes.append(DocItem(
                id=el.get('Id', ''), kind='datum',
                name=_text(el, 'name')))
        elif tag == 'CoordinateSystemDef':
            doc.coordinate_systems.append(DocItem(
                id=el.get('Id', ''), kind='coordsys',
                name=_text(el, 'name')))
        elif tag == 'MeshDef':
            doc.meshes.append(DocItem(
                id=el.get('Id', ''), kind='mesh',
                name=_text(el, 'name')))
        elif tag == 'DrawingSheetDef':
            doc.drawing_sheets.append(DocItem(
                id=el.get('Id', ''), kind='drawing_sheet',
                name=_text(el, 'name')))
        elif tag == 'NamedViewDef':
            doc.named_views.append(DocItem(
                id=el.get('Id', ''), kind='named_view',
                name=_text(el, 'name')))
        elif tag == 'SheetMetalBehaviorDef':
            doc.sheet_metal.append(DocItem(
                id=el.get('Id', ''), kind='sheet_metal'))
        elif tag in ('MaterialDef', 'MaterialDatabaseMaterialDef'):
            name = _text(el, 'name') or _text(el, 'displayName')
            if name and name not in doc.materials:
                doc.materials.append(name)
    return doc
"""OPC (Open Packaging Conventions) container layer for .scdoc files.

A .scdoc file is a ZIP package following the same OPC rules as .docx:
  * [Content_Types].xml  - extension defaults + part overrides
  * _rels/.rels          - package-level relationships (main document ...)
  * <part>/_rels/*.rels  - per-part relationships
  * SpaceClaim/document.xml is the design tree root part.

This module lists the parts, maps extensions to declared content types and
builds the relationship graph so higher layers can locate the SAB geometry
and graphics streams without hard-coding paths.
"""
from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

RELS_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CTYPES_NS = '{http://schemas.openxmlformats.org/package/2006/content-types}'


@dataclass
class Part:
    name: str
    size: int
    compressed_size: int
    content_type: str

    @property
    def ext(self) -> str:
        return posixpath.splitext(self.name)[1].lstrip('.').lower()


@dataclass
class Relationship:
    source: str            # part the .rels file belongs to ('' = package root)
    rel_id: str
    rel_type: str          # e.g. .../internal/partBodyGeometry#<guid>:2
    target: str            # resolved absolute part path (or external URI)
    target_mode: str = 'Internal'

    @property
    def type_name(self) -> str:
        """Short suffix of the relationship type, e.g. 'partBodyGeometry'."""
        t = self.rel_type.rstrip('0123456789#:')
        if '#' in self.rel_type:
            base, _, frag = self.rel_type.partition('#')
            t = base.rsplit('/', 1)[-1] + '#' + frag
        else:
            t = self.rel_type.rsplit('/', 1)[-1]
        return t


@dataclass
class Package:
    path: str
    parts: List[Part] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    content_type_defaults: Dict[str, str] = field(default_factory=dict)
    content_type_overrides: Dict[str, str] = field(default_factory=dict)

    # -- accessors ----------------------------------------------------------
    def part(self, name: str) -> Optional[Part]:
        for p in self.parts:
            if p.name == name:
                return p
        return None

    def read(self, name: str) -> bytes:
        with zipfile.ZipFile(self.path) as z:
            return z.read(name)

    def rels_of(self, source: str = '') -> List[Relationship]:
        """Relationships owned by `source` ('' = package root)."""
        return [r for r in self.relationships if r.source == source]

    def find_main_document(self) -> Optional[str]:
        """Locate the design tree part via the package-level rels."""
        for r in self.rels_of(''):
            if 'document' in r.rel_type.lower() and r.target_mode == 'Internal':
                return r.target
        for p in self.parts:
            if p.name.endswith('document.xml'):
                return p.name
        return None

    def find_geometry(self) -> List[Part]:
        """Parts whose relationship type mentions geometry (the .sab streams)."""
        rels = [r for r in self.relationships if 'geometry' in r.rel_type.lower()]
        out = []
        for r in rels:
            p = self.part(r.target)
            if p:
                out.append(p)
        return out


# -- parsing ---------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _resolve_target(source_dir: str, target: str) -> str:
    if target.startswith('/'):
        return target.lstrip('/')
    return posixpath.normpath(posixpath.join(source_dir, target))


def _parse_rels(pkg: Package, zipinfo_names: List[str]) -> None:
    for name in zipinfo_names:
        if not (name.startswith('_rels/') or '/_rels/' in name):
            continue
        if not name.endswith('.rels'):
            continue
        # source part: '_rels/.rels' -> '' ; 'A/_rels/B.xml.rels' -> 'A/B.xml'
        base = name[:-len('.rels')]
        if base.startswith('_rels/'):
            source = ''
            rel_dir = ''
        else:
            rel_dir = posixpath.dirname(posixpath.dirname(name))  # strip /_rels
            source = posixpath.join(rel_dir, posixpath.basename(base))
        try:
            with zipfile.ZipFile(pkg.path) as z:
                data = z.read(name)
        except KeyError:
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise ValueError(f'bad rels XML in {name}: {exc}') from exc
        for rel in root.findall(f'{RELS_NS}Relationship'):
            target = rel.get('Target', '')
            mode = rel.get('TargetMode', 'Internal')
            resolved = _resolve_target(rel_dir, target) if mode == 'Internal' else target
            pkg.relationships.append(Relationship(
                source=source,
                rel_id=rel.get('Id', ''),
                rel_type=rel.get('Type', ''),
                target=resolved,
                target_mode=mode,
            ))


def parse_package(path: str) -> Package:
    """Open a .scdoc OPC package and index its parts + relationships."""
    pkg = Package(path=path)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        infos = {zi.filename: zi for zi in z.infolist()}
        ct_data = z.read('[Content_Types].xml') if '[Content_Types].xml' in names else b''
        _parse_rels(pkg, names)

    root = ET.fromstring(ct_data)
    for el in root:
        tag = _local(el.tag)
        if tag == 'Default':
            pkg.content_type_defaults[el.get('Extension', '').lower()] = el.get('ContentType', '')
        elif tag == 'Override':
            pkg.content_type_overrides[el.get('PartName', '').lstrip('/')] = el.get('ContentType', '')

    for name in names:
        if name.endswith('/'):
            continue
        zi = infos[name]
        ct = pkg.content_type_overrides.get(name)
        if ct is None:
            ext = posixpath.splitext(name)[1].lstrip('.').lower()
            ct = pkg.content_type_defaults.get(ext, 'application/octet-stream')
        pkg.parts.append(Part(
            name=name,
            size=zi.file_size,
            compressed_size=zi.compress_size,
            content_type=ct,
        ))
    return pkg
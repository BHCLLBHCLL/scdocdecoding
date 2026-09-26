"""Comparable SpaceClaim-ground-truth view extracted from a .scdoc.

Used by the manifest-driven corpus suite.  Counts prefer the design-tree
(document.xml) + renderlist instance expansion so they match SpaceClaim's
``GetBodies()`` / face / edge tallies; volumes and areas come from the SAB
metrics (planar + analytic cylinder/cone/sphere/torus).
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import document, facets, opc, sab, topology
from .document import _units_length_symbol
from .report import parse_renderlist


def _load_models(pkg: opc.Package) -> List[Tuple[str, topology.SabModel]]:
    out = []
    for gp in pkg.find_geometry():
        sf = sab.tokenize(pkg.read(gp.name))
        out.append((gp.name, topology.SabModel(sf)))
    return out


def _render_body_instances(render_views) -> List[Dict]:
    """Flatten renderlist body instances: {body_id, path, transform}."""
    if not render_views:
        return []
    view = render_views[0]
    inst = []
    for item in view.get('items') or []:
        # parse_renderlist keeps bodies as list of dicts with 'id'
        path = None
        # re-parse raw attrs is not available; Path is on Item in XML but
        # parse_renderlist currently drops it — recover via transform+id only.
        for b in item.get('bodies') or []:
            inst.append({
                'body_id': b.get('id'),
                'item_id': item.get('id'),
                'transform': item.get('transform'),
            })
    return inst


def _enrich_renderlist(xml_bytes: bytes) -> List[Dict]:
    """Like parse_renderlist but also keeps Item Path (component id)."""
    import xml.etree.ElementTree as ET

    def local(tag: str) -> str:
        return tag.rsplit('}', 1)[-1]

    root = ET.fromstring(xml_bytes)
    views = []
    for view in root:
        if local(view.tag) != 'View':
            continue
        items = []
        for item in view:
            if local(item.tag) != 'Item':
                continue
            bodies = []
            for body in item:
                if local(body.tag) != 'Body':
                    continue
                color = body.get('Color')
                rgb = None
                if color is not None:
                    c = int(color) & 0xFFFFFFFF
                    rgb = [(c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF]
                bodies.append({
                    'id': body.get('Id'),
                    'visible': body.get('Visible'),
                    'rgb': rgb,
                    'fill_style': body.get('FillStyle'),
                    'rendering_style': body.get('RenderingStyle'),
                    'finish_style': body.get('FinishStyle'),
                })
            items.append({
                'id': item.get('Id'),
                'bodies': bodies,
                'transform': item.get('Transform'),
                'path': item.get('Path') or '',
            })
        views.append({'id': view.get('Id'), 'box': view.get('Box'), 'items': items})
    return views


def build_corpus_view(path: str) -> Dict:
    """Extract a dict aligned with the corpus case-JSON ``actual`` block."""
    pkg = opc.parse_package(path)
    doc_part = pkg.find_main_document()
    doc = document.parse_document(pkg.read(doc_part)) if doc_part else None

    models = _load_models(pkg)
    scale = 1000.0
    if models:
        scale = models[0][1].sab.unit_scale or scale
    elif doc is not None:
        scale = doc.units.factor

    # Index SAB bodies by doc id across all geometry parts.
    sab_by_id: Dict[str, Tuple[topology.SabModel, object]] = {}
    sab_bodies_ordered = []
    surface_counter: Counter = Counter()
    curve_counter: Counter = Counter()
    for _name, model in models:
        for body in model.of_kind('body'):
            did = model.doc_id_of(body)
            sab_bodies_ordered.append((model, body, did))
            if did:
                sab_by_id[did] = (model, body)
        for face in model.of_kind('face'):
            label = model.surface_kind_label(face)
            if label:
                surface_counter[label] += 1
        for edge in model.of_kind('edge'):
            c = model.e(edge.curve) if edge.curve >= 0 else None
            if c is None:
                continue
            kind = c.kind
            if kind == 'straight':
                curve_counter['Straight'] += 1
            elif kind == 'ellipse':
                ratio = c.ratio if c.ratio is not None else 1.0
                curve_counter['Circle' if abs(ratio - 1.0) < 1e-9 else 'Ellipse'] += 1
            elif kind in ('intcurve', 'spline', 'surfintcur'):
                curve_counter['Spline'] += 1
            else:
                curve_counter[kind.capitalize()] += 1

    render_part = None
    for r in pkg.rels_of(doc_part or ''):
        if 'renderlist' in r.rel_type.lower():
            render_part = r.target
    render_views = _enrich_renderlist(pkg.read(render_part)) if render_part else []

    # Instance list: prefer renderlist body occurrences (captures shared-part
    # instances), restricted to design-tree NominalBodyDefs.  Fall back to
    # document bodies when renderlist is absent.  Mesh-only docs (no
    # NominalBodyDef) correctly report zero B-rep bodies.
    doc_body_ids = {b.id for b in doc.bodies} if doc is not None else set()
    instances = []
    if doc_body_ids and render_views:
        for item in render_views[0].get('items') or []:
            for b in item.get('bodies') or []:
                bid = b.get('id')
                if bid not in doc_body_ids:
                    continue
                instances.append({
                    'body_id': bid,
                    'path': item.get('path') or '',
                    'component_id': item.get('path') or '',
                })
    if not instances and doc_body_ids:
        for b in doc.bodies:
            instances.append({'body_id': b.id, 'path': '', 'component_id': ''})

    def _body_topo(body_def: Optional[document.BodyDef], model_body):
        faces = edges = vertices = 0
        if body_def is not None:
            faces = len(body_def.faces)
            edges = len(body_def.edges)
            # Vertices: unique ends of design-tree edges in the SAB.
            if model_body is not None:
                model, body = model_body
                doc_edge_ids = {e.id for e in body_def.edges}
                verts = set()
                for ed in model.of_kind('edge'):
                    did = model.doc_id_of(ed)
                    if did not in doc_edge_ids:
                        continue
                    if ed.v1 >= 0:
                        verts.add(ed.v1)
                    if ed.v2 >= 0:
                        verts.add(ed.v2)
                vertices = len(verts)
        elif model_body is not None:
            model, body = model_body
            faces = len(model.body_faces(body))
            # count edges/verts via coedges
            eidxs, vidxs = set(), set()
            for f in model.body_faces(body):
                for loop in model.loops_of_face(f):
                    for ce in model.coedges_of_loop(loop):
                        if ce.edge >= 0:
                            eidxs.add(ce.edge)
                            ed = model.e(ce.edge)
                            if ed is not None:
                                if ed.v1 >= 0:
                                    vidxs.add(ed.v1)
                                if ed.v2 >= 0:
                                    vidxs.add(ed.v2)
            edges, vertices = len(eidxs), len(vidxs)
        return faces, edges, vertices

    total_faces = total_edges = total_vertices = 0
    volume = 0.0
    area = 0.0
    body_list = []
    for inst in instances:
        bid = inst['body_id']
        body_def = doc.body_by_doc_id(bid) if doc is not None else None
        model_body = sab_by_id.get(bid)
        f, e, v = _body_topo(body_def, model_body)
        total_faces += f
        total_edges += e
        total_vertices += v
        vol_mm3 = area_mm2 = 0.0
        bbox = None
        if model_body is not None:
            model, body = model_body
            metrics = model.body_metrics(body)
            vol_mm3 = metrics['volume'] * scale ** 3
            area_mm2 = metrics['area'] * scale * scale
            volume += vol_mm3
            area += area_mm2
            if body.bbox_min and body.bbox_max:
                bbox = [
                    [body.bbox_min[i] * scale for i in range(3)],
                    [body.bbox_max[i] * scale for i in range(3)],
                ]
        name = None
        if doc is not None:
            cap = doc.caption_for(bid)
            name = cap.name if cap else None
        # Component display name from caption on the path id.
        comp_name = ''
        if doc is not None and inst.get('path'):
            ccap = doc.caption_for(inst['path'])
            if ccap:
                comp_name = ccap.name
        body_list.append({
            'name': name or '',
            'path': comp_name,
            'faces': f,
            'edges': e,
            'vertices': v,
            'volume_mm3': vol_mm3,
            'area_mm2': area_mm2,
            'bbox_mm': bbox,
        })

    # Mesh-only documents (no SAB bodies): still count MeshDef.
    n_bodies = len(instances)
    if n_bodies == 0 and doc is not None and doc.meshes:
        n_bodies = 0  # mesh bodies are not B-rep bodies

    # Soft-parse facets (STL-import meshes may use an unsupported layout).
    facets_part = None
    for r in pkg.rels_of(doc_part or ''):
        if 'bodyfacets' in r.rel_type.lower():
            facets_part = r.target
    facets_error = None
    fac = None
    if facets_part:
        try:
            fac = facets.parse_facets(pkg.read(facets_part))
        except facets.FacetsError as exc:
            facets_error = str(exc)

    component_list = []
    if doc is not None:
        for comp in doc.components:
            cap = doc.caption_for(comp.id)
            component_list.append({
                'name': cap.name if cap else '',
                'path': '',
                'id': comp.id,
            })

    units_length = 'mm'
    units_system = 'Metric'
    if doc is not None:
        units_length = _units_length_symbol(doc.units.length_type, doc.units.symbol)
        units_system = doc.units.system

    # Layer / named-selection / material names
    layers = [l.name for l in doc.layers] if doc else []
    named_selections = [n.name for n in doc.named] if doc else []
    materials = list(doc.materials) if doc else []
    # SpaceClaim always exposes a default "未知材料" / Unknown material entry
    # in the materials list even when no MaterialDef is serialised.
    if doc is not None and not materials:
        materials = ['未知材料']

    return {
        'bodies': n_bodies,
        'faces': total_faces,
        'edges': total_edges,
        'vertices': total_vertices,
        'volume_mm3': volume,
        'area_mm2': area,
        'components': len(doc.components) if doc else 0,
        'part_defs': doc.part_def_count if doc else 0,
        'beams': len(doc.beams) if doc else 0,
        'mating_conditions': len(doc.mating_conditions) if doc else 0,
        'datum_planes': len(doc.datum_planes) if doc else 0,
        'coordinate_systems': doc.coordinate_system_count if doc else 1,
        'meshes': len(doc.meshes) if doc else 0,
        'drawing_sheets': len(doc.drawing_sheets) if doc else 0,
        'root_curves': len(doc.sketch_curves) if doc else 0,
        'named_selections': named_selections,
        'layers': layers,
        'materials': materials,
        'body_list': body_list,
        'component_list': component_list,
        'surface_types': dict(surface_counter),
        'curve_types': dict(curve_counter),
        'units_length': units_length,
        'units_system': units_system,
        'body_names': sorted(b['name'] for b in body_list if b['name']),
        'facets_error': facets_error,
        'facet_face_count': len(fac.faces) if fac is not None else None,
        'sab_parts': len(models),
        'sheet_metal': len(doc.sheet_metal) if doc else 0,
        'named_views': len(doc.named_views) if doc else 0,
    }

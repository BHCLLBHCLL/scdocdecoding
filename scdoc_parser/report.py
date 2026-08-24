"""Full-model report builder: OPC package + document.xml + SAB B-rep + facets.

The three data layers are cross-linked through the '0:N' doc ids:
  * document.xml  NominalBodyDef / NominalFaceDef / NominalEdgeDef ids
  * SAB           ATTRIB_XACIS_NAME attribute values on body/face/edge
  * facets.bin    edge-table doc-id numbers (e.g. (12, 0, 45) -> '0:45')

renderlist.xml contributes the display bounding box and body colours
(Color is a signed 0xAARRGGBB int; -7362897 = 0xFF8FA6AF -> RGB 143,166,175,
matching document.xml body colour '143, 166, 175').

build_report() returns a JSON-ready dict with per-layer summaries plus
cross-layer validation checks.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from . import document, facets, opc, sab, topology


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def parse_renderlist(xml_bytes: bytes) -> List[Dict]:
    """Views of renderlist.xml: bounding box + per-body display attributes."""
    root = ET.fromstring(xml_bytes)
    views = []
    for view in root:
        if _local(view.tag) != 'View':
            continue
        items = []
        for item in view:
            if _local(item.tag) != 'Item':
                continue
            bodies = []
            for body in item:
                if _local(body.tag) != 'Body':
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
            })
        views.append({'id': view.get('Id'), 'box': view.get('Box'), 'items': items})
    return views


def _face_edge_doc_ids(model: topology.SabModel, face) -> set:
    ids = set()
    for loop in model.loops_of_face(face):
        for ce in model.coedges_of_loop(loop):
            ed = model.e(ce.edge)
            if ed is not None:
                did = model.doc_id_of(ed)
                if did:
                    ids.add(did)
    return ids


def _facet_face_doc_ids(fac: facets.FacetsFile, fnode: facets.FaceNode) -> set:
    return {r.edge_id and fac.doc_id_of_edge(r.edge_id) for r in fnode.edge_refs} - {None}


def _vsub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _vdot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def build_report(path: str) -> Dict:
    pkg = opc.parse_package(path)

    doc_part = pkg.find_main_document()
    doc = document.parse_document(pkg.read(doc_part)) if doc_part else None

    geom_parts = pkg.find_geometry()
    sab_model = None
    if geom_parts:
        sf = sab.tokenize(pkg.read(geom_parts[0].name))
        sab_model = topology.SabModel(sf)

    # facets part via the bodyFacets relationship
    facets_part = None
    for r in pkg.rels_of(doc_part or ''):
        if 'bodyfacets' in r.rel_type.lower():
            facets_part = r.target
    fac = facets.parse_facets(pkg.read(facets_part)) if facets_part else None

    # renderlist
    render_part = None
    for r in pkg.rels_of(doc_part or ''):
        if 'renderlist' in r.rel_type.lower():
            render_part = r.target
    render_views = parse_renderlist(pkg.read(render_part)) if render_part else []

    scale = sab_model.sab.unit_scale if sab_model else (doc.units.factor if doc else 1000.0)

    checks: List[Dict] = []

    def check(name, ok, detail):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})

    # ---- document layer -----------------------------------------------------
    doc_section = None
    if doc is not None:
        doc_section = {
            'version': doc.version,
            'import_path': doc.import_path,
            'import_source': doc.import_source,
            'design_id': doc.design_id,
            'part_ids': doc.parts,
            'units': {
                'length_type': doc.units.length_type,
                'factor': doc.units.factor,
                'symbol': doc.units.symbol,
            },
            'layers': [{
                'id': l.id, 'name': l.name, 'color': l.color,
                'visible': l.visible, 'locked': l.locked,
            } for l in doc.layers],
            'captions': [c.__dict__ for c in doc.captions],
            'bodies': [{
                'id': b.id,
                'name': doc.caption_for(b.id).name if doc.caption_for(b.id) else None,
                'layer_id': b.layer_id,
                'type': b.type,
                'color': b.color,
                'rendering_style': b.rendering_style,
                'face_ids': [f.id for f in b.faces],
                'edge_ids': [e.id for e in b.edges],
                'edge_reversed': {e.id: e.is_reversed for e in b.edges if e.is_reversed},
            } for b in doc.bodies],
            'sketch_curves': [{
                'id': sc.id, 'kind': sc.kind, 'origin': sc.origin,
                'direction': sc.direction, 'interval': sc.interval,
            } for sc in doc.sketch_curves],
            'default_blend_radius_mm': (doc.default_blend_radius * scale
                                        if doc.default_blend_radius is not None else None),
        }

    # ---- B-rep layer ---------------------------------------------------------
    brep_section = topology.model_summary(sab_model, scale) if sab_model else None

    # ---- mesh layer ----------------------------------------------------------
    mesh_section = facets.facets_summary(fac, scale) if fac else None

    # ---- cross-layer validation ---------------------------------------------
    if doc is not None and sab_model is not None:
        doc_body_ids = {b.id for b in doc.bodies}
        sab_body_ids = {model_did for b in sab_model.of_kind('body')
                        if (model_did := sab_model.doc_id_of(b))}
        check('doc_sab_body_ids', doc_body_ids == sab_body_ids,
              f'doc={sorted(doc_body_ids)} sab={sorted(sab_body_ids)}')

        doc_face_ids = {f.id for b in doc.bodies for f in b.faces}
        sab_face_ids = {d for f in sab_model.of_kind('face')
                        if (d := sab_model.doc_id_of(f))}
        check('doc_sab_face_ids', doc_face_ids == sab_face_ids,
              f'{len(doc_face_ids)} doc vs {len(sab_face_ids)} sab face ids, '
              f'diff={sorted(doc_face_ids ^ sab_face_ids)}')

        doc_edge_ids = {e.id for b in doc.bodies for e in b.edges}
        sab_edge_ids = {d for e in sab_model.of_kind('edge')
                        if (d := sab_model.doc_id_of(e))}
        check('doc_sab_edge_ids', doc_edge_ids == sab_edge_ids,
              f'{len(doc_edge_ids)} doc vs {len(sab_edge_ids)} sab edge ids, '
              f'diff={sorted(doc_edge_ids ^ sab_edge_ids)}')

        check('units_consistency',
              abs(doc.units.factor - sab_model.sab.unit_scale) < 1e-9,
              f'document factor={doc.units.factor}, SAB unit_scale={sab_model.sab.unit_scale}')

    if sab_model is not None and fac is not None:
        # facet edge table ids vs SAB edge ids
        sab_edge_ids = {sab_model.doc_id_of(e) for e in sab_model.of_kind('edge')} - {None}
        fac_edge_ids = set(fac.edge_map.values())
        check('facet_sab_edge_ids', fac_edge_ids == sab_edge_ids,
              f'{len(fac_edge_ids)} facet vs {len(sab_edge_ids)} sab edge ids, '
              f'diff={sorted(fac_edge_ids ^ sab_edge_ids)}')

        # body linkage
        check('facet_body_link',
              fac.body_doc_id is not None and
              fac.body_doc_id == sab_model.doc_id_of(sab_model.of_kind('body')[0]),
              f'facet body={fac.body_doc_id}')

        # map SAB doc edge id -> endpoints (metres)
        sab_edges_by_id = {}
        for e in sab_model.of_kind('edge'):
            did = sab_model.doc_id_of(e)
            if did:
                sab_edges_by_id[did] = sab_model.edge_endpoints(e)

        # every facet boundary edge coincides with its SAB edge
        tol = 1e-6
        mismatches = []
        matched = 0
        for fnode in fac.faces:
            for r in fnode.edge_refs:
                seg = fnode.edge_segment(r)
                did = fac.doc_id_of_edge(r.edge_id)
                ref = sab_edges_by_id.get(did)
                if seg is None or ref is None:
                    mismatches.append(f'edge {r.edge_id} ({did}): missing data')
                    continue
                ok = ((topology.vclose(seg[0], ref[0], tol) and topology.vclose(seg[1], ref[1], tol)) or
                      (topology.vclose(seg[0], ref[1], tol) and topology.vclose(seg[1], ref[0], tol)))
                if ok:
                    matched += 1
                else:
                    mismatches.append(f'edge {r.edge_id} ({did}): {seg} vs {ref}')
        check('facet_edges_match_brep', not mismatches and matched > 0,
              f'{matched} facet edge instances coincide with B-rep edges'
              + (f'; mismatches={mismatches[:3]}' if mismatches else ''))

        # map facet face -> SAB face via shared edge doc ids, then check
        # corner positions lie on the B-rep plane and normals agree
        sab_faces_by_edges = {}
        for f in sab_model.of_kind('face'):
            eids = frozenset(_face_edge_doc_ids(sab_model, f))
            if eids:
                sab_faces_by_edges[eids] = f
        on_plane = 0
        normal_ok = 0
        face_links = 0
        plane_errs = []
        normal_errs = []
        for fnode in fac.faces:
            eids = frozenset(_facet_face_doc_ids(fac, fnode))
            sf = sab_faces_by_edges.get(eids)
            if sf is None:
                continue
            face_links += 1
            fm = sab_model.face_metrics(sf)
            n = fm['normal'] if fm else None
            offset = fm['offset'] if fm else None
            surf = sab_model.e(sf.surface)
            if n is None or offset is None or surf is None:
                continue
            for c in fnode.corners:
                d = abs(_vdot(c.position, n) - offset)
                if d < 1e-6:
                    on_plane += 1
                else:
                    plane_errs.append(round(d, 9))
                cn = _vsub(c.normal, (0, 0, 0))
                if _vdot(cn, n) > 0.999:
                    normal_ok += 1
                else:
                    normal_errs.append(round(_vdot(cn, n), 6))
        total_corners = sum(len(f.corners) for f in fac.faces)
        check('facet_faces_link_brep', face_links == len(fac.faces),
              f'{face_links}/{len(fac.faces)} facet faces linked via shared edge ids')
        check('facet_corners_on_brep_planes', on_plane == total_corners and not plane_errs,
              f'{on_plane}/{total_corners} corners on their B-rep plane'
              + (f'; max err={max(plane_errs)}m' if plane_errs else ''))
        check('facet_normals_match_brep', normal_ok == total_corners and not normal_errs,
              f'{normal_ok}/{total_corners} corner normals aligned with B-rep face normal'
              + (f'; worst dot={min(normal_errs)}' if normal_errs else ''))

        # triangle winding: CCW around the face normal
        import math
        winding_ok = 0
        winding_bad = 0
        for fnode in fac.faces:
            nrm = fnode.corners[0].normal
            for (a, b, c) in fnode.triangles:
                pa, pb, pc = fnode.corners[a].position, fnode.corners[b].position, fnode.corners[c].position
                u = _vsub(pb, pa)
                v = _vsub(pc, pa)
                cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                if _vdot(cr, nrm) > 0:
                    winding_ok += 1
                else:
                    winding_bad += 1
        check('facet_triangle_winding', winding_bad == 0 and winding_ok > 0,
              f'{winding_ok} triangles CCW around corner normals, {winding_bad} reversed')

    # bounding boxes across layers
    boxes = {}
    if sab_model is not None:
        for b in sab_model.of_kind('body'):
            if b.bbox_min and b.bbox_max:
                boxes['sab'] = [list(b.bbox_min), list(b.bbox_max)]
    if fac is not None:
        pts = [c.position for f in fac.faces for c in f.corners]
        if pts:
            boxes['facets'] = [[min(p[i] for p in pts) for i in range(3)],
                               [max(p[i] for p in pts) for i in range(3)]]
    if render_views:
        try:
            lo_hi = [float(x) for x in render_views[0]['box'].split(',')]
            boxes['renderlist'] = [lo_hi[:3], lo_hi[3:]]
        except (ValueError, AttributeError):
            pass
    if len(boxes) >= 2:
        def flat(box):
            return [v for p in box for v in p]
        names = sorted(boxes)
        ok = True
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                fa, fb = flat(boxes[names[i]]), flat(boxes[names[j]])
                if len(fa) == len(fb) and all(abs(a - b) < 1e-6 for a, b in zip(fa, fb)):
                    continue
                ok = False
        check('bbox_consistency', ok,
              'SAB / facets / renderlist bounding boxes agree: '
              + str({k: [[round(x, 6) for x in p] for p in v] for k, v in boxes.items()}))

    # ---- package section -----------------------------------------------------
    package_section = {
        'path': pkg.path,
        'part_count': len(pkg.parts),
        'parts': [{
            'name': p.name, 'size': p.size,
            'compressed_size': p.compressed_size, 'content_type': p.content_type,
        } for p in pkg.parts],
        'relationships': [{
            'source': r.source, 'type': r.type_name, 'target': r.target,
        } for r in pkg.relationships],
        'key_parts': {
            'document': doc_part,
            'geometry': geom_parts[0].name if geom_parts else None,
            'facets': facets_part,
            'renderlist': render_part,
        },
    }

    all_checks = []
    for sec in (brep_section, mesh_section):
        if sec:
            all_checks.extend(sec.get('checks', []))
    all_checks.extend(checks)
    passed = sum(1 for c in all_checks if c['ok'])
    failed = [c['check'] for c in all_checks if not c['ok']]

    return {
        'file': path,
        'package': package_section,
        'document': doc_section,
        'geometry': brep_section,
        'mesh': mesh_section,
        'renderlist': {'views': render_views},
        'cross_checks': checks,
        'validation': {
            'total': len(all_checks),
            'passed': passed,
            'failed': failed,
            'all_ok': not failed,
        },
    }
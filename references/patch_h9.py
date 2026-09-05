# -*- coding: utf-8 -*-
"""H9: add write_scdoc_multi (multi-part assembly writer) to scdoc_write.py."""
import io

P = "scdm/scdoc_write.py"
s = io.open(P, encoding="utf-8").read()

anchor = 'def write_scdoc(path: str, kdoc, name: str = "design") -> None:'
assert anchor in s

ADD = r'''def write_scdoc_multi(path: str, kdoc, name: str = "design") -> int:
    """H9: multi-part assembly scdoc — one SAB per component plus a
    component-hierarchy document.xml.  Returns the number of parts."""
    from scdm.sab_emit import (Worklist, Makers, MAGIC, END_NAME, _s, _ri,
                               _td, T_FLAG_A, T_RECORD)

    def build_sab_for(items, colors):
        wl = Worklist()
        makers = Makers(items, colors)
        body = wl.run([("body", bi) for bi in range(len(items))], makers)
        out = bytearray()
        out += MAGIC
        blob = b"\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
        out += _ri(len(blob)) + blob
        out += _s("SpaceClaim")
        out += _s("ACIS 29.0 NT")
        out += _s("Mon Aug 24 00:13:12 2026")
        out += _td(1000.0) + _td(1e-8) + _td(1e-10)
        out += bytes([T_FLAG_A])
        out += _s("FQ8FFTTT5P7PJFMUMMYS2_J8B48CXKNEWAP4QAQV2CS3PP65QBQCNVPEFCMUSP6XAAPKK47XTA84Q")
        out += body
        out += bytes([T_RECORD, len(END_NAME)]) + END_NAME.encode("latin-1")
        return bytes(out)

    comps = list(kdoc.components)
    groups = []
    used = set()
    for comp in comps:
        bids = set(comp.body_ids)
        items, colors = [], []
        for b in kdoc.bodies:
            if b.id in bids and b.id not in used:
                items.append(_item_of(b))
                colors.append(tuple(getattr(b, "color", None)
                                    or (0.745, 0.902, 0.961)))
                used.add(b.id)
        if items:
            groups.append((comp.name, items, colors))
    rest_items, rest_colors = [], []
    for b in kdoc.bodies:
        if b.id not in used:
            rest_items.append(_item_of(b))
            rest_colors.append(tuple(getattr(b, "color", None)
                                     or (0.745, 0.902, 0.961)))
    if rest_items:
        groups.append((name or "design", rest_items, rest_colors))
    if not groups:
        raise ValueError("没有可写出的实体")

    import zipfile
    template = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "box.scdoc")
    doc_xml = _assembly_document_xml(kdoc, groups, name or "design")
    with zipfile.ZipFile(template) as src, \
            zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            if (n.endswith(".sab") or n.endswith("facets.bin")
                    or n.endswith("checksums.bin")
                    or n.endswith("checksums.bin.rels")):
                continue
            if n.endswith("document.xml"):
                out.writestr(n, doc_xml)
            elif n.endswith("document.xml.rels"):
                rels = ['<?xml version="1.0" encoding="utf-8"?>',
                        '<Relationships xmlns="http://schemas.openxmlformats'
                        '.org/package/2006/relationships">']
                for gi in range(len(groups)):
                    rels.append(
                        '  <Relationship Type="http://www.spaceclaim.com/'
                        'relationships/internal/partBodyGeometry#fc598e53-'
                        '8ab6-41b2-b8ea-b7917346ae70:' + str(gi + 2) +
                        '" Target="/SpaceClaim/Geometry/part' +
                        str(gi + 1) + 'bodies.sab" Id="Rg' + str(gi + 1) +
                        '"/>')
                rels.append('</Relationships>')
                out.writestr(n, "\n".join(rels).encode("utf-8"))
            else:
                out.writestr(n, src.read(n))
        for gi, (_gname, items, colors) in enumerate(groups):
            items2 = [it[:4] for it in items]
            out.writestr("SpaceClaim/Geometry/part%dbodies.sab" % (gi + 1),
                         build_sab_for(items2, colors))
    return len(groups)


def _item_of(body):
    """Extract the ('planar'|'cyl'|...) item tuple for one body."""
    sols = K.explore(body.shape, "solid") or [body.shape]
    s = sols[0]
    info = _cyl_info(s)
    if info is not None:
        return ("cyl", info)
    sfo = _sphere_info(s)
    if sfo is not None:
        return ("sphere", sfo)
    tfo = _torus_info(s)
    if tfo is not None:
        return ("torus", tfo)
    return ("planar",) + _extract_solid(s)


def _assembly_document_xml(kdoc, groups, name: str) -> bytes:
    """Full-generation document.xml: PartDef per component, per-face ids
    matching each part's SAB attrib ids, layer + named-view sections."""
    parts = []
    captions = []
    for gi, (gname, items, colors) in enumerate(groups):
        pid = 2 + gi * 60
        bid = 23 + gi * 60
        face_n = sum(len(it[3]) if it[0] == "planar"
                     else (1 if it[0] in ("sphere", "torus") else 3)
                     for it in items)
        edge_n = sum(len(it[2]) if it[0] == "planar"
                     else (1 if it[0] in ("sphere", "torus") else 2)
                     for it in items)
        c = colors[0] if colors else (0.745, 0.902, 0.961)
        rgb = "%d, %d, %d" % (int(c[0] * 255), int(c[1] * 255),
                              int(c[2] * 255))
        faces = "".join(
            '<NominalFaceDef Id="0:%d"/>' % (27 + 3 * k + gi * 60)
            for k in range(face_n))
        edges = "".join(
            '<NominalEdgeDef Id="0:%d"><isReversed>False</isReversed>'
            '</NominalEdgeDef>' % (45 + 3 * k + gi * 60)
            for k in range(edge_n))
        parts.append(
            '<PartDef Id="0:%d"><DefaultEdgeTreatmentDef Id="0:%d">'
            '<blendRadius>0</blendRadius></DefaultEdgeTreatmentDef>'
            '<NominalBodyDef Id="0:%d"><layerId>0:9</layerId>'
            '<type>Solid</type><color>%s</color>'
            '<renderingStyle>Plastic</renderingStyle>'
            '<fillStyle>Opaque</fillStyle>'
            '<finishStyle>MediumGloss</finishStyle>%s%s'
            '</NominalBodyDef></PartDef>'
            % (pid, 13 + gi * 60, bid, rgb, faces, edges))
        captions.append(
            '<CaptionDef Id="0:%d"><subjectId>0:%d</subjectId>'
            '<name>%s</name><type>Mutable</type></CaptionDef>'
            % (85 + gi * 60, bid, gname))
    layer = ('<PresentationDef sectionId="22222222-2222-2222-2222-'
             '222222222222" Id="0:5" xmlns="urn:presentation">'
             '<LayerDef Id="0:9"><name>Layer 1</name><visible>True</visible>'
             '<locked>False</locked><color>143, 175, 143</color></LayerDef>')
    for comp in getattr(kdoc, "components", []):
        layer += ('<LayerDef Id="0:%d"><name>%s</name>'
                  '<visible>%s</visible><locked>%s</locked>'
                  '<color>143, 175, 143</color></LayerDef>'
                  % (100 + (hash(comp.id) % 500), comp.name,
                     comp.visible, comp.anchored))
    layer += '</PresentationDef>'
    views = ('<SavedViewsDef sectionId="44444444-4444-4444-4444-'
             '444444444444" Id="0:6" xmlns="urn:view">')
    for v in getattr(kdoc, "views", []):
        views += ('<ViewDef><name>%s</name><position>%s</position>'
                  '<focal>%s</focal></ViewDef>'
                  % (v.get("name", "view"), v.get("pos", (0, 0, 1)),
                     v.get("focal", (0, 0, 0))))
    views += '</SavedViewsDef>'
    xml = ('<?xml version="1.0" encoding="utf-8"?>'
           '<Document version="1.520" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xmlns="urn:core"><nextId>109</nextId>'
           '<importPath>%s.scdoc</importPath>'
           '<importTimestamp>01/01/2026 00:00:00</importTimestamp>'
           '<Design sectionId="11111111-1111-1111-1111-111111111111" '
           'Id="0:1" xmlns="urn:nom">%s</Design>%s%s'
           '<DocumentSettingsDef sectionId="33333333-3333-3333-3333-'
           '333333333333" Id="0:16" xmlns="urn:presentation">'
           '<DocumentUnitsDef Id="0:17"><units><lengthProperties>'
           '<type>MM</type><factor>1000</factor><symbol>mm</symbol>'
           '<decimalPlaces>2</decimalPlaces></lengthProperties></units>'
           '</DocumentUnitsDef></DocumentSettingsDef>'
           '<PresentationDef2 sectionId="55555555-5555-5555-5555-'
           '555555555555" Id="0:7" xmlns="urn:nom">%s'
           '</PresentationDef2></Document>'
           % (name, "".join(parts), layer, views, "".join(captions)))
    return xml.encode("utf-8")


'''

s = s.replace(anchor, ADD + anchor, 1)
io.open(P, "w", encoding="utf-8").write(s)
print("write_scdoc_multi added")

# -*- coding: utf-8 -*-
# scdm_cases API signature probe (phase B second half). Writes _probe\probe_signatures.json. Not a corpus case.
CASE = {'case_id': 'probe_signatures_001', 'category': '_probe', 'feature': 'probe', 'priority': 'P9',
        'title': 'API signature probe', 'params': {}, 'expect': {}, 'commands': [],
        'out_dir': r'D:\training\caedecoder\scdm_cases\_probe'}

TYPES = ["StandardHoles", "Sketch2DRound", "ReplaceFacesWithFace", "SelectionPoint", "RectangleProfile", "CircleProfile",
         "PolygonProfile", "Profile", "Fill", "Wrap", "SplitEdge", "SplitFace", "ProjectToSolid", "FacetConvert", "FacetReduce",
         "STLFile", "Beam", "MetricUnits", "ImperialUnits", "Note", "CoordinateSystem", "MirrorComponents", "Midsurface",
         "Enclosure", "VolumeExtract", "Workpiece", "Hole", "DesignMesh", "ConvertToSolid", "StitchFaces", "FixMissingFaces",
         "FixExtraEdges", "ShareTopology", "ForceShareTopology", "IcepakSimplify", "IcepakSimplifyLevelZeroOptions",
         "IcepakSimplifyLevelOneOptions", "SheetMetalAspect", "Units", "HoleFit", "DepthMeasurement", "DrawingSheet",
         "ExtrudeProfile", "Layer", "RenameObject", "SurfaceBody", "Cylinder", "BoxUV", "FaceEdgeSplitter", "WrapDirections",
         "EnclosureCushion", "IEnclosureCushion", "CylinderBody", "DocumentSave", "FacetThicken", "FacetSmooth", "FacetRemesh"]
ENUMS = ["EnclosureType", "FaceSplitType", "FillMode", "FillType", "WrapDirections", "CrossSectionItemType", "CreationType",
         "HoleFit", "DepthMeasurement", "HoleDepthMeasurement", "MetricLengthUnit", "MetricMassUnit", "AngleUnit",
         "ImperialLengthUnit", "UnitsSystemType", "LocationPoint", "FacetQuality", "ThickenDirection", "StlInputOptions",
         "PartType", "InteractionMode", "FaceColorTarget", "DraftSide"]


def _types_named(name):
    out = []
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        try:
            ts = asm.GetExportedTypes()
        except Exception:
            continue
        for t in ts:
            if t.Name == name and (t.Namespace or "").startswith("SpaceClaim.Api") and ("V18" in t.Namespace or "V19" in t.Namespace):
                out.append(t)
    return out


def _tn(t):
    try:
        if t.IsGenericType:
            return "%s[%s]" % (t.Name.split("`")[0], ",".join(_tn(a) for a in t.GetGenericArguments()))
        return t.Name
    except Exception:
        return unicode(t)


def _sig(m):
    ps = []
    for p in m.GetParameters():
        s = "%s %s" % (_tn(p.ParameterType), p.Name)
        if p.IsOptional:
            s += "=opt"
        ps.append(s)
    return "(" + ", ".join(ps) + ")"


def build(ctx):
    block((0, 0, 0), (10, 10, 10), "Probe_Block")
    F = System.Reflection.BindingFlags
    out = {}
    for n in TYPES:
        for t in _types_named(n):
            d = {}
            d["ctors"] = [_sig(c) for c in t.GetConstructors()]
            d["static"] = sorted(set("%s%s -> %s" % (m.Name, _sig(m), _tn(m.ReturnType)) for m in t.GetMethods(F.Public | F.Static) if not m.Name.startswith("get_") and not m.Name.startswith("op_")))
            d["props"] = sorted(set("%s: %s" % (p.Name, _tn(p.PropertyType)) for p in t.GetProperties()))
            d["inst"] = sorted(set("%s%s -> %s" % (m.Name, _sig(m), _tn(m.ReturnType)) for m in t.GetMethods(F.Public | F.Instance) if not m.Name.startswith("get_") and not m.Name.startswith("set_") and m.DeclaringType == t))
            if t.IsEnum:
                d["enum"] = list(System.Enum.GetNames(t))
            out[t.FullName] = d
    for n in ENUMS:
        for t in _types_named(n):
            if t.IsEnum:
                out[t.FullName] = {"enum": list(System.Enum.GetNames(t))}
    # scripting types around sheet metal / flange / holes
    kw = ["SheetMetal", "Flange", "Unfold", "Bend", "Relief", "Hem", "Junction"]
    found = []
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        try:
            ts = asm.GetExportedTypes()
        except Exception:
            continue
        for t in ts:
            ns = t.Namespace or ""
            if ns.startswith("SpaceClaim.Api.V18") and any(k in t.Name for k in kw):
                found.append(t.FullName)
    out["_sheetmetal_types_V18"] = sorted(found)
    part = master(GetRootPart())
    out["_part_members"] = sorted(n for n in dir(part) if not n.startswith("_"))
    body = list(GetRootPart().Bodies)[0]
    out["_designbody_members"] = sorted(n for n in dir(master(body)) if not n.startswith("_"))
    out["_doc_members"] = sorted(n for n in dir(DocumentHelper.GetActiveDocument()) if not n.startswith("_"))
    out["_units_members"] = sorted(n for n in dir(DocumentHelper.GetActiveDocument().Units) if not n.startswith("_"))
    p = r"D:\training\caedecoder\scdm_cases\_probe\probe_signatures.json"
    write_text(p, js(out))
    ctx.data["probe_types"] = len(out)

if "SCDM_BATCH" not in globals():
    execfile(r"D:\training\caedecoder\scdm_cases\_framework\scdm_fw.py")
    run_standalone(CASE, build, r"D:\training\caedecoder\scdm_cases\_probe\probe_signatures_001.py")

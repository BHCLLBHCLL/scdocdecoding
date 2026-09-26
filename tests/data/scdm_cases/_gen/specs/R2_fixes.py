BATCH = "R2_fixes"
_MID = '''
def chk_mid():
    if not any(is_sheet(x) for x in all_bodies()):
        raise Exception("no midsurface sheet created")
def mk_mid():
    try:
        return Midsurface(MidsurfaceOptions())
    except Exception:
        return Midsurface()
def mid_pairs(pairs):
    m = mk_mid()
    for f1, f2 in pairs:
        m.AddMatchingFacePairs(f1, f2)
    m.Execute()
    chk_mid()
def mid_range(s, lo, hi):
    m = mk_mid()
    m.AddFacePairsByRange(s, MM(lo), MM(hi))
    m.Execute()
    chk_mid()
def mid_conv(s, t):
    Midsurface.Convert(s, MM(t))
    chk_mid()
'''
_HOLE = '''
def std_hole(ctx, b, x, y, opts):
    top = top_face(b)
    pt = P(x, y, bbox(b)[1][2])
    HL = find_type(ctx, "HoleLocation")
    _safe(lambda: ctor_sigs(ctx, "HoleLocation"))
    mf = master(top)
    uv = _safe(lambda: mf.Shape.ProjectPoint(pt).Param)
    pool = [("IDesignFace", top), ("DesignFace", mf), ("Point", pt), ("PointUV", uv),
            ("IList`1", List[Point]([pt])), ("ICollection`1", List[Point]([pt])), ("IEnumerable`1", List[Point]([pt]))]
    def by_null():
        loc = auto_new(ctx, "HoleLocation", HL, pool)
        L = List[HL]()
        L.Add(loc)
        return StandardHoles.Create(L, None, opts)
    def by_opts():
        loc = auto_new(ctx, "HoleLocation2", HL, pool)
        L = List[HL]()
        L.Add(loc)
        return StandardHoles.Create(L, opts)
    r = first_ok(ctx, "standard_hole", [by_null, by_opts])
    ctx.data["hole_result"] = _safe(lambda: [n for n in dir(r) if not n.startswith("_")])
    return r
o = StandardHolesOptions()
ctx.data["hole_opts_default"] = dict((n, _safe(lambda: unicode(getattr(o, n)))) for n in ["SeriesName", "FastenerName", "HoleFit", "HoleRadius", "DrillSize", "HoleDepth", "DepthMeasurement", "Tapped"])
'''
CASES = [
("12_prepare_midsurface_001_plate_t2", {"expect": {},
  "notes": "fix R2: Midsurface object with explicit face pair (top/bottom) first, then by thickness range, then Convert; each form checked for a created sheet"}, _MID + '''
b = block((0, 0, 0), (100, 50, 2), "Plate_T2")
first_ok(ctx, "midsurface", [lambda: mid_pairs([(top_face(b), bottom_face(b))]), lambda: mid_range(sel(b), 1.5, 2.5),
                             lambda: mid_conv(sel(b), 2)])
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x)] for x in all_bodies()]
sh = [x for x in all_bodies() if is_sheet(x)]
intent("has_sheet", bool(sh), True)
intent("sheet_z_mm", round(bbox(sh[0])[0][2], 3), 1.0, 0.01)
'''),
("12_prepare_midsurface_002_L_bracket_t3", {"expect": {},
  "notes": "fix R2: Midsurface by thickness range 2..4 mm on the merged L solid, then explicit face pairs, then Convert; each form checked"}, _MID + '''
a = block((0, 0, 0), (60, 40, 3), "L_Bracket")
w = block((0, 0, 3), (3, 40, 40), "L_Wall")
Combine.Merge(sel(a, w))
b = largest()
set_name(b, "L_Bracket")
first_ok(ctx, "midsurface", [lambda: mid_range(sel(b), 2, 4),
                             lambda: mid_pairs([(face_extreme(b, (0, 0, 1), -1), [f for f in b.Faces if gtype(f) == "Plane" and abs(bbox(f)[0][2] - 3) < 1e-6 and abs(bbox(f)[1][2] - 3) < 1e-6][0]),
                                                (face_extreme(b, (1, 0, 0), -1), [f for f in b.Faces if gtype(f) == "Plane" and abs(bbox(f)[0][0] - 3) < 1e-6 and abs(bbox(f)[1][0] - 3) < 1e-6][0])]),
                             lambda: mid_conv(sel(b), 3)])
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x)] for x in all_bodies()]
intent("has_sheet", any(is_sheet(x) for x in all_bodies()), True)
'''),
("12_prepare_volumeextract_001_pipe", {"expect": {},
  "notes": "fix R2: pipe built by Intersect keeping the 5654.9 mm3 tube region (the cutter is bigger than the tube, so 'keep largest' was wrong); VolumeExtract(caps, bore face) -> fluid volume 10053.1 mm3"}, '''
outer = cylinder((0, 0, 0), (0, 0, 50), 10, "Pipe")
inner = cylinder((0, 0, -5), (0, 0, 55), 8, "Bore_Cutter")
Combine.Intersect(sel(outer), sel(inner), MakeSolidsOptions())
pipe = min(bodies_now(), key=lambda x: abs((vol(x) or 0) - 5654.867))
rest = [x for x in bodies_now() if not (x == pipe)]
if rest:
    Delete.Execute(sel(rest))
set_name(pipe, "Pipe")
intent("pipe_volume_mm3", round(vol(pipe), 1), 5654.9, 0.5)
c1 = sheet_circle((0, 0, 0), 8, "Cap_Bottom")
c2 = sheet_circle((0, 0, 50), 8, "Cap_Top")
bore = [f for f in faces(pipe, "Cylinder") if abs(_safe(lambda: f.Shape.Geometry.Radius, 0) - MM(8)) < 1e-6]
ctx.data["bore_faces"] = len(bore)
caps = [face0(c1), face0(c2)]
def chk():
    if not any(abs((vol(x) or 0) - 10053.1) < 20 for x in all_bodies() if not is_sheet(x)):
        raise Exception("no fluid volume")
def v1():
    VolumeExtract.Create(sel(caps), sel(bore[0]))
    chk()
def v2():
    VolumeExtract.Create(sel(caps), sel(bore[0]), VolumeExtractOptions())
    chk()
def v3():
    VolumeExtract.Create(sel(bore[0]), sel(caps))
    chk()
first_ok(ctx, "volume_extract", [v1, v2, v3])
vols = sorted([round(vol(x) or 0, 1) for x in all_bodies() if not is_sheet(x)])
ctx.data["solid_volumes"] = vols
intent("fluid_present", any(abs(v - 10053.1) < 20 for v in vols), True)
'''),
("13_wrap_001_rect_onto_cylinder", {"expect": {},
  "notes": "fix R2: Wrap(sheet body, target) forms incl. body target and explicit WrapDirections; each form checked for an imprint on the cylinder"}, '''
cy = cylinder((0, 0, 0), (0, 0, 40), 10, "Wrap_Target_Cyl")
sh = planar(poly_curves([(10, -5, 15), (10, 5, 15), (10, 5, 25), (10, -5, 25)]), plane_at((10, 0, 20), (1, 0, 0)), "Wrap_Rect")
tgt = faces(cy, "Cylinder")[0]
o = WrapOptions()
ctx.data["wrap_opts_members"] = [n for n in dir(o) if not n.startswith("_")]
def cyl_faces():
    return max(face_count(x) for x in all_bodies() if not is_sheet(x))
def chk():
    if cyl_faces() <= 3:
        raise Exception("no imprint (faces=%d)" % cyl_faces())
def wd():
    w = (globals().get("WrapDirections") or find_type(ctx, "WrapDirections"))()
    w.BasePlane = plane_at((10, 0, 20), (1, 0, 0))
    w.SourcePoint = P(10, 0, 20)
    w.TargetPoint = P(10, 0, 20)
    w.SourceDirection = D(0, 1, 0)
    w.TargetDirection = D(0, 1, 0)
    return w
def w1():
    Wrap.Create(sel(sh), sel(cy), o)
    chk()
def w2():
    Wrap.Create(sel(sh), sel(tgt), wd(), o)
    chk()
def w3():
    Wrap.Create(sel(sh), sel(cy), wd(), o)
    chk()
def w4():
    Wrap.Create(sel(face0(sh)), sel(cy), o)
    chk()
first_ok(ctx, "wrap", [w1, w2, w3, w4])
ctx.data["cyl_faces"] = cyl_faces()
intent_range("cyl_faces_after_imprint", cyl_faces(), 4, 12)
'''),
("13_convertsolid_001_closed_sheets", {"expect": {"bodies": 1},
  "notes": "reinterpreted (R2): V19 ConvertToSolid only accepts a Mesh selection ('must include a Mesh selection'); block 20 mm -> FacetConvert mesh -> ConvertToSolid(mergeFaces=True) -> solid 8000 mm3"}, '''
b = block((0, 0, 0), (20, 20, 20), "Convert_Source")
FacetConvert.Create(sel(b), FacetConvertOptions())
m = list(GetRootPart().Meshes)[0]
ctx.data["meshes_before"] = len(list(GetRootPart().Meshes))
first_ok(ctx, "convert", [lambda: ConvertToSolid.Execute(sel(m), True), lambda: ConvertToSolid.Execute(sel(m), False)])
_safe(lambda: set_name(largest(), "Converted_Solid"))
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x), round(vol(x) or 0, 1), face_count(x)] for x in all_bodies()]
intent("solid_8000", any((not is_sheet(x)) and abs((vol(x) or 0) - 8000) < 1 for x in all_bodies()), True)
'''),
("14_hole_cbore_001_M6", {"expect": {"bodies": 1},
  "notes": "fix R2: secondarySelection None instead of Selection.Empty(); explicit HoleRadius 3.2 mm (options default radius is 0)"}, _HOLE + '''
b = block((0, 0, 0), (40, 30, 20), "Cbore_Block")
setp(ctx, o, [("SeriesName", "ISO"), ("FastenerName", "M6"), ("HoleFit", _safe(lambda: HoleFit.Medium)), ("HoleRadius", MM(3.2)),
              ("CounterboreRadius", MM(5.5)), ("CounterboreDepth", MM(6.5)), ("HoleDepth", MM(15))], "hole_opts")
std_hole(ctx, b, 20, 15, o)
ctx.data["faces_after"] = face_count(largest())
intent_range("volume_removed_mm3", 24000 - total_volume(), 100, 2000)
'''),
("14_hole_tapped_001_M8_cosmetic", {"expect": {"bodies": 1},
  "notes": "fix R2: secondarySelection None; explicit HoleRadius 3.4 mm (M8 tap drill 6.8)"}, _HOLE + '''
b = block((0, 0, 0), (40, 30, 20), "Tapped_Block")
setp(ctx, o, [("SeriesName", "ISO"), ("FastenerName", "M8"), ("Tapped", True), ("HoleRadius", MM(3.4)), ("HoleDepth", MM(15))], "hole_opts")
r = std_hole(ctx, b, 20, 15, o)
ctx.attempt("cosmetic", lambda: StandardHoles.ModifyCosmeticThread(sel(faces(largest(), "Cylinder")), True))
intent_range("volume_removed_mm3", 24000 - total_volume(), 300, 1500)
'''),
("15_mesh_stl_import_001", {"expect": {"components": 1},
  "notes": "fix R2: STL exported by this case to 15_mesh_facet\\\\_inputs (scdm_cases only), then inserted; SpaceClaim puts the mesh into a new component, so the mesh is counted inside components"}, '''
import System
d = System.IO.Path.Combine(CASE["out_dir"], "_inputs")
if not System.IO.Directory.Exists(d):
    System.IO.Directory.CreateDirectory(d)
stl = System.IO.Path.Combine(d, "cylinder_r10_h30.stl")
cylinder((0, 0, 0), (0, 0, 30), 10, "Stl_Source_Cyl")
first_ok(ctx, "export_stl", [lambda: STLFile.Export(stl), lambda: DocumentSave.Execute(stl)])
ctx.data["stl_bytes"] = _safe(lambda: System.IO.FileInfo(stl).Length)
Delete.Execute(sel(bodies_now()))
io = STLImportOptions()
setp(ctx, io, [("ImportType", _safe(lambda: enum_pick(type(io.ImportType), "ConnectedMesh")))], "stl_opts")
first_ok(ctx, "insert_stl", [lambda: STLFile.Insert(stl, io), lambda: DocumentInsert.Execute(stl)])
ms = []
for c in GetRootPart().Components:
    ms += list(_safe(lambda: c.Template.Meshes, []) or [])
ms += list(GetRootPart().Meshes)
ctx.data["meshes_found"] = len(ms)
if ms:
    _safe(lambda: set_name(ms[0], "Imported_Cyl_Mesh"))
intent("meshes_in_doc", len(ms), 1)
'''),
("15_mesh_reduce_001_50pct", {"expect": {"meshes": 1},
  "notes": "fix R2: facet count read via several mesh shape members; coarse sphere r10 to keep FacetReduce fast"}, '''
s = sphere((0, 0, 0), 10, "Reduce_Sphere")
FacetConvert.Create(sel(s), FacetConvertOptions())
m = list(GetRootPart().Meshes)[0]
_safe(lambda: set_name(m, "Sphere_Mesh"))
def nfac():
    mm = list(GetRootPart().Meshes)[0]
    sh = mm.Shape
    for f in [lambda: sh.Facets.Count, lambda: len(list(sh.Facets)), lambda: sh.FacetCount, lambda: sh.NumberOfFacets,
              lambda: sh.Triangles.Count, lambda: len(list(sh.Triangles))]:
        v = _safe(f)
        if v:
            return int(v)
    return None
ctx.data["mesh_shape_members"] = _safe(lambda: [n for n in dir(m.Shape) if not n.startswith("_")][:80])
n0 = nfac()
o = FacetReduceOptions()
ctx.data["fr_defaults"] = [_safe(lambda: unicode(o.DefaultTriangleReduction)), _safe(lambda: unicode(o.DefaultMaxError))]
setp(ctx, o, [("TriangleReduction", 0.5)], "fr_opts")
first_ok(ctx, "reduce", [lambda: FacetReduce.Create(sel(m), o), lambda: FacetReduce.Create(sel(list(GetRootPart().Meshes)), o)])
n1 = nfac()
ctx.data["facets"] = [n0, n1]
if n0 and n1:
    intent("reduced", n1 < n0, True)
'''),
]
_WRAP = """
def wrap_rect(ctx, cy, sh):
    tgt = faces(cy, "Cylinder")[0]
    o = WrapOptions()
    ctx.data["wrap_opts_members"] = [n for n in dir(o) if not n.startswith("_")]
    def cyl_faces():
        return max(face_count(x) for x in all_bodies() if not is_sheet(x))
    def chk():
        if cyl_faces() <= 3:
            raise Exception("no imprint (faces=%d)" % cyl_faces())
    def wd():
        w = (globals().get("WrapDirections") or find_type(ctx, "WrapDirections"))()
        w.BasePlane = plane_at((10, 0, 20), (1, 0, 0))
        w.SourcePoint = P(10, 0, 20)
        w.TargetPoint = P(10, 0, 20)
        w.SourceDirection = D(0, 1, 0)
        w.TargetDirection = D(0, 1, 0)
        return w
    def w1():
        Wrap.Create(sel(sh), sel(cy), o)
        chk()
    def w2():
        Wrap.Create(sel(sh), sel(tgt), wd(), o)
        chk()
    def w3():
        Wrap.Create(sel(sh), sel(cy), wd(), o)
        chk()
    def w4():
        Wrap.Create(sel(face0(sh)), sel(cy), o)
        chk()
    first_ok(ctx, "wrap", [w1, w2, w3, w4])
    return cyl_faces()
"""
B = {}
B["20_combo_asm_014_two_components"] = ("fix R2: component display name lives on the component template; name set with checked forms (ComponentHelper.SetName / RenameObject / Template.Name) and read back from Name or Template.Name", {"components": 2, "bodies": 2}, """
cp = component("Plate", lambda: block((0, 0, 0), (60, 40, 10), "Plate_Body"))
cb = component("Boss", lambda: cylinder((30, 20, 10), (30, 20, 30), 8, "Boss_Body"))
def cname(c):
    return [unicode(_safe(lambda: c.Name, "")), unicode(_safe(lambda: c.Template.Name, "")), unicode(_safe(lambda: master(c).Template.Name, ""))]
def chk():
    if u"Base_Plate" not in cname(cp):
        raise Exception("name not visible: %s" % cname(cp))
def s1():
    ComponentHelper.SetName(cp, "Base_Plate")
    chk()
def s2():
    RenameObject.Execute(sel(cp), "Base_Plate")
    chk()
def s3():
    raw("template_name", lambda: setattr(master(cp).Template, "Name", "Base_Plate"))
    chk()
ctx.data["names_before"] = [cname(x) for x in GetRootPart().Components]
first_ok(ctx, "setname", [s1, s2, s3])
ctx.data["component_names"] = [cname(x) for x in GetRootPart().Components]
intent("has_Base_Plate", any(u"Base_Plate" in cname(x) for x in GetRootPart().Components), True)
""")
B["20_combo_helix_023_spring_ends_ground"] = ("fix R2: helical-sweep bboxes are loose, so the two end pieces after splitting at z=2/z=18 are identified as the two smallest pieces (not by bbox)", {"bodies": 1}, """
r = CircularSurface.Create(MM(1), D(0, 1, 0), P(10, 0, 0))
RevolveFaces.ByHelix(sel(face0(r.CreatedBody)), axis_line(), D(0, 0, 1), MM(20), MM(5), 0.0, True, False, RevolveFaceOptions())
delete_sheets()
v_full = vol(largest())
ctx.data["volume_full_mm3"] = v_full
SplitBody.ByCutter(sel(largest()), plane_xy(2))
SplitBody.ByCutter(sel([x for x in bodies_now()]), plane_xy(18))
ps = sorted(bodies_now(), key=lambda x: vol(x) or 0)
ctx.data["piece_volumes"] = [vol(x) for x in ps]
gone = ps[:-1] if len(ps) >= 3 else []
ctx.data["pieces_deleted"] = len(gone)
if gone:
    Delete.Execute(sel(gone))
name_bodies(["Spring"])
intent("pieces_deleted", len(gone), 2)
intent_range("kept_fraction", total_volume() / v_full, 0.70, 0.90)
""")
B["20_combo_wrap_026_cylinder_wrap_text_pull"] = ("fix R2: wrap forms checked for an imprint (body target / WrapDirections), then the imprinted patch pulled out 1 mm", {"bodies": 1}, _WRAP + """
cy = cylinder((0, 0, 0), (0, 0, 40), 10, "Wrap_Cyl")
sh = planar(poly_curves([(10, -5, 15), (10, 5, 15), (10, 5, 25), (10, -5, 25)]), plane_at((10, 0, 20), (1, 0, 0)), "Wrap_Rect")
nf = wrap_rect(ctx, cy, sh)
ctx.data["faces_after_wrap"] = nf
delete_sheets()
cy = largest()
small = min([f for f in cy.Faces if gtype(f) != "Plane"], key=lambda f: shape_of(f).Area)
first_ok(ctx, "pull", [lambda: ExtrudeFaces.Execute(sel(small), MM(1), ExtrudeFaceOptions())])
name_bodies(["Wrap_Cyl"], [largest()])
intent_range("volume_gain_mm3", total_volume() - 3.14159265 * 100 * 40, 50, 150)
""")
B["20_combo_edit_030_pull_after_pattern"] = ("fix R2: patterning a whole body creates pattern components, so the boss is merged first and its faces are patterned (4 bosses on one body); then the plate bottom is pulled 2 mm and the boss top edges rounded", {"bodies": 1}, """
plate = block((0, 0, 0), (60, 40, 5), "Base_Plate")
boss = cylinder((10, 20, 5), (10, 20, 10), 3, "Boss")
Combine.Merge(sel(plate, boss))
b = largest()
bf = [f for f in b.Faces if _dist(bbox_center(f), (10, 20, 7.5)) < 3.0]
ctx.data["boss_faces"] = len(bf)
dirc = dcurve(seg((0, -5, 0), (10, -5, 0)), "Pattern_Direction_X")
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("LinearDirection", sel(dirc)), ("CountX", 4), ("PitchX", MM(12))], "linear")
Pattern.CreateLinear(sel(bf), d, None)
b = largest()
extrude(bottom_face(b), 2)
b = largest()
tops = [e for e in edges_at_z(b, 10)]
ConstantRound.Execute(sel(tops), MM(1), ConstantRoundOptions())
name_bodies(["Base_Plate"], [largest()])
intent("bodies", len(bodies_now()), 1)
intent("boss_top_edges", len(tops), 4)
intent_range("volume_mm3", total_volume(), 60 * 40 * 7 + 4 * 3.14159265 * 9 * 5 - 60, 60 * 40 * 7 + 4 * 3.14159265 * 9 * 5)
""")
B["20_combo_mesh_032_mesh_plus_solid"] = ("fix R2: headless Copy/Paste left no body, so the second cylinder is modelled directly and converted to a facet mesh", {"bodies": 1, "meshes": 1}, """
c = cylinder((0, 0, 0), (0, 0, 30), 10, "Solid_Cyl")
c2 = cylinder((40, 0, 0), (40, 0, 30), 10, "Cyl_To_Mesh")
FacetConvert.Create(sel(c2), FacetConvertOptions())
_safe(lambda: set_name(list(GetRootPart().Meshes)[0], "Cyl_Mesh"))
intent("solid_volume_mm3", round(total_volume(), 1), round(3.14159265 * 100 * 30, 1), 1.0)
""")
import json as _json, os as _os
_PLAN = {c["case_key"]: c for c in _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "_inventory", "combo_plan.json"), encoding="utf-8"))["combos"]}
for _k in B:
    _c = _PLAN[_k]
    _n, _e, _b = B[_k]
    CASES.append((_k, {"category": "20_combo", "feature": "combo", "priority": _c["priority"], "title": _c["title"],
                       "commands": _c["features"], "inventory_expect": _c.get("expect"), "expect": _e,
                       "notes": _n + " | steps: " + "; ".join(_c["steps"]) + " | headless_feasibility: " + _c.get("headless_feasibility", "")}, _b))

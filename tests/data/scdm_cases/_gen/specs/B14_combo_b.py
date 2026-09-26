BATCH = "B14_combo_b"
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
    def by_auto():
        loc = auto_new(ctx, "HoleLocation", HL, pool)
        L = List[HL]()
        L.Add(loc)
        return StandardHoles.Create(L, None, opts)
    def by_auto2():
        loc = auto_new(ctx, "HoleLocation2", HL, pool)
        L = List[HL]()
        L.Add(loc)
        return StandardHoles.Create(L, opts)
    r = first_ok(ctx, "standard_hole", [by_auto, by_auto2])
    ctx.data["hole_result"] = _safe(lambda: [n for n in dir(r) if not n.startswith("_")])
    return r
'''
_BEAM = '''
def nn(x):
    if x is None:
        raise Exception("None")
    return x
def profile_part(ctx, r):
    ctx.data["profile_result_members"] = _safe(lambda: [n for n in dir(r) if not n.startswith("_")][:40])
    comps = list(GetRootPart().Components)
    return first_ok(ctx, "profile_part", [lambda: nn(_safe(lambda: r.CreatedProfile)), lambda: nn(comps[-1].Template),
                                          lambda: nn(master(comps[-1]).Template)])
def make_beams(ctx, prof, curves):
    BM = rawt("Beam")
    out = []
    for c in curves:
        out.append(first_ok(ctx, "beam", [lambda: raw("beam", lambda: BM.Create(prof, master(c))),
                                          lambda: raw("beam", lambda: BM.Create(prof, c)),
                                          lambda: Beam.Create(sel(c), prof)]))
    return out
'''
_DRAFT = '''
def drafted(ctx, name, kind="block"):
    """Draft the side faces so the part narrows towards the top (neutral plane = bottom face). Tries angle sign /
    draft side combinations on a fresh body and keeps the first whose volume shrinks and whose bbox stays inside."""
    import math
    forms = [("This", -5), ("This", 5), ("Other", 5), ("Other", -5), ("NoSplit", -5), ("NoSplit", 5)]
    ang0 = 5 if kind == "block" else 3
    v_full = 24000.0 if kind == "block" else math.pi * 100 * 20
    lim = (0.0, 40.0) if kind == "block" else (-10.0, 10.0)
    log = []
    for sd, sgn in forms:
        if bodies_now():
            Delete.Execute(sel(bodies_now()))
        if kind == "block":
            b = block((0, 0, 0), (40, 30, 20), name)
            sides = [face_extreme(b, a, s) for a in [(1, 0, 0), (0, 1, 0)] for s in (1, -1)]
        else:
            b = cylinder((0, 0, 0), (0, 0, 20), 10, name)
            sides = faces(b, "Cylinder")
        ang = ang0 if sgn > 0 else -ang0
        try:
            DraftFaces.Execute(sel(sides), sel(bottom_face(b)), getattr(DraftSide, sd), DEG(ang), getattr(ExtrudeType, "None"), DraftOptions())
        except Exception as e:
            log.append([sd, ang, "error: " + unicode(e)[:120]])
            continue
        b = largest()
        v, bb = vol(b), bbox(b)
        log.append([sd, ang, v, bb])
        if v is not None and v < v_full - 1.0 and bb[0][0] >= lim[0] - 1e-3 and bb[1][0] <= lim[1] + 1e-3:
            ctx.data["draft_form"] = [sd, ang]
            ctx.data["draft_log"] = log
            return b
    ctx.data["draft_log"] = log
    raise Exception("no draft form narrowed the part inward: %s" % log)
'''
B = {}
E = {}
B["20_combo_asm_017_mates_align_tangent"] = '''
plate = block((0, 0, 0), (60, 40, 10), "Plate_Body")
subtract(ctx, plate, cylinder((30, 20, -5), (30, 20, 15), 4, "Hole_Cutter"))
set_name(largest(), "Plate_Body")
cylinder((100, 20, 5), (100, 20, 35), 4, "Pin_Body")
ComponentHelper.CreateSeparateComponents(sel(bodies_now()))
comps = list(GetRootPart().Components)
cp = [c for c in comps if any(x.Name == "Plate_Body" for x in comp_bodies(c))][0]
cq = [c for c in comps if any(x.Name == "Pin_Body" for x in comp_bodies(c))][0]
pb = comp_bodies(cp)[0]
pin = comp_bodies(cq)[0]
raw("align", lambda: AlignCondition.Create(GetRootPart(), faces(pb, "Cylinder")[0], faces(pin, "Cylinder")[0]))
raw("tangent", lambda: TangentCondition.Create(GetRootPart(), top_face(pb), bottom_face(pin)))
'''
E["20_combo_asm_017_mates_align_tangent"] = {"components": 2, "mating_conditions": 2}
B["20_combo_sm_018_sheetmetal_bracket"] = '''
a = block((0, 0, 0), (100, 50, 2), "U_Bracket")
w1 = block((0, 0, 2), (2, 50, 22), "Wall_1")
w2 = block((98, 0, 2), (100, 50, 22), "Wall_2")
Combine.Merge(sel(a, w1, w2))
root = GetRootPart()
raw("sheetmetal", lambda: master(root).ConvertToSheetMetal())
b = largest()
asp = master(root).SheetMetal
LE = List[rawt("DesignEdge")]
cre = [edge_nearest(b, (2, 25, 2)), edge_nearest(b, (98, 25, 2))]
first_ok(ctx, "bends", [lambda: raw("bend", lambda: asp.CreateMissingBends(LE([master(e) for e in cre]), MM(1)))])
ctx.data["faces_after_bends"] = face_count(largest())
f = first_ok(ctx, "unfold", [lambda: raw("unfold", lambda: asp.Unfold(master(bottom_face(largest()))))])
ctx.data["bboxes"] = [bbox(x) for x in all_bodies()]
'''
E["20_combo_sm_018_sheetmetal_bracket"] = {}
B["20_combo_beam_019_frame_with_profiles"] = _BEAM + '''
hz = [((0, 0, 0), (1000, 0, 0)), ((1000, 0, 0), (1000, 500, 0)), ((1000, 500, 0), (0, 500, 0)), ((0, 500, 0), (0, 0, 0))]
vt = [((0, 0, 0), (0, 0, 800)), ((1000, 0, 0), (1000, 0, 800))]
ch = [dcurve(seg(p, q), "Frame_H_%d" % (i + 1)) for i, (p, q) in enumerate(hz)]
cv = [dcurve(seg(p, q), "Frame_V_%d" % (i + 1)) for i, (p, q) in enumerate(vt)]
pi = profile_part(ctx, BeamProfile.CreateI(MM(50), MM(100), MM(8), MM(5), "I_100x50"))
make_beams(ctx, pi, ch)
pr = profile_part(ctx, BeamProfile.CreateRectangular(MM(3), MM(60), MM(40), "Rect_Tube_60x40x3"))
bv = make_beams(ctx, pr, cv)
ctx.attempt("orientation", lambda: Beam.SetOrientation(sel(bv), DEG(30)))
'''
E["20_combo_beam_019_frame_with_profiles"] = {"beams": 6}
B["20_combo_prep_020_midsurface_share_topology"] = '''
a = block((0, 0, 0), (100, 50, 3), "Plate_Base")
b = block((48.5, 0, 3), (51.5, 50, 40), "Plate_Web")
def chk_mid():
    if not any(is_sheet(x) for x in all_bodies()):
        raise Exception("no midsurface sheet created")
def mk_mid():
    try:
        return Midsurface(MidsurfaceOptions())
    except Exception:
        return Midsurface()
def mid_range():
    m = mk_mid()
    m.AddFacePairsByRange(sel(a, b), MM(2), MM(4))
    m.Execute()
    chk_mid()
def mid_pairs():
    m = mk_mid()
    m.AddMatchingFacePairs(top_face(a), bottom_face(a))
    m.AddMatchingFacePairs(face_extreme(b, (1, 0, 0), 1), face_extreme(b, (1, 0, 0), -1))
    m.Execute()
    chk_mid()
def mid_conv():
    Midsurface.Convert(sel(a, b), MM(3))
    chk_mid()
first_ok(ctx, "midsurface", [mid_range, mid_pairs, mid_conv])
ctx.data["after_mid"] = [[unicode(x.Name), is_sheet(x)] for x in all_bodies()]
first_ok(ctx, "share", [lambda: ShareTopology.FindAndFix(sel(all_bodies()), ShareTopologyOptions()), lambda: ShareTopology.FindAndFix()])
intent_range("sheet_bodies", len([x for x in all_bodies() if is_sheet(x)]), 1, 3)
'''
E["20_combo_prep_020_midsurface_share_topology"] = {}
B["20_combo_prep_021_enclosure_named_selection"] = '''
b = block((0, 0, 0), (40, 30, 20), "Inner_Body")
o = EnclosureOptions()
setp(ctx, o, [("EnclosureType", _safe(lambda: EnclosureType.Box))], "encl_opts")
Enclosure.Create(sel(b), o)
enc = [x for x in all_bodies() if x.Name != "Inner_Body"]
ctx.data["enclosure_names"] = [unicode(x.Name) for x in enc]
e = max(enc, key=lambda x: bbox(x)[1][0] - bbox(x)[0][0])
set_name(e, "Enclosure_Box")
r = NamedSelection.Create(sel(face_extreme(e, (1, 0, 0), -1)), Selection.Empty())
NamedSelection.Rename(unicode(r.CreatedNamedSelection.Name), "Inlet")
r = NamedSelection.Create(sel(face_extreme(e, (1, 0, 0), 1)), Selection.Empty())
NamedSelection.Rename(unicode(r.CreatedNamedSelection.Name), "Outlet")
intent("ns_count", len(doc_stats()["named_selections"]), 2)
'''
E["20_combo_prep_021_enclosure_named_selection"] = {"bodies": 2}
B["20_combo_hole_022_holes_pattern_plate"] = _HOLE + '''
plate = cylinder((0, 0, 0), (0, 0, 10), 50, "Hole_Disk")
o = StandardHolesOptions()
setp(ctx, o, [("SeriesName", "ISO"), ("FastenerName", "M6"), ("HoleRadius", MM(3.2)), ("CounterboreRadius", MM(5.5)), ("CounterboreDepth", MM(6.5)), ("HoleDepth", MM(10))], "hole_opts")
std_hole(ctx, plate, 30, 0, o)
p = largest()
hf = [f for f in p.Faces if gtype(f) != "Plane" and _dist(bbox_center(f), (30, 0, 5)) < 8]
outer = max(faces(p, "Cylinder"), key=lambda f: bbox(f)[1][0] - bbox(f)[0][0])
d = CircularPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("CircularAxis", sel(outer)), ("CircularCount", 4), ("CircularAngle", DEG(360))], "circular")
first_ok(ctx, "pattern", [lambda: Pattern.CreateCircular(sel(hf), d, None)])
ctx.data["faces_after"] = face_count(largest())
'''
E["20_combo_hole_022_holes_pattern_plate"] = {"bodies": 1}
B["20_combo_helix_023_spring_ends_ground"] = '''
r = CircularSurface.Create(MM(1), D(0, 1, 0), P(10, 0, 0))
RevolveFaces.ByHelix(sel(face0(r.CreatedBody)), axis_line(), D(0, 0, 1), MM(20), MM(5), 0.0, True, False, RevolveFaceOptions())
delete_sheets()
SplitBody.ByCutter(sel(largest()), plane_xy(2))
SplitBody.ByCutter(sel([x for x in bodies_now()]), plane_xy(18))
gone = [x for x in bodies_now() if bbox(x)[1][2] <= 2.001 or bbox(x)[0][2] >= 17.999]
ctx.data["pieces_deleted"] = len(gone)
if gone:
    Delete.Execute(sel(gone))
name_bodies(["Spring"])
bb = [bbox(x) for x in bodies_now()]
intent("z_min_mm", round(min(x[0][2] for x in bb), 3), 2.0, 0.01)
intent("z_max_mm", round(max(x[1][2] for x in bb), 3), 18.0, 0.01)
'''
E["20_combo_helix_023_spring_ends_ground"] = {}
B["20_combo_draft_024_molded_part"] = _DRAFT + '''
b = drafted(ctx, "Molded_Part")
ConstantRound.Execute(sel(edges_at_z(largest(), 20)), MM(2), ConstantRoundOptions())
Shell.RemoveFaces(sel(bottom_face(largest())), MM(-1.5))
name_bodies(["Molded_Part"], [largest()])
intent_range("volume_mm3", total_volume(), 2000, 9000)
'''
E["20_combo_draft_024_molded_part"] = {"bodies": 1}
B["20_combo_surface_025_sheets_stitch_thicken"] = '''
import math
a = sheet_rect(0, 0, 20, 20, 0, "Sheet_Floor")
w = planar(poly_curves([(20, 0, 0), (20, 20, 0), (20, 20, 20), (20, 0, 20)]), plane_at((20, 10, 10), (1, 0, 0)), "Sheet_Wall")
srf = Cylinder.Create(Frame.Create(P(0, 0, 0), D(1, 0, 0), D(0, 1, 0)), MM(5))
ctx.attempt("surface_body", lambda: SurfaceBody.Create(srf, BoxUV.Create(Interval.Create(0, math.pi), Interval.Create(MM(30), MM(40))), GetRootPart(), "Cyl_Patch"))
first_ok(ctx, "stitch", [lambda: StitchFaces.FindAndFix(sel(a, w)), lambda: StitchFaces.FindAndFix(sel(a, w), StitchOptions())])
st = [x for x in all_bodies() if is_sheet(x) and face_count(x) == 2]
ctx.data["stitched"] = len(st)
tgt = st[0] if st else a
first_ok(ctx, "thicken", [lambda: ThickenFaces.Execute(sel(list(tgt.Faces)), MM(1), ThickenFaceOptions()),
                          lambda: ThickenFaces.Execute(sel(list(tgt.Faces)), D(0, 0, 1), MM(1), ThickenFaceOptions()),
                          lambda: ThickenFaces.Execute(sel(tgt), MM(1), ThickenFaceOptions())])
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x), round(vol(x) or 0, 1)] for x in all_bodies()]
intent("stitched_two_face_sheet", len(st), 1)
intent("has_solid", any(not is_sheet(x) for x in all_bodies()), True)
'''
E["20_combo_surface_025_sheets_stitch_thicken"] = {}
B["20_combo_wrap_026_cylinder_wrap_text_pull"] = '''
cy = cylinder((0, 0, 0), (0, 0, 40), 10, "Wrap_Cyl")
sh = planar(poly_curves([(10, -5, 15), (10, 5, 15), (10, 5, 25), (10, -5, 25)]), plane_at((10, 0, 20), (1, 0, 0)), "Wrap_Rect")
tgt = faces(cy, "Cylinder")[0]
first_ok(ctx, "wrap", [lambda: Wrap.Create(sel(face0(sh)), sel(tgt), WrapOptions()), lambda: Wrap.Create(sel(sh), sel(tgt), WrapOptions())])
delete_sheets()
cy = largest()
small = min([f for f in cy.Faces if gtype(f) != "Plane"], key=lambda f: shape_of(f).Area)
first_ok(ctx, "pull", [lambda: ExtrudeFaces.Execute(sel(small), MM(1), ExtrudeFaceOptions())])
name_bodies(["Wrap_Cyl"], [largest()])
intent_range("volume_gain_mm3", total_volume() - 3.14159265 * 100 * 40, 50, 150)
'''
E["20_combo_wrap_026_cylinder_wrap_text_pull"] = {"bodies": 1}
B["20_combo_units_027_inch_doc_primitives"] = '''
doc = DocumentHelper.GetActiveDocument()
raw("units", lambda: setattr(doc.Units, "ActiveUnitsSystem", UnitsSystemType.Imperial))
_safe(lambda: raw("iu", lambda: setattr(doc.Units, "ImperialUnits", rawt("ImperialUnits")(ImperialLengthUnit.Inches, enum_pick(rawt("ImperialMassUnit"), "Pounds", "PoundMass"), rawt("AngleUnit").Degrees))))
block((0, 0, 0), (25.4, 50.8, 76.2), "Block_1x2x3in")
cylinder((50.8, 25.4, 0), (50.8, 25.4, 25.4), 12.7, "Cyl_D1in_H1in")
intent("units_system", unicode(doc.Units.ActiveUnitsSystem), u"Imperial")
intent("volume_mm3", round(total_volume(), 1), round(25.4 ** 3 * (6 + 3.14159265 * 0.25), 1), 5.0)
'''
E["20_combo_units_027_inch_doc_primitives"] = {"bodies": 2}
B["20_combo_multi_028_many_bodies_8"] = '''
bs = []
for i in range(8):
    x = 30 * i
    if i % 3 == 0:
        bs.append(block((x, 0, 0), (x + 20, 20, 10 + i), "Body_%d_Block" % (i + 1)))
    elif i % 3 == 1:
        bs.append(cylinder((x + 10, 10, 0), (x + 10, 10, 15 + i), 8, "Body_%d_Cyl" % (i + 1)))
    else:
        bs.append(sphere((x + 10, 10, 10), 9, "Body_%d_Sphere" % (i + 1)))
for i, b in enumerate(bs):
    ColorHelper.SetColor(sel(b), SetColorOptions(), Color.FromArgb(255, (37 * i) % 256, (91 * i) % 256, (53 * i + 60) % 256))
intent("names_unique", len(set(unicode(b.Name) for b in all_bodies())), 8)
'''
E["20_combo_multi_028_many_bodies_8"] = {"bodies": 8}
B["20_combo_multi_029_many_components_8"] = '''
for i in range(8):
    component("Comp_%d" % (i + 1), lambda: block((30 * i, 0, 0), (30 * i + 20, 20, 10 + 2 * i), "Comp_%d_Body" % (i + 1)))
'''
E["20_combo_multi_029_many_components_8"] = {"components": 8, "bodies": 8}
B["20_combo_edit_030_pull_after_pattern"] = '''
plate = block((0, 0, 0), (60, 40, 5), "Base_Plate")
boss = cylinder((10, 20, 5), (10, 20, 10), 3, "Boss")
dirc = dcurve(seg((0, -5, 0), (10, -5, 0)), "Pattern_Direction_X")
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("LinearDirection", sel(dirc)), ("CountX", 4), ("PitchX", MM(12))], "linear")
Pattern.CreateLinear(sel(boss), d, None)
Combine.Merge(sel(bodies_now()))
b = largest()
extrude(bottom_face(b), 2)
b = largest()
tops = [e for e in edges_at_z(b, 10)]
ConstantRound.Execute(sel(tops), MM(1), ConstantRoundOptions())
name_bodies(["Base_Plate"], [largest()])
intent("boss_top_edges", len(tops), 4)
intent_range("volume_mm3", total_volume(), 60 * 40 * 7 + 4 * 3.14159265 * 9 * 5 - 60, 60 * 40 * 7 + 4 * 3.14159265 * 9 * 5)
'''
E["20_combo_edit_030_pull_after_pattern"] = {"bodies": 1}
B["20_combo_view_031_named_views_section"] = '''
cp = component("Plate", lambda: block((0, 0, 0), (60, 40, 10), "Plate_Body"))
cb = component("Boss", lambda: cylinder((30, 20, 10), (30, 20, 30), 8, "Boss_Body"))
ViewHelper.SetProjection(ViewHelper.ViewProjection.Isometric, True, False)
ViewHelper.CreateNamedView("Iso_Assembly")
ViewHelper.SetProjection(ViewHelper.ViewProjection.Front, True, False)
ViewHelper.CreateNamedView("Front_Assembly")
r = ViewHelper.SetSectionPlane(Plane.Create(Frame.Create(P(0, 20, 0), D(1, 0, 0), D(0, 0, 1))))
ctx.data["section_ok"] = _safe(lambda: r.Success)
intent("activate_iso", bool(ViewHelper.ActivateNamedView("Iso_Assembly", True, False)), True)
'''
E["20_combo_view_031_named_views_section"] = {"components": 2}
B["20_combo_mesh_032_mesh_plus_solid"] = '''
c = cylinder((0, 0, 0), (0, 0, 30), 10, "Solid_Cyl")
def copy_move():
    Copy.ToClipboard(sel(c))
    Paste.FromClipboard()
    nb = [x for x in bodies_now() if x.Name != "Solid_Cyl" or x is not c]
    return nb
first_ok(ctx, "copy", [copy_move])
bs = bodies_now()
cp = [x for x in bs if not (x.Equals(c))]
if not cp:
    cp = [bs[-1]]
Move.Translate(sel(cp[0]), D(1, 0, 0), MM(40), MoveOptions())
FacetConvert.Create(sel(cp[0]), FacetConvertOptions())
_safe(lambda: set_name(list(GetRootPart().Meshes)[0], "Cyl_Mesh"))
'''
E["20_combo_mesh_032_mesh_plus_solid"] = {"bodies": 1, "meshes": 1}

import json as _json, os as _os
_PLAN = {c["case_key"]: c for c in _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "_inventory", "combo_plan.json"), encoding="utf-8"))["combos"]}
CASES = []
for _k in B:
    _c = _PLAN[_k]
    CASES.append((_k, {"category": "20_combo", "feature": "combo", "priority": _c["priority"], "title": _c["title"],
                       "commands": _c["features"], "inventory_expect": _c.get("expect"), "expect": E[_k],
                       "notes": "steps: " + "; ".join(_c["steps"]) + " | headless_feasibility: " + _c.get("headless_feasibility", "")}, B[_k]))

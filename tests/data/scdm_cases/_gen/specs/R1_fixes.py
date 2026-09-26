BATCH = "R1_fixes"
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
_NF = '''
def not_feasible_if_all_fail(ctx, key, fns, reason):
    try:
        return first_ok(ctx, key, fns)
    except Exception as e:
        raise NotFeasible(reason + " | last error: " + unicode(e)[-300:])
'''
CASES = [
("03_pull_profile_001_rect_30x10_h5", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 1500.0},
  "notes": "retry R1: RectangleProfile(Plane, w, h, PointUV location, angle) with explicit PointUV.Create(0,0) and 0.0"}, _NF + '''
RP = find_type(ctx, "RectangleProfile")
_safe(lambda: ctor_sigs(ctx, "RectangleProfile"))
def mk():
    return RP(Plane.PlaneXY, MM(30), MM(10), PointUV.Create(0, 0), 0.0)
not_feasible_if_all_fail(ctx, "extrude_profile", [
    lambda: ExtrudeProfile.Execute(mk(), MM(5), master(GetRootPart()), "Profile_Rect"),
    lambda: ExtrudeProfile.Execute(mk(), MM(5)),
    lambda: ExtrudeProfile.Execute(RP(Plane.PlaneXY, MM(30), MM(10), PointUV.Origin, 0.0), MM(5))],
    "ExtrudeProfile with RectangleProfile not usable from RunScript")
name_bodies(["Profile_Rect"])
'''),
("03_pull_profile_002_circle_r6_h12", {"expect": {"bodies": 1, "faces": 3, "volume_mm3": 1357.168026},
  "notes": "retry R1: CircleProfile(Plane, r, PointUV location, angle) with explicit PointUV.Create(0,0) and 0.0"}, _NF + '''
CP = find_type(ctx, "CircleProfile")
_safe(lambda: ctor_sigs(ctx, "CircleProfile"))
def mk():
    return CP(Plane.PlaneXY, MM(6), PointUV.Create(0, 0), 0.0)
not_feasible_if_all_fail(ctx, "extrude_profile", [
    lambda: ExtrudeProfile.Execute(mk(), MM(12), master(GetRootPart()), "Profile_Circle"),
    lambda: ExtrudeProfile.Execute(mk(), MM(12)),
    lambda: ExtrudeProfile.Execute(CP(Plane.PlaneXY, MM(6), PointUV.Origin, 0.0), MM(12))],
    "ExtrudeProfile with CircleProfile not usable from RunScript")
name_bodies(["Profile_Circle"])
'''),
("02_sketch_round2d_001_rect_corner_r4", {"notes": "retry R1: recorded-journal form Sketch2DRound.Create(SelectionPoint.Create(GetRootPart().Curves[i], u), ..., r) with raw curve parameters near the corner"}, _NF + '''
sketch_mode()
for p, q in [((0, 0), (40, 0)), ((40, 0), (40, 20)), ((40, 20), (0, 20)), ((0, 20), (0, 0))]:
    SketchLine.Create(P2(*p), P2(*q))
cs = curves_now()
ctx.data["curves_before"] = len(cs)
cb = root_curve_near((20, 0, 0))
cl = root_curve_near((0, 10, 0))
SP = globals().get("SelectionPoint") or find_type(ctx, "SelectionPoint")
def u_at(c, pt):
    return c.Shape.ProjectPoint(P(*pt)).Param
ub, ul = u_at(cb, (3, 0, 0)), u_at(cl, (0, 3, 0))
ctx.data["u"] = [ub, ul]
def chk():
    n = len(curves_now())
    if n < 5:
        raise Exception("no fillet arc (curves=%d)" % n)
def f1():
    Sketch2DRound.Create(SP.Create(cl, ul), SP.Create(cb, ub), MM(4))
    chk()
def f2():
    Sketch2DRound.Create(SP.Create(cl, System.Array[float]([ul])), SP.Create(cb, System.Array[float]([ub])), MM(4))
    chk()
def f3():
    Sketch2DRound.Create(SP.Create(cb, ub), SP.Create(cl, ul), MM(4))
    chk()
def f4():
    Sketch2DRound.Create(SP.CreateCurve(cl, ul), SP.CreateCurve(cb, ub), MM(4))
    chk()
not_feasible_if_all_fail(ctx, "round2d", [f1, f2, f3, f4], "Sketch2DRound with SelectionPoint not usable headless")
ctx.data["curves_after"] = len(curves_now())
finish_sketch(ctx, "Rect_Round4")
b = largest() if bodies_now() else None
if b is not None:
    intent("area_mm2", round(shape_of(b).Area * 1e6, 2), round(800 - (4 - 3.14159265) * 16, 2), 0.05)
'''),
("07_replaceface_001_block_top_to_plane", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 24000.0},
  "notes": "reinterpreted (R1): V19 ReplaceFacesWithFace only merges several faces into one face (no target/source replace exists); block top split in two, then both halves replaced by one face (faces 7 -> 6)"}, _NF + '''
b = block((0, 0, 0), (40, 30, 20), "Replace_Block")
SplitFace.ByTwoPoints(sel(top_face(b)), P(20, 0, 20), P(20, 30, 20))
b = largest()
halves = [f for f in b.Faces if gtype(f) == "Plane" and abs(bbox(f)[0][2] - 20) < 1e-6 and abs(bbox(f)[1][2] - 20) < 1e-6]
ctx.data["top_halves"] = len(halves)
ctx.data["faces_before"] = face_count(b)
def chk():
    if face_count(largest()) != 6:
        raise Exception("faces still %d" % face_count(largest()))
def fl(fs):
    l = List[API.IDesignFace]()
    for f in fs:
        l.Add(f)
    return l
def f1():
    ReplaceFacesWithFace.Execute(sel(halves))
    chk()
def f2():
    ReplaceFacesWithFace.Execute(sel(halves), ReplaceFacesWithFaceOptions())
    chk()
def f3():
    ReplaceFacesWithFace.Execute(fl(halves))
    chk()
not_feasible_if_all_fail(ctx, "replace", [f1, f2, f3], "ReplaceFacesWithFace did not merge the split faces headless")
set_name(largest(), "Replace_Block")
'''),
("06_pattern_linear_002_hole_2d_3x4", {"expect": {"bodies": 1},
  "notes": "fix R1: plate 80x80x5, seed hole r2 at (34,40) so the 3x4 pattern stays on the plate whichever Y sign is inferred"}, '''
plate = block((0, 0, 0), (80, 80, 5), "Plate_Holes")
subtract(ctx, plate, cylinder((34, 40, -1), (34, 40, 6), 2, "Hole_Cutter"))
p = largest()
set_name(p, "Plate_Holes")
hole = faces(p, "Cylinder")[0]
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.Two), ("LinearDirection", sel(edge_nearest(p, (40, 0, 0), "Line"))),
              ("CountX", 3), ("PitchX", MM(12)), ("CountY", 4), ("PitchY", MM(10))], "linear")
r = Pattern.CreateLinear(sel(hole), d, None)
ctx.data["pattern_success"] = _safe(lambda: r.Success)
ctx.data["hole_centres_mm"] = sorted([bbox_center(f)[:2] for f in faces(largest(), "Cylinder")])
intent("hole_faces", len(faces(largest(), "Cylinder")), 12)
intent("volume_mm3", round(total_volume(), 2), round(32000 - 12 * 3.14159265 * 4 * 5, 2), 0.5)
'''),
("03_pull_cut_003_upto_face", {"expect": {"bodies": 2},
  "notes": "fix R1: boss (sketch circle r5 on the plate) pulled up to the underside of a separate ceiling block with ForceIndependent, then merged into the plate only; ceiling stays a separate body"}, '''
plate = block((0, 0, 0), (40, 40, 10), "UpTo_Plate")
ceil = block((0, 0, 30), (40, 40, 35), "UpTo_Ceiling")
s = sheet_circle((20, 20, 10), 5, "UpTo_Profile")
target = bottom_face(ceil)
o = ExtrudeFaceOptions()
o.ExtrudeType = ExtrudeType.ForceIndependent
first_ok(ctx, "upto", [
    lambda: ExtrudeFaces.UpTo(sel(face0(s)), D(0, 0, 1), sel(target), P(20, 20, 10), o),
    lambda: ExtrudeFaces.UpTo(sel(face0(s)), D(0, 0, 1), sel(target), P(20, 20, 30), o)])
delete_sheets()
boss = [x for x in bodies_now() if abs(bbox(x)[0][2] - 10) < 1e-6 and abs(bbox(x)[1][2] - 30) < 1e-6]
ctx.data["boss_found"] = len(boss)
Combine.Merge(sel(body_named("UpTo_Plate"), boss[0]))
pl = [x for x in bodies_now() if bbox(x)[0][2] < 1e-6][0]
set_name(pl, "UpTo_Plate")
ctx.data["bodies_after"] = [[unicode(x.Name), vol(x), bbox(x)] for x in bodies_now()]
intent("ceiling_volume_mm3", vol(body_named("UpTo_Ceiling")), 8000.0)
intent("plate_boss_volume_mm3", round(vol(body_named("UpTo_Plate")), 2), round(16000 + 3.14159265 * 25 * 20, 2), 0.5)
'''),
("07_draft_001_block_4sides_5deg", {"expect": {"bodies": 1, "faces": 6},
  "notes": "fix R1: draft must narrow the block towards the top (neutral plane bottom face); sign/side chosen by validated trial on a fresh body"}, _DRAFT + '''
b = drafted(ctx, "Draft_Block", "block")
ctx.data["bbox_after_mm"] = bbox(b)
ctx.data["volume_after_mm3"] = vol(b)
bt = [f for f in b.Faces if gtype(f) == "Plane" and abs(bbox(f)[0][2] - 20) < 1e-6 and abs(bbox(f)[1][2] - 20) < 1e-6][0]
tb = bbox(bt)
intent_range("top_face_x_span_mm", tb[1][0] - tb[0][0], 36.0, 39.9)
intent_range("volume_mm3", vol(b), 20000, 23999)
'''),
("07_draft_002_cyl_side_3deg", {"expect": {"bodies": 1, "faces": 3},
  "notes": "fix R1: cylinder side drafted 3 deg so it narrows towards the top (cone); validated trial of sign/side"}, _DRAFT + '''
import math
b = drafted(ctx, "Draft_Cyl", "cyl")
ctx.data["surface_types_after"] = [gtype(f) for f in b.Faces]
r_top = 10 - 20 * math.tan(math.radians(3))
intent("volume_mm3", round(vol(b), 1), round(math.pi * 20 / 3 * (100 + 10 * r_top + r_top ** 2), 1), 2.0)
'''),
]

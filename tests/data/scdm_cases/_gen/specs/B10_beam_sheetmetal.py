BATCH = "B10_beam_sheetmetal"
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
CASES = [
("09_beam_profile_001_I_100x50", {"expect": {}}, _BEAM + '''
r = BeamProfile.CreateI(MM(50), MM(100), MM(8), MM(5), "I_100x50")
prof = profile_part(ctx, r)
ctx.data["profile"] = [unicode(_safe(lambda: prof.Name)), unicode(_safe(lambda: prof.GetType().Name))]
dcurve(seg((0, 0, 0), (0, 0, 500)), "Beam_Path")
make_beams(ctx, prof, curves_now())
intent("beams", doc_stats()["beams"], 1)
'''),
("09_beam_profile_002_rect_tube_60x40x3", {"expect": {}}, _BEAM + '''
r = BeamProfile.CreateRectangular(MM(3), MM(60), MM(40), "Rect_Tube_60x40x3")
prof = profile_part(ctx, r)
dcurve(seg((0, 0, 0), (500, 0, 0)), "Beam_Path")
make_beams(ctx, prof, curves_now())
intent("beams", doc_stats()["beams"], 1)
'''),
("09_beam_profile_003_circular_d40_d34", {"expect": {}}, _BEAM + '''
r = BeamProfile.CreateCircular(MM(40), MM(34), "Tube_D40_d34")
prof = profile_part(ctx, r)
dcurve(seg((0, 0, 0), (0, 500, 0)), "Beam_Path")
make_beams(ctx, prof, curves_now())
intent("beams", doc_stats()["beams"], 1)
'''),
("09_beam_create_001_line_I", {"expect": {"beams": 1}}, _BEAM + '''
dcurve(seg((0, 0, 0), (1000, 0, 0)), "Beam_Line_1000")
prof = profile_part(ctx, BeamProfile.CreateI(MM(50), MM(100), MM(8), MM(5), "I_100x50"))
make_beams(ctx, prof, curves_now())
'''),
("09_beam_create_002_frame_4lines_rect", {"expect": {"beams": 4}}, _BEAM + '''
pts = [(0, 0, 0), (1000, 0, 0), (1000, 500, 0), (0, 500, 0)]
for i in range(4):
    dcurve(seg(pts[i], pts[(i + 1) % 4]), "Frame_Edge_%d" % (i + 1))
prof = profile_part(ctx, BeamProfile.CreateRectangular(MM(3), MM(60), MM(40), "Rect_Tube_60x40x3"))
make_beams(ctx, prof, curves_now())
'''),
("09_beam_create_003_orient30_centroid", {"expect": {"beams": 1}}, _BEAM + '''
dcurve(seg((0, 0, 0), (1000, 0, 0)), "Beam_Line_1000")
prof = profile_part(ctx, BeamProfile.CreateI(MM(50), MM(100), MM(8), MM(5), "I_100x50"))
bm = make_beams(ctx, prof, curves_now())
first_ok(ctx, "orientation", [lambda: Beam.SetOrientation(sel(bm), DEG(30))])
first_ok(ctx, "position", [lambda: Beam.SetPosition(sel(bm), Beam.AnchorPosition.Centroid),
                           lambda: [setattr(x, "AnchorPosition", enum_pick(type(x.AnchorPosition), "Centroid")) for x in bm]])
ctx.data["beam_state"] = _safe(lambda: [[unicode(x.Orientation), unicode(x.AnchorPosition)] for x in bm])
'''),
("08_sheetmetal_convert_001_block_t2", {"expect": {"bodies": 1, "volume_mm3": 10000.0}}, '''
block((0, 0, 0), (100, 50, 2), "Sheet_Plate_T2")
root = GetRootPart()
raw("sheetmetal", lambda: master(root).ConvertToSheetMetal())
intent("part_type", unicode(_safe(lambda: master(root).Type)), u"SheetMetal")
'''),
("08_sheetmetal_flange_001_90deg_l20", {"expect": {"bodies": 1},
  "notes": "flange realised as L-shaped plate (base 100x50x2 + 20 mm wall) converted to sheet metal, then SheetMetalAspect.CreateMissingBends(r=1) on the crease (8 faces + 2 bend faces)"}, '''
a = block((0, 0, 0), (100, 50, 2), "Flange_Part")
w = block((98, 0, 2), (100, 50, 22), "Wall")
Combine.Merge(sel(a, w))
b = largest()
root = GetRootPart()
raw("sheetmetal", lambda: master(root).ConvertToSheetMetal())
b = largest()
asp = master(root).SheetMetal
ctx.data["aspect_members"] = [n for n in dir(asp) if not n.startswith("_")]
_safe(lambda: ctor_sigs(ctx, "BendSpecification"))
inner = edge_nearest(b, (98, 25, 2))
outer = edge_nearest(b, (100, 25, 0))
LE = List[rawt("DesignEdge")]
first_ok(ctx, "bends", [lambda: raw("bend", lambda: asp.CreateMissingBends(LE([master(inner)]), MM(1))),
                        lambda: raw("bend", lambda: asp.CreateMissingBends(LE([master(outer)]), MM(1))),
                        lambda: raw("bend", lambda: asp.CreateMissingBends(LE([master(inner), master(outer)]), MM(1)))])
ctx.data["faces_after"] = face_count(largest())
intent("faces_after_bend", face_count(largest()), 10)
intent("volume_mm3", round(total_volume(), 2), 11914.17, 0.5)
'''),
("08_sheetmetal_unfold_001", {"expect": {},
  "notes": "L-bracket with bend (as flange_001), then SheetMetalAspect.Unfold(base bottom face)"}, '''
a = block((0, 0, 0), (100, 50, 2), "Bracket")
w = block((98, 0, 2), (100, 50, 22), "Wall")
Combine.Merge(sel(a, w))
b = largest()
root = GetRootPart()
raw("sheetmetal", lambda: master(root).ConvertToSheetMetal())
b = largest()
asp = master(root).SheetMetal
LE = List[rawt("DesignEdge")]
ctx.attempt("bends", lambda: raw("bend", lambda: asp.CreateMissingBends(LE([master(edge_nearest(b, (98, 25, 2)))]), MM(1))))
anchor = bottom_face(largest())
f = first_ok(ctx, "unfold", [lambda: raw("unfold", lambda: asp.Unfold(master(anchor)))])
ctx.data["unfold_result"] = _safe(lambda: unicode(f.GetType().Name))
ctx.data["flat_pattern"] = _safe(lambda: unicode(master(root).FlatPattern))
ctx.data["bboxes"] = [bbox(x) for x in all_bodies()]
'''),
]

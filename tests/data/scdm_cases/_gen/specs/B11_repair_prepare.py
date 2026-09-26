BATCH = "B11_repair_prepare"
_CUBE = '''
def cube_sheets(s):
    out = []
    for ax in range(3):
        for side in (0, s):
            def pt(u, v):
                q = [0, 0, 0]
                q[ax] = side
                q[(ax + 1) % 3] = u
                q[(ax + 2) % 3] = v
                return tuple(q)
            pts = [pt(0, 0), pt(s, 0), pt(s, s), pt(0, s)]
            n = [0, 0, 0]
            n[ax] = 1
            c = [s / 2.0] * 3
            c[ax] = side
            out.append(planar(poly_curves(pts), plane_at(tuple(c), tuple(n)), "Sheet_%s%s" % ("XYZ"[ax], "0" if side == 0 else "1")))
    return out
'''
CASES = [
("12_repair_stitch_001_six_sheets_to_solid", {"expect": {"bodies": 1}}, _CUBE + '''
sh = cube_sheets(20)
ctx.data["sheets_before"] = len(bodies_now())
first_ok(ctx, "stitch", [lambda: StitchFaces.FindAndFix(sel(sh)),
                         lambda: StitchFaces.FindAndFix(sel(sh), StitchOptions()),
                         lambda: StitchFaces.FindAndFix()])
b = largest()
intent("solid_volume_mm3", round(vol(b) or 0, 3), 8000.0, 1.0)
intent("faces", face_count(b), 6)
'''),
("12_repair_missingface_001_open_box", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (20, 20, 20), "Open_Box")
Delete.Execute(sel(top_face(b)))
b = largest()
ctx.data["faces_open"] = face_count(b)
ctx.data["is_sheet_open"] = is_sheet(b)
first_ok(ctx, "fix_missing", [lambda: FixMissingFaces.FindAndFix(sel(b)), lambda: FixMissingFaces.FindAndFix()])
b = largest()
intent("faces", face_count(b), 6)
intent("volume_mm3", round(vol(b) or 0, 3), 8000.0, 1.0)
'''),
("12_repair_extraedges_001_split_face_merge", {"expect": {"bodies": 1, "volume_mm3": 24000.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Split_Block")
SplitFace.ByTwoPoints(sel(top_face(b)), P(20, 0, 20), P(20, 30, 20))
b = largest()
ctx.data["faces_split"] = face_count(b)
first_ok(ctx, "fix_extra", [lambda: FixExtraEdges.FindAndFix(sel(b)), lambda: FixExtraEdges.FindAndFix()])
intent("faces_before", ctx.data["faces_split"], 7)
intent("faces_after", face_count(largest()), 6)
'''),
("12_prepare_midsurface_001_plate_t2", {"expect": {}}, '''
b = block((0, 0, 0), (100, 50, 2), "Plate_T2")
def by_obj():
    m = Midsurface()
    m.AddMatchingFacePairs(top_face(b), bottom_face(b))
    return m.Execute()
first_ok(ctx, "midsurface", [lambda: Midsurface.Convert(sel(b), MM(2)), by_obj,
                             lambda: Midsurface.Convert(sel(b), MM(2.5))])
st = doc_stats()
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x)] for x in all_bodies()]
intent("has_sheet", any(is_sheet(x) for x in all_bodies()), True)
'''),
("12_prepare_midsurface_002_L_bracket_t3", {"expect": {}}, '''
a = block((0, 0, 0), (60, 40, 3), "L_Bracket")
w = block((0, 0, 3), (3, 40, 40), "L_Wall")
Combine.Merge(sel(a, w))
b = largest()
first_ok(ctx, "midsurface", [lambda: Midsurface.Convert(sel(b), MM(3)), lambda: Midsurface.Convert(sel(b), MM(3.5))])
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x)] for x in all_bodies()]
intent("has_sheet", any(is_sheet(x) for x in all_bodies()), True)
'''),
("12_prepare_sharetopo_001_two_blocks_touching", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (20, 20, 20), "Left_Block")
b = block((20, 0, 0), (40, 20, 20), "Right_Block")
ctx.data["faces_before"] = doc_stats()["faces"]
o = ShareTopologyOptions()
setp(ctx, o, [], "st_opts")
first_ok(ctx, "share", [lambda: ShareTopology.FindAndFix(sel(a, b), o), lambda: ShareTopology.FindAndFix(o), lambda: ShareTopology.FindAndFix()])
ctx.data["faces_after"] = doc_stats()["faces"]
ctx.data["share_mode"] = _safe(lambda: unicode(master(GetRootPart()).ShareTopology))
'''),
("12_prepare_sharetopo_002_force_tol0p1", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (20, 20, 20), "Left_Block")
b = block((20.05, 0, 0), (40, 20, 20), "Right_Block_Gap_0p05")
ctx.data["faces_before"] = doc_stats()["faces"]
first_ok(ctx, "force_share", [lambda: ForceShareTopology.Execute(sel(a, b), MM(0.1))])
ctx.data["faces_after"] = doc_stats()["faces"]
'''),
("12_prepare_enclosure_001_box_cushion10", {"expect": {"bodies": 2}}, '''
b = block((0, 0, 0), (40, 30, 20), "Enclosed_Block")
o = EnclosureOptions()
setp(ctx, o, [("EnclosureType", _safe(lambda: EnclosureType.Box))], "encl_opts")
def by_obj():
    e = Enclosure(sel(b), o)
    c = e.EnclosureCushion
    ctx.data["cushion_type"] = unicode(_safe(lambda: c.GetType().FullName))
    mem = [n for n in dir(c) if not n.startswith("_")]
    ctx.data["cushion_members"] = mem
    done = []
    for n in mem:
        try:
            if isinstance(getattr(c, n), float):
                setattr(c, n, MM(10))
                done.append(n)
        except Exception:
            pass
    ctx.data["cushion_set"] = done
    _safe(lambda: setattr(e, "EnclosureCushion", c))
    return e.Execute()
first_ok(ctx, "enclosure", [by_obj, lambda: Enclosure.Create(sel(b), o)])
bbs = [bbox(x) for x in all_bodies()]
ctx.data["bboxes"] = bbs
intent_range("enclosure_x_span_mm", max(x[1][0] - x[0][0] for x in bbs), 40.001, 200)
'''),
("12_prepare_volumeextract_001_pipe", {"expect": {},
  "notes": "tube r10/r8 h50 with two capping sheets r8; VolumeExtract(caps, inner face) -> fluid volume"}, '''
outer = cylinder((0, 0, 0), (0, 0, 50), 10, "Pipe")
inner = cylinder((0, 0, -5), (0, 0, 55), 8, "Bore_Cutter")
subtract(ctx, outer, inner)
pipe = largest()
c1 = sheet_circle((0, 0, 0), 8, "Cap_Bottom")
c2 = sheet_circle((0, 0, 50), 8, "Cap_Top")
bore = [f for f in faces(pipe, "Cylinder") if abs(_safe(lambda: f.Shape.Geometry.Radius, 0) - MM(8)) < 1e-6]
ctx.data["bore_faces"] = len(bore)
caps = [face0(c1), face0(c2)]
first_ok(ctx, "volume_extract", [lambda: VolumeExtract.Create(sel(caps), sel(bore[0])),
                                 lambda: VolumeExtract.Create(sel(bore[0]), sel(caps)),
                                 lambda: VolumeExtract.Create(sel(caps), sel(bore[0]), VolumeExtractOptions())])
vols = sorted([round(vol(x) or 0, 1) for x in all_bodies() if not is_sheet(x)])
ctx.data["solid_volumes"] = vols
intent("fluid_present", any(abs(v - 10053.1) < 20 for v in vols), True)
'''),
("12_prepare_workpiece_001", {"expect": {}}, '''
b = block((0, 0, 0), (40, 30, 20), "Part_With_Pocket")
cut = block((10, 10, 10), (30, 20, 25), "Pocket_Cutter")
subtract(ctx, b, cut)
first_ok(ctx, "workpiece", [lambda: Workpiece.Create(sel(largest()), WorkpieceOptions()), lambda: Workpiece.Create(sel(largest()))])
ctx.data["bodies_after"] = [[unicode(x.Name), round(vol(x) or 0, 1)] for x in all_bodies()]
intent_range("bodies", len(all_bodies()), 2, 3)
'''),
("12_prepare_icepak_simplify_001_level1", {"expect": {}}, '''
b = block((0, 0, 0), (40, 30, 20), "Icepak_Block")
cyl = cylinder((20, 15, 20), (20, 15, 30), 5, "Icepak_Boss")
Combine.Merge(sel(b, cyl))
o0 = IcepakSimplifyLevelZeroOptions()
o1 = IcepakSimplifyLevelOneOptions()
setp(ctx, o0, [("PreserveOriginal", False)], "o0")
setp(ctx, o1, [("CleanUp", True)], "o1")
first_ok(ctx, "icepak", [lambda: IcepakSimplify.ExecuteLevelOne(sel(largest()), o0, o1)])
ctx.data["bodies_after"] = [[unicode(x.Name), face_count(x), round(vol(x) or 0, 1)] for x in all_bodies()]
'''),
]

BATCH = "B06_move_pattern"
CASES = [
("06_move_translate_001_block_x25", {"expect": {"bodies": 1, "volume_mm3": 1000.0}}, '''
b = block((0, 0, 0), (10, 10, 10), "Moved_Block")
Move.Translate(sel(b), D(1, 0, 0), MM(25), MoveOptions())
ctx.data["bbox_after_mm"] = bbox(body_named("Moved_Block"))
'''),
("06_move_translate_002_copy_y30", {"expect": {"bodies": 2, "volume_mm3": 2000.0}}, '''
b = block((0, 0, 0), (10, 10, 10), "Block_Original")
o = MoveOptions()
o.Copy = True
Move.Translate(sel(b), D(0, 1, 0), MM(30), o)
bs = sorted(bodies_now(), key=lambda x: bbox_center(x)[1])
name_bodies(["Block_Original", "Block_Copy_Y30"], bs)
ctx.data["centres_mm"] = [bbox_center(x) for x in bs]
'''),
("06_move_rotate_001_block_z45", {"expect": {"bodies": 1, "volume_mm3": 1000.0}}, '''
b = block((0, 0, 0), (20, 10, 5), "Rotated_Block")
Move.Rotate(sel(b), axis_line((0, 0, 0), (0, 0, 1)), DEG(45), MoveOptions())
ctx.data["bbox_after_mm"] = bbox(body_named("Rotated_Block"))
'''),
("06_move_rotate_002_cyl_x90_copy", {"expect": {"bodies": 2}}, '''
b = cylinder((0, 0, 0), (0, 0, 30), 5, "Cyl_Original")
o = MoveOptions()
o.Copy = True
Move.Rotate(sel(b), axis_line((0, 0, 0), (1, 0, 0)), DEG(90), o)
bs = sorted(bodies_now(), key=lambda x: bbox_center(x)[2], reverse=True)
name_bodies(["Cyl_Original", "Cyl_Copy_RotX90"], bs)
ctx.data["bboxes_mm"] = [bbox(x) for x in bs]
'''),
("06_move_scale_001_uniform_2x", {"expect": {"bodies": 1, "volume_mm3": 8000.0}}, '''
b = block((0, 0, 0), (10, 10, 10), "Scaled_2x")
Scale.Execute(sel(b), P(0, 0, 0), 2.0)
'''),
("06_move_scale_002_nonuniform_1x2x0p5", {"expect": {"bodies": 1, "volume_mm3": 1000.0}}, '''
b = block((0, 0, 0), (10, 10, 10), "Scaled_NonUniform")
Scale.Execute(sel(b), Frame.World, Vector.Create(1.0, 2.0, 0.5))
ctx.data["bbox_after_mm"] = bbox(body_named("Scaled_NonUniform"))
'''),
("06_move_mirror_001_block_about_yz", {"expect": {"bodies": 2, "volume_mm3": 2000.0}}, '''
b = block((5, 0, 0), (15, 10, 10), "Mirror_Source")
DatumPlaneCreator.Create(P(0, 0, 0), D(1, 0, 0))
dp = list(GetRootPart().DatumPlanes)[-1]
_safe(lambda: set_name(dp, "Mirror_Plane_YZ"))
Mirror.Execute(sel(b), sel(dp), MirrorOptions())
bs = sorted(bodies_now(), key=lambda x: bbox_center(x)[0], reverse=True)
name_bodies(["Mirror_Source", "Mirror_Copy"], bs)
'''),
("06_move_mirror_002_merge_halves", {"expect": {"bodies": 1, "volume_mm3": 4000.0}}, '''
b = block((0, 0, 0), (10, 20, 10), "Mirror_Half")
f = face_extreme(b, (1, 0, 0), -1)
o = MirrorOptions()
o.MergeObjects = True
Mirror.Execute(sel(b), sel(f), o)
name_bodies(["Mirror_Merged"], [largest()])
ctx.data["bbox_mm"] = bbox(largest())
'''),
("06_pattern_linear_001_cyl_1d_5x10", {"expect": {"bodies": 5}}, '''
b = cylinder((0, 0, 0), (0, 0, 5), 2, "Pattern_Pin")
dirc = dcurve(seg((0, -5, 0), (10, -5, 0)), "Pattern_Direction_X")
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("LinearDirection", sel(dirc)),
              ("CountX", 5), ("PitchX", MM(10))], "linear")
r = Pattern.CreateLinear(sel(b), d, None)
ctx.data["pattern_success"] = _safe(lambda: r.Success)
name_bodies(["Pattern_Pin"], sorted(bodies_now(), key=lambda x: bbox_center(x)[0]))
ctx.data["pin_centres_mm"] = [bbox_center(x) for x in bodies_now()]
'''),
("06_pattern_linear_002_hole_2d_3x4", {"expect": {"bodies": 1}}, '''
plate = block((0, 0, 0), (60, 50, 5), "Plate_Holes")
c = cylinder((10, 10, -1), (10, 10, 6), 2, "Hole_Cutter")
subtract(ctx, plate, c)
p = largest()
set_name(p, "Plate_Holes")
hole = faces(p, "Cylinder")[0]
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.Two), ("LinearDirection", sel(edge_nearest(p, (30, 0, 0), "Line"))),
              ("CountX", 3), ("PitchX", MM(12)), ("CountY", 4), ("PitchY", MM(10))], "linear")
r = Pattern.CreateLinear(sel(hole), d, None)
ctx.data["pattern_success"] = _safe(lambda: r.Success)
ctx.data["hole_faces"] = len(faces(largest(), "Cylinder"))
'''),
("06_pattern_linear_003_body_copy_3", {"expect": {"bodies": 3}}, '''
b = block((0, 0, 0), (10, 10, 10), "Pattern_Block")
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("LinearDirection", sel(edge_nearest(b, (5, 0, 0), "Line"))),
              ("CountX", 3), ("PitchX", MM(25))], "linear")
r = Pattern.CreateLinear(sel(b), d, None)
ctx.data["pattern_success"] = _safe(lambda: r.Success)
name_bodies(["Pattern_Block"], sorted(bodies_now(), key=lambda x: bbox_center(x)[0]))
'''),
("06_pattern_circular_001_holes_6_360", {"expect": {"bodies": 1}}, '''
disk = cylinder((0, 0, 0), (0, 0, 5), 40, "Disk_Holes")
c = cylinder((25, 0, -1), (25, 0, 6), 3, "Hole_Cutter")
subtract(ctx, disk, c)
p = largest()
set_name(p, "Disk_Holes")
hole = [f for f in faces(p, "Cylinder") if abs(_dist(bbox_center(f), (25, 0, 2.5))) < 5][0]
d = CircularPatternData()
outer = max(faces(p, "Cylinder"), key=lambda f: bbox(f)[1][0] - bbox(f)[0][0])
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("CircularAxis", sel(outer)),
              ("CircularCount", 6), ("CircularAngle", DEG(360))], "circular")
r = Pattern.CreateCircular(sel(hole), d, None)
ctx.data["pattern_success"] = _safe(lambda: r.Success)
ctx.data["cyl_faces"] = len(faces(largest(), "Cylinder"))
'''),
("06_pattern_circular_002_bodies_4_180", {"expect": {"bodies": 4}}, '''
b = block((20, -2, 0), (26, 2, 4), "Circ_Block")
ax = dcurve(seg((0, 0, 0), (0, 0, 10)), "Pattern_Axis_Z")
d = CircularPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("CircularAxis", sel(ax)),
              ("CircularCount", 4), ("CircularAngle", DEG(180))], "circular")
r = Pattern.CreateCircular(sel(b), d, None)
ctx.data["pattern_success"] = _safe(lambda: r.Success)
name_bodies(["Circ_Block"])
ctx.data["block_centres_mm"] = [bbox_center(x) for x in bodies_now()]
'''),
("06_pattern_fill_001_holes_in_plate", {"expect": {"bodies": 1}}, '''
plate = block((0, 0, 0), (80, 60, 5), "Plate_Fill")
c = cylinder((5, 5, -1), (5, 5, 6), 2, "Hole_Cutter")
subtract(ctx, plate, c)
p = largest()
set_name(p, "Plate_Fill")
hole = faces(p, "Cylinder")[0]
region = top_face(p)
d = FillPatternData()
setp(ctx, d, [("FillPatternType", FillPatternType.Grid), ("XSpacing", MM(10)), ("YSpacing", MM(10)),
              ("Margin", MM(3)), ("LinearDirection", sel(edge_nearest(p, (40, 0, 5), "Line")))], "fill")
first_ok(ctx, "fill", [
    lambda: Pattern.CreateFill(sel(hole, region), d, None),
    lambda: Pattern.CreateFill(sel(hole), d, None)])
ctx.data["hole_faces"] = len(faces(largest(), "Cylinder"))
'''),
("06_move_trajectory_001_block_along_arc", {"expect": {"bodies": 1, "volume_mm3": 64.0}}, '''
path = dcurve(arc_curve((0, 0, 0), 50, 0, 90), "Trajectory_Arc")
b = block((48, -2, -2), (52, 2, 2), "Traj_Block")
first_ok(ctx, "along", [
    lambda: Move.AlongTrajectory(sel(b), sel(path), P(0, 50, 0), MoveOptions()),
    lambda: Move.AlongTrajectory(sel(b), sel(path), MM(78.539816), MoveOptions()),
    lambda: Move.AlongTrajectory(sel(b), sel(path), 1.0, MoveOptions())])
ctx.data["bbox_after_mm"] = bbox(body_named("Traj_Block"))
'''),
]

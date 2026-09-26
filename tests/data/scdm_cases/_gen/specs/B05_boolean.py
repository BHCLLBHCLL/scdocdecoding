BATCH = "B05_boolean"
CASES = [
("05_boolean_merge_001_two_blocks_overlap", {"expect": {"bodies": 1, "volume_mm3": 15000.0}}, '''
a = block((0, 0, 0), (20, 20, 20), "Merge_A")
b = block((10, 10, 10), (30, 30, 30), "Merge_B")
first_ok(ctx, "merge", [
    lambda: Combine.Merge(sel(a, b)),
    lambda: Combine.Merge(sel(a), sel(b))])
name_bodies(["Merged_Blocks"], [largest()])
'''),
("05_boolean_merge_002_block_plus_cyl", {"expect": {"bodies": 1, "volume_mm3": 20021.238597}}, '''
a = block((0, 0, 0), (40, 40, 10), "Merge_Base")
b = cylinder((20, 20, 0), (20, 20, 30), 8, "Merge_Boss")
first_ok(ctx, "merge", [
    lambda: Combine.Merge(sel(a, b)),
    lambda: Combine.Merge(sel(a), sel(b))])
name_bodies(["Base_With_Boss"], [largest()])
'''),
("05_boolean_merge_003_touching_faces", {"expect": {"bodies": 1, "volume_mm3": 16000.0}}, '''
a = block((0, 0, 0), (20, 20, 20), "Touch_A")
b = block((20, 0, 0), (40, 20, 20), "Touch_B")
first_ok(ctx, "merge", [
    lambda: Combine.Merge(sel(a, b)),
    lambda: Combine.Merge(sel(a), sel(b))])
name_bodies(["Touching_Merged"], [largest()])
'''),
("05_boolean_subtract_001_block_minus_cyl", {"expect": {"bodies": 1, "faces": 7, "volume_mm3": 30429.203673}}, '''
a = block((0, 0, 0), (40, 40, 20), "Plate")
c = cylinder((20, 20, -5), (20, 20, 25), 5, "Cutter")
k = subtract(ctx, a, c)
name_bodies(["Plate_With_Hole"], k)
'''),
("05_boolean_subtract_002_block_minus_sphere", {"expect": {"bodies": 1, "volume_mm3": 62232.854132}}, '''
a = block((0, 0, 0), (40, 40, 40), "Cube")
s = sphere((40, 40, 40), 15, "Corner_Sphere")
k = subtract(ctx, a, s)
name_bodies(["Cube_Corner_Cut"], k)
'''),
("05_boolean_subtract_003_keep_cutter", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (40, 40, 20), "Plate")
c = cylinder((20, 20, -5), (20, 20, 25), 5, "Cutter")
k = subtract(ctx, a, c, keep_cutter=True)
name_bodies(["Plate_With_Hole", "Cutter_Kept"], k)
'''),
("05_boolean_intersect_001_block_sphere", {"expect": {"bodies": 1}}, '''
a = block((-10, -10, -10), (10, 10, 10), "Cube20")
s = sphere((0, 0, 0), 14, "Sphere14")
k = intersect_keep(ctx, a, s)
name_bodies(["Cube_Sphere_Common"], [k])
'''),
("05_boolean_intersect_002_two_cylinders_cross", {"expect": {"bodies": 1, "volume_mm3": 5333.333333}}, '''
a = cylinder((-30, 0, 0), (30, 0, 0), 10, "Cyl_X")
b = cylinder((0, -30, 0), (0, 30, 0), 10, "Cyl_Y")
k = intersect_keep(ctx, a, b)
name_bodies(["Steinmetz"], [k])
'''),
("05_boolean_splitbody_001_block_by_plane_mid", {"expect": {"bodies": 2, "volume_mm3": 24000.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Split_Block")
SplitBody.ByCutter(sel(b), plane_xy(10))
bs = sorted(bodies_now(), key=lambda x: bbox_center(x)[2])
name_bodies(["Split_Lower", "Split_Upper"], bs)
'''),
("05_boolean_splitbody_002_cyl_by_oblique_plane", {"expect": {"bodies": 2, "volume_mm3": 12566.370614}}, '''
b = cylinder((0, 0, 0), (0, 0, 40), 10, "Split_Cyl")
s = 2 ** -0.5
SplitBody.ByCutter(sel(b), Plane.Create(Frame.Create(P(0, 0, 20), D(s, 0, -s), D(0, 1, 0))))
bs = sorted(bodies_now(), key=lambda x: bbox_center(x)[2])
name_bodies(["Split_Cyl_Lower", "Split_Cyl_Upper"], bs)
'''),
("05_boolean_splitbody_003_by_face", {"expect": {"bodies": 3}}, '''
b = block((0, 0, 0), (40, 30, 20), "Split_Target")
t = sheet_rect(-10, -10, 50, 40, 8, "Split_Tool_Sheet")
SplitBody.ByCutter(sel(b), sel(face0(t)), True)
solids = sorted([x for x in bodies_now() if not is_sheet(x)], key=lambda x: bbox_center(x)[2])
name_bodies(["Split_By_Face_Lower", "Split_By_Face_Upper"], solids)
'''),
("05_boolean_imprint_001_block_cyl_curves", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (40, 40, 20), "Imprint_Block")
c = cylinder((20, 20, 10), (20, 20, 40), 5, "Imprint_Tool")
fa = shape_of(a).Faces.Count
Combine.Intersect(sel(a), sel(c), MakeCurvesOptions())
ctx.data["block_faces_before_after"] = [fa, shape_of(body_named("Imprint_Block")).Faces.Count]
'''),
]

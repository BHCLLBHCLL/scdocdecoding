BATCH = "B03_pull"
CASES = [
("03_pull_extrude_001_rect_40x20_h10", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 8000.0}}, '''
s = sheet_rect(0, 0, 40, 20, 0, "Extrude_Rect")
extrude(face0(s), 10, (0, 0, 1))
name_bodies(["Extrude_Rect"], [largest()])
'''),
("03_pull_extrude_002_circle_r10_h25", {"expect": {"bodies": 1, "faces": 3, "volume_mm3": 7853.981634}}, '''
s = sheet_circle((0, 0, 0), 10, "Extrude_Circle")
extrude(face0(s), 25, (0, 0, 1))
name_bodies(["Extrude_Circle"], [largest()])
'''),
("03_pull_extrude_003_spline_profile_h5", {"expect": {"bodies": 1}}, '''
pts = [(0, 0, 0), (20, -5, 0), (35, 5, 0), (25, 20, 0), (5, 18, 0)]
s = planar([spline_curve(pts, True)], plane_xy(0), "Extrude_Spline")
extrude(face0(s), 5, (0, 0, 1))
name_bodies(["Extrude_Spline"], [largest()])
'''),
("03_pull_extrude_004_symmetric_h20", {"expect": {"bodies": 1, "faces": 6}}, '''
s = sheet_rect(0, 0, 40, 20, 0, "Extrude_Symmetric")
extrude(face0(s), 20, (0, 0, 1), sym=True)
b = largest()
name_bodies(["Extrude_Symmetric"], [b])
ctx.data["bbox_mm"] = bbox(b)
'''),
("03_pull_cut_001_pocket_rect_depth5", {"expect": {"bodies": 1, "volume_mm3": 31500.0}}, '''
b = block((0, 0, 0), (40, 40, 20), "Pocket_Block")
s = sheet_rect(15, 15, 25, 25, 20, "Pocket_Profile")
extrude(face0(s), 5, (0, 0, -1), ExtrudeType.Cut)
delete_sheets(ctx)
name_bodies(["Pocket_Block"], [largest()])
'''),
("03_pull_cut_002_through_hole_r4", {"expect": {"bodies": 1, "volume_mm3": 30994.690351}}, '''
b = block((0, 0, 0), (40, 40, 20), "Hole_Block")
s = sheet_circle((20, 20, 20), 4, "Hole_Profile")
extrude(face0(s), 20, (0, 0, -1), ExtrudeType.Cut)
delete_sheets(ctx)
name_bodies(["Hole_Block"], [largest()])
'''),
("03_pull_cut_003_upto_face", {"notes": "boss extruded from a sketch circle on the plate up to the underside of a separate ceiling block"}, '''
plate = block((0, 0, 0), (40, 40, 10), "UpTo_Plate")
ceil = block((0, 0, 30), (40, 40, 35), "UpTo_Ceiling")
s = sheet_circle((20, 20, 10), 5, "UpTo_Profile")
target = bottom_face(ceil)
o = ExtrudeFaceOptions()
o.ExtrudeType = ExtrudeType.Add
first_ok(ctx, "upto", [
    lambda: ExtrudeFaces.UpTo(sel(face0(s)), D(0, 0, 1), sel(target), P(20, 20, 10), o),
    lambda: ExtrudeFaces.UpTo(sel(face0(s)), D(0, 0, 1), sel(target), P(20, 20, 30), o)])
ctx.data["bodies_after"] = [[unicode(x.Name), vol(x), bbox(x)] for x in bodies_now()]
'''),
("03_pull_face_001_block_top_plus10", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 36000.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Block_TopPulled")
ExtrudeFaces.Execute(sel(top_face(b)), MM(10), ExtrudeFaceOptions())
'''),
("03_pull_face_002_block_side_minus3", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 22200.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Block_SidePushed")
ExtrudeFaces.Execute(sel(face_extreme(b, (1, 0, 0), 1)), MM(-3), ExtrudeFaceOptions())
'''),
("03_pull_extrudeedge_001_line_to_sheet", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 800.0}}, '''
c = dcurve(seg((0, 0, 0), (40, 0, 0)), "Edge_Line40")
first_ok(ctx, "extrude_edge", [
    lambda: ExtrudeEdges.Execute(sel(c), P(0, 0, 0), D(0, 0, 1), MM(20), ExtrudeEdgeOptions()),
    lambda: ExtrudeEdges.Execute(sel(c), MM(20), ExtrudeEdgeOptions())])
name_bodies(["Sheet_From_Line"])
'''),
("03_pull_extrudeedge_002_arc_to_sheet", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 628.318531}}, '''
c = dcurve(arc_curve((0, 0, 0), 20, 0, 180), "Edge_Arc180")
first_ok(ctx, "extrude_edge", [
    lambda: ExtrudeEdges.Execute(sel(c), P(20, 0, 0), D(0, 0, 1), MM(10), ExtrudeEdgeOptions()),
    lambda: ExtrudeEdges.Execute(sel(c), MM(10), ExtrudeEdgeOptions())])
name_bodies(["Sheet_From_Arc"])
'''),
("03_pull_revolve_001_rect_360", {"expect": {"bodies": 1, "volume_mm3": 12566.370614}}, '''
s = planar(poly_curves([(5, 0, 0), (15, 0, 0), (15, 0, 20), (5, 0, 20)]), plane_xz(), "Revolve_Ring")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 360)
name_bodies(["Revolve_Ring"], [largest()])
'''),
("03_pull_revolve_002_rect_90", {"expect": {"bodies": 1, "volume_mm3": 3141.592654}}, '''
s = planar(poly_curves([(5, 0, 0), (15, 0, 0), (15, 0, 20), (5, 0, 20)]), plane_xz(), "Revolve_Quarter")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 90)
name_bodies(["Revolve_Quarter"], [largest()])
'''),
("03_pull_revolve_003_spline_profile_360", {"expect": {"bodies": 1}}, '''
cs = [spline_curve([(5, 0, 0), (12, 0, 6), (9, 0, 14), (5, 0, 20)]), seg((5, 0, 20), (5, 0, 0))]
s = planar(cs, plane_xz(), "Revolve_Spline")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 360)
name_bodies(["Revolve_Spline"], [largest()])
'''),
("03_pull_helix_001_circle_r1_pitch5_h20", {"expect": {"bodies": 1}}, '''
r = CircularSurface.Create(MM(1), D(0, 1, 0), P(10, 0, 0))
f = face0(r.CreatedBody)
RevolveFaces.ByHelix(sel(f), axis_line(), D(0, 0, 1), MM(20), MM(5), 0.0, True, False, RevolveFaceOptions())
name_bodies(["Helix_Coil"], [largest()])
'''),
("03_pull_helix_002_tapered_5deg", {"expect": {"bodies": 1}}, '''
r = CircularSurface.Create(MM(1), D(0, 1, 0), P(10, 0, 0))
f = face0(r.CreatedBody)
RevolveFaces.ByHelix(sel(f), axis_line(), D(0, 0, 1), MM(20), MM(5), DEG(5), True, False, RevolveFaceOptions())
name_bodies(["Helix_Tapered"], [largest()])
'''),
("03_pull_sweep_001_circle_along_arc", {"expect": {"bodies": 1}}, '''
path = dcurve(arc_curve((0, 0, 0), 40, 0, 90), "Sweep_Path_Arc")
r = CircularSurface.Create(MM(3), D(0, 1, 0), P(40, 0, 0))
Sweep.Execute(sel(face0(r.CreatedBody)), sel(path), SweepCommandOptions())
b = largest()
name_bodies(["Sweep_Arc"], [b])
ctx.data["volume_pappus_mm3"] = round(math.pi * 9 * (math.pi / 2 * 40), 6)
'''),
("03_pull_sweep_002_rect_along_spline", {"expect": {"bodies": 1}}, '''
path = dcurve(spline_curve([(0, 0, 0), (10, 5, 10), (20, 0, 20), (30, -5, 25)]), "Sweep_Path_Spline")
n = _unit((10, 5, 10))
try:
    ev = path.Shape.Geometry.Evaluate(path.Shape.Bounds.Start)
    d = ev.Tangent
    n = _unit((d.X, d.Y, d.Z))
except Exception as e:
    ctx.data["tangent_eval_error"] = unicode(e)
x = _perp(n)
y = _cross(n, x)
cor = [tuple(a * x[i] + b * y[i] for i in range(3)) for a, b in [(-2, -1), (2, -1), (2, 1), (-2, 1)]]
s = planar(poly_curves(cor), Plane.Create(Frame.Create(P(0, 0, 0), D(*x), D(*y))), "Sweep_Profile_Rect")
Sweep.Execute(sel(face0(s)), sel(path), SweepCommandOptions())
name_bodies(["Sweep_Spline"], [largest()])
'''),
("03_pull_sweep_003_along_polyline", {"expect": {"bodies": 1}}, '''
p1 = dcurve(seg((0, 0, 0), (0, 0, 30)), "Sweep_Path_L1")
p2 = dcurve(seg((0, 0, 30), (20, 0, 30)), "Sweep_Path_L2")
r = CircularSurface.Create(MM(2), D(0, 0, 1), P(0, 0, 0))
Sweep.Execute(sel(face0(r.CreatedBody)), sel(p1, p2), SweepCommandOptions())
name_bodies(["Sweep_L"], [largest()])
'''),
("03_pull_loft_001_rect_to_circle", {"expect": {"bodies": 1}}, '''
a = sheet_rect(-10, -10, 10, 10, 0, "Loft_Rect")
b = sheet_circle((0, 0, 30), 8, "Loft_Circle")
Loft.Create(sel(face0(a), face0(b)), None, LoftOptions())
name_bodies(["Loft_RectCircle"], [largest()])
'''),
("03_pull_loft_002_three_circles", {"expect": {"bodies": 1}}, '''
fs = [face0(sheet_circle((0, 0, z), r, "Loft_C%d" % i)) for i, (z, r) in enumerate([(0, 10), (20, 5), (40, 12)])]
Loft.Create(sel(fs), None, LoftOptions())
name_bodies(["Loft_3Circles"], [largest()])
'''),
("03_pull_loft_003_ruled", {"expect": {"bodies": 1, "volume_mm3": 4666.666667}}, '''
a = sheet_rect(-10, -10, 10, 10, 0, "Ruled_Bottom")
b = sheet_rect(-5, -5, 5, 5, 20, "Ruled_Top")
o = LoftOptions()
o.IsRuled = True
Loft.Create(sel(face0(a), face0(b)), None, o)
name_bodies(["Loft_Ruled"], [largest()])
'''),
("03_pull_profile_001_rect_30x10_h5", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 1500.0}}, '''
prof = find_type(ctx, "RectangleProfile")(Plane.PlaneXY, MM(30), MM(10))
first_ok(ctx, "extrude_profile", [
    lambda: ExtrudeProfile.Execute(prof, MM(5), master(GetRootPart()), "Profile_Rect"),
    lambda: ExtrudeProfile.Execute(prof, MM(5))])
name_bodies(["Profile_Rect"])
'''),
("03_pull_profile_002_circle_r6_h12", {"expect": {"bodies": 1, "faces": 3, "volume_mm3": 1357.168026}}, '''
prof = find_type(ctx, "CircleProfile")(Plane.PlaneXY, MM(6))
first_ok(ctx, "extrude_profile", [
    lambda: ExtrudeProfile.Execute(prof, MM(12), master(GetRootPart()), "Profile_Circle"),
    lambda: ExtrudeProfile.Execute(prof, MM(12))])
name_bodies(["Profile_Circle"])
'''),
]

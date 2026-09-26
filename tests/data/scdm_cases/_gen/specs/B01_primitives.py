BATCH = "B01_primitives"
S3 = 3 ** -0.5
CASES = [
("01_primitives_block_001_10x20x30", {"expect": {"bodies": 1, "faces": 6, "edges": 12, "vertices": 8, "volume_mm3": 6000.0}}, '''
block((0, 0, 0), (10, 20, 30), "Block_10x20x30")
'''),
("01_primitives_block_002_offset_neg", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 1500.0}}, '''
block((-15, -5, -2.5), (15, 5, 2.5), "Block_Offset_Neg")
'''),
("01_primitives_block_003_thin_100x100x0p5", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 5000.0}}, '''
block((0, 0, 0), (100, 100, 0.5), "Thin_Plate")
'''),
("01_primitives_cylinder_001_r10_h20_z", {"expect": {"bodies": 1, "faces": 3, "volume_mm3": 6283.185307}}, '''
cylinder((0, 0, 0), (0, 0, 20), 10, "Cyl_Z")
ctx.data["cylinder_arg_order"] = CYL_ORDER[0]
'''),
("01_primitives_cylinder_002_r5_h50_x", {"expect": {"bodies": 1, "faces": 3, "volume_mm3": 3926.990817}}, '''
cylinder((0, 0, 0), (50, 0, 0), 5, "Cyl_X")
ctx.data["cylinder_arg_order"] = CYL_ORDER[0]
'''),
("01_primitives_cylinder_003_r2_h1_oblique", {"expect": {"bodies": 1, "faces": 3, "volume_mm3": 12.566371}}, '''
s = 3 ** -0.5
cylinder((0, 0, 0), (s, s, s), 2, "Cyl_Oblique")
ctx.data["cylinder_arg_order"] = CYL_ORDER[0]
'''),
("01_primitives_sphere_001_r10", {"expect": {"bodies": 1, "faces": 1, "volume_mm3": 4188.790205}}, '''
sphere((0, 0, 0), 10, "Sphere_R10")
'''),
("01_primitives_sphere_002_r3_offcenter", {"expect": {"bodies": 1, "faces": 1, "volume_mm3": 113.097336}}, '''
sphere((5, -7, 2), 3, "Sphere_R3_Off")
'''),
("01_primitives_tube_001_line_r2_l50", {"expect": {"bodies": 1}}, '''
c = dcurve(seg((0, 0, 0), (50, 0, 0)), "Tube_Path_Line")
r = TubeBody.Create(sel(c), MM(2), ExtrudeType.ForceIndependent)

name_bodies(["Tube_Line"])
ctx.data["tube_volume_mm3"] = vol(largest())
'''),
("01_primitives_tube_002_arc_r3", {"expect": {"bodies": 1}}, '''
c = dcurve(arc_curve((0, 0, 0), 30, 0, 90), "Tube_Path_Arc")
TubeBody.Create(sel(c), MM(3), ExtrudeType.ForceIndependent)
name_bodies(["Tube_Arc"])
ctx.data["tube_volume_mm3"] = vol(largest())
'''),
("01_primitives_tube_003_spline_r1", {"expect": {"bodies": 1}}, '''
c = dcurve(spline_curve([(0, 0, 0), (10, 5, 5), (20, 0, 10), (30, 5, 15)]), "Tube_Path_Spline")
TubeBody.Create(sel(c), MM(1), ExtrudeType.ForceIndependent)
name_bodies(["Tube_Spline"])
'''),
("01_primitives_cone_001_r10_h20", {"expect": {"bodies": 1, "volume_mm3": 2094.395102},
  "commands": ["PlanarBody.Create (triangle in XZ)", "RevolveFaces.Execute(360deg about Z)"]}, '''
s = planar(poly_curves([(0, 0, 0), (10, 0, 0), (0, 0, 20)]), plane_xz(), "Cone_Profile")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 360)
name_bodies(["Cone"], [largest()])
'''),
("01_primitives_cone_002_frustum_r10_r5_h15", {"expect": {"bodies": 1, "volume_mm3": 2748.893572},
  "commands": ["PlanarBody.Create (trapezoid in XZ)", "RevolveFaces.Execute(360deg about Z)"]}, '''
s = planar(poly_curves([(0, 0, 0), (10, 0, 0), (5, 0, 15), (0, 0, 15)]), plane_xz(), "Frustum_Profile")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 360)
name_bodies(["Frustum"], [largest()])
'''),
("01_primitives_torus_001_R20_r5", {"expect": {"bodies": 1, "volume_mm3": 9869.604401},
  "commands": ["CircularSurface.Create", "RevolveFaces.Execute(360deg about Z)"]}, '''
r = CircularSurface.Create(MM(5), D(0, 1, 0), P(20, 0, 0))
revolve(face0(r.CreatedBody), (0, 0, 0), (0, 0, 1), 360)
name_bodies(["Torus"], [largest()])
'''),
("01_primitives_torus_002_partial_180deg", {"expect": {"bodies": 1, "volume_mm3": 4934.802201},
  "commands": ["CircularSurface.Create", "RevolveFaces.Execute(180deg about Z)"]}, '''
r = CircularSurface.Create(MM(5), D(0, 1, 0), P(20, 0, 0))
revolve(face0(r.CreatedBody), (0, 0, 0), (0, 0, 1), 180)
name_bodies(["Torus_Half"], [largest()])
'''),
("01_primitives_planar_001_rect_40x20", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 800.0}}, '''
sheet_rect(0, 0, 40, 20, 0, "Planar_Rect")
'''),
("01_primitives_planar_002_circle_r15", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 706.858347}}, '''
sheet_circle((0, 0, 0), 15, "Planar_Circle")
'''),
]

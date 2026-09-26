BATCH = "B13_combo_a"
B = {}
E = {}
B["20_combo_bracket_001_sketch_pull_round_hole"] = '''
s = planar(poly_curves([(0, 0, 0), (60, 0, 0), (60, 8, 0), (8, 8, 0), (8, 40, 0), (0, 40, 0)]), plane_xy(0), "L_Bracket")
extrude(face0(s), 30)
b = largest()
ConstantRound.Execute(sel(edge_nearest(b, (8, 8, 15), "Line")), MM(5), ConstantRoundOptions())
b = largest()
for x in (30, 50):
    subtract(ctx, largest(), cylinder((x, -1, 15), (x, 9, 15), 3, "Hole_Cutter"))
delete_sheets()
name_bodies(["L_Bracket"], [largest()])
intent("volume_mm3", round(total_volume(), 1), 21788.5, 3.0)
'''
E["20_combo_bracket_001_sketch_pull_round_hole"] = {"bodies": 1}
B["20_combo_flange_002_revolve_pattern_chamfer"] = '''
s = planar(poly_curves([(10, 0, 0), (50, 0, 0), (50, 0, 10), (20, 0, 10), (20, 0, 30), (10, 0, 30)]), plane_xz(), "Flange")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 360)
delete_sheets()
subtract(ctx, largest(), cylinder((40, 0, -1), (40, 0, 11), 5, "Hole_Cutter"))
p = largest()
hole = [f for f in faces(p, "Cylinder") if _dist(bbox_center(f), (40, 0, 5)) < 6][0]
outer = max(faces(p, "Cylinder"), key=lambda f: bbox(f)[1][0] - bbox(f)[0][0])
d = CircularPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.One), ("CircularAxis", sel(outer)),
              ("CircularCount", 6), ("CircularAngle", DEG(360))], "circular")
Pattern.CreateCircular(sel(hole), d, None)
p = largest()
rim = max(edges_at_z(p, 10), key=lambda e: bbox(e)[1][0] - bbox(e)[0][0])
Chamfer.Execute(sel(rim), MM(1))
name_bodies(["Flange"], [largest()])
intent("hole_faces", len([f for f in faces(largest(), "Cylinder") if abs(bbox(f)[1][0] - bbox(f)[0][0] - 10) < 0.01]), 6)
intent_range("volume_mm3", total_volume(), 89250, 89480)
'''
E["20_combo_flange_002_revolve_pattern_chamfer"] = {"bodies": 1}
B["20_combo_plate_003_linear_pattern_holes_round"] = '''
plate = block((0, 0, 0), (80, 80, 5), "Plate_Holes")
subtract(ctx, plate, cylinder((34, 40, -1), (34, 40, 6), 2, "Hole_Cutter"))
p = largest()
hole = faces(p, "Cylinder")[0]
d = LinearPatternData()
setp(ctx, d, [("PatternDimension", PatternDimensionType.Two), ("LinearDirection", sel(edge_nearest(p, (40, 0, 0), "Line"))),
              ("CountX", 3), ("PitchX", MM(12)), ("CountY", 4), ("PitchY", MM(10))], "linear")
Pattern.CreateLinear(sel(hole), d, None)
p = largest()
ctx.data["hole_faces"] = len(faces(p, "Cylinder"))
vert = [e for e in edges(p, "Line") if abs(bbox(e)[1][2] - bbox(e)[0][2] - 5) < 1e-3]
ConstantRound.Execute(sel(vert), MM(1), ConstantRoundOptions())
name_bodies(["Plate_Holes"], [largest()])
intent("hole_faces", ctx.data["hole_faces"], 12)
intent("vertical_edges_rounded", len(vert), 4)
'''
E["20_combo_plate_003_linear_pattern_holes_round"] = {"bodies": 1}
B["20_combo_housing_004_block_shell_round"] = '''
b = block((0, 0, 0), (80, 60, 40), "Housing")
vert = [e for e in edges(b, "Line") if abs(bbox(e)[1][2] - bbox(e)[0][2] - 40) < 1e-3]
ConstantRound.Execute(sel(vert), MM(8), ConstantRoundOptions())
b = largest()
Shell.RemoveFaces(sel(top_face(b)), MM(-2))
name_bodies(["Housing"], [largest()])
intent("vertical_edges", len(vert), 4)
intent("volume_mm3", round(total_volume(), 1), 29248.6, 60.0)
'''
E["20_combo_housing_004_block_shell_round"] = {"bodies": 1}
B["20_combo_bool_005_block_cyl_sphere"] = '''
b = block((0, 0, 0), (40, 40, 20), "Bool_Part")
c = cylinder((20, 20, 20), (20, 20, 40), 10, "Boss")
Combine.Merge(sel(b, c))
b = largest()
subtract(ctx, b, sphere((20, 20, 40), 8, "Sphere_Cutter"))
tool = cylinder((20, 20, -1), (20, 20, 50), 18, "Intersect_Tool")
intersect_keep(ctx, largest([x for x in bodies_now() if x.Name != "Intersect_Tool"]), tool)
name_bodies(["Bool_Part"], [largest()])
bb = bbox(largest())
intent("x_span_mm", round(bb[1][0] - bb[0][0], 3), 36.0, 0.01)
intent("bodies_left", len(bodies_now()), 1)
'''
E["20_combo_bool_005_block_cyl_sphere"] = {"bodies": 1}
B["20_combo_shaft_006_revolve_chamfer_keyway"] = '''
s = planar(poly_curves([(0, 0, 0), (10, 0, 0), (10, 0, 40), (8, 0, 40), (8, 0, 70), (0, 0, 70)]), plane_xz(), "Shaft")
revolve(face0(s), (0, 0, 0), (0, 0, 1), 360)
delete_sheets()
b = largest()
ends = [max(edges_at_z(b, 0), key=lambda e: bbox(e)[1][0]), max(edges_at_z(b, 70), key=lambda e: bbox(e)[1][0])]
Chamfer.Execute(sel(ends), MM(1))
subtract(ctx, largest(), block((7, -3, 5), (11, 3, 35), "Keyway_Cutter"))
name_bodies(["Shaft"], [largest()])
v0 = 3.14159265 * (100 * 40 + 64 * 30)
intent_range("volume_mm3", total_volume(), v0 - 700, v0 - 450)
'''
E["20_combo_shaft_006_revolve_chamfer_keyway"] = {"bodies": 1}
B["20_combo_spline_007_spline_extrude_round"] = '''
import math
pts = [(25 * math.cos(a) * (1 + 0.15 * math.cos(3 * a)), 25 * math.sin(a) * (1 + 0.15 * math.cos(3 * a)), 0) for a in [i * math.pi / 4 for i in range(8)]]
s = planar([spline_curve(pts, True)], plane_xy(0), "Spline_Disk")
extrude(face0(s), 10)
delete_sheets()
b = largest()
ConstantRound.Execute(sel(edges_at_z(b, 10)), MM(1), ConstantRoundOptions())
name_bodies(["Spline_Disk"], [largest()])
intent_range("faces", face_count(largest()), 4, 8)
'''
E["20_combo_spline_007_spline_extrude_round"] = {"bodies": 1}
B["20_combo_loft_008_loft_shell"] = '''
fs = [face0(sheet_circle((0, 0, z), r, "Loft_C%d" % i)) for i, (z, r) in enumerate([(0, 10), (20, 6), (40, 12)])]
Loft.Create(sel(fs), None, LoftOptions())
delete_sheets()
b = largest()
v0 = vol(b)
Shell.RemoveFaces(sel(top_face(b)), MM(-1))
name_bodies(["Loft_Shell"], [largest()])
ctx.data["loft_volume_mm3"] = v0
intent_range("shell_fraction", round(vol(largest()) / v0, 3), 0.05, 0.4)
'''
E["20_combo_loft_008_loft_shell"] = {"bodies": 1}
B["20_combo_sweep_009_pipe_bend"] = '''
p1 = dcurve(seg((0, 0, 0), (0, 0, 30)), "Path_L1")
p2 = dcurve(arc_curve((40, 0, 30), 40, -90, 0, (0, 1, 0), (0, 0, 1)), "Path_Arc")
p3 = dcurve(seg((40, 0, 70), (80, 0, 70)), "Path_L2")
ctx.data["arc_ends"] = [edge_mid(p2)]
r = CircularSurface.Create(MM(10), D(0, 0, 1), P(0, 0, 0))
Sweep.Execute(sel(face0(r.CreatedBody)), sel(p1, p2, p3), SweepCommandOptions())
delete_sheets()
b = largest()
e1 = face_extreme(b, (0, 0, 1), -1)
e2 = face_extreme(b, (1, 0, 0), 1)
Shell.RemoveFaces(sel(e1, e2), MM(-1))
name_bodies(["Pipe_Bend"], [largest()])
L = 30 + 40 * 3.14159265 / 2 + 40
intent("volume_mm3", round(total_volume(), 1), round(L * 3.14159265 * (100 - 81), 1), 80.0)
'''
E["20_combo_sweep_009_pipe_bend"] = {"bodies": 1}
B["20_combo_mirror_010_half_model_mirror_merge"] = '''
b = block((0, 0, 0), (30, 20, 5), "Bracket_Half")
c = cylinder((20, 10, 5), (20, 10, 15), 4, "Boss")
Combine.Merge(sel(b, c))
b = largest()
o = MirrorOptions()
o.MergeObjects = True
Mirror.Execute(sel(b), sel(face_extreme(b, (1, 0, 0), -1)), o)
name_bodies(["Bracket_Full"], [largest()])
intent("volume_mm3", round(total_volume(), 1), round(2 * (3000 + 3.14159265 * 16 * 10), 1), 1.0)
intent("x_min_mm", round(bbox(largest())[0][0], 3), -30.0, 0.01)
'''
E["20_combo_mirror_010_half_model_mirror_merge"] = {"bodies": 1}
B["20_combo_split_011_split_multi_body_names_colors"] = '''
b = block((0, 0, 0), (40, 30, 30), "Split_Stack")
SplitBody.ByCutter(sel(b), plane_xy(10))
up = [x for x in bodies_now() if bbox(x)[0][2] > 5][0]
SplitBody.ByCutter(sel(up), plane_xy(20))
bs = sorted(bodies_now(), key=lambda x: bbox(x)[0][2])
name_bodies(["Part_A", "Part_B", "Part_C"], bs)
cols = [Color.FromArgb(255, 255, 0, 0), Color.FromArgb(255, 0, 180, 0), Color.FromArgb(255, 0, 0, 255)]
for x, col in zip(bs, cols):
    ColorHelper.SetColor(sel(x), SetColorOptions(), col)
intent("names", sorted([unicode(x.Name) for x in all_bodies()]), [u"Part_A", u"Part_B", u"Part_C"])
'''
E["20_combo_split_011_split_multi_body_names_colors"] = {"bodies": 3, "volume_mm3": 36000.0}
B["20_combo_doc_012_layers_colors_named_selections"] = '''
a = block((0, 0, 0), (20, 20, 20), "Doc_Block")
c = cylinder((40, 10, 0), (40, 10, 20), 8, "Doc_Cylinder")
s = sphere((70, 10, 10), 10, "Doc_Sphere")
Layers.Create("L_solids_A")
Layers.Create("L_solids_B")
Layers.AssignLayer(sel(a, c), "L_solids_A")
Layers.AssignLayer(sel(s), "L_solids_B")
ColorHelper.SetColor(sel(top_face(a)), SetColorOptions(), Color.FromArgb(255, 255, 128, 0))
ColorHelper.SetColor(sel(faces(c, "Cylinder")), SetColorOptions(), Color.FromArgb(255, 0, 128, 255))
for nm, obj in [("NS_Block_Top", [top_face(a)]), ("NS_Cyl_Side", faces(c, "Cylinder")), ("NS_Sphere", [s])]:
    r = NamedSelection.Create(sel(obj), Selection.Empty())
    NamedSelection.Rename(unicode(r.CreatedNamedSelection.Name), nm)
intent("ns_count", len(doc_stats()["named_selections"]), 3)
'''
E["20_combo_doc_012_layers_colors_named_selections"] = {"bodies": 3}
B["20_combo_doc_013_datums_named_selection_on_edges"] = '''
b = block((0, 0, 0), (40, 30, 20), "Datum_Round_Block")
ConstantRound.Execute(sel(edges_at_z(b, 20)), MM(2), ConstantRoundOptions())
b = largest()
DatumPlaneCreator.Create(P(0, 0, 5), D(0, 0, 1))
first_ok(ctx, "datum_axis", [lambda: DatumLineCreator.Create(P(20, 15, 0), D(0, 0, 1))])
rounds = faces(b, "Cylinder")
r = NamedSelection.Create(sel(rounds), Selection.Empty())
NamedSelection.Rename(unicode(r.CreatedNamedSelection.Name), "NS_Round_Faces")
intent("round_faces", len(rounds), 4)
'''
E["20_combo_doc_013_datums_named_selection_on_edges"] = {"bodies": 1, "datum_planes": 1}
B["20_combo_asm_014_two_components"] = '''
cp = component("Plate", lambda: block((0, 0, 0), (60, 40, 10), "Plate_Body"))
cb = component("Boss", lambda: cylinder((30, 20, 10), (30, 20, 30), 8, "Boss_Body"))
first_ok(ctx, "setname", [lambda: ComponentHelper.SetName(cp, "Base_Plate"), lambda: RenameObject.Execute(sel(cp), "Base_Plate")])
ctx.data["component_names"] = [unicode(x.Name) for x in GetRootPart().Components]
intent("has_Base_Plate", any(unicode(x.Name) == u"Base_Plate" for x in GetRootPart().Components), True)
'''
E["20_combo_asm_014_two_components"] = {"components": 2, "bodies": 2}
B["20_combo_asm_015_instances_pattern"] = '''
comp = component("Bolt", lambda: cylinder((0, 0, 0), (0, 0, 30), 4, "Bolt_Body"))
root = GetRootPart()
tmpl = _safe(lambda: comp.Template) or master(comp).Template
for i in range(1, 4):
    def inst():
        n0 = len(list(root.Components))
        Copy.ToClipboard(sel(comp))
        Paste.FromClipboard()
        cs = list(root.Components)
        if len(cs) <= n0:
            raise Exception("paste created no component")
        return cs[-1]
    c = first_ok(ctx, "copy_%d" % i, [inst, lambda: raw("instance", lambda: Component.Create(master(root), tmpl))])
    c.Transform(Matrix.CreateTranslation(Vector.Create(MM(30 * i), 0, 0)))
    if i == 3:
        c.Transform(Matrix.CreateRotation(Line.Create(P(90, 0, 0), D(1, 0, 0)), DEG(90)))
ctx.data["part_defs"] = doc_stats()["part_defs"]
intent("bodies", len(all_bodies()), 4)
'''
E["20_combo_asm_015_instances_pattern"] = {"components": 4}
B["20_combo_asm_016_nested_3levels_colors_layers"] = '''
c1 = ComponentHelper.CreateAtRoot("Level_1")
c2 = first_ok(ctx, "l2", [lambda: list(ComponentHelper.CreateAtComponent(c1, "Level_2").CreatedComponents)[0], lambda: list(c1.Components)[0]])
c3 = first_ok(ctx, "l3", [lambda: list(ComponentHelper.CreateAtComponent(c2, "Level_3").CreatedComponents)[0], lambda: list(c2.Components)[0]])
Layers.Create("L_level_1")
Layers.Create("L_level_3")
for i, c in enumerate([c1, c2, c3]):
    ComponentHelper.SetActive(c)
    b = block((30 * i, 0, 0), (30 * i + 20, 20, 10 * (i + 1)), "Level_%d_Body" % (i + 1))
    ColorHelper.SetColor(sel(b), SetColorOptions(), Color.FromArgb(255, 80 * i, 100, 255 - 80 * i))
    if i != 1:
        Layers.AssignLayer(sel(b), "L_level_%d" % (i + 1))
ComponentHelper.SetRootActive()
ctx.data["component_list"] = doc_stats()["component_list"]
intent("bodies", len(all_bodies()), 3)
'''
E["20_combo_asm_016_nested_3levels_colors_layers"] = {"components": 3}

import json as _json, os as _os
_PLAN = {c["case_key"]: c for c in _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "_inventory", "combo_plan.json"), encoding="utf-8"))["combos"]}
CASES = []
for _k in B:
    _c = _PLAN[_k]
    CASES.append((_k, {"category": "20_combo", "feature": "combo", "priority": _c["priority"], "title": _c["title"],
                       "commands": _c["features"], "inventory_expect": _c.get("expect"), "expect": E[_k],
                       "notes": "steps: " + "; ".join(_c["steps"]) + " | headless_feasibility: " + _c.get("headless_feasibility", "")}, B[_k]))

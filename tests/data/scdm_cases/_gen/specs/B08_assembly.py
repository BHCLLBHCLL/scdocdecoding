BATCH = "B08_assembly"
CASES = [
("10_assembly_component_001_two_bodies_two_comps", {"expect": {"bodies": 2, "components": 2}}, '''
a = block((0, 0, 0), (30, 20, 10), "Base_Block")
c = cylinder((50, 10, 0), (50, 10, 20), 5, "Boss_Cyl")
r = ComponentHelper.CreateSeparateComponents(sel(a, c))
comps = list(GetRootPart().Components)
for cp in comps:
    n = [x.Name for x in comp_bodies(cp)]
    ctx.attempt("setname_" + (n[0] if n else "?"), lambda: ComponentHelper.SetName(cp, "Comp_" + (n[0] if n else "X")))
ctx.data["component_names"] = [unicode(x.Name) for x in GetRootPart().Components]
'''),
("10_assembly_component_002_nested_2levels", {"expect": {"bodies": 1, "components": 2}}, '''
c1 = ComponentHelper.CreateAtRoot("Level_1")
r = ComponentHelper.CreateAtComponent(c1, "Level_2")
c2 = first_ok(ctx, "level2", [lambda: list(r.CreatedComponents)[0], lambda: list(c1.Components)[0]])
ComponentHelper.SetActive(c2)
block((0, 0, 0), (20, 20, 20), "Nested_Block")
ComponentHelper.SetRootActive()
ctx.data["paths"] = doc_stats()["component_list"]
'''),
("10_assembly_component_003_separate_components_4", {"expect": {"bodies": 4, "components": 4}}, '''
bs = [block((30 * i, 0, 0), (30 * i + 20, 20, 10 + 5 * i), "Part_%d" % (i + 1)) for i in range(4)]
ComponentHelper.CreateSeparateComponents(sel(bs))
ctx.data["component_names"] = [unicode(x.Name) for x in GetRootPart().Components]
'''),
("10_assembly_instance_001_3_instances_translated", {"expect": {"components": 3, "part_defs": 1, "bodies": 3}}, '''
comp = component("Bolt", lambda: cylinder((0, 0, 0), (0, 0, 30), 4, "Bolt_Body"))
root = GetRootPart()
tmpl = _safe(lambda: comp.Template) or master(comp).Template
for i in (1, 2):
    c = raw("instance", lambda: Component.Create(master(root), tmpl))
    c.Transform(Matrix.CreateTranslation(Vector.Create(MM(50 * i), 0, 0)))
intent("instance_x_max_mm", round(max(bbox(b)[1][0] for b in all_bodies()), 3), 104.0)
'''),
("10_assembly_instance_002_rotated_instance", {"expect": {"components": 2, "part_defs": 1, "bodies": 2}}, '''
comp = component("Arm", lambda: block((0, -2, 0), (40, 2, 4), "Arm_Body"))
root = GetRootPart()
tmpl = _safe(lambda: comp.Template) or master(comp).Template
c = raw("instance", lambda: Component.Create(master(root), tmpl))
c.Transform(Matrix.CreateRotation(Line.Create(P(0, 0, 0), D(0, 0, 1)), DEG(90)))
bbs = [bbox(b) for b in all_bodies()]
ctx.data["bboxes"] = bbs
intent("rotated_y_max_mm", round(max(x[1][1] for x in bbs), 3), 40.0)
'''),
("10_assembly_instance_003_make_independent", {"expect": {"components": 2, "part_defs": 2, "bodies": 2}}, '''
comp = component("Pin", lambda: cylinder((0, 0, 0), (0, 0, 20), 3, "Pin_Body"))
root = GetRootPart()
tmpl = _safe(lambda: comp.Template) or master(comp).Template
c = raw("instance", lambda: Component.Create(master(root), tmpl))
c.Transform(Matrix.CreateTranslation(Vector.Create(MM(30), 0, 0)))
ctx.data["part_defs_before"] = doc_stats()["part_defs"]
comps = list(root.Components)
first_ok(ctx, "make_independent", [lambda: ComponentHelper.MakeIndependent(comps[-1]),
                                   lambda: ComponentHelper.MakeIndependent(sel(comps[-1]))])
'''),
("10_assembly_mirrorcomp_001", {"expect": {"components": 2}}, '''
comp = component("Wing", lambda: block((10, 0, 0), (30, 10, 5), "Wing_Body"))
r = DatumPlaneCreator.Create(P(0, 0, 0), D(1, 0, 0))
dp = list(GetRootPart().DatumPlanes)[-1]
_safe(lambda: set_name(dp, "Mirror_YZ"))
MirrorComponents.Execute(sel(comp), sel(dp))
ctx.data["bboxes"] = [bbox(b) for b in all_bodies()]
intent("mirrored_x_min_mm", round(min(bbox(b)[0][0] for b in all_bodies()), 3), -30.0)
'''),
("10_assembly_align_001_axis_axis", {"expect": {"components": 2, "mating_conditions": 1},
  "notes": "condition is stored; headless RunScript does not solve/move components"}, '''
plate = block((0, 0, 0), (60, 40, 10), "Plate_Body")
subtract(ctx, plate, cylinder((30, 20, -5), (30, 20, 15), 4, "Hole_Cutter"))
set_name(largest(), "Plate_Body")
cylinder((100, 20, 5), (100, 20, 35), 4, "Pin_Body")
ComponentHelper.CreateSeparateComponents(sel(bodies_now()))
comps = list(GetRootPart().Components)
cp = [c for c in comps if any(x.Name == "Plate_Body" for x in comp_bodies(c))][0]
cq = [c for c in comps if any(x.Name == "Pin_Body" for x in comp_bodies(c))][0]
pb = comp_bodies(cp)[0]
hole = faces(pb, "Cylinder")[0]
pin = faces(comp_bodies(cq)[0], "Cylinder")[0]
raw("align", lambda: AlignCondition.Create(GetRootPart(), hole, pin))
ctx.data["pin_bbox_after"] = bbox(comp_bodies(cq)[0])
'''),
("10_assembly_tangent_001_face_face", {"expect": {"components": 2, "mating_conditions": 1}}, '''
ca = component("Lower", lambda: block((0, 0, 0), (40, 40, 10), "Lower_Body"))
cb = component("Upper", lambda: block((0, 0, 20), (20, 20, 30), "Upper_Body"))
raw("tangent", lambda: TangentCondition.Create(GetRootPart(), top_face(comp_bodies(ca)[0]), bottom_face(comp_bodies(cb)[0])))
'''),
("10_assembly_anchor_001_plate", {"expect": {"components": 1, "mating_conditions": 1}}, '''
cp = component("Anchored_Plate", lambda: block((0, 0, 0), (60, 40, 5), "Plate_Body"))
raw("anchor", lambda: AnchorCondition.Create(GetRootPart(), cp))
'''),
("10_assembly_rigid_001", {"expect": {"components": 2, "mating_conditions": 1}}, '''
ca = component("Part_A", lambda: block((0, 0, 0), (30, 30, 10), "Body_A"))
cb = component("Part_B", lambda: block((40, 0, 0), (70, 30, 10), "Body_B"))
raw("rigid", lambda: RigidCondition.Create(GetRootPart(), ca, cb))
'''),
("10_assembly_insert_001_step_block", {"expect": {"bodies": 2},
  "notes": "STEP written by this case to 10_assembly\\\\_inputs (scdm_cases only), then inserted next to a native block"}, '''
import System
d = System.IO.Path.Combine(CASE["out_dir"], "_inputs")
if not System.IO.Directory.Exists(d):
    System.IO.Directory.CreateDirectory(d)
stp = System.IO.Path.Combine(d, "insert_block_20x10x5.stp")
block((0, 0, 0), (20, 10, 5), "Step_Source_Block")
first_ok(ctx, "export_step", [lambda: DocumentSave.Execute(stp), lambda: DocumentHelper.GetActiveDocument().SaveAs(stp)])
ctx.data["step_exists"] = System.IO.File.Exists(stp)
Delete.Execute(sel(bodies_now()))
block((40, 0, 0), (60, 10, 5), "Native_Block")
if System.IO.File.Exists(stp):
    DocumentInsert.Execute(stp)
else:
    raise Exception("STEP export produced no file")
ctx.data["bodies_after_insert"] = [unicode(b.Name) for b in all_bodies()]
intent("total_volume_mm3", total_volume(), 2000.0)
'''),
]

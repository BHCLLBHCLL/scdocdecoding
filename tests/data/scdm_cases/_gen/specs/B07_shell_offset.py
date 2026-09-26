BATCH = "B07_shell_offset"
CASES = [
("07_shell_open_001_block_top_t2", {"expect": {"bodies": 1, "faces": 11, "volume_mm3": 7152.0},
  "notes": "t=2 inward: Shell.RemoveFaces(..., MM(-2)) (V18 API: positive grows outward)"}, '''
b = block((0, 0, 0), (40, 30, 20), "Housing")
Shell.RemoveFaces(sel(top_face(b)), MM(-2))
ctx.data["bbox_after_mm"] = bbox(body_named("Housing"))
'''),
("07_shell_closed_002_hollow_sphere_t1", {"expect": {"bodies": 1, "faces": 2, "volume_mm3": 1135.162145}}, '''
b = sphere((0, 0, 0), 10, "Hollow_Sphere")
first_ok(ctx, "shell_body", [
    lambda: Shell.ShellBodies(sel(b), MM(-1)),
    lambda: Shell.ShellBodies(sel(b), MM(1))])
ctx.data["volume_after_mm3"] = vol(body_named("Hollow_Sphere"))
'''),
("07_shell_open_003_cyl_top_t1p5", {"expect": {"bodies": 1, "faces": 5, "volume_mm3": 2955.845988},
  "notes": "t=1.5 inward"}, '''
b = cylinder((0, 0, 0), (0, 0, 30), 10, "Cup")
Shell.RemoveFaces(sel(top_face(b)), MM(-1.5))
'''),
("07_offset_001_block_top_plus3", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 27600.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Offset_Block")
OffsetFaces.Execute(sel(top_face(b)), MM(3), OffsetFaceOptions())
'''),
("07_offset_002_cyl_face_minus1", {"expect": {"bodies": 1, "faces": 3}}, '''
b = cylinder((0, 0, 0), (0, 0, 20), 10, "Offset_Cyl")
OffsetFaces.Execute(sel(faces(b, "Cylinder")), MM(-1), OffsetFaceOptions())
ctx.data["volume_after_mm3"] = vol(body_named("Offset_Cyl"))
ctx.data["r9_volume_mm3"] = round(math.pi * 81 * 20, 6)
'''),
("07_thicken_001_planar_t2", {"expect": {"bodies": 1, "faces": 6, "volume_mm3": 1600.0}}, '''
s = sheet_rect(0, 0, 40, 20, 0, "Thickened_Plate")
ThickenFaces.Execute(sel(face0(s)), D(0, 0, 1), MM(2), ThickenFaceOptions())
name_bodies(["Thickened_Plate"], [largest()])
'''),
("07_thicken_002_cyl_sheet_t1", {"expect": {"bodies": 1}}, '''
c = dcurve(arc_curve((0, 0, 0), 20, 0, 180), "HalfCyl_Arc")
ExtrudeEdges.Execute(sel(c), P(20, 0, 0), D(0, 0, 1), MM(30), ExtrudeEdgeOptions())
sh = [x for x in bodies_now() if is_sheet(x)]
ctx.data["sheets"] = len(sh)
s = sh[0]
set_name(s, "HalfCyl_Thick")
ThickenFaces.Execute(sel(face0(s)), D(1, 0, 0), MM(1), ThickenFaceOptions())
name_bodies(["HalfCyl_Thick"], [largest()])
ctx.data["volume_outward_mm3"] = round(math.pi * (21 ** 2 - 20 ** 2) / 2 * 30, 6)
'''),
("07_draft_001_block_4sides_5deg", {"expect": {"bodies": 1, "faces": 6}}, '''
b = block((0, 0, 0), (40, 30, 20), "Draft_Block")
sides = [face_extreme(b, a, s) for a in [(1, 0, 0), (0, 1, 0)] for s in (1, -1)]
ref = bottom_face(b)
first_ok(ctx, "draft", [
    lambda: DraftFaces.Execute(sel(sides), sel(ref), DraftSide.This, DEG(5), getattr(ExtrudeType, "None"), DraftOptions()),
    lambda: DraftFaces.Execute(sel(sides), sel(ref), DraftSide.NoSplit, DEG(5), getattr(ExtrudeType, "None"), DraftOptions()),
    lambda: DraftFaces.Execute(sel(sides), sel(ref), DraftSide.This, DEG(5), ExtrudeType.Add, DraftOptions())])
ctx.data["bbox_after_mm"] = bbox(body_named("Draft_Block"))
ctx.data["volume_after_mm3"] = vol(body_named("Draft_Block"))
'''),
("07_draft_002_cyl_side_3deg", {"expect": {"bodies": 1, "faces": 3}}, '''
b = cylinder((0, 0, 0), (0, 0, 20), 10, "Draft_Cyl")
first_ok(ctx, "draft", [
    lambda: DraftFaces.Execute(sel(faces(b, "Cylinder")), sel(bottom_face(b)), DraftSide.This, DEG(3), getattr(ExtrudeType, "None"), DraftOptions()),
    lambda: DraftFaces.Execute(sel(faces(b, "Cylinder")), sel(bottom_face(b)), DraftSide.NoSplit, DEG(3), getattr(ExtrudeType, "None"), DraftOptions())])
ctx.data["surface_types_after"] = [gtype(f) for f in body_named("Draft_Cyl").Faces]
'''),
("07_replaceface_001_block_top_to_plane", {"expect": {"volume_mm3": 30000.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Replace_Block")
t = sheet_rect(-10, -10, 50, 40, 25, "Replace_Target")
top = top_face(b)
tf = face0(t)
def _replace(fn):
    fn()
    z = bbox(body_named("Replace_Block"))[1][2]
    if abs(z - 25.0) > 1e-3:
        raise Exception("no change (block zmax %.4f)" % z)
def _faces_list(*fs):
    l = List[API.IDesignFace]()
    for f in fs:
        l.Add(f)
    return l
first_ok(ctx, "replace", [
    lambda: _replace(lambda: ReplaceFacesWithFace.Execute(_faces_list(top, tf))),
    lambda: _replace(lambda: ReplaceFacesWithFace.Execute(_faces_list(tf, top))),
    lambda: _replace(lambda: ReplaceFacesWithFace.Execute(sel(tf, top))),
    lambda: _replace(lambda: ReplaceFacesWithFace.Execute(sel(top, tf)))])
ctx.data["target_bbox_after_mm"] = _safe(lambda: bbox(body_named("Replace_Target")))
ctx.data["block_bbox_after_mm"] = bbox(body_named("Replace_Block"))
'''),
("07_detach_001_block_top", {"expect": {"bodies": 2}}, '''
b = block((0, 0, 0), (40, 30, 20), "Detach_Block")
DetachFaces.Execute(sel(top_face(b)))
bs = sorted(bodies_now(), key=lambda x: 0 if is_sheet(x) else 1)
name_bodies(["Detached_Top_Face", "Detach_Block"], bs)
'''),
]

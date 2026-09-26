BATCH = "B12_surface_holes_mesh"
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
_HOLE = '''
def std_hole(ctx, b, x, y, opts):
    top = top_face(b)
    pt = P(x, y, bbox(b)[1][2])
    HL = find_type(ctx, "HoleLocation")
    _safe(lambda: ctor_sigs(ctx, "HoleLocation"))
    mf = master(top)
    uv = _safe(lambda: mf.Shape.ProjectPoint(pt).Param)
    pool = [("IDesignFace", top), ("DesignFace", mf), ("Point", pt), ("PointUV", uv),
            ("IList`1", List[Point]([pt])), ("ICollection`1", List[Point]([pt])), ("IEnumerable`1", List[Point]([pt]))]
    def by_auto():
        loc = auto_new(ctx, "HoleLocation", HL, pool)
        L = List[HL]()
        L.Add(loc)
        return StandardHoles.Create(L, Selection.Empty(), opts)
    def by_auto2():
        loc = auto_new(ctx, "HoleLocation2", HL, pool)
        L = List[HL]()
        L.Add(loc)
        return StandardHoles.Create(L, opts)
    r = first_ok(ctx, "standard_hole", [by_auto, by_auto2])
    ctx.data["hole_result"] = _safe(lambda: [n for n in dir(r) if not n.startswith("_")])
    return r
'''
_HOLE_OPTS = '''
o = StandardHolesOptions()
ctx.data["hole_opts_default"] = dict((n, _safe(lambda: unicode(getattr(o, n)))) for n in ["SeriesName", "FastenerName", "HoleFit", "HoleRadius", "DrillSize", "HoleDepth", "DepthMeasurement", "Tapped"])
'''
CASES = [
("13_surface_circular_001_r20", {"expect": {"bodies": 1}}, '''
first_ok(ctx, "circular", [lambda: CircularSurface.Create(MM(20), D(0, 0, 1), P(0, 0, 0)),
                           lambda: CircularSurface.Create(MM(20), Direction.DirZ, Point.Origin)])
name_bodies(["Circular_Surface_R20"])
intent("area_mm2", round(doc_stats()["area_mm2"], 2), 1256.64, 0.5)
'''),
("13_surface_rect_001_30x10", {"expect": {"bodies": 1}}, '''
first_ok(ctx, "rect", [lambda: RectangularSurface.Create(MM(30), MM(10), P(0, 0, 0)),
                       lambda: RectangularSurface.Create(MM(30), MM(10))])
name_bodies(["Rect_Surface_30x10"])
intent("area_mm2", round(doc_stats()["area_mm2"], 2), 300.0, 0.5)
'''),
("13_surface_body_001_cylinder_patch", {"expect": {"bodies": 1}}, '''
import math
srf = Cylinder.Create(Frame.World, MM(10))
box = BoxUV.Create(Interval.Create(0, math.pi), Interval.Create(0, MM(20)))
first_ok(ctx, "surface_body", [lambda: SurfaceBody.Create(srf, box, GetRootPart(), "Cylinder_Patch"),
                               lambda: SurfaceBody.Create(srf, box, master(GetRootPart()), "Cylinder_Patch"),
                               lambda: SurfaceBody.Create(srf, box)])
name_bodies(["Cylinder_Patch"])
intent("area_mm2", round(doc_stats()["area_mm2"], 2), 628.32, 0.5)
'''),
("13_fill_001_cap_open_box", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (20, 20, 20), "Capped_Box")
Delete.Execute(sel(top_face(b)))
b = largest()
loop = edges_at_z(b, 20)
o = FillOptions()
setp(ctx, o, [("FillType", _safe(lambda: FillType.Cap))], "fill_opts")
first_ok(ctx, "fill", [lambda: Fill.Execute(sel(loop), Selection.Empty(), o, FillMode.ThreeD),
                       lambda: Fill.Execute(sel(loop)),
                       lambda: Fill.Execute(sel(loop), None, FillOptions(), FillMode.ThreeD)])
b = largest()
intent("faces", face_count(b), 6)
intent("volume_mm3", round(vol(b) or 0, 2), 8000.0, 1.0)
'''),
("13_fill_002_patch_4_splines", {"expect": {}}, '''
c = [spline_curve([(0, 0, 0), (15, 0, 4), (30, 0, 0)]), spline_curve([(30, 0, 0), (30, 15, 4), (30, 30, 0)]),
     spline_curve([(30, 30, 0), (15, 30, 4), (0, 30, 0)]), spline_curve([(0, 30, 0), (0, 15, 4), (0, 0, 0)])]
dc = [dcurve(s, "Boundary_%d" % (i + 1)) for i, s in enumerate(c)]
first_ok(ctx, "fill", [lambda: Fill.Execute(sel(dc), Selection.Empty(), FillOptions(), FillMode.ThreeD),
                       lambda: Fill.Execute(sel(dc))])
name_bodies(["Spline_Patch"])
intent("sheet_bodies", len([x for x in all_bodies() if is_sheet(x)]), 1)
intent_range("area_mm2", doc_stats()["area_mm2"], 850, 1100)
'''),
("13_splitface_001_block_top_two_points", {"expect": {"bodies": 1, "faces": 7, "volume_mm3": 24000.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Split_Block")
SplitFace.ByTwoPoints(sel(top_face(b)), P(20, 0, 20), P(20, 30, 20))
'''),
("13_splitedge_001_by_count3", {"expect": {"bodies": 1, "edges": 14}}, '''
b = block((0, 0, 0), (40, 30, 20), "Split_Edge_Block")
SplitEdge.ByCount(sel(edge_nearest(b, (20, 0, 20))), 3)
'''),
("13_project_001_circle_onto_block_top", {"expect": {"bodies": 1, "volume_mm3": 24000.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Project_Block")
c = dcurve(circle_curve((20, 15, 30), 5), "Circle_R5")
o = ProjectToSolidOptions()
first_ok(ctx, "project", [lambda: ProjectToSolid.Execute(sel(c), sel(top_face(b)), Selection.Empty(), o),
                          lambda: ProjectToSolid.Execute(sel(c), sel(top_face(b)), sel(edge_nearest(b, (0, 0, 10))), o),
                          lambda: ProjectToSolid.Execute(sel(c), sel(b), Selection.Empty(), o)])
intent("faces", face_count(largest()), 7)
'''),
("13_wrap_001_rect_onto_cylinder", {"expect": {}}, '''
cy = cylinder((0, 0, 0), (0, 0, 40), 10, "Wrap_Target_Cyl")
sh = planar(poly_curves([(10, -5, 15), (10, 5, 15), (10, 5, 25), (10, -5, 25)]), plane_at((10, 0, 20), (1, 0, 0)), "Wrap_Rect")
tgt = faces(cy, "Cylinder")[0]
o = WrapOptions()
first_ok(ctx, "wrap", [lambda: Wrap.Create(sel(face0(sh)), sel(tgt), o),
                       lambda: Wrap.Create(sel(sh), sel(tgt), o),
                       lambda: Wrap.Create(sel(face0(sh)), sel(tgt))])
cyb = [x for x in all_bodies() if not is_sheet(x)]
ctx.data["cyl_faces"] = [face_count(x) for x in cyb]
intent_range("cyl_faces_after_imprint", max(face_count(x) for x in cyb), 4, 12)
'''),
("13_convertsolid_001_closed_sheets", {"expect": {}}, _CUBE + '''
sh = cube_sheets(20)
first_ok(ctx, "convert", [lambda: ConvertToSolid.Execute(sel(sh), True), lambda: ConvertToSolid.Execute(sel(sh), False)])
ctx.data["bodies_after"] = [[unicode(x.Name), is_sheet(x), round(vol(x) or 0, 1)] for x in all_bodies()]
intent("solid_8000", any((not is_sheet(x)) and abs((vol(x) or 0) - 8000) < 1 for x in all_bodies()), True)
'''),
("14_hole_simple_001_d6_depth10", {"expect": {"bodies": 1}}, _HOLE + _HOLE_OPTS + '''
b = block((0, 0, 0), (40, 30, 20), "Hole_Block")
setp(ctx, o, [("HoleRadius", MM(3)), ("HoleDepth", MM(10))], "hole_opts")
std_hole(ctx, b, 20, 15, o)
intent("volume_mm3", round(total_volume(), 1), round(24000 - 3.14159265 * 9 * 10, 1), 30.0)
'''),
("14_hole_cbore_001_M6", {"expect": {"bodies": 1}}, _HOLE + _HOLE_OPTS + '''
b = block((0, 0, 0), (40, 30, 20), "Cbore_Block")
setp(ctx, o, [("SeriesName", "ISO"), ("FastenerName", "M6"), ("HoleFit", _safe(lambda: HoleFit.Medium)),
              ("CounterboreRadius", MM(5.5)), ("CounterboreDepth", MM(6.5)), ("HoleDepth", MM(15))], "hole_opts")
std_hole(ctx, b, 20, 15, o)
intent_range("volume_removed_mm3", 24000 - total_volume(), 100, 2000)
'''),
("14_hole_csink_001_90deg", {"expect": {"bodies": 1}}, _HOLE + _HOLE_OPTS + '''
b = block((0, 0, 0), (40, 30, 20), "Csink_Block")
setp(ctx, o, [("HoleRadius", MM(3)), ("HoleDepth", MM(12)), ("CountersinkRadius", MM(6)), ("CountersinkAngle", DEG(90))], "hole_opts")
std_hole(ctx, b, 20, 15, o)
intent_range("volume_removed_mm3", 24000 - total_volume(), 300, 1500)
'''),
("14_hole_tapped_001_M8_cosmetic", {"expect": {"bodies": 1}}, _HOLE + _HOLE_OPTS + '''
b = block((0, 0, 0), (40, 30, 20), "Tapped_Block")
setp(ctx, o, [("SeriesName", "ISO"), ("FastenerName", "M8"), ("Tapped", True), ("HoleDepth", MM(15))], "hole_opts")
r = std_hole(ctx, b, 20, 15, o)
ctx.attempt("cosmetic", lambda: StandardHoles.ModifyCosmeticThread(sel(faces(largest(), "Cylinder")), True))
intent_range("volume_removed_mm3", 24000 - total_volume(), 300, 1500)
'''),
("15_mesh_convert_001_block", {"expect": {"meshes": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Mesh_Block")
o = FacetConvertOptions()
ctx.data["fc_opts_members"] = [n for n in dir(o) if not n.startswith("_")]
first_ok(ctx, "facet_convert", [lambda: FacetConvert.Create(sel(b), o), lambda: FacetConvert.Create(sel(b))])
_safe(lambda: set_name(list(GetRootPart().Meshes)[0], "Block_Mesh"))
ctx.data["facets"] = _safe(lambda: list(GetRootPart().Meshes)[0].Shape.Facets.Count)
'''),
("15_mesh_stl_import_001", {"expect": {"meshes": 1},
  "notes": "STL exported by this case to 15_mesh_facet\\\\_inputs (scdm_cases only), then inserted as connected mesh"}, '''
import System
d = System.IO.Path.Combine(CASE["out_dir"], "_inputs")
if not System.IO.Directory.Exists(d):
    System.IO.Directory.CreateDirectory(d)
stl = System.IO.Path.Combine(d, "cylinder_r10_h30.stl")
cylinder((0, 0, 0), (0, 0, 30), 10, "Stl_Source_Cyl")
first_ok(ctx, "export_stl", [lambda: STLFile.Export(stl), lambda: DocumentSave.Execute(stl)])
ctx.data["stl_bytes"] = _safe(lambda: System.IO.FileInfo(stl).Length)
Delete.Execute(sel(bodies_now()))
io = STLImportOptions()
setp(ctx, io, [("ImportType", _safe(lambda: enum_pick(type(io.ImportType), "ConnectedMesh")))], "stl_opts")
first_ok(ctx, "insert_stl", [lambda: STLFile.Insert(stl, io), lambda: DocumentInsert.Execute(stl)])
_safe(lambda: set_name(list(GetRootPart().Meshes)[0], "Imported_Cyl_Mesh"))
'''),
("15_mesh_reduce_001_50pct", {"expect": {"meshes": 1}}, '''
s = sphere((0, 0, 0), 20, "Reduce_Sphere")
FacetConvert.Create(sel(s), FacetConvertOptions())
m = list(GetRootPart().Meshes)[0]
_safe(lambda: set_name(m, "Sphere_Mesh"))
n0 = _safe(lambda: m.Shape.Facets.Count)
o = FacetReduceOptions()
ctx.data["fr_opts_members"] = [n for n in dir(o) if not n.startswith("_")]
setp(ctx, o, [("TriangleReduction", 0.5)], "fr_opts")
first_ok(ctx, "reduce", [lambda: FacetReduce.Create(sel(m), o), lambda: FacetReduce.Create(sel(list(GetRootPart().Meshes)), o)])
n1 = _safe(lambda: list(GetRootPart().Meshes)[0].Shape.Facets.Count)
ctx.data["facets"] = [n0, n1]
intent("reduced", bool(n0 and n1 and n1 < n0), True)
'''),
]

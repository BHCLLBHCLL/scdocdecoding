BATCH = "B04_edge"
CASES = [
("04_edge_round_001_block_1edge_r3", {"expect": {"bodies": 1, "faces": 7, "volume_mm3": 23922.750307}}, '''
b = block((0, 0, 0), (40, 30, 20), "Round_Block_1Edge")
e = edge_nearest(b, (20, 30, 20), "Line")
ctx.data["edge_mid_mm"] = edge_mid(e)
ConstantRound.Execute(sel(e), MM(3), ConstantRoundOptions())
'''),
("04_edge_round_002_block_all12_r2", {"expect": {"bodies": 1, "faces": 26}}, '''
b = block((0, 0, 0), (40, 30, 20), "Round_Block_All")
ConstantRound.Execute(sel(edges(b)), MM(2), ConstantRoundOptions())
'''),
("04_edge_round_003_cyl_top_r2", {"expect": {"bodies": 1, "faces": 4}}, '''
b = cylinder((0, 0, 0), (0, 0, 20), 10, "Round_Cyl_Top")
es = edges_at_z(b, 20)
ctx.data["top_edges"] = len(es)
ConstantRound.Execute(sel(es), MM(2), ConstantRoundOptions())
'''),
("04_edge_round_004_vertex_blend_3edges_r4", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Round_Vertex_Blend")
es = [edge_nearest(b, p, "Line") for p in [(20, 30, 20), (40, 15, 20), (40, 30, 10)]]
ctx.data["edge_mids_mm"] = [edge_mid(e) for e in es]
ConstantRound.Execute(sel(es), MM(4), ConstantRoundOptions())
'''),
("04_edge_fullround_001_rib_3faces", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 5, 10), "Rib")
fs = [face_extreme(b, (0, 1, 0), -1), top_face(b), face_extreme(b, (0, 1, 0), 1)]
first_ok(ctx, "fullround", [
    lambda: FullRound.Execute(sel(fs)),
    lambda: FullRound.Execute(sel(fs[1], fs[0], fs[2]))])
ctx.data["cylinder_faces"] = len(faces(body_named("Rib"), "Cylinder"))
'''),
("04_edge_chamfer_001_block_1edge_d2", {"expect": {"bodies": 1, "faces": 7, "volume_mm3": 23920.0}}, '''
b = block((0, 0, 0), (40, 30, 20), "Chamfer_Block_1Edge")
e = edge_nearest(b, (20, 30, 20), "Line")
Chamfer.Execute(sel(e), MM(2))
'''),
("04_edge_chamfer_002_block_4edges_d1_d3", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Chamfer_Block_4Edges")
es = edges_at_z(b, 20, "Line")
ctx.data["top_edges"] = len(es)
Chamfer.Execute(sel(es), MM(1), MM(3))
'''),
("04_edge_chamfer_003_cyl_top_d1", {"expect": {"bodies": 1, "faces": 4}}, '''
b = cylinder((0, 0, 0), (0, 0, 20), 10, "Chamfer_Cyl_Top")
Chamfer.Execute(sel(edges_at_z(b, 20)), MM(1))
'''),
("04_edge_splitround_001", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "SplitRound_Block")
e = edge_nearest(b, (20, 30, 20), "Line")
ConstantRound.Execute(sel(e), MM(3), ConstantRoundOptions())
b = body_named("SplitRound_Block")
rf = faces(b, "Cylinder")[0]
res = [x for x in rf.Edges]
long_edges = [x for x in res if gtype(x) == "Line"]
ctx.data["round_face_edges"] = [[gtype(x), edge_mid(x)] for x in res]
ctx.data["long_edges"] = len(long_edges)
e0 = long_edges[0]
m = edge_mid(e0)
first_ok(ctx, "splitround", [
    lambda: SplitRound.Execute(sel(e0), P(*m), MM(2)),
    lambda: SplitRound.Execute(sel(e0), P(*m), 0.0)])
ctx.data["faces_after"] = shape_of(body_named("SplitRound_Block")).Faces.Count
'''),
]

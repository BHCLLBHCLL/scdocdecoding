# -*- coding: utf-8 -*-
# Generates feature_inventory.json / combo_plan.json / feature_inventory.md for scdm_cases.
# Usage: python gen_inventory.py [out_dir]
import json, collections, datetime, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
NOW = "2026-09-26T01:40:00+08:00"
CATS = collections.OrderedDict([
 ("00_smoke", "Smoke / pipeline checks"),
 ("01_primitives", "Primitive solids (block, cylinder, sphere, tube, cone/torus via revolve)"),
 ("02_sketch", "Sketch curves, sketch constraints & dimensions (DesignCurve / SketchCurveDef)"),
 ("03_pull", "Pull-family solid creation: extrude, cut, revolve, sweep, loft, helix"),
 ("04_edge", "Edge treatments: constant round, full round, chamfer"),
 ("05_boolean", "Combine/split: merge, subtract, intersect, split body/face"),
 ("06_move_pattern", "Move/rotate/scale/mirror/pattern"),
 ("07_shell_offset", "Shell, offset, thicken, draft, replace/detach faces"),
 ("08_sheetmetal", "Sheet metal (no V19 scripting command -> GUI/API only)"),
 ("09_beam", "Beams & beam profiles"),
 ("10_assembly", "Components, instances, mirror components, assembly conditions"),
 ("11_doc_attrs", "Document attributes: names, layers, colors, named selections, datums, views, units"),
 ("12_repair_prepare", "NEW: Repair (Fix*) and Prepare (midsurface, share topology, volume extract, enclosure...)"),
 ("13_surface_curve", "NEW: Surface/sheet bodies, fill/patch, project/wrap, split face, 3D curves"),
 ("14_holes_threads", "NEW: Standard holes (counterbore/countersink/tapped)"),
 ("15_mesh_facet", "NEW: Facet/mesh bodies (DesignMesh)"),
 ("20_combo", "Combination cases (see combo_plan.json)"),
])

F = []
def f(id, cat, en, zh, api, opts, variants, impact, status, evidence, prio, feas, notes=""):
    F.append(collections.OrderedDict([
        ("id", id), ("category", cat), ("name_en", en), ("name_zh", zh),
        ("v19_api", api), ("key_options", opts), ("variants", variants),
        ("expected_scdoc_impact", impact), ("repo_support", status),
        ("repo_evidence", evidence), ("priority", prio), ("headless_feasibility", feas),
        ("notes", notes)]))
def V(key, params, expect=None):
    d = collections.OrderedDict([("case_key", key), ("params", params)])
    if expect: d["expect"] = expect
    return d

G = "geometry-only (SAB)"
GD = "geometry (SAB) + document.xml tree entries"
D = "document.xml only (no new geometry)"
EV_BOX = "scdoc_parser decodes plane/straight; official box opens (00_smoke parser 29/33, only 10mm-hardcoded checks fail)"
EV_ANA = "topology.py decodes cone/sphere/torus/ellipse; golden cyl.scdoc; gap \u00a72.1 (22 SAB classes)"
EV_SPL = "topology.py decodes nubs/nurbs knots+poles; procedural classes (skinsur/sweepsur/offsur/intcurve) keep sense flag only; golden loft/spline/splineedge.scdoc"
EV_NONE_DOC = "no parser handler in scdoc_parser/document.py for this element"

# ---------- 00 smoke
f("smoke_box", "00_smoke", "Block (smoke)", "\u65b9\u5757\uff08\u5192\u70df\uff09", ["BlockBody.Create"], ["ExtrudeType.ForceIndependent"],
  [V("00_smoke_box_001_20x20x20", {"p0_mm":[0,0,0], "p1_mm":[20,20,20]}, {"bodies":1,"faces":6,"edges":12})],
  G, "supported", "DONE 2026-09-26: 00_smoke run headless OK", "P0", "yes", "already generated")

# ---------- 01 primitives
f("prim_block", "01_primitives", "Block", "\u65b9\u5757", ["BlockBody.Create(Point,Point,ExtrudeType)"], ["ExtrudeType: ForceIndependent/ForceAdd/ForceCut"],
  [V("01_primitives_block_001_10x20x30", {"p0_mm":[0,0,0],"p1_mm":[10,20,30]}, {"faces":6,"edges":12,"volume_mm3":6000}),
   V("01_primitives_block_002_offset_neg", {"p0_mm":[-15,-5,-2.5],"p1_mm":[15,5,2.5]}, {"volume_mm3":1500}),
   V("01_primitives_block_003_thin_100x100x0p5", {"p0_mm":[0,0,0],"p1_mm":[100,100,0.5]})],
  G, "supported", EV_BOX, "P0", "yes")
f("prim_cylinder", "01_primitives", "Cylinder", "\u5706\u67f1", ["CylinderBody.Create(center,start,end,ExtrudeType)"], ["axis by 3 points", "ExtrudeType"],
  [V("01_primitives_cylinder_001_r10_h20_z", {"axis":"Z","r_mm":10,"h_mm":20}, {"faces":3,"edges":3}),
   V("01_primitives_cylinder_002_r5_h50_x", {"axis":"X","r_mm":5,"h_mm":50}),
   V("01_primitives_cylinder_003_r2_h1_oblique", {"axis":[1,1,1],"r_mm":2,"h_mm":1})],
  G, "supported", EV_ANA + "; golden cyl.scdoc; official-open cyl bodies=1", "P0", "yes")
f("prim_sphere", "01_primitives", "Sphere", "\u7403", ["SphereBody.Create(center,endPoint,ExtrudeType)"], [],
  [V("01_primitives_sphere_001_r10", {"c_mm":[0,0,0],"r_mm":10}, {"faces":1}),
   V("01_primitives_sphere_002_r3_offcenter", {"c_mm":[5,-7,2],"r_mm":3})],
  G, "supported", EV_ANA + "; interop_matrix sphere row", "P0", "yes")
f("prim_tube", "01_primitives", "Tube around curve", "\u7ba1\u9053", ["TubeBody.Create(ISelection curve, radius, ExtrudeType)"], ["needs a DesignCurve (line/arc/spline) selection"],
  [V("01_primitives_tube_001_line_r2_l50", {"path":"line 50mm","r_mm":2}),
   V("01_primitives_tube_002_arc_r3", {"path":"arc R30 90deg","r_mm":3}),
   V("01_primitives_tube_003_spline_r1", {"path":"3D spline 4pts","r_mm":1})],
  G, "partial", EV_ANA + "; spline path -> sweep surface: " + EV_SPL, "P1", "needs selection setup (create DesignCurve first)")
f("prim_cone_revolve", "01_primitives", "Cone / frustum (revolve of triangle/trapezoid)", "\u5706\u9525/\u5706\u53f0", ["SketchLine.CreateChain","RevolveFaces.Execute(face, Line axis, angle, RevolveFaceOptions)"], ["angle 2pi"],
  [V("01_primitives_cone_001_r10_h20", {"r_base_mm":10,"h_mm":20}),
   V("01_primitives_cone_002_frustum_r10_r5_h15", {"r1_mm":10,"r2_mm":5,"h_mm":15})],
  G, "supported", EV_ANA + "; P0-2 frustum written+official-open", "P0", "needs selection setup (sketch->solidify->face)")
f("prim_torus_revolve", "01_primitives", "Torus (revolve of circle)", "\u5706\u73af", ["SketchCircle.Create","RevolveFaces.Execute"], [],
  [V("01_primitives_torus_001_R20_r5", {"major_r_mm":20,"minor_r_mm":5}),
   V("01_primitives_torus_002_partial_180deg", {"major_r_mm":20,"minor_r_mm":5,"angle_deg":180})],
  G, "supported", EV_ANA + "; interop_matrix torus row", "P0", "needs selection setup")
f("prim_planar_body", "01_primitives", "Planar (sheet) body from curves", "\u5e73\u9762\u4f53", ["PlanarBody.Create(Plane, curves, parent, name)"], [],
  [V("01_primitives_planar_001_rect_40x20", {"plane":"XY","rect_mm":[40,20]}, {"faces":1,"sheet":True}),
   V("01_primitives_planar_002_circle_r15", {"plane":"XY","r_mm":15})],
  G, "partial", "single-sided sheet bodies: face sense/sheet shell decoding not covered by golden samples", "P1", "yes")

# ---------- 02 sketch
sk = "SketchCurveDef in PartSketchCurveContainerDef (document.xml) + wire geometry"
f("sk_line", "02_sketch", "Sketch line / polyline", "\u76f4\u7ebf", ["SketchLine.Create","SketchLine.CreateChain"], ["isConstruction","centerline"],
  [V("02_sketch_line_001_single_50", {"p0":[0,0],"p1":[50,0]}),
   V("02_sketch_line_002_chain_closed_tri", {"pts":[[0,0],[40,0],[20,30]],"close":True}),
   V("02_sketch_line_003_construction", {"p0":[0,0],"p1":[0,40],"isConstruction":True})],
  D + " (" + sk + ")", "partial", "document.py parses SketchCurveDef origin/dir/start/end only (lines); construction flag not read", "P0", "yes (ViewHelper.SetSketchPlane + create; leave in sketch mode or SetViewMode(Solid) to solidify)")
f("sk_rect", "02_sketch", "Sketch rectangle", "\u77e9\u5f62", ["SketchRectangle.Create(p1,p2,p3)"], ["3-point / rotated"],
  [V("02_sketch_rect_001_40x20", {"p":[[0,0],[40,0],[40,20]]}),
   V("02_sketch_rect_002_rotated_30deg", {"p":"3-point rotated 30deg"})],
  D + " (4 line SketchCurveDef)", "partial", "lines parsed; rectangle grouping not", "P1", "yes")
f("sk_circle", "02_sketch", "Sketch circle", "\u5706", ["SketchCircle.Create(Point2D,radius)"], [],
  [V("02_sketch_circle_001_r10", {"c":[0,0],"r_mm":10}),
   V("02_sketch_circle_002_two_concentric_r5_r10", {"r_mm":[5,10]})],
  D + " (circle SketchCurveDef)", "partial", "document.py SketchCurve kind defaults to 'line'; circle params (radius/frame) not decoded", "P0", "yes")
f("sk_arc", "02_sketch", "Sketch arc (center/3-point/tangent/sweep)", "\u5706\u5f27", ["SketchArc.Create","SketchArc.Create3PointArc","SketchArc.CreateSweepArc","SketchArc.CreateTangentArc"], ["sense"],
  [V("02_sketch_arc_001_center_r20_90deg", {"c":[0,0],"start":[20,0],"end":[0,20]}),
   V("02_sketch_arc_002_3point", {"pts":[[0,0],[10,5],[20,0]]}),
   V("02_sketch_arc_003_tangent_after_line", {"line":[[0,0],[20,0]],"end":[30,10]})],
  D + " (arc SketchCurveDef with interval)", "partial", "interval read generically; arc geometry not typed", "P0", "yes")
f("sk_ellipse", "02_sketch", "Sketch ellipse", "\u692d\u5706", ["SketchEllipse.Create"], [],
  [V("02_sketch_ellipse_001_a20_b10", {"a_mm":20,"b_mm":10}),
   V("02_sketch_ellipse_002_rotated_45", {"a_mm":15,"b_mm":5,"major_dir_deg":45})],
  D, "partial", "ellipse SAB curve decoded; sketch ellipse doc entry not", "P1", "yes")
f("sk_polygon", "02_sketch", "Sketch polygon", "\u591a\u8fb9\u5f62", ["SketchPolygon.Create(Point2D,dirX,dirY,internalRadius,n)"], ["n sides"],
  [V("02_sketch_polygon_001_hex_r10", {"n":6,"r_mm":10}),
   V("02_sketch_polygon_002_pent_r8", {"n":5,"r_mm":8})],
  D, "partial", "lines parsed individually", "P2", "yes")
f("sk_spline", "02_sketch", "Sketch spline (NURBS through points)", "\u6837\u6761", ["SketchNurbs.CreateFrom2DPoints(periodic, points)"], ["periodic", "end tangents"],
  [V("02_sketch_spline_001_open_5pts", {"pts":[[0,0],[10,8],[20,-4],[30,6],[40,0]],"periodic":False}),
   V("02_sketch_spline_002_periodic_6pts", {"periodic":True,"n":6}),
   V("02_sketch_spline_003_end_tangents", {"n":4,"startVector":[1,1],"endVector":[1,-1]})],
  D + " (NurbsCurve serialized in document.xml)", "none", "document.py has no NURBS sketch curve decoding", "P0", "yes")
f("sk_point_offset", "02_sketch", "Sketch point / offset curve / corner / 2D round / trim / split", "\u70b9/\u504f\u79fb/\u5012\u89d2/\u4fee\u526a", ["SketchPoint.Create","SketchOffsetCurve.Create","SketchCorner.Create","Sketch2DRound.Create","TrimSketchCurve.Execute","SplitSketchCurve.Execute"], [],
  [V("02_sketch_point_001", {"p":[5,5]}),
   V("02_sketch_offset_001_rect_offset3", {"rect":[40,20],"offset_mm":3}),
   V("02_sketch_round2d_001_rect_corner_r4", {"rect":[40,20],"r_mm":4})],
  D, "partial", "points/offsets not decoded", "P2", "needs selection setup")
f("sk_constraints", "02_sketch", "Sketch constraints (horizontal, vertical, coincident, tangent, parallel, perpendicular, concentric, equal, midpoint, symmetric, fixed)", "\u8349\u56fe\u7ea6\u675f", ["Constraint.Create*","SketchHelper.StartConstraintSketching","ConstraintHelper.ModelWellDefined"], ["constraint-based sketch mode"],
  [V("02_sketch_constraint_001_hv_rect", {"constraints":["Horizontal","Vertical"]}),
   V("02_sketch_constraint_002_tangent_line_arc", {"constraints":["Tangent"]}),
   V("02_sketch_constraint_003_concentric_equal", {"constraints":["Concentric","EqualRadius"]})],
  D + " (constraint objects in sketch)", "none", "repo has its own sketch_solver.py (internal model) but no scdoc decoding of official constraint XML", "P1", "needs selection setup (SelectionPoint on curves); may require constraint sketching mode - verify headless")
f("sk_dimensions", "02_sketch", "Sketch dimensions (length/radial/diameter/angle/distance)", "\u5c3a\u5bf8", ["Dimension.CreateLength","Dimension.CreateRadial","Dimension.CreateDiameter","Dimension.CreateAngle","Dimension.CreateDistance","Dimension.Modify"], ["DimensionAlignment"],
  [V("02_sketch_dim_001_length_40", {"value_mm":40}),
   V("02_sketch_dim_002_radius_10", {"value_mm":10}),
   V("02_sketch_dim_003_angle_30", {"value_deg":30})],
  D, "none", EV_NONE_DOC, "P1", "needs selection setup; verify headless")
f("sk_datum_curve", "02_sketch", "3D design curve (line/arc/spline outside sketch)", "3D\u66f2\u7ebf", ["DesignCurve.Create (API)","SketchCurve.Create","ProjectToSketch.Create"], [],
  [V("02_sketch_designcurve_001_3d_line", {"p0":[0,0,0],"p1":[10,20,30]}),
   V("02_sketch_designcurve_002_helix_spline", {"type":"NurbsCurve.CreateThroughPoints helix 3 turns"})],
  GD, "partial", "DesignCurve stored as curve geometry + DesignCurveDef; not decoded by parser", "P1", "yes")

# ---------- 03 pull
f("pull_extrude_face", "03_pull", "Extrude (pull) sketch region to solid", "\u62c9\u52a8-\u62c9\u4f38", ["ExtrudeFaces.Execute(sel, Direction, distance, ExtrudeFaceOptions)"], ["ExtrudeType Add/Cut/ForceIndependent", "PullSymmetric", "draft"],
  [V("03_pull_extrude_001_rect_40x20_h10", {"profile":"rect 40x20","h_mm":10}),
   V("03_pull_extrude_002_circle_r10_h25", {"profile":"circle r10","h_mm":25}),
   V("03_pull_extrude_003_spline_profile_h5", {"profile":"closed spline","h_mm":5}),
   V("03_pull_extrude_004_symmetric_h20", {"profile":"rect","h_mm":20,"PullSymmetric":True})],
  G, "supported", EV_BOX + "; spline profile -> spline side faces: " + EV_SPL, "P0", "needs selection setup (face from solidified sketch)")
f("pull_extrude_cut", "03_pull", "Extrude cut (pocket / through hole)", "\u62c9\u52a8-\u5207\u9664", ["ExtrudeFaces.Execute ExtrudeType.Cut","ExtrudeFaces.UpTo"], ["Cut","UpTo face"],
  [V("03_pull_cut_001_pocket_rect_depth5", {"base":"block 40x40x20","pocket":"rect 10x10 depth 5"}),
   V("03_pull_cut_002_through_hole_r4", {"base":"block 40x40x20","hole_r_mm":4,"through":True}),
   V("03_pull_cut_003_upto_face", {"mode":"UpTo"})],
  G, "supported", "cylinder inner faces decoded; P0-2 drilled-box written+official", "P0", "needs selection setup")
f("pull_face_offset", "03_pull", "Pull existing face (grow/shrink body)", "\u62c9\u52a8\u9762", ["ExtrudeFaces.Execute on body face"], [],
  [V("03_pull_face_001_block_top_plus10", {"face":"+Z","d_mm":10}),
   V("03_pull_face_002_block_side_minus3", {"face":"+X","d_mm":-3})],
  G, "supported", EV_BOX, "P1", "needs selection setup (pick face by normal)")
f("pull_extrude_edges", "03_pull", "Extrude edges/curves to surface", "\u62c9\u4f38\u8fb9", ["ExtrudeEdges.Execute"], [],
  [V("03_pull_extrudeedge_001_line_to_sheet", {"curve":"line 40","d_mm":20}),
   V("03_pull_extrudeedge_002_arc_to_sheet", {"curve":"arc R20 180deg","d_mm":10})],
  G, "partial", "sheet bodies (single face, open shell) not in golden set", "P1", "needs selection setup")
f("pull_revolve", "03_pull", "Revolve", "\u65cb\u8f6c", ["RevolveFaces.Execute(sel, Line axis, angle, RevolveFaceOptions)","RevolveEdges.Execute"], ["angle", "ExtrudeType"],
  [V("03_pull_revolve_001_rect_360", {"profile":"rect 10x20 offset 5 from axis","angle_deg":360}),
   V("03_pull_revolve_002_rect_90", {"angle_deg":90}),
   V("03_pull_revolve_003_spline_profile_360", {"profile":"spline+line closed","angle_deg":360})],
  G, "supported", EV_ANA + "; spline revolve -> rotsur (procedural) " + EV_SPL, "P0", "needs selection setup")
f("pull_helix", "03_pull", "Revolve by helix (spring/thread)", "\u87ba\u65cb", ["RevolveFaces.ByHelix","RevolveEdges.ByHelix"], ["pitch","height","taper","rightHanded"],
  [V("03_pull_helix_001_circle_r1_pitch5_h20", {"profile":"circle r1 at R10","pitch_mm":5,"h_mm":20}),
   V("03_pull_helix_002_tapered_5deg", {"taper_deg":5})],
  G, "partial", EV_SPL + " (helix sweep -> sweepsur/intcurve procedural)", "P1", "needs selection setup")
f("pull_sweep", "03_pull", "Sweep profile along trajectory", "\u626b\u63a0", ["Sweep.Execute(sel, trajectories, SweepCommandOptions)"], ["keep normal / twist"],
  [V("03_pull_sweep_001_circle_along_arc", {"profile":"circle r3","path":"arc R40 90deg"}),
   V("03_pull_sweep_002_rect_along_spline", {"profile":"rect 4x2","path":"3D spline"}),
   V("03_pull_sweep_003_along_polyline", {"path":"L-shaped line chain"})],
  G, "partial", EV_SPL, "P0", "needs selection setup (profile face + trajectory curve)")
f("pull_loft", "03_pull", "Loft / blend between profiles", "\u653e\u6837/\u6df7\u5408", ["Loft.Create(blendSelection, guideSelection, LoftOptions)","Loft.CreateCenterLine"], ["ruled", "guides"],
  [V("03_pull_loft_001_rect_to_circle", {"profiles":["rect 20x20 z=0","circle r8 z=30"]}),
   V("03_pull_loft_002_three_circles", {"profiles":["r10 z0","r5 z20","r12 z40"]}),
   V("03_pull_loft_003_ruled", {"ruled":True})],
  G, "partial", EV_SPL + "; golden loft.scdoc", "P0", "needs selection setup")
f("pull_extrude_profile", "03_pull", "Extrude API Profile directly", "\u8f6e\u5ed3\u62c9\u4f38", ["ExtrudeProfile.Execute(Profile, distance, parent, name)"], ["RectangleProfile/CircleProfile/PolygonProfile (API)"],
  [V("03_pull_profile_001_rect_30x10_h5", {"profile":"RectangleProfile 30x10","h_mm":5}),
   V("03_pull_profile_002_circle_r6_h12", {"profile":"CircleProfile r6","h_mm":12})],
  G, "supported", EV_BOX, "P2", "yes (no selection needed; also allows body naming)")

# ---------- 04 edge
f("edge_round", "04_edge", "Constant radius round (fillet)", "\u5012\u5706\u89d2", ["ConstantRound.Execute(sel edges, radius, ConstantRoundOptions)"], ["edges: single / all / tangent chain"],
  [V("04_edge_round_001_block_1edge_r3", {"base":"block 40x30x20","edges":1,"r_mm":3}),
   V("04_edge_round_002_block_all12_r2", {"edges":12,"r_mm":2}),
   V("04_edge_round_003_cyl_top_r2", {"base":"cyl r10 h20","edges":"top circle","r_mm":2}),
   V("04_edge_round_004_vertex_blend_3edges_r4", {"edges":"3 edges meeting at vertex","r_mm":4})],
  G + " (+ RoundInfo/round face attributes in document.xml)", "partial", "cyl/torus round faces decoded; vertex blends are spline/rb_blend procedural (" + EV_SPL + "); P0-2 filleted box official-open", "P0", "needs selection setup (edges by geometry)")
f("edge_full_round", "04_edge", "Full round", "\u5168\u5706\u89d2", ["FullRound.Execute(selFaces)"], [],
  [V("04_edge_fullround_001_rib_3faces", {"base":"block 40x5x10","faces":"side-top-side"})],
  G, "partial", "same as round", "P2", "needs selection setup")
f("edge_chamfer", "04_edge", "Chamfer (equal/unequal)", "\u5012\u89d2", ["Chamfer.Execute(sel, distance)","Chamfer.Execute(sel, d1, d2)"], [],
  [V("04_edge_chamfer_001_block_1edge_d2", {"d_mm":2}),
   V("04_edge_chamfer_002_block_4edges_d1_d3", {"d1_mm":1,"d2_mm":3}),
   V("04_edge_chamfer_003_cyl_top_d1", {"base":"cyl r10 h20","d_mm":1})],
  G, "supported", EV_BOX + " (planar chamfer faces) / cone for cylinder chamfer", "P0", "needs selection setup")
f("edge_split_round", "04_edge", "Round utilities (split round, restore rounds)", "\u5706\u89d2\u5de5\u5177", ["SplitRound.Execute","NamedSelection.RestoreRounds","RoundInfo.Create"], [],
  [V("04_edge_splitround_001", {"base":"block+round r3"})],
  GD, "none", EV_NONE_DOC, "P2", "needs selection setup")

# ---------- 05 boolean
f("bool_merge", "05_boolean", "Combine - merge (union)", "\u7ec4\u5408-\u5408\u5e76", ["Combine.Merge(target, tool)","MergeBodies.Execute"], [],
  [V("05_boolean_merge_001_two_blocks_overlap", {"a":"block 0..20","b":"block 10..30"}),
   V("05_boolean_merge_002_block_plus_cyl", {"a":"block 40x40x10","b":"cyl r8 h30 at center"}),
   V("05_boolean_merge_003_touching_faces", {"a":"block","b":"block sharing a face"})],
  G, "supported", EV_BOX + "; " + EV_ANA, "P0", "yes (bodies from GetRootPart().Bodies)")
f("bool_subtract", "05_boolean", "Combine - subtract (cut body with tool, RemoveRegions)", "\u7ec4\u5408-\u51cf", ["Combine.Intersect(target, tool, MakeSolidsOptions)","Combine.RemoveRegions"], ["keep cutter"],
  [V("05_boolean_subtract_001_block_minus_cyl", {"a":"block 40x40x20","b":"cyl r5 through"}),
   V("05_boolean_subtract_002_block_minus_sphere", {"a":"block 40","b":"sphere r15 at corner"}),
   V("05_boolean_subtract_003_keep_cutter", {"keepCutter":True})],
  G, "supported", EV_ANA, "P0", "yes (verify region-selection step for subtract; SpaceClaim subtract = Intersect + RemoveRegions)")
f("bool_intersect", "05_boolean", "Combine - intersect (common)", "\u7ec4\u5408-\u76f8\u4ea4", ["Combine.Intersect + RemoveRegions"], [],
  [V("05_boolean_intersect_001_block_sphere", {"a":"block 20","b":"sphere r14 centered"}),
   V("05_boolean_intersect_002_two_cylinders_cross", {"a":"cyl X r10","b":"cyl Y r10"})],
  G, "partial", "Steinmetz intersection edges are intcurve (procedural): " + EV_SPL, "P0", "yes")
f("bool_split_body", "05_boolean", "Split body by plane / face / body", "\u62c6\u5206\u4e3b\u4f53", ["SplitBody.ByCutter(body, Plane)","SplitBody.ByCutter(body, toolFaces, extend)"], [],
  [V("05_boolean_splitbody_001_block_by_plane_mid", {"plane":"z=10"}),
   V("05_boolean_splitbody_002_cyl_by_oblique_plane", {"plane":"normal (1,0,1)"}),
   V("05_boolean_splitbody_003_by_face", {"tool":"face of other body"})],
  G, "supported", EV_BOX + "; oblique cut of cylinder -> ellipse edges decoded", "P0", "yes")
f("bool_imprint", "05_boolean", "Imprint / intersect to curves", "\u538b\u5370", ["Combine.Intersect(target, tool, MakeCurvesOptions)","FixImprint"], [],
  [V("05_boolean_imprint_001_block_cyl_curves", {"mode":"MakeCurves"})],
  G, "partial", "imprinted edges split faces; OK for analytic", "P1", "yes")

# ---------- 06 move/pattern
f("mp_translate", "06_move_pattern", "Move - translate", "\u79fb\u52a8-\u5e73\u79fb", ["Move.Translate(sel, Direction, distance, MoveOptions)"], ["Copy on/off"],
  [V("06_move_translate_001_block_x25", {"d_mm":25,"dir":"X"}),
   V("06_move_translate_002_copy_y30", {"d_mm":30,"dir":"Y","copy":True})],
  G, "supported", EV_BOX, "P1", "yes")
f("mp_rotate", "06_move_pattern", "Move - rotate", "\u79fb\u52a8-\u65cb\u8f6c", ["Move.Rotate(sel, Line axis, angle, MoveOptions)"], [],
  [V("06_move_rotate_001_block_z45", {"axis":"Z","deg":45}),
   V("06_move_rotate_002_cyl_x90_copy", {"axis":"X","deg":90,"copy":True})],
  G, "supported", EV_BOX, "P1", "yes")
f("mp_scale", "06_move_pattern", "Scale body (uniform / non-uniform)", "\u7f29\u653e", ["Scale.Execute(sel, origin, scale)","Scale.Execute(sel, frame, Vector scale)"], [],
  [V("06_move_scale_001_uniform_2x", {"s":2}),
   V("06_move_scale_002_nonuniform_1x2x0p5", {"s":[1,2,0.5]})],
  G, "supported", "non-uniform scale of cylinder -> ellipse/spline", "P2", "yes")
f("mp_mirror", "06_move_pattern", "Mirror body (and mirror relationship)", "\u955c\u50cf", ["Mirror.Execute(sel, mirrorPlane, MirrorOptions)","DatumPlaneCreator.Create"], ["merge", "keep relation"],
  [V("06_move_mirror_001_block_about_yz", {"plane":"YZ"}),
   V("06_move_mirror_002_merge_halves", {"merge":True})],
  GD + " (mirror plane datum; possible MirrorRelation)", "partial", "geometry supported; mirror relation doc entry not decoded", "P0", "needs selection setup (datum plane or face as mirror plane)")
f("mp_pattern_linear", "06_move_pattern", "Linear pattern", "\u7ebf\u6027\u9635\u5217", ["Pattern.CreateLinear(sel, LinearPatternData)","Pattern.ModifyLinear"], ["count X/Y, pitch, 1D/2D"],
  [V("06_pattern_linear_001_cyl_1d_5x10", {"count":5,"pitch_mm":10}),
   V("06_pattern_linear_002_hole_2d_3x4", {"count":[3,4],"pitch_mm":[12,10],"member":"through hole in plate"}),
   V("06_pattern_linear_003_body_copy_3", {"count":3,"pitch_mm":25})],
  GD + " (PatternDef/pattern relationship entries)", "none", EV_NONE_DOC + " (pattern relationship); geometry parts supported", "P0", "needs selection setup (face group or body)")
f("mp_pattern_circular", "06_move_pattern", "Circular pattern", "\u5706\u5f62\u9635\u5217", ["Pattern.CreateCircular(sel, CircularPatternData)"], ["count, angle, axis"],
  [V("06_pattern_circular_001_holes_6_360", {"count":6,"angle_deg":360,"member":"hole r3 on disk r40"}),
   V("06_pattern_circular_002_bodies_4_180", {"count":4,"angle_deg":180})],
  GD, "none", EV_NONE_DOC, "P0", "needs selection setup")
f("mp_pattern_fill", "06_move_pattern", "Fill pattern", "\u586b\u5145\u9635\u5217", ["Pattern.CreateFill(sel, FillPatternData)"], [],
  [V("06_pattern_fill_001_holes_in_plate", {"member":"hole r2","region":"plate face 80x60"})],
  GD, "none", EV_NONE_DOC, "P2", "needs selection setup")
f("mp_along_trajectory", "06_move_pattern", "Move along trajectory / orient", "\u6cbf\u8f68\u8ff9\u79fb\u52a8", ["Move.AlongTrajectory","Move.OrientTo","Move.ToCoordinate"], [],
  [V("06_move_trajectory_001_block_along_arc", {"path":"arc R50 90deg"})],
  G, "supported", EV_BOX, "P2", "needs selection setup")

# ---------- 07 shell/offset
f("so_shell", "07_shell_offset", "Shell (remove faces / hollow)", "\u62bd\u58f3", ["Shell.RemoveFaces(sel faces, thickness)","Shell.ShellBodies(sel bodies, thickness)"], ["inside/outside by sign"],
  [V("07_shell_open_001_block_top_t2", {"base":"block 40x30x20","remove":"+Z","t_mm":2}),
   V("07_shell_closed_002_hollow_sphere_t1", {"base":"sphere r10","t_mm":1}),
   V("07_shell_open_003_cyl_top_t1p5", {"base":"cyl r10 h30","remove":"top","t_mm":1.5})],
  G, "supported", EV_BOX + "; hollow = 2 shells (void) - verify multi-shell lump decode", "P0", "needs selection setup")
f("so_offset", "07_shell_offset", "Offset faces", "\u504f\u79fb\u9762", ["OffsetFaces.Execute(sel, offset, OffsetFaceOptions)","OffsetRelation.ChangeOffset"], ["offset relationship"],
  [V("07_offset_001_block_top_plus3", {"d_mm":3}),
   V("07_offset_002_cyl_face_minus1", {"d_mm":-1})],
  GD + " (possible OffsetRelation)", "partial", "geometry supported; offset relation not decoded", "P1", "needs selection setup")
f("so_thicken", "07_shell_offset", "Thicken surface to solid", "\u52a0\u539a", ["ThickenFaces.Execute(sel, Direction, value, ThickenFaceOptions)"], [],
  [V("07_thicken_001_planar_t2", {"base":"planar rect 40x20","t_mm":2}),
   V("07_thicken_002_cyl_sheet_t1", {"base":"half-cylinder sheet r20","t_mm":1})],
  G, "supported", EV_BOX, "P1", "needs selection setup")
f("so_draft", "07_shell_offset", "Draft faces", "\u62d4\u6a21", ["DraftFaces.Execute(sel, refFaces, DraftSide, angle, ExtrudeType, DraftOptions)"], [],
  [V("07_draft_001_block_4sides_5deg", {"neutral":"-Z","angle_deg":5}),
   V("07_draft_002_cyl_side_3deg", {"base":"cyl","angle_deg":3})],
  G, "supported", "planes / cone decoded", "P1", "needs selection setup")
f("so_replace_detach", "07_shell_offset", "Replace faces / detach faces", "\u66ff\u6362\u9762/\u5206\u79bb\u9762", ["ReplaceFacesWithFace.Execute","DetachFaces.Execute"], [],
  [V("07_replaceface_001_block_top_to_plane", {}), V("07_detach_001_block_top", {})],
  G, "supported", EV_BOX, "P2", "needs selection setup")

# ---------- 08 sheet metal
f("sm_all", "08_sheetmetal", "Sheet metal (convert, flange, bend, unfold, junction, relief)", "\u94a3\u91d1", ["NONE in SpaceClaim.Api.V19.Scripting; raw API SheetMetalAspect/Bend are read-only (no Create)"], ["would need GUI journaling or V19 non-scripting API"],
  [V("08_sheetmetal_convert_001_block_t2", {"base":"block 100x50x2","thickness_mm":2}),
   V("08_sheetmetal_flange_001_90deg_l20", {"angle_deg":90,"length_mm":20,"bend_r_mm":1}),
   V("08_sheetmetal_unfold_001", {})],
  GD + " (sheet metal part attributes, bends)", "none", "repo sheetmetal.py is an internal OCCT model; no scdoc decode of official sheet-metal XML", "P1", "GUI-only (user builds in GUI once with recording on; saves into 08_sheetmetal)")

# ---------- 09 beam
f("beam_profile", "09_beam", "Beam profile creation (I/L/T/channel/rect/circular/...)", "\u6881\u622a\u9762", ["BeamProfile.CreateI/CreateL/CreateT/CreateChannel/CreateRectangular/CreateCircular/CreateDisk/CreateFlatBar/CreateHat/CreateZ/CreateCustom","BeamProfile.CreateFromLibrary"], [],
  [V("09_beam_profile_001_I_100x50", {"type":"I","baseWidth":50,"depth":100,"tf":8,"tw":5}),
   V("09_beam_profile_002_rect_tube_60x40x3", {"type":"Rectangular","t":3,"w":60,"d":40}),
   V("09_beam_profile_003_circular_d40_d34", {"type":"Circular","od":40,"id":34})],
  GD + " (profile component + beam section properties)", "none", "BeamProfiles library .scdoc used only for named-selection format; beams.py is internal model", "P1", "yes")
f("beam_create", "09_beam", "Beam along curve", "\u521b\u5efa\u6881", ["Beam.Create(sel curves, profile)","Beam.SetOrientation/SetPosition/SetType/ReverseBeam","Beam.ExtractProfile"], ["Beam/Cable/Truss/Spring type", "anchor"],
  [V("09_beam_create_001_line_I", {"curve":"line 1000mm","profile":"I"}),
   V("09_beam_create_002_frame_4lines_rect", {"curve":"rect frame 1000x500","profile":"Rectangular"}),
   V("09_beam_create_003_orient30_centroid", {"orientation_deg":30,"anchor":"Centroid"})],
  GD, "none", EV_NONE_DOC, "P1", "needs selection setup (DesignCurve + profile)")

# ---------- 10 assembly
f("asm_component", "10_assembly", "Create component / move bodies to component", "\u7ec4\u4ef6", ["ComponentHelper.CreateAtRoot","ComponentHelper.MoveBodiesToComponent","ComponentHelper.CreateSeparateComponents","ComponentHelper.SetName"], [],
  [V("10_assembly_component_001_two_bodies_two_comps", {"bodies":["block","cyl"]}),
   V("10_assembly_component_002_nested_2levels", {"levels":2}),
   V("10_assembly_component_003_separate_components_4", {"bodies":4})],
  GD + " (ComponentDef/PartDef, per-part SAB, moniker rels)", "partial", "writer mirrors official ComponentDef/refId/trans (TODO-9 bodies=2); scdoc_parser/document.py only lists PartDef ids; golden assembly_sample.scdoc", "P0", "yes")
f("asm_instance", "10_assembly", "Component instances (copy/paste component, transform)", "\u7ec4\u4ef6\u5b9e\u4f8b", ["Copy.ToClipboard/Paste.FromClipboard","ComponentHelper.CopyToComponent","Move.Translate on component","ComponentHelper.MakeIndependent"], [],
  [V("10_assembly_instance_001_3_instances_translated", {"n":3,"pitch_mm":50}),
   V("10_assembly_instance_002_rotated_instance", {"deg":90}),
   V("10_assembly_instance_003_make_independent", {})],
  GD + " (instances share one PartDef; <trans> matrix)", "partial", "trans matrix handled by writer; parser does not expose instances", "P0", "yes (clipboard in headless: verify)")
f("asm_mirror_components", "10_assembly", "Mirror components", "\u955c\u50cf\u7ec4\u4ef6", ["MirrorComponents.Execute"], [],
  [V("10_assembly_mirrorcomp_001", {"plane":"YZ"})],
  GD, "none", EV_NONE_DOC, "P2", "needs selection setup")
f("asm_conditions", "10_assembly", "Assembly conditions (align, tangent, orient, anchor, rigid, gear)", "\u88c5\u914d\u7ea6\u675f", ["(raw API) AlignCondition.Create / TangentCondition.Create / OrientCondition.Create / AnchorCondition.Create / RigidCondition.Create / GearCondition.Create (SpaceClaim.Api.V19)"], ["no Scripting command; Constraint.* are sketch constraints"],
  [V("10_assembly_align_001_axis_axis", {"a":"plate hole axis","b":"pin axis"}), V("10_assembly_tangent_001_face_face", {}), V("10_assembly_anchor_001_plate", {}), V("10_assembly_rigid_001", {})],
  GD + " (condition entries)", "none", "repo mates.py is internal; NYI TODO-1 asks for official assembly+mate sample", "P0", "needs selection setup (raw API on component faces/axes; verify signatures in API_Class_Library.chm)")
f("asm_insert_file", "10_assembly", "Insert external file as component", "\u63d2\u5165\u6587\u4ef6", ["DocumentInsert.Execute(filename)"], [],
  [V("10_assembly_insert_001_step_block", {"file":"STEP generated in 01_primitives"})],
  GD + " (external reference / import source)", "partial", "importSource/importPath parsed", "P2", "yes")

# ---------- 11 doc attrs
f("doc_rename", "11_doc_attrs", "Rename body/component (captions)", "\u91cd\u547d\u540d", ["RenameObject.Execute(sel, name)","HasNameExtensions.SetName"], [],
  [V("11_doc_rename_001_body_Block_A", {"name":"Block_A"}),
   V("11_doc_rename_002_unicode_name", {"name":"\u4e3b\u4f53_\u6d4b\u8bd5"})],
  D + " (CaptionDef)", "supported", "document.py parses RootCaptionDef/CaptionDef", "P0", "yes")
f("doc_layers", "11_doc_attrs", "Layers (create, assign, color, visibility, lock)", "\u56fe\u5c42", ["Layers.Create/AssignLayer/SetColor/SetVisibility/SetLock/Rename"], [],
  [V("11_doc_layers_001_two_layers_assign", {"layers":["L_red","L_blue"]}),
   V("11_doc_layers_002_hidden_locked", {"visible":False,"locked":True})],
  D + " (LayerDef)", "supported", "document.py parses LayerDef name/color/visible/locked", "P0", "yes")
f("doc_colors", "11_doc_attrs", "Body / face color, fill style", "\u989c\u8272", ["ColorHelper.SetColor(sel, SetColorOptions, Color)","ColorHelper.SetFillStyle"], ["FaceColorTarget/EdgeColorTarget"],
  [V("11_doc_color_001_body_red", {"target":"body","rgb":[255,0,0]}),
   V("11_doc_color_002_face_green", {"target":"face +Z","rgb":[0,200,0]}),
   V("11_doc_color_003_transparent_50", {"alpha":128})],
  GD + " (NominalBodyDef color; SAB rgb_color attrib)", "partial", "body color parsed; face color / transparency not", "P0", "yes")
f("doc_named_selection", "11_doc_attrs", "Named selections (groups)", "\u547d\u540d\u9009\u62e9/\u7ec4", ["NamedSelection.Create(primary, secondary)","NamedSelection.Rename/Replace/Delete"], [],
  [V("11_doc_ns_001_faces_top_bottom", {"members":"2 faces"}),
   V("11_doc_ns_002_edges_and_body", {"members":"4 edges + body"}),
   V("11_doc_ns_003_renamed", {"rename":["Group1","Inlet"]})],
  D + " (NamedSelectionDef/StoredSelectionTableDef + monikers)", "partial", "names parsed; member monikers not bound (NYI TODO-6)", "P0", "yes")
f("doc_datum", "11_doc_attrs", "Datum plane / axis / point / origin (coordinate system)", "\u57fa\u51c6\u9762/\u8f74/\u70b9/\u5750\u6807\u7cfb", ["DatumPlaneCreator.Create","DatumLineCreator.Create","DatumPointCreator.Create","DatumOriginCreator.Create"], [],
  [V("11_doc_datum_001_plane_offset_z10", {"origin":[0,0,10],"normal":[0,0,1]}),
   V("11_doc_datum_002_axis_and_point", {}),
   V("11_doc_datum_003_origin_rotated", {"rot_deg":30})],
  D + " (DatumPlaneDef/DatumLineDef/DatumPointDef/CoordinateSystemDef)", "none", EV_NONE_DOC, "P1", "yes")
f("doc_named_view", "11_doc_attrs", "Named views / section plane", "\u547d\u540d\u89c6\u56fe", ["ViewHelper.CreateNamedView","ViewHelper.SetProjection","ViewHelper.SetSectionPlane"], [],
  [V("11_doc_view_001_named_iso", {"name":"Iso1"}),
   V("11_doc_view_002_two_views", {"names":["Front","Top"]})],
  D + " (SavedViewsDef / windows.xml)", "none", "NYI TODO-7: no official sample; unlock via RunScript", "P1", "needs GUI window? (headless has no view) - test both modes")
f("doc_coordsys", "11_doc_attrs", "Coordinate system", "\u5750\u6807\u7cfb", ["(raw API) CoordinateSystem.Create","DatumOriginCreator.Create"], [],
  [V("11_doc_coordsys_001_translated_rotated", {"origin":[10,0,0],"rot_deg":30})],
  D, "none", EV_NONE_DOC, "P2", "yes")
f("doc_notes", "11_doc_attrs", "3D notes / annotations", "\u6ce8\u91ca", ["(raw API) Note.Create"], [],
  [V("11_doc_note_001_text_on_face", {"text":"HELLO"})],
  D + " (annotation plane + note)", "none", EV_NONE_DOC, "P2", "needs selection setup (raw API, verify)")
f("doc_drawing_sheet", "11_doc_attrs", "Drawing sheet with general/projected views", "\u5de5\u7a0b\u56fe\u7eb8", ["(raw API) DrawingSheet.Create","DrawingView.CreateGeneralView/CreateProjectedView"], [],
  [V("11_doc_drawing_001_A3_3views", {"format":"A3","views":["front","top","right"]})],
  D + " (DrawingSheetDef, views)", "none", "repo writes its own DrawingSheetDef template (P2-3) but parser does not read official drawing sheets", "P2", "unknown (drawing windows in headless - verify)")
f("doc_visibility", "11_doc_attrs", "Visibility / suppress for physics / lock", "\u53ef\u89c1\u6027/\u6291\u5236/\u9501\u5b9a", ["ViewHelper.SetObjectVisibility","ViewHelper.SetSuppressForPhysics","ViewHelper.LockBodies"], [],
  [V("11_doc_visibility_001_hidden_body", {}), V("11_doc_suppress_001", {}), V("11_doc_lock_001", {})],
  D, "none", EV_NONE_DOC, "P2", "yes")
f("doc_material", "11_doc_attrs", "Material assignment", "\u6750\u6599", ["(raw API) DocumentMaterial.Create / LibraryMaterial -> DesignBody.Material"], [],
  [V("11_doc_material_001_steel", {"material":"Steel"})],
  D + " (DocumentMaterial / MaterialLibrary)", "none", "materials.py internal only", "P2", "yes (raw API, verify)")
f("doc_units", "11_doc_attrs", "Document units (mm / m / inch)", "\u5355\u4f4d", ["(raw API) Units / Document units setter (to locate); UnitsHelper.GetDocumentUnits is read-only"], [],
  [V("11_doc_units_001_inch", {"units":"IN"}), V("11_doc_units_002_meter", {"units":"M"})],
  D + " (DocumentUnitsDef)", "supported", "document.py parses DocumentUnitsDef", "P1", "unknown - no scripting setter found; may need API/GUI")

# ---------- 12 repair/prepare
f("rp_fix", "12_repair_prepare", "Repair: stitch, gaps, missing faces, split edges, extra edges, small faces, short edges, duplicates, merge faces", "\u4fee\u590d", ["StitchFaces/FixGaps/FixMissingFaces/FixSplitEdges/FixExtraEdges/FixSmallFaces/FixShortEdges/FixDuplicateFaces/FixCurveGaps/FixDuplicateCurves/FixExtendableSurfaces/FixInterference .FindAndFix"], [],
  [V("12_repair_stitch_001_six_sheets_to_solid", {"setup":"6 planar sheets forming cube"}),
   V("12_repair_missingface_001_open_box", {"setup":"box with deleted face"}),
   V("12_repair_extraedges_001_split_face_merge", {})],
  G, "supported", "results are ordinary B-rep; decoder value is in the defective inputs", "P2", "yes (need crafted defective inputs)")
f("rp_midsurface", "12_repair_prepare", "Midsurface", "\u4e2d\u9762", ["Midsurface.Convert(bodies, thickness)","MidsurfaceOffsetFaces.Create","MidsurfaceAspectExtensions.SetThickness"], [],
  [V("12_prepare_midsurface_001_plate_t2", {"base":"plate 100x50x2"}),
   V("12_prepare_midsurface_002_L_bracket_t3", {})],
  GD + " (sheet body + MidSurfaceAspect thickness)", "none", EV_NONE_DOC, "P1", "yes")
f("rp_share_topology", "12_repair_prepare", "Share topology", "\u5171\u4eab\u62d3\u6251", ["ShareTopology.FindAndFix","ForceShareTopology.Execute","UnShareTopology.Execute","SharePrep.Execute"], [],
  [V("12_prepare_sharetopo_001_two_blocks_touching", {}), V("12_prepare_sharetopo_002_force_tol0p1", {"tol_mm":0.1})],
  GD, "none", EV_NONE_DOC, "P1", "yes")
f("rp_volume_extract", "12_repair_prepare", "Volume extract / enclosure / workpiece / shrinkwrap", "\u4f53\u79ef\u62bd\u53d6/\u5305\u56f4", ["VolumeExtract.Create","Enclosure.Create","Workpiece.Create","Shrinkwrap.Create"], ["Box/Cylinder/Sphere cushion"],
  [V("12_prepare_enclosure_001_box_cushion10", {"cushion_mm":10}),
   V("12_prepare_volumeextract_001_pipe", {"base":"shelled cylinder with capping faces"}),
   V("12_prepare_workpiece_001", {})],
  GD + " (EnclosureAspect/VolumeExtractionAspect)", "none", EV_NONE_DOC, "P2", "needs selection setup")
f("rp_icepak", "12_repair_prepare", "Icepak objects (enclosure, fan, grille, opening, simplify)", "Icepak \u5bf9\u8c61", ["IcepakEnclosure/IcepakFan/IcepakGrille/IcepakOpening/IcepakSimplify"], [],
  [V("12_prepare_icepak_simplify_001_level1", {})],
  GD, "none", EV_NONE_DOC, "P2", "yes (niche)")

# ---------- 13 surface/curve
f("sc_surfaces", "13_surface_curve", "Surface bodies: circular/rectangular surface, SurfaceBody from API surface", "\u66f2\u9762\u4f53", ["CircularSurface.Create","RectangularSurface.Create","SurfaceBody.Create(Surface, BoxUV)"], [],
  [V("13_surface_circular_001_r20", {"r_mm":20}),
   V("13_surface_rect_001_30x10", {}),
   V("13_surface_body_001_cylinder_patch", {"surface":"Cylinder r10","uv":"0..pi x 0..20"})],
  G, "partial", "sheet bodies not in golden set", "P1", "yes")
f("sc_fill", "13_surface_curve", "Fill / patch (cap holes, N-sided patch)", "\u586b\u5145", ["Fill.Execute(sel, secondary, FillOptions, FillMode)"], [],
  [V("13_fill_001_cap_open_box", {}), V("13_fill_002_patch_4_splines", {})],
  G, "partial", EV_SPL, "P1", "needs selection setup")
f("sc_split_face", "13_surface_curve", "Split face (by curves/cutter/two points/parametric), split edge", "\u62c6\u5206\u9762/\u8fb9", ["SplitFace.ByTwoPoints/ByCutter/ByParametric/ByCurves","SplitEdge.ByCount/ByLength/ByProportion"], [],
  [V("13_splitface_001_block_top_two_points", {}), V("13_splitedge_001_by_count3", {"n":3})],
  G, "supported", EV_BOX, "P1", "needs selection setup")
f("sc_project_wrap", "13_surface_curve", "Project curves to solid / wrap / imprint", "\u6295\u5f71/\u7f20\u7ed5", ["ProjectToSolid.Execute","Wrap.Create","ProjectToSketch.Create","MoveImprintEdges.Execute"], [],
  [V("13_project_001_circle_onto_block_top", {}), V("13_wrap_001_rect_onto_cylinder", {})],
  G, "partial", "wrapped edges on cylinder are intcurve: " + EV_SPL, "P2", "needs selection setup")
f("sc_convert_solid", "13_surface_curve", "Convert to solid / auto-skin / skin from height field", "\u8f6c\u6362\u4e3a\u5b9e\u4f53", ["ConvertToSolid.Execute","AutoSkin.Execute"], [],
  [V("13_convertsolid_001_closed_sheets", {})],
  G, "partial", "", "P2", "yes")

# ---------- 14 holes
f("hole_standard", "14_holes_threads", "Standard holes (simple, counterbore, countersink, tapped, cosmetic thread)", "\u6807\u51c6\u5b54/\u87ba\u7eb9", ["StandardHoles.Create(nomFaceToLocations, StandardHolesOptions)","StandardHoles.Modify*","StandardHoles.Find/Convert","(raw API) Hole.Create"], ["drill size, depth, cbore/csink, tap, cosmetic thread"],
  [V("14_hole_simple_001_d6_depth10", {"d_mm":6,"depth_mm":10}),
   V("14_hole_cbore_001_M6", {"series":"ISO","fastener":"M6","counterbore":True}),
   V("14_hole_csink_001_90deg", {"csink_angle_deg":90}),
   V("14_hole_tapped_001_M8_cosmetic", {"tap":True,"cosmetic":True})],
  GD + " (hole feature data + cylinder/cone faces)", "partial", "cylinder/cone geometry decoded; hole feature XML not", "P1", "needs selection setup (face + location map) - StandardHolesOptions API to verify")

# ---------- 15 mesh
f("mesh_facet", "15_mesh_facet", "Facet (mesh) bodies: convert solid->mesh, reduce, smooth, thicken, boolean", "\u7f51\u683c\u4f53", ["FacetConvert.Create","FacetReduce/FacetSmooth/FacetRemesh/FacetMerge/FacetSubtract/FacetThicken","STLFile.Import/Insert"], [],
  [V("15_mesh_convert_001_block", {}), V("15_mesh_stl_import_001", {"file":"exported STL of cylinder"}), V("15_mesh_reduce_001_50pct", {})],
  GD + " (DesignMesh storage)", "none", "repo reads STL via OCCT; no scdoc DesignMesh decode", "P2", "yes")

inv = collections.OrderedDict([
 ("schema", "scdm_cases/feature_inventory v1"),
 ("generated_at", NOW),
 ("spaceclaim", {"product":"ANSYS SpaceClaim 2019 R3","version":"2019.3.38912","scripting_api":"SpaceClaim.Api.V19.Scripting (RunScript host namespace)"}),
 ("sources", ["SpaceClaim.Api.V19.dll reflection (850 types; *Condition.Create, Hole.Create, DocumentMaterial.Create, Note.Create, DrawingSheet.Create, CoordinateSystem.Create present; SheetMetal* read-only)", "SpaceClaim.Api.V19.Scripting.dll reflection (852 exported types, 171 in Commands namespace, 154 command classes with static entry points) -> _inventory/raw/v19_scripting_reflection.txt",
              "Scripting/LoadSCDMAPITypesV19.py", "Snippets/V19 (21 snippets)",
              "repo: scdm_api_types.md, function_gap_analysis.md, docs/NYI_INVENTORY.md, docs/IMPROVEMENT_PRIORITIES.md, scdoc_parser/*"]),
 ("categories", CATS),
 ("status_legend", {"supported":"decoder already parses the resulting geometry/doc entries (evidence given)","partial":"geometry partly decoded or doc entries only partly parsed","none":"no decoding of the resulting doc entries/geometry kind"}),
 ("priority_legend", {"P0":"core geometry/doc constructs every real file contains or explicit repo TODO gaps","P1":"common features with new doc entries or geometry kinds","P2":"niche / low decoder value"}),
 ("feasibility_legend", {"yes":"runs from points/values only","needs selection setup":"script must locate faces/edges/curves by geometry before the command","GUI-only":"no scripting entry point in V19"}),
 ("features", F),
])
json.dump(inv, open(os.path.join(OUT,"feature_inventory.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- combos
C = []
def c(key, title, steps, features, expect, prio, feas="needs selection setup"):
    C.append(collections.OrderedDict([("case_key", key), ("title", title), ("steps", steps), ("features", features), ("expect", expect), ("priority", prio), ("headless_feasibility", feas)]))
c("20_combo_bracket_001_sketch_pull_round_hole", "L-bracket: sketch L profile, pull 30, round inner edge r5, 2 through holes r3", ["sketch L chain 60x40 t8","extrude 30","ConstantRound inner edge r5","cut 2 holes r3"], ["sk_line","pull_extrude_face","edge_round","pull_extrude_cut"], {"bodies":1}, "P0")
c("20_combo_flange_002_revolve_pattern_chamfer", "Pipe flange: revolve profile, circular pattern of 6 bolt holes, chamfer outer edge", ["revolve flange section","cut hole r5 at R40","circular pattern 6","chamfer 1mm"], ["pull_revolve","pull_extrude_cut","mp_pattern_circular","edge_chamfer"], {"bodies":1}, "P0")
c("20_combo_plate_003_linear_pattern_holes_round", "Plate 100x60x5 with 3x4 hole pattern and all-edge rounds", ["block","hole r2","linear pattern 3x4","round r1 outer edges"], ["prim_block","pull_extrude_cut","mp_pattern_linear","edge_round"], {"bodies":1}, "P0")
c("20_combo_housing_004_block_shell_round", "Housing: block, round vertical edges r8, shell open top t2", ["block 80x60x40","round 4 vertical edges r8","shell remove top t2"], ["prim_block","edge_round","so_shell"], {"bodies":1}, "P0")
c("20_combo_bool_005_block_cyl_sphere", "Boolean chain: block + cylinder boss merge, subtract sphere, intersect with cylinder", ["block","cyl merge","sphere subtract","intersect with big cyl"], ["bool_merge","bool_subtract","bool_intersect"], {"bodies":1}, "P0", "yes")
c("20_combo_shaft_006_revolve_chamfer_keyway", "Stepped shaft: revolve 3 diameters, chamfer ends, keyway pocket", ["revolve stepped profile","chamfer both ends 1mm","keyway pocket 6x30 depth 3"], ["pull_revolve","edge_chamfer","pull_extrude_cut"], {"bodies":1}, "P0")
c("20_combo_spline_007_spline_extrude_round", "Spline cam: closed spline profile extruded 10, rounded r1", ["sketch periodic spline","extrude 10","round top edge r1"], ["sk_spline","pull_extrude_face","edge_round"], {"bodies":1}, "P0")
c("20_combo_loft_008_loft_shell", "Bottle: loft rect->circle->circle, shell open top 1mm", ["3 profiles","loft","shell"], ["pull_loft","so_shell"], {"bodies":1}, "P1")
c("20_combo_sweep_009_pipe_bend", "Bent pipe: sweep circle along line-arc-line path, shell both ends", ["path chain","sweep circle r10","shell remove 2 end faces t1"], ["pull_sweep","so_shell"], {"bodies":1}, "P1")
c("20_combo_mirror_010_half_model_mirror_merge", "Half model mirrored about YZ and merged", ["half bracket","mirror YZ merge"], ["mp_mirror","bool_merge"], {"bodies":1}, "P0")
c("20_combo_split_011_split_multi_body_names_colors", "Block split into 3 bodies by 2 planes, each renamed + colored", ["block","split z=10","split z=20","rename Part_A..C","colors"], ["bool_split_body","doc_rename","doc_colors"], {"bodies":3}, "P0", "yes")
c("20_combo_doc_012_layers_colors_named_selections", "Doc attributes: 3 bodies on 2 layers, face colors, 3 named selections (inlet/outlet/wall)", ["3 primitives","2 layers","face colors","NamedSelection x3"], ["doc_layers","doc_colors","doc_named_selection","doc_rename"], {"bodies":3,"named_selections":3,"layers":3}, "P0", "yes")
c("20_combo_doc_013_datums_named_selection_on_edges", "Datum plane + axis + named selection of edges on filleted block", ["block","round","datum plane z=5","datum axis","NS of round faces"], ["doc_datum","edge_round","doc_named_selection"], {}, "P1")
c("20_combo_asm_014_two_components", "2-component assembly: plate + boss in separate components, renamed", ["block in comp Plate","cyl in comp Boss","SetName"], ["asm_component","doc_rename"], {"components":2,"bodies":2}, "P0", "yes")
c("20_combo_asm_015_instances_pattern", "Assembly with 1 part definition instanced 4x (translated + rotated)", ["comp Bolt","copy/paste 3x","move/rotate instances"], ["asm_component","asm_instance","mp_translate","mp_rotate"], {"components":4,"part_defs":2}, "P0")
c("20_combo_asm_016_nested_3levels_colors_layers", "Nested assembly 3 levels, bodies colored + layered", ["root/sub/subsub comps","bodies in each","layers/colors"], ["asm_component","doc_layers","doc_colors"], {"components":3}, "P1", "yes")
c("20_combo_asm_017_mates_align_tangent", "2-component assembly with align + tangent conditions", ["plate + pin comps","align axis","tangent faces"], ["asm_component","asm_conditions"], {"conditions":2}, "P0", "needs selection setup (raw API conditions, verify)")
c("20_combo_sm_018_sheetmetal_bracket", "Sheet metal bracket: convert plate, 2 flanges, relief, unfold", ["plate 100x50x2","convert to sheet metal","flange 90deg x2","unfold"], ["sm_all"], {}, "P1", "GUI-only")
c("20_combo_beam_019_frame_with_profiles", "Beam frame: rectangular frame of 4 lines + 2 diagonals, I profile + rect tube", ["6 design curves","BeamProfile I & Rect","Beam.Create","orientation"], ["beam_profile","beam_create","sk_datum_curve"], {"beams":6}, "P1")
c("20_combo_prep_020_midsurface_share_topology", "Plate assembly midsurfaced and topology shared", ["2 plates T-joint","Midsurface","ShareTopology"], ["rp_midsurface","rp_share_topology"], {}, "P1", "yes")
c("20_combo_prep_021_enclosure_named_selection", "CFD prep: body + box enclosure (cushion 20) + named selections inlet/outlet", ["body","Enclosure","NamedSelection faces"], ["rp_volume_extract","doc_named_selection"], {}, "P1")
c("20_combo_hole_022_holes_pattern_plate", "Plate with counterbored M6 hole circular-patterned 4x", ["plate","StandardHoles cbore M6","circular pattern 4"], ["hole_standard","mp_pattern_circular"], {}, "P1")
c("20_combo_helix_023_spring_ends_ground", "Spring: helix sweep of circle, ends cut flat by split planes", ["revolve by helix","split body by 2 planes","delete ends"], ["pull_helix","bool_split_body"], {}, "P1")
c("20_combo_draft_024_molded_part", "Molded box: extrude, draft 3deg, round r2, shell t1.5", ["block","draft 4 sides","round","shell"], ["so_draft","edge_round","so_shell"], {}, "P1")
c("20_combo_surface_025_sheets_stitch_thicken", "Sheets: 2 planar + 1 cylindrical surface stitched, thickened 2mm", ["planar bodies","surface body","StitchFaces","Thicken"], ["prim_planar_body","sc_surfaces","rp_fix","so_thicken"], {}, "P2")
c("20_combo_wrap_026_cylinder_wrap_text_pull", "Cylinder with wrapped rectangle imprint pulled 1mm", ["cyl","sketch rect","Wrap","pull imprint"], ["sc_project_wrap","pull_face_offset"], {}, "P2")
c("20_combo_units_027_inch_doc_primitives", "Inch document with block+cylinder (unit factor check)", ["set units IN","block 1x2x3 in","cyl"], ["doc_units","prim_block","prim_cylinder"], {}, "P1", "unknown (units setter)")
c("20_combo_multi_028_many_bodies_8", "8 bodies (mixed primitives) in root, each named/colored - id allocation stress", ["8 primitives","rename","colors"], ["prim_block","prim_cylinder","prim_sphere","doc_rename","doc_colors"], {"bodies":8}, "P0", "yes")
c("20_combo_multi_029_many_components_8", "8 components each with one body (IMPROVEMENT_PRIORITIES P0-1 id collision scenario)", ["8 comps x 1 body"], ["asm_component"], {"components":8,"bodies":8}, "P0", "yes")
c("20_combo_edit_030_pull_after_pattern", "Pattern of bosses then pull base face + round (pattern relation survives edit)", ["plate","boss","linear pattern 4","pull base -2","round bosses r1"], ["mp_pattern_linear","pull_face_offset","edge_round"], {}, "P1")
c("20_combo_view_031_named_views_section", "Named views + section plane on assembly", ["assembly from 014","CreateNamedView x2","SetSectionPlane"], ["doc_named_view","asm_component"], {}, "P1", "needs GUI window? (test)")
c("20_combo_mesh_032_mesh_plus_solid", "Document with solid body + facet body converted from a copy", ["cyl","copy","FacetConvert"], ["mesh_facet","prim_cylinder"], {}, "P2", "yes")
combo = collections.OrderedDict([("schema","scdm_cases/combo_plan v1"),("generated_at",NOW),("folder","20_combo"),("count",len(C)),("combos",C)])
json.dump(combo, open(os.path.join(OUT,"combo_plan.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- stats + md
by_cat = collections.OrderedDict((k, [x for x in F if x["category"]==k]) for k in CATS if k!="20_combo")
nvar = sum(len(x["variants"]) for x in F)
pc = collections.Counter(x["priority"] for x in F)
pv = collections.Counter()
for x in F: pv[x["priority"]] += len(x["variants"])
fe = collections.Counter(x["headless_feasibility"].split(" ")[0].split("(")[0] for x in F)
st = collections.Counter(x["repo_support"] for x in F)
L = []
L.append("# SpaceClaim V19 (2019 R3) feature inventory for scdm_cases\n")
L.append("Generated %s from SpaceClaim.Api.V19.Scripting.dll reflection (154 command classes), Snippets\\V19 and the scdocdecoding repo docs. Machine-readable: `feature_inventory.json`, `combo_plan.json`; raw reflection dump in `raw/`.\n" % NOW)
L.append("## Totals\n")
L.append("- Features: **%d**; single-case variants: **%d**; combo cases: **%d**" % (len(F), nvar, len(C)))
L.append("- Priority (features / variants): " + ", ".join("%s %d / %d" % (p, pc[p], pv[p]) for p in ("P0","P1","P2")))
L.append("- Repo support: " + ", ".join("%s %d" % (k, st[k]) for k in ("supported","partial","none")))
L.append("- Headless feasibility: yes %d, needs selection setup %d, GUI-only %d, other/unknown %d\n" % (sum(1 for x in F if x["headless_feasibility"].startswith("yes")), sum(1 for x in F if x["headless_feasibility"].startswith("needs selection")), sum(1 for x in F if x["headless_feasibility"].startswith("GUI-only")), sum(1 for x in F if not (x["headless_feasibility"].startswith(("yes","needs selection","GUI-only"))))))
L.append("## Per category\n")
L.append("| Category | Features | Variants | P0 | P1 | P2 |")
L.append("|---|---|---|---|---|---|")
for k, xs in by_cat.items():
    L.append("| `%s` | %d | %d | %d | %d | %d |" % (k, len(xs), sum(len(x["variants"]) for x in xs), *[sum(1 for x in xs if x["priority"]==p) for p in ("P0","P1","P2")]))
L.append("| `20_combo` | - | %d | %d | %d | %d |\n" % (len(C), *[sum(1 for x in C if x["priority"]==p) for p in ("P0","P1","P2")]))
for k, xs in by_cat.items():
    L.append("## %s \u2014 %s\n" % (k, CATS[k]))
    L.append("| id | Feature (EN / \u4e2d\u6587) | V19 API | Variants | Impact | Repo | Prio | Headless |")
    L.append("|---|---|---|---|---|---|---|---|")
    for x in xs:
        L.append("| `%s` | %s / %s | %s | %s | %s | %s | %s | %s |" % (x["id"], x["name_en"], x["name_zh"], "<br>".join("`%s`" % a for a in x["v19_api"]), "<br>".join(v["case_key"] for v in x["variants"]), x["expected_scdoc_impact"], x["repo_support"], x["priority"], x["headless_feasibility"]))
    L.append("")
L.append("## Combination cases (`20_combo`)\n")
L.append("| case | description | features | prio | headless |")
L.append("|---|---|---|---|---|")
for x in C:
    L.append("| `%s` | %s | %s | %s | %s |" % (x["case_key"], x["title"], ", ".join(x["features"]), x["priority"], x["headless_feasibility"]))
L.append("\n## Not scriptable in V19 (GUI-only / needs non-scripting API)\n")
L.append("- **Sheet metal**: no SheetMetal* class among the 171 Scripting Commands types; the raw API only exposes read-side `SheetMetalAspect/SheetMetalFeature/Bend` (no Create) -> GUI-only for generation.\n- **Assembly conditions**: no Scripting command (`Constraint.*` are *sketch* constraints) BUT the raw API has `AlignCondition/TangentCondition/OrientCondition/AnchorCondition/RigidCondition/GearCondition.Create` -> feasible via raw API from the RunScript host (to verify).\n- **Variable-radius round**: only ConstantRound / FullRound / Chamfer exist.\n- **Material**: via raw API `DocumentMaterial.Create` + `DesignBody.Material`; **document units setter**: not found yet (UnitsHelper is read-only).\n- **Named views**: ViewHelper.CreateNamedView exists but needs a window \u2014 test in GUI mode.\n")
L.append("## Estimate\n")
L.append("- SpaceClaim launch overhead measured in 00_smoke: ~85 s start + ~36 s exit \u2248 2 min; smoke script body 23 s (includes first-command warm-up).\n- Plan: one launch per category batch (\u2264 ~25 cases per launch, `DocumentHelper.CreateNewDocument` + `CloseDocument` per case), assume ~10\u201315 s/case in-process.\n- Scriptable cases: %d single (excl. done smoke + 3 GUI-only sheet-metal) + %d combos (excl. 1 GUI-only) \u2248 %d cases.\n- Launches: ~14 (one per category 01\u201315, combos split in 2) \u2192 ~28 min overhead + ~%d\u00d712 s \u2248 %d min in-process \u2192 **~75 min pure run time**; budget 2\u20134 h wall clock including fix-up re-runs of selection-heavy categories.\n" % (nvar-4, len(C)-1, nvar-4+len(C)-1, nvar-4+len(C)-1, round((nvar-4+len(C)-1)*12/60)))
open(os.path.join(OUT,"feature_inventory.md"),"w",encoding="utf-8").write("\n".join(L))
print(len(F), nvar, len(C), dict(pc), dict(pv), dict(st))
for k, xs in by_cat.items(): print(k, len(xs), sum(len(x["variants"]) for x in xs))
print("P0:", [x["id"] for x in F if x["priority"]=="P0"])

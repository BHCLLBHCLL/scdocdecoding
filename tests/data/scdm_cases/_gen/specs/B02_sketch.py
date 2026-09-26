BATCH = "B02_sketch"
CASES = [
("02_sketch_line_001_single_50", {"expect": {"bodies": 0, "root_curves": 1}}, '''
sketch_mode()
SketchLine.Create(P2(0, 0), P2(50, 0))
finish_sketch(ctx, "Line50")
'''),
("02_sketch_line_002_chain_closed_tri", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 600.0}}, '''
sketch_mode()
pts = List[Point]()
for p in [(0, 0, 0), (40, 0, 0), (20, 30, 0)]:
    pts.Add(P(*p))
SketchLine.CreateChain(pts, True)
finish_sketch(ctx, "Triangle")
'''),
("02_sketch_line_003_construction", {}, '''
sketch_mode()
SketchLine.Create(P2(0, 0), P2(0, 40), True)
SketchLine.Create(P2(-10, 0), P2(10, 0))
finish_sketch(ctx, "Construction")
'''),
("02_sketch_rect_001_40x20", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 800.0}}, '''
sketch_mode()
SketchRectangle.Create(P2(0, 0), P2(40, 0), P2(40, 20))
finish_sketch(ctx, "Rect_40x20")
'''),
("02_sketch_rect_002_rotated_30deg", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 800.0}}, '''
c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
p2 = (40 * c, 40 * s)
p3 = (p2[0] - 20 * s, p2[1] + 20 * c)
sketch_mode()
SketchRectangle.Create(P2(0, 0), P2(*p2), P2(*p3))
finish_sketch(ctx, "Rect_Rot30")
'''),
("02_sketch_circle_001_r10", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 314.159265}}, '''
sketch_mode()
SketchCircle.Create(P2(0, 0), MM(10))
finish_sketch(ctx, "Circle_R10")
'''),
("02_sketch_circle_002_two_concentric_r5_r10", {}, '''
sketch_mode()
SketchCircle.Create(P2(0, 0), MM(5))
SketchCircle.Create(P2(0, 0), MM(10))
finish_sketch(ctx, "Concentric")
'''),
("02_sketch_arc_001_center_r20_90deg", {"expect": {"bodies": 0, "root_curves": 1}}, '''
sketch_mode()
SketchArc.Create(P2(0, 0), P2(20, 0), P2(0, 20))
finish_sketch(ctx, "Arc_Center")
'''),
("02_sketch_arc_002_3point", {"expect": {"bodies": 0, "root_curves": 1}}, '''
sketch_mode()
SketchArc.Create3PointArc(P2(0, 0), P2(10, 5), P2(20, 0))
finish_sketch(ctx, "Arc_3Pt")
'''),
("02_sketch_arc_003_tangent_after_line", {"expect": {"bodies": 0, "root_curves": 2}}, '''
sketch_mode()
l = cc(SketchLine.Create(P2(0, 0), P2(20, 0)))
first_ok(ctx, "tangent_arc", [
    lambda: SketchArc.CreateTangentArc(sel(l[0]), P2(30, 10)),
    lambda: SketchArc.CreateTangentArc(P2(20, 0), P2(30, 10), DirectionUV.Create(1, 0))])
finish_sketch(ctx, "Line_TangentArc")
'''),
("02_sketch_ellipse_001_a20_b10", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 628.318531}}, '''
sketch_mode()
SketchEllipse.Create(P2(0, 0), DirectionUV.Create(1, 0), DirectionUV.Create(0, 1), MM(20), MM(10))
finish_sketch(ctx, "Ellipse_20x10")
'''),
("02_sketch_ellipse_002_rotated_45", {"expect": {"bodies": 1, "faces": 1, "area_mm2": 235.619449}}, '''
c = math.cos(math.radians(45))
sketch_mode()
SketchEllipse.Create(P2(0, 0), DirectionUV.Create(c, c), DirectionUV.Create(-c, c), MM(15), MM(5))
finish_sketch(ctx, "Ellipse_Rot45")
'''),
("02_sketch_polygon_001_hex_r10", {"expect": {"bodies": 1, "faces": 1}}, '''
sketch_mode()
SketchPolygon.Create(P2(0, 0), DirectionUV.Create(1, 0), DirectionUV.Create(0, 1), MM(10), 6)
finish_sketch(ctx, "Hexagon")
'''),
("02_sketch_polygon_002_pent_r8", {"expect": {"bodies": 1, "faces": 1}}, '''
sketch_mode()
SketchPolygon.Create(P2(0, 0), DirectionUV.Create(1, 0), DirectionUV.Create(0, 1), MM(8), 5)
finish_sketch(ctx, "Pentagon")
'''),
("02_sketch_spline_001_open_5pts", {"expect": {"bodies": 0, "root_curves": 1}}, '''
sketch_mode()
SketchNurbs.CreateFrom2DPoints(False, P2L([(0, 0), (10, 8), (20, -4), (30, 6), (40, 0)]))
finish_sketch(ctx, "Spline_Open")
'''),
("02_sketch_spline_002_periodic_6pts", {"expect": {"bodies": 1, "faces": 1}}, '''
pts = []
for i in range(6):
    a = math.radians(60 * i)
    r = 15 if i % 2 == 0 else 10
    pts.append((r * math.cos(a), r * math.sin(a)))
sketch_mode()
SketchNurbs.CreateFrom2DPoints(True, P2L(pts))
finish_sketch(ctx, "Spline_Periodic")
'''),
("02_sketch_spline_003_end_tangents", {"expect": {"bodies": 0, "root_curves": 1}}, '''
sketch_mode()
SketchNurbs.CreateFrom2DPoints(False, P2L([(0, 0), (10, 5), (20, 5), (30, 0)]), VectorUV.Create(MM(10), MM(10)), VectorUV.Create(MM(10), MM(-10)))
finish_sketch(ctx, "Spline_Tangents")
'''),
("02_sketch_point_001", {}, '''
sketch_mode()
SketchPoint.Create(P2(5, 5))
finish_sketch(ctx, "Point")
ctx.data["root_points"] = _safe(lambda: GetRootPart().DatumPoints.Count)
'''),
("02_sketch_offset_001_rect_offset3", {}, '''
sketch_mode()
r = SketchRectangle.Create(P2(0, 0), P2(40, 0), P2(40, 20))
cs = cc(r)
ctx.data["rect_curves"] = len(cs)
first_ok(ctx, "offset", [
    lambda: SketchOffsetCurve.Create(sel(cs), MM(3)),
    lambda: SketchOffsetCurve.Create(sel(cs), P2(-3, -3))])
finish_sketch(ctx, "Rect_Offset3")
'''),
("02_sketch_round2d_001_rect_corner_r4", {}, '''
sketch_mode()
cb = cc(SketchLine.Create(P2(0, 0), P2(40, 0)))[0]
cr = cc(SketchLine.Create(P2(40, 0), P2(40, 20)))[0]
ct = cc(SketchLine.Create(P2(40, 20), P2(0, 20)))[0]
cl = cc(SketchLine.Create(P2(0, 20), P2(0, 0)))[0]
def _sp(c, at_end):
    iv = c.Shape.Bounds
    return SelectionPoint.CreateCurve(c, iv.End - 1e-4 if at_end else iv.Start + 1e-4)
first_ok(ctx, "round2d", [
    lambda: Sketch2DRound.Create(_sp(cl, True), _sp(cb, False), MM(4)),
    lambda: Sketch2DRound.Create(Selection.Create(cl), Selection.Create(cb), MM(4)),
    lambda: Sketch2DRound.Create(sel(curves_now()[3]), sel(curves_now()[0]), MM(4))])
finish_sketch(ctx, "Rect_Round4")
'''),
("02_sketch_constraint_001_hv_rect", {}, '''
sketch_mode()
ctx.attempt("StartConstraintSketching", lambda: SketchHelper.StartConstraintSketching())
pts = [(0, 0), (40, 1), (41, 20), (0, 20)]
cs = [cc(SketchLine.Create(P2(*pts[i]), P2(*pts[(i + 1) % 4])))[0] for i in range(4)]
ctx.attempt("horizontal_c1", lambda: Constraint.CreateHorizontal(sel(cs[0])))
ctx.attempt("horizontal_c3", lambda: Constraint.CreateHorizontal(sel(cs[2])))
ctx.attempt("vertical_c2", lambda: Constraint.CreateVertical(sel(cs[1])))
ctx.attempt("vertical_c4", lambda: Constraint.CreateVertical(sel(cs[3])))
ctx.data["satisfied"] = _safe(lambda: ConstraintHelper.ModelSatisfied())
if not (ctx.ok("horizontal_c1") or ctx.ok("vertical_c2")):
    raise Exception("no constraint created")
finish_sketch(ctx, "HV_Rect")
'''),
("02_sketch_constraint_002_tangent_line_arc", {}, '''
sketch_mode()
ctx.attempt("StartConstraintSketching", lambda: SketchHelper.StartConstraintSketching())
l = cc(SketchLine.Create(P2(0, 0), P2(20, 0)))[0]
a = cc(SketchArc.Create(P2(20, 10), P2(20, 1), P2(30, 10)))[0]
first_ok(ctx, "tangent", [
    lambda: Constraint.CreateTangent(SelectionPoint.CreateCurve(l, None), SelectionPoint.CreateCurve(a, None)),
    lambda: Constraint.CreateTangent(SelectionPoint.CreateCurve(l, MM(20)), SelectionPoint.CreateCurve(a, 0.0)),
    lambda: Constraint.CreateTangent(SelectionPoint.Create(l, System.Array[float]([MM(20)])), SelectionPoint.Create(a, System.Array[float]([0.0])))])
ctx.data["satisfied"] = _safe(lambda: ConstraintHelper.ModelSatisfied())
finish_sketch(ctx, "Tangent_LineArc")
'''),
("02_sketch_constraint_003_concentric_equal", {}, '''
sketch_mode()
ctx.attempt("StartConstraintSketching", lambda: SketchHelper.StartConstraintSketching())
c1 = cc(SketchCircle.Create(P2(0, 0), MM(10)))[0]
c2 = cc(SketchCircle.Create(P2(1, 1), MM(7)))[0]
ctx.attempt("concentric", lambda: Constraint.CreateConcentric(sel(c1), sel(c2)))
ctx.attempt("equal_radius", lambda: Constraint.CreateEqualRadius(sel(c1), sel(c2)))
ctx.data["satisfied"] = _safe(lambda: ConstraintHelper.ModelSatisfied())
if not (ctx.ok("concentric") or ctx.ok("equal_radius")):
    raise Exception("no constraint created")
finish_sketch(ctx, "Concentric_Equal")
'''),
("02_sketch_dim_001_length_40", {}, '''
sketch_mode()
ctx.attempt("StartConstraintSketching", lambda: SketchHelper.StartConstraintSketching())
l = cc(SketchLine.Create(P2(0, 0), P2(35, 0)))[0]
Dimension.CreateLength(sel(l), MM(40))
finish_sketch(ctx, "Dim_Length40")
ctx.data["curve_lengths_mm"] = [_safe(lambda: round(c.Shape.Length * 1000, 6)) for c in curves_now()]
'''),
("02_sketch_dim_002_radius_10", {}, '''
sketch_mode()
ctx.attempt("StartConstraintSketching", lambda: SketchHelper.StartConstraintSketching())
c = cc(SketchCircle.Create(P2(0, 0), MM(8)))[0]
Dimension.CreateRadial(sel(c), MM(10))
finish_sketch(ctx, "Dim_Radius10")
'''),
("02_sketch_dim_003_angle_30", {}, '''
sketch_mode()
ctx.attempt("StartConstraintSketching", lambda: SketchHelper.StartConstraintSketching())
l1 = cc(SketchLine.Create(P2(0, 0), P2(30, 0)))[0]
l2 = cc(SketchLine.Create(P2(0, 0), P2(25, 10)))[0]
first_ok(ctx, "angle_dim", [
    lambda: Dimension.CreateAngle(sel(l1), sel(l2), False, DEG(30)),
    lambda: Dimension.CreateAngle(sel(l1), sel(l2), True, DEG(30))])
finish_sketch(ctx, "Dim_Angle30")
'''),
("02_sketch_designcurve_001_3d_line", {"expect": {"bodies": 0, "root_curves": 1}}, '''
dcurve(seg((0, 0, 0), (10, 20, 30)), "Line3D")
'''),
("02_sketch_designcurve_002_helix_spline", {"expect": {"bodies": 0, "root_curves": 1}}, '''
pts = []
for i in range(3 * 16 + 1):
    t = 2 * math.pi * i / 16.0
    pts.append((10 * math.cos(t), 10 * math.sin(t), 5 * i / 16.0))
dcurve(spline_curve(pts), "Helix3Turns")
'''),
]

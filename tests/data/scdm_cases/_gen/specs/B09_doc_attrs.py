BATCH = "B09_doc_attrs"
CASES = [
("11_doc_rename_001_body_Block_A", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Temp_Name")
RenameObject.Execute(sel(b), "Block_A")
intent("body_name", unicode(all_bodies()[0].Name), u"Block_A")
'''),
("11_doc_rename_002_unicode_name", {"expect": {"bodies": 1},
  "notes": "deliberate non-ASCII body name (encoding test); English-name normalisation disabled for this case"}, '''
ctx.data["keep_unicode_names"] = True
b = block((0, 0, 0), (40, 30, 20), "Temp_Name")
nm = u"\\u4e3b\\u4f53_\\u6d4b\\u8bd5"
RenameObject.Execute(sel(b), nm)
intent("body_name", unicode(all_bodies()[0].Name), nm)
'''),
("11_doc_layers_001_two_layers_assign", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (40, 30, 20), "Red_Block")
b = block((60, 0, 0), (100, 30, 20), "Blue_Block")
Layers.Create("L_red")
Layers.Create("L_blue")
Layers.AssignLayer(sel(a), "L_red")
Layers.AssignLayer(sel(b), "L_blue")
Layers.SetColor(List[str](["L_red"]), Color.FromArgb(255, 255, 0, 0), True)
Layers.SetColor(List[str](["L_blue"]), Color.FromArgb(255, 0, 0, 255), True)
L = doc_stats()["layers"]
intent("has_L_red_L_blue", any("L_red" in unicode(x) for x in L) and any("L_blue" in unicode(x) for x in L), True)
ctx.data["body_layers"] = [unicode(_safe(lambda: master(x).Layer.Name)) for x in all_bodies()]
'''),
("11_doc_layers_002_hidden_locked", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (40, 30, 20), "Visible_Block")
b = block((60, 0, 0), (100, 30, 20), "Hidden_Locked_Block")
Layers.Create("L_hidden")
Layers.AssignLayer(sel(b), "L_hidden")
ctx.attempt("visibility", lambda: Layers.SetVisibility(List[str](["L_hidden"]), False))
ctx.attempt("lock", lambda: Layers.SetLock("L_hidden", True))
lay = [x for x in DocumentHelper.GetActiveDocument().Layers if unicode(x.Name) == "L_hidden"]
ctx.data["layer_state"] = _safe(lambda: {"visible": unicode(_safe(lambda: lay[0].IsVisible(None))), "locked": unicode(_safe(lambda: lay[0].IsLocked))})
if not (ctx.ok("visibility") and ctx.ok("lock")):
    raise Exception("layer visibility/lock failed")
'''),
("11_doc_color_001_body_red", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Red_Body")
o = SetColorOptions()
setp(ctx, o, [("FaceColorTarget", _safe(lambda: FaceColorTarget.Body))], "color_opts")
ColorHelper.SetColor(sel(b), o, Color.FromArgb(255, 255, 0, 0))
ctx.data["body_color"] = _safe(lambda: unicode(master(b).GetColor(None)))
'''),
("11_doc_color_002_face_green", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Green_Top_Block")
ColorHelper.SetColor(sel(top_face(b)), SetColorOptions(), Color.FromArgb(255, 0, 200, 0))
ctx.data["top_color"] = _safe(lambda: unicode(master(top_face(b)).GetColor(None)))
'''),
("11_doc_color_003_transparent_50", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Transparent_Block")
o = SetColorOptions()
setp(ctx, o, [("UseAlpha", True), ("FaceColorTarget", _safe(lambda: FaceColorTarget.Body))], "color_opts")
ColorHelper.SetColor(sel(b), o, Color.FromArgb(128, 0, 0, 255))
ctx.data["body_color"] = _safe(lambda: unicode(master(b).GetColor(None)))
'''),
("11_doc_ns_001_faces_top_bottom", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "NS_Block")
r = NamedSelection.Create(sel(top_face(b), bottom_face(b)), Selection.Empty())
NamedSelection.Rename(unicode(r.CreatedNamedSelection.Name), "Top_Bottom")
intent("ns_names", [unicode(x) for x in doc_stats()["named_selections"]], [u"Top_Bottom"])
'''),
("11_doc_ns_002_edges_and_body", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "NS_Block")
tops = edges_at_z(b, 20)
r = NamedSelection.Create(sel(list(tops) + [b]), Selection.Empty())
NamedSelection.Rename(unicode(r.CreatedNamedSelection.Name), "Top_Edges_And_Body")
ctx.data["member_count"] = _safe(lambda: len(list(r.CreatedNamedSelection.Items)))
intent("top_edges", len(tops), 4)
'''),
("11_doc_ns_003_renamed", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "NS_Block")
r = NamedSelection.Create(sel(face_extreme(b, (1, 0, 0), -1)), Selection.Empty())
old = unicode(r.CreatedNamedSelection.Name)
ctx.data["default_name"] = old
NamedSelection.Rename(old, "Group1")
NamedSelection.Rename("Group1", "Inlet")
intent("ns_names", [unicode(x) for x in doc_stats()["named_selections"]], [u"Inlet"])
'''),
("11_doc_datum_001_plane_offset_z10", {"expect": {"datum_planes": 1}}, '''
block((0, 0, 0), (40, 30, 20), "Datum_Block")
DatumPlaneCreator.Create(P(0, 0, 10), D(0, 0, 1))
dp = list(GetRootPart().DatumPlanes)[-1]
_safe(lambda: set_name(dp, "Plane_Z10"))
'''),
("11_doc_datum_002_axis_and_point", {"expect": {"bodies": 1}}, '''
block((0, 0, 0), (40, 30, 20), "Datum_Block")
first_ok(ctx, "datum_line", [lambda: DatumLineCreator.Create(P(0, 0, 0), D(0, 0, 1)),
                             lambda: DatumLineCreator.Create(P(0, 0, 0), P(0, 0, 50))])
first_ok(ctx, "datum_point", [lambda: DatumPointCreator.Create(P(10, 10, 10))])
root = GetRootPart()
ctx.data["datum_lines"] = _safe(lambda: root.DatumLines.Count)
ctx.data["datum_points"] = _safe(lambda: root.DatumPoints.Count)
'''),
("11_doc_datum_003_origin_rotated", {"expect": {"bodies": 1}, "notes": "doc_stats reports coordinate_systems=2 for one DatumOriginCreator origin (walk counts it twice); checked as range 1..2"}, '''
import math
block((0, 0, 0), (40, 30, 20), "Datum_Block")
a = math.radians(30)
DatumOriginCreator.Create(P(0, 0, 0), D(math.cos(a), math.sin(a), 0), D(-math.sin(a), math.cos(a), 0))
intent_range("coordinate_systems", doc_stats()["coordinate_systems"], 1, 2)
'''),
("11_doc_view_001_named_iso", {"expect": {"bodies": 1}}, '''
block((0, 0, 0), (40, 30, 20), "View_Block")
ViewHelper.SetProjection(ViewHelper.ViewProjection.Isometric, True, False)
ViewHelper.CreateNamedView("Iso1")
intent("activate_Iso1", bool(ViewHelper.ActivateNamedView("Iso1", True, False)), True)
'''),
("11_doc_view_002_two_views", {"expect": {"bodies": 1}}, '''
block((0, 0, 0), (40, 30, 20), "View_Block")
ViewHelper.SetProjection(ViewHelper.ViewProjection.Front, True, False)
ViewHelper.CreateNamedView("Front")
ViewHelper.SetProjection(ViewHelper.ViewProjection.Top, True, False)
ViewHelper.CreateNamedView("Top")
intent("activate_Front", bool(ViewHelper.ActivateNamedView("Front", True, False)), True)
'''),
("11_doc_coordsys_001_translated_rotated", {"expect": {"bodies": 1}, "notes": "raw CoordinateSystem.Create; doc_stats reports coordinate_systems=2 (range-checked)"}, '''
import math
block((0, 0, 0), (40, 30, 20), "CS_Block")
a = math.radians(30)
fr = Frame.Create(P(10, 0, 0), D(math.cos(a), math.sin(a), 0), D(-math.sin(a), math.cos(a), 0))
CS = rawt("CoordinateSystem")
root = GetRootPart()
first_ok(ctx, "coordsys", [lambda: raw("cs", lambda: CS.Create(master(root), "CS_1", fr)),
                           lambda: raw("cs", lambda: CS.Create(root, "CS_1", fr)),
                           lambda: DatumOriginCreator.Create(P(10, 0, 0), fr.DirX, fr.DirY)])
intent_range("coordinate_systems", doc_stats()["coordinate_systems"], 1, 2)
'''),
("11_doc_note_001_text_on_face", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Note_Block")
lp = enum_pick(LocationPoint, "Center", "MiddleCenter")
top = top_face(b)
mf = master(top)
uv = _safe(lambda: mf.Shape.ProjectPoint(P(20, 15, 20)).Param) or PointUV.Create(0, 0)
ctx.data["uv"] = unicode(uv)
root = GetRootPart()
dp_holder = []
def on_datum():
    dp = raw("datum", lambda: DatumPlane.Create(master(root), "Note_Plane_On_Top", Plane.Create(Frame.Create(P(0, 0, 20), D(1, 0, 0), D(0, 1, 0)))))
    return raw("n", lambda: Note.Create(dp, PointUV.Create(MM(20), MM(15)), lp, MM(4), "HELLO"))
n = first_ok(ctx, "note", [lambda: raw("n", lambda: Note.Create(mf, uv, lp, MM(4), "HELLO")),
                           lambda: raw("n", lambda: Note.Create(mf, PointUV.Create(MM(20), MM(15)), lp, MM(4), "HELLO")),
                           lambda: raw("n", lambda: Note.Create(top, uv, lp, MM(4), "HELLO")),
                           on_datum])
ctx.data["note_parent"] = _safe(lambda: unicode(n.Parent.GetType().Name))
ctx.data["note_text"] = _safe(lambda: unicode(n.Text))
'''),
("11_doc_drawing_001_A3_3views", {"expect": {"drawing_sheets": 1}}, '''
block((0, 0, 0), (40, 30, 20), "Drawing_Block")
doc = DocumentHelper.GetActiveDocument()
ds = raw("sheet", lambda: DrawingSheet.Create(doc, 0.42, 0.297))
_safe(lambda: raw("name", lambda: setattr(ds, "Name", "Sheet_A3")))
v = raw("gv", lambda: DrawingView.CreateGeneralView(ds, master(GetRootPart()), Matrix.Identity, PointUV.Create(0.12, 0.18)))
raw("pv_top", lambda: DrawingView.CreateProjectedView(v, PointUV.Create(0.12, 0.08)))
raw("pv_right", lambda: DrawingView.CreateProjectedView(v, PointUV.Create(0.28, 0.18)))
intent("views", _safe(lambda: ds.Views.Count), 3)
'''),
("11_doc_visibility_001_hidden_body", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (40, 30, 20), "Shown_Block")
b = block((60, 0, 0), (100, 30, 20), "Hidden_Block")
ViewHelper.SetObjectVisibility(sel(b), VisibilityType.Hide)
ctx.data["visible"] = _safe(lambda: unicode(master(b).IsVisible(None)))
'''),
("11_doc_suppress_001", {"expect": {"bodies": 2}}, '''
a = block((0, 0, 0), (40, 30, 20), "Active_Block")
b = block((60, 0, 0), (100, 30, 20), "Suppressed_Block")
ViewHelper.SetSuppressForPhysics(sel(b), True)
ctx.data["suppressed"] = _safe(lambda: unicode(master(b).IsSuppressed))
'''),
("11_doc_lock_001", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Locked_Block")
ViewHelper.LockBodies(sel(b), True)
ctx.data["locked"] = _safe(lambda: unicode(master(b).IsLocked))
'''),
("11_doc_material_001_steel", {"expect": {"bodies": 1}}, '''
b = block((0, 0, 0), (40, 30, 20), "Steel_Block")
doc = DocumentHelper.GetActiveDocument()
m = raw("material", lambda: DocumentMaterial.Create(doc, "Steel", 7850.0))
raw("assign", lambda: setattr(master(b), "Material", m))
intent("body_material", _safe(lambda: unicode(master(b).Material.Name)), u"Steel")
ctx.data["mass_props"] = _safe(lambda: [unicode(master(b).MassProperties.Mass), unicode(master(b).MassProperties.Volume)])
ctx.data["material_density"] = _safe(lambda: unicode(m.MaterialProperties))
'''),
("11_doc_units_001_inch", {"expect": {"bodies": 1}}, '''
block((0, 0, 0), (25.4, 50.8, 76.2), "Inch_Block")
doc = DocumentHelper.GetActiveDocument()
u = doc.Units
IU, IM, AU = rawt("ImperialUnits"), rawt("ImperialMassUnit"), rawt("AngleUnit")
first_ok(ctx, "imperial_units", [lambda: raw("iu", lambda: setattr(u, "ImperialUnits", IU(ImperialLengthUnit.Inches, enum_pick(IM, "Pounds", "PoundMass", "Pound"), AU.Degrees))),
                                 lambda: None])
raw("units", lambda: setattr(u, "ActiveUnitsSystem", UnitsSystemType.Imperial))
ctx.data["units_after"] = [unicode(doc.Units.ActiveUnitsSystem), unicode(doc.Units.Length)]
intent("units_system", unicode(doc.Units.ActiveUnitsSystem), u"Imperial")
intent("length_is_inch", "inch" in unicode(_safe(lambda: doc.Units.ImperialUnits.Length)).lower(), True)
'''),
("11_doc_units_002_meter", {"expect": {"bodies": 1},
  "notes": "fix: MetricUnits replaced via ctor MetricUnits(Meters, Kilograms, Degrees)"}, '''
block((0, 0, 0), (40, 30, 20), "Meter_Block")
doc = DocumentHelper.GetActiveDocument()
u = doc.Units
MU, MM_, AU = rawt("MetricUnits"), rawt("MetricMassUnit"), rawt("AngleUnit")
ctx.data["before"] = unicode(u.Length)
raw("mu", lambda: setattr(u, "MetricUnits", MU(MetricLengthUnit.Meters, enum_pick(MM_, "Kilograms", "Kilogram"), AU.Degrees)))
raw("units", lambda: setattr(u, "ActiveUnitsSystem", UnitsSystemType.Metric))
ctx.data["after"] = [unicode(doc.Units.ActiveUnitsSystem), unicode(doc.Units.Length), unicode(_safe(lambda: doc.Units.MetricUnits.Length))]
intent("metric_length_meters", unicode(_safe(lambda: doc.Units.MetricUnits.Length)), u"Meters")
'''),
]

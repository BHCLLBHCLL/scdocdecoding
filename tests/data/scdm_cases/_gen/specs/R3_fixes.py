BATCH = "R3_fixes"
_WRAP = """
def wrap_rect(ctx, cy, sh, strict=True):
    o = WrapOptions()
    ctx.data["wrap_opts_members"] = [n for n in dir(o) if not n.startswith("_")]
    n_c0 = len(curves_now())
    def cyl_faces():
        return max(face_count(x) for x in all_bodies() if not is_sheet(x))
    def chk():
        ctx.data["after_wrap"] = {"cyl_faces": cyl_faces(), "curves": len(curves_now()), "bodies": [[unicode(x.Name), is_sheet(x), face_count(x)] for x in all_bodies()]}
        if cyl_faces() <= 3 and (strict or len(curves_now()) <= n_c0):
            raise Exception("no imprint (faces=%d)" % cyl_faces())
    def w1():
        Wrap.Create(sel(cy), sel(face0(sh)), o)
        chk()
    def w2():
        Wrap.Create(sel(cy), sel(list(sh.Edges)), o)
        chk()
    def w3():
        Wrap.Create(sel(cy), sel(sh), o)
        chk()
    first_ok(ctx, "wrap", [w1, w2, w3])
    return cyl_faces()
"""
CASES = [
("13_wrap_001_rect_onto_cylinder", {"expect": {},
  "notes": "fix R3: Wrap.Create(selectObject = target body, secondarySelection = sheet face / edges to wrap, WrapOptions); checked for an imprint on the cylinder"}, _WRAP + '''
cy = cylinder((0, 0, 0), (0, 0, 40), 10, "Wrap_Target_Cyl")
sh = planar(poly_curves([(10, -5, 15), (10, 5, 15), (10, 5, 25), (10, -5, 25)]), plane_at((10, 0, 20), (1, 0, 0)), "Wrap_Rect")
nf = wrap_rect(ctx, cy, sh, strict=False)
ctx.data["cyl_faces"] = nf
intent_range("cyl_faces_after_imprint", nf, 4, 12)
'''),
("12_prepare_volumeextract_001_pipe", {"expect": {},
  "notes": "fix R3: pipe from Intersect (tube region 5654.9 mm3); VolumeExtract with the cap sheet BODIES as selection (bore face / pipe body as secondary) -> fluid volume 10053.1 mm3"}, '''
outer = cylinder((0, 0, 0), (0, 0, 50), 10, "Pipe")
inner = cylinder((0, 0, -5), (0, 0, 55), 8, "Bore_Cutter")
Combine.Intersect(sel(outer), sel(inner), MakeSolidsOptions())
pipe = min(bodies_now(), key=lambda x: abs((vol(x) or 0) - 5654.867))
rest = [x for x in bodies_now() if not (x == pipe)]
if rest:
    Delete.Execute(sel(rest))
set_name(pipe, "Pipe")
intent("pipe_volume_mm3", round(vol(pipe), 1), 5654.9, 0.5)
c1 = sheet_circle((0, 0, 0), 8, "Cap_Bottom")
c2 = sheet_circle((0, 0, 50), 8, "Cap_Top")
bore = [f for f in faces(pipe, "Cylinder") if abs(_safe(lambda: f.Shape.Geometry.Radius, 0) - MM(8)) < 1e-6]
ctx.data["bore_faces"] = len(bore)
def chk():
    if not any(abs((vol(x) or 0) - 10053.1) < 20 for x in all_bodies() if not is_sheet(x)):
        raise Exception("no fluid volume")
def v1():
    VolumeExtract.Create(sel(c1, c2), sel(bore[0]))
    chk()
def v2():
    VolumeExtract.Create(sel(c1, c2), sel(pipe))
    chk()
def v3():
    VolumeExtract.Create(sel(c1, c2), sel(bore[0]), VolumeExtractOptions())
    chk()
def v4():
    VolumeExtract.Create(sel(bore[0]), sel(c1, c2))
    chk()
first_ok(ctx, "volume_extract", [v1, v2, v3, v4])
vols = sorted([round(vol(x) or 0, 1) for x in all_bodies() if not is_sheet(x)])
ctx.data["solid_volumes"] = vols
intent("fluid_present", any(abs(v - 10053.1) < 20 for v in vols), True)
'''),
]
B = {}
B["20_combo_wrap_026_cylinder_wrap_text_pull"] = ("fix R3: Wrap.Create(target body, sheet face/edges) checked for an imprint, then the imprinted patch pulled out 1 mm", {"bodies": 1}, _WRAP + """
cy = cylinder((0, 0, 0), (0, 0, 40), 10, "Wrap_Cyl")
sh = planar(poly_curves([(10, -5, 15), (10, 5, 15), (10, 5, 25), (10, -5, 25)]), plane_at((10, 0, 20), (1, 0, 0)), "Wrap_Rect")
nf = wrap_rect(ctx, cy, sh, strict=True)
ctx.data["faces_after_wrap"] = nf
delete_sheets()
cy = largest()
small = min([f for f in cy.Faces if gtype(f) != "Plane"], key=lambda f: shape_of(f).Area)
first_ok(ctx, "pull", [lambda: ExtrudeFaces.Execute(sel(small), MM(1), ExtrudeFaceOptions())])
name_bodies(["Wrap_Cyl"], [largest()])
intent_range("volume_gain_mm3", total_volume() - 3.14159265 * 100 * 40, 50, 150)
""")
import json as _json, os as _os
_PLAN = {c["case_key"]: c for c in _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "_inventory", "combo_plan.json"), encoding="utf-8"))["combos"]}
for _k in B:
    _c = _PLAN[_k]
    _n, _e, _b = B[_k]
    CASES.append((_k, {"category": "20_combo", "feature": "combo", "priority": _c["priority"], "title": _c["title"],
                       "commands": _c["features"], "inventory_expect": _c.get("expect"), "expect": _e,
                       "notes": _n + " | steps: " + "; ".join(_c["steps"]) + " | headless_feasibility: " + _c.get("headless_feasibility", "")}, _b))

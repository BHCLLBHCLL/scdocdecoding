# -*- coding: utf-8 -*-
# scdm_cases smoke test: 20x20x20 mm box via SpaceClaim V19 recording-style scripting API.
# Run:  SpaceClaim.exe /RunScript="<abs path to this file>" /ExitAfterScript=True [/Headless=True]
# The /RunScript host injects the scripting namespace (GetRootPart, BlockBody, MM, ...) - no imports.
import System
import traceback
import time

OUT_DIR = r"D:\training\caedecoder\scdm_cases\00_smoke"
SCDOC = OUT_DIR + r"\00_smoke_box_001_20x20x20.scdoc"
RESULT = OUT_DIR + r"\00_smoke_result.json"

res = {"case": "00_smoke_box_001_20x20x20", "stage": "running", "success": False,
       "steps": [], "errors": [], "bodies": 0, "faces": 0, "edges": 0,
       "volume_m3": None, "scdoc": SCDOC, "scdoc_exists": False, "api_assemblies": []}
t0 = time.time()


def _js(o):
    if o is None:
        return "null"
    if o is True:
        return "true"
    if o is False:
        return "false"
    if isinstance(o, (int, long, float)):
        return repr(o)
    if isinstance(o, dict):
        return "{" + ", ".join('"%s": %s' % (k, _js(o[k])) for k in sorted(o)) + "}"
    if isinstance(o, (list, tuple)):
        return "[" + ", ".join(_js(x) for x in o) + "]"
    s = unicode(o)
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return '"' + s + '"'


def write_result():
    res["elapsed_s"] = round(time.time() - t0, 3)
    System.IO.File.WriteAllText(RESULT, _js(res))


def step(name):
    res["steps"].append(name)


def err(where):
    res["errors"].append(where + ": " + traceback.format_exc())


write_result()  # "running" marker: proves the script actually started

try:
    try:
        for a in System.AppDomain.CurrentDomain.GetAssemblies():
            n = a.GetName().Name
            if n.startswith("SpaceClaim.Api.V"):
                res["api_assemblies"].append(n)
    except Exception:
        err("assemblies")

    # 1. new document
    try:
        DocumentHelper.CreateNewDocument()
        step("DocumentHelper.CreateNewDocument")
    except Exception:
        err("CreateNewDocument")

    # 2. box: BlockBody first, sketch+extrude fallback
    made = False
    try:
        BlockBody.Create(Point.Create(MM(0), MM(0), MM(0)),
                         Point.Create(MM(20), MM(20), MM(20)),
                         ExtrudeType.ForceIndependent)
        made = len(GetRootPart().Bodies) > 0
        step("BlockBody.Create" + ("" if made else " (no body)"))
    except Exception:
        err("BlockBody.Create")
    if not made:
        try:
            ViewHelper.SetSketchPlane(Plane.PlaneXY)
            SketchRectangle.Create(Point2D.Create(MM(0), MM(0)),
                                   Point2D.Create(MM(20), MM(0)),
                                   Point2D.Create(MM(20), MM(20)))
            ViewHelper.SetViewMode(InteractionMode.Solid)
            face = GetRootPart().Bodies[0].Faces[0]
            ExtrudeFaces.Execute(Selection.Create(face), MM(20), ExtrudeFaceOptions())
            made = len(GetRootPart().Bodies) > 0
            step("SketchRectangle+ExtrudeFaces")
        except Exception:
            err("SketchRectangle+ExtrudeFaces")

    # 3. counts
    try:
        root = GetRootPart()
        vol = 0.0
        for b in root.Bodies:
            res["bodies"] += 1
            res["faces"] += b.Faces.Count
            res["edges"] += b.Edges.Count
            try:
                vol += b.MassProperties.Volume
            except Exception:
                vol += b.Shape.Volume
        res["volume_m3"] = vol
    except Exception:
        err("counts")

    # 4. save
    saved = False
    try:
        DocumentSave.Execute(SCDOC)
        saved = System.IO.File.Exists(SCDOC)
        step("DocumentSave.Execute" + ("" if saved else " (no file)"))
    except Exception:
        err("DocumentSave.Execute")
    if not saved:
        try:
            GetActiveWindow().Document.SaveAs(SCDOC)
            saved = System.IO.File.Exists(SCDOC)
            step("Document.SaveAs" + ("" if saved else " (no file)"))
        except Exception:
            err("Document.SaveAs")

    res["scdoc_exists"] = System.IO.File.Exists(SCDOC)
    if res["scdoc_exists"]:
        res["scdoc_size"] = System.IO.FileInfo(SCDOC).Length
    res["success"] = bool(made and res["scdoc_exists"] and res["bodies"] == 1
                          and res["faces"] == 6 and res["edges"] == 12)
except Exception:
    err("top-level")

res["stage"] = "done"
try:
    write_result()
except Exception:
    System.IO.File.WriteAllText(RESULT, '{"stage": "done", "success": false, "errors": ["result serialization failed"]}')
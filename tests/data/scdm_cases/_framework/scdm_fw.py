# -*- coding: utf-8 -*-
# scdm_cases batch framework v1 (IronPython 2.7 inside SpaceClaim 2019 R3, /RunScript host).
# Load it into the RunScript namespace from a driver or case script:
#     execfile(r"D:\training\caedecoder\scdm_cases\_framework\scdm_fw.py")
# Case script contract: defines CASE (dict) and build(ctx); see _framework\README_framework.md.
import System, clr, time, math, traceback
clr.AddReference("System.Drawing")
from System.Drawing import Color
from System.Collections.Generic import List

FW_VERSION = "1.1"
SCDM_ROOT = r"D:\training\caedecoder\scdm_cases"
FW_PATH = SCDM_ROOT + r"\_framework\scdm_fw.py"
SC_VERSION = "2019.3.38912"
_U8 = System.Text.UTF8Encoding(False)


# ---------------------------------------------------------------- raw API types
# RunScript scripts run against the V18 API (objects are SpaceClaim.Api.V18.*) and only the Scripting
# namespace is imported. Pull the raw document-API types used by cases into the global namespace.
RAW_API_NAMES = ["DocumentMaterial", "LibraryMaterial", "Material", "LocationPoint", "UnitsSystemType",
                 "MetricLengthUnit", "ImperialLengthUnit", "DrawingSheet", "DrawingView", "DrawingSheetContents",
                 "RigidCondition", "AnchorCondition", "AlignCondition", "TangentCondition", "OrientCondition",
                 "Note", "DatumPlane", "DatumLine", "DatumPoint", "Component", "Part", "DesignBody",
                 "DesignCurve", "Layer", "Units", "WriteBlock", "Task", "TextPoint", "Symbol"]


def _api_module():
    ns = "SpaceClaim.Api.V18"
    try:
        ns = GetRootPart().GetType().Namespace or ns
    except Exception:
        pass
    mod = __import__(ns)
    for part in ns.split(".")[1:]:
        mod = getattr(mod, part)
    return mod


try:
    API = _api_module()
except Exception:
    import SpaceClaim.Api.V18 as API
RAW_API_INJECTED = []
for _n in RAW_API_NAMES:
    _v = getattr(API, _n, None)
    if _v is not None and (_n not in globals() or _n in ("DatumPlane", "Note", "Component", "Part", "DesignBody")):
        # the raw classes are forced for names whose Scripting counterparts differ
        if _n in globals() and globals()[_n] is not _v:
            globals()["Scripting_" + _n] = globals()[_n]
        globals()[_n] = _v
        RAW_API_INJECTED.append(_n)


def now():
    return System.DateTime.Now.ToString("yyyy-MM-ddTHH:mm:sszzz")


def tb():
    return traceback.format_exc()


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ---------------------------------------------------------------- JSON (no json module dependency)
def js(o, ind=0):
    pad = "\n" + " " * (ind + 1)
    if o is None:
        return "null"
    if o is True:
        return "true"
    if o is False:
        return "false"
    if isinstance(o, (int, long)) and not isinstance(o, bool):
        return str(o)
    if isinstance(o, float):
        if o != o or o in (float("inf"), float("-inf")):
            return "null"
        return repr(o)
    if isinstance(o, dict):
        if not o:
            return "{}"
        ks = sorted(o.keys(), key=lambda k: unicode(k))
        return "{" + ",".join(pad + js(unicode(k)) + ": " + js(o[k], ind + 1) for k in ks) + "\n" + " " * ind + "}"
    if isinstance(o, (list, tuple, set)):
        o = list(o)
        if not o:
            return "[]"
        if all(not isinstance(x, (dict, list, tuple, set)) for x in o):
            return "[" + ", ".join(js(x, ind + 1) for x in o) + "]"
        return "[" + ",".join(pad + js(x, ind + 1) for x in o) + "\n" + " " * ind + "]"
    s = unicode(o)
    out = []
    for ch in s:
        c = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif c < 32:
            out.append('\\u%04x' % c)
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def write_text(path, s):
    d = System.IO.Path.GetDirectoryName(path)
    if d and not System.IO.Directory.Exists(d):
        System.IO.Directory.CreateDirectory(d)
    tmp = path + ".tmp"
    System.IO.File.WriteAllText(tmp, s, _U8)
    if System.IO.File.Exists(path):
        System.IO.File.Delete(path)
    System.IO.File.Move(tmp, path)


# ---------------------------------------------------------------- units / vectors (mm in, SI inside)
def P(x, y, z):
    return Point.Create(MM(x), MM(y), MM(z))


def P2(u, v):
    return Point2D.Create(MM(u), MM(v))


def D(x, y, z):
    return Direction.Create(x, y, z)


def mm(p):
    return (round(p.X * 1000.0, 6), round(p.Y * 1000.0, 6), round(p.Z * 1000.0, 6))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _unit(v):
    n = math.sqrt(_dot(v, v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _perp(ax):
    a = _unit(ax)
    t = (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0)
    return _unit(_cross(a, t))


def master(x):
    m = _safe(lambda: x.Master)
    return m if m is not None else x


def enum_pick(enum_type, *prefer):
    """Return the enum value whose name matches one of prefer (exact, then substring)."""
    names = list(System.Enum.GetNames(enum_type))
    for p in prefer:
        if p in names:
            return System.Enum.Parse(enum_type, p)
    for p in prefer:
        for n in names:
            if p.lower() in n.lower():
                return System.Enum.Parse(enum_type, n)
    raise Exception("enum %s has none of %s (names=%s)" % (enum_type, prefer, names))


# ---------------------------------------------------------------- selection helpers
def listify(objs):
    out = []
    for o in objs:
        if o is None:
            continue
        if isinstance(o, (list, tuple, set)):
            out.extend(listify(list(o)))
        elif isinstance(o, System.Collections.IEnumerable) and not isinstance(o, basestring):
            out.extend(listify(list(o)))
        else:
            out.append(o)
    return out


def sel(*objs):
    items = listify(objs)
    if not items:
        return Selection.Empty()
    if len(items) == 1:
        return Selection.Create(items[0])
    try:
        lst = List[IDocObject]()
        for i in items:
            lst.Add(i)
        return Selection.Create(lst)
    except Exception:
        return Selection.Union(*[Selection.Create(i) for i in items])


def gtype(x):
    t = _safe(lambda: x.Shape.Geometry.GetType().Name)
    if t is None:
        t = _safe(lambda: master(x).Shape.Geometry.GetType().Name, "?")
    return t


def _box(x):
    b = _safe(lambda: x.Shape.GetBoundingBox(Matrix.Identity))
    if b is None:  # occurrence body: Shape is a TrimmedSpace -> use master shape + occurrence transform
        tm = _safe(lambda: x.TransformToMaster)
        m = master(x).Shape
        b = m.GetBoundingBox(tm.Inverse if tm is not None else Matrix.Identity)
    return b


def bbox(x):
    b = _box(x)
    return (mm(b.MinCorner), mm(b.MaxCorner))


def bbox_center(x):
    return mm(_box(x).Center)


def shape_of(x):
    """Topology-bearing shape (Body) for a design body or occurrence (counts/volume are transform-invariant)."""
    s = _safe(lambda: x.Shape)
    if s is not None and hasattr(s, "Faces"):
        return s
    return master(x).Shape


def faces(body, kind=None, where=None):
    out = []
    for f in body.Faces:
        if kind and gtype(f) != kind:
            continue
        if where and not where(f):
            continue
        out.append(f)
    return out


def plane_axis(f):
    try:
        n = f.Shape.Geometry.Frame.DirZ
    except Exception:
        n = master(f).Shape.Geometry.Frame.DirZ
        tm = _safe(lambda: f.TransformToMaster)
        if tm is not None:
            n = tm.Inverse * n
    return _unit((n.X, n.Y, n.Z))


def face_extreme(body, axis=(0, 0, 1), side=1):
    """Planar face perpendicular to axis with the largest (side=1) / smallest (side=-1) position."""
    ax = _unit(axis)
    best, bv = None, None
    for f in faces(body, "Plane"):
        if abs(_dot(plane_axis(f), ax)) < 0.999:
            continue
        v = side * _dot(bbox_center(f), ax)
        if bv is None or v > bv:
            best, bv = f, v
    if best is None:
        raise Exception("face_extreme: no planar face normal to %s" % (axis,))
    return best


def top_face(body):
    return face_extreme(body, (0, 0, 1), 1)


def bottom_face(body):
    return face_extreme(body, (0, 0, 1), -1)


def face_nearest(body, pt, kind=None):
    fs = faces(body, kind)
    if not fs:
        raise Exception("face_nearest: no faces of kind %s" % kind)
    return min(fs, key=lambda f: _dist(bbox_center(f), pt))


def edges(body, kind=None, where=None):
    out = []
    for e in body.Edges:
        if kind and gtype(e) != kind:
            continue
        if where and not where(e):
            continue
        out.append(e)
    return out


def edge_mid(e):
    try:
        return mm(e.Shape.EvalMid().Point)
    except Exception:
        return bbox_center(e)


def edge_nearest(body, pt, kind=None):
    es = edges(body, kind)
    if not es:
        raise Exception("edge_nearest: no edges of kind %s" % kind)
    return min(es, key=lambda e: _dist(edge_mid(e), pt))


def edges_parallel(body, axis):
    ax = _unit(axis)
    out = []
    for e in edges(body, "Line"):
        d = e.Shape.Geometry.Direction
        if abs(_dot(_unit((d.X, d.Y, d.Z)), ax)) > 0.999:
            out.append(e)
    return out


def common_edges(fa, fb):
    ids = [e for e in fb.Edges]
    return [e for e in fa.Edges if any(e == x for x in ids)]


def body_named(name, part=None):
    part = part or DocumentHelper.GetActivePart()
    for b in part.Bodies:
        if unicode(b.Name) == name:
            return b
    for b in all_bodies():
        if unicode(b.Name) == name:
            return b
    raise Exception("body_named: %s not found" % name)


# ---------------------------------------------------------------- naming / creation
def set_name(obj, name):
    try:
        RenameObject.Execute(Selection.Create(obj), name)
    except Exception:
        pass
    if _safe(lambda: unicode(obj.Name)) == name:
        return obj
    for fn in (lambda: obj.SetName(name), lambda: setattr(master(obj), "Name", name), lambda: setattr(obj, "Name", name)):
        try:
            fn()
            if _safe(lambda: unicode(obj.Name)) == name:
                return obj
        except Exception:
            pass
    raise Exception("set_name failed: %s" % name)


def _created(res, part, n0):
    b = _safe(lambda: res.CreatedBody)
    if b is not None:
        return b
    cb = _safe(lambda: list(res.CreatedBodies), [])
    if cb:
        return cb[-1]
    bs = list(part.Bodies)
    if len(bs) > n0:
        return bs[-1]
    raise Exception("no body created")


def block(p0, p1, name=None):
    ap = DocumentHelper.GetActivePart()
    n0 = ap.Bodies.Count
    b = _created(BlockBody.Create(P(*p0), P(*p1), ExtrudeType.ForceIndependent), ap, n0)
    return set_name(b, name) if name else b


CYL_ORDER = [None]  # remembered argument order of CylinderBody.Create that produced a valid cylinder


def cylinder(base, top, r, name=None):
    """Solid cylinder axis base->top, radius r (mm). Validates volume; tries the 3-point argument orders."""
    ax = tuple(top[i] - base[i] for i in range(3))
    h = math.sqrt(_dot(ax, ax))
    pp = _perp(ax)
    rb = tuple(base[i] + r * pp[i] for i in range(3))
    rt = tuple(top[i] + r * pp[i] for i in range(3))
    want = math.pi * r * r * h
    orders = [("base,top,rbase", (base, top, rb)), ("base,rbase,top", (base, rb, top)), ("base,top,rtop", (base, top, rt))]
    if CYL_ORDER[0]:
        orders.sort(key=lambda o: o[0] != CYL_ORDER[0])
    ap = DocumentHelper.GetActivePart()
    tried = []
    for key, pts in orders:
        n0 = ap.Bodies.Count
        try:
            b = _created(CylinderBody.Create(P(*pts[0]), P(*pts[1]), P(*pts[2]), ExtrudeType.ForceIndependent), ap, n0)
        except Exception as e:
            tried.append((key, unicode(e)))
            continue
        v = _safe(lambda: shape_of(b).Volume * 1e9)
        if v is not None and abs(v - want) <= 1e-3 * want:
            CYL_ORDER[0] = key
            return set_name(b, name) if name else b
        tried.append((key, v))
        _safe(lambda: Delete.Execute(Selection.Create(b)))
    raise Exception("cylinder: no CylinderBody.Create order gave volume %.3f: %s" % (want, tried))


def sphere(c, r, name=None):
    ap = DocumentHelper.GetActivePart()
    n0 = ap.Bodies.Count
    b = _created(SphereBody.Create(P(*c), P(c[0] + r, c[1], c[2]), ExtrudeType.ForceIndependent), ap, n0)
    return set_name(b, name) if name else b


def component(name, builder=None):
    """Create a root-level component, optionally run builder() with it active; returns IComponent."""
    c = ComponentHelper.CreateAtRoot(name)
    if builder:
        ComponentHelper.SetActive(c)
        try:
            builder()
        finally:
            ComponentHelper.SetRootActive()
    return c


def raw(label, fn):
    """Run a raw-API (SpaceClaim.Api.V18/V19) write; falls back to WriteBlock.ExecuteTask if required."""
    try:
        return fn()
    except Exception as e:
        m = unicode(e).lower()
        if "write" not in m and "block" not in m and "task" not in m:
            raise
    _A = API
    box = []
    _A.WriteBlock.ExecuteTask(label, _A.Task(lambda: box.append(fn())))
    return box[0] if box else None


# ---------------------------------------------------------------- document statistics
def _walk(part, path, acc):
    for b in part.Bodies:
        acc["bodies"].append(("/".join(path), b))
    for c in part.Components:
        acc["components"].append(("/".join(path), c))
        try:
            _walk(c.Content, path + [unicode(c.Name)], acc)
        except Exception:
            pass


def all_bodies():
    acc = {"bodies": [], "components": []}
    _walk(GetRootPart(), [], acc)
    return [b for _, b in acc["bodies"]]


def _inc(d, k):
    d[k] = d.get(k, 0) + 1


def doc_stats():
    root = GetRootPart()
    acc = {"bodies": [], "components": []}
    _walk(root, [], acc)
    st = {"bodies": 0, "faces": 0, "edges": 0, "vertices": 0, "volume_mm3": 0.0, "area_mm2": 0.0,
          "body_list": [], "surface_types": {}, "curve_types": {}}
    for path, b in acc["bodies"]:
        s = shape_of(b)
        bi = {"name": _safe(lambda: unicode(b.Name)), "path": path,
              "faces": s.Faces.Count, "edges": s.Edges.Count,
              "vertices": _safe(lambda: s.Vertices.Count, 0),
              "closed": _safe(lambda: bool(s.IsClosed)), "manifold": _safe(lambda: bool(s.IsManifold)),
              "volume_mm3": _safe(lambda: round(s.Volume * 1e9, 6)),
              "bbox_mm": _safe(lambda: bbox(b))}
        area = 0.0
        for f in s.Faces:
            _inc(st["surface_types"], _safe(lambda: f.Geometry.GetType().Name, "?"))
            area += _safe(lambda: f.Area, 0.0)
        for e in s.Edges:
            _inc(st["curve_types"], _safe(lambda: e.Geometry.GetType().Name, "?"))
        bi["area_mm2"] = round(area * 1e6, 6)
        st["bodies"] += 1
        st["faces"] += bi["faces"]
        st["edges"] += bi["edges"]
        st["vertices"] += bi["vertices"] or 0
        st["volume_mm3"] += bi["volume_mm3"] or 0.0
        st["area_mm2"] += bi["area_mm2"]
        st["body_list"].append(bi)
    st["volume_mm3"] = round(st["volume_mm3"], 6)
    st["area_mm2"] = round(st["area_mm2"], 6)
    st["components"] = len(acc["components"])
    st["component_list"] = []
    templates = []
    for path, c in acc["components"]:
        st["component_list"].append({"name": _safe(lambda: unicode(c.Name)), "path": path})
        t = _safe(lambda: c.Template)
        if t is None:
            t = _safe(lambda: master(c).Template)
        if t is not None and not any(t == x for x in templates):
            templates.append(t)
    st["part_defs"] = len(templates)
    st["root_curves"] = _safe(lambda: root.Curves.Count)
    st["datum_planes"] = _safe(lambda: root.DatumPlanes.Count)
    st["coordinate_systems"] = _safe(lambda: root.CoordinateSystems.Count)
    st["beams"] = _safe(lambda: root.Beams.Count)
    st["meshes"] = _safe(lambda: root.Meshes.Count)
    st["mating_conditions"] = _safe(lambda: master(root).MatingConditions.Count)
    doc = _safe(lambda: DocumentHelper.GetActiveDocument())
    if doc is not None:
        st["layers"] = _safe(lambda: [unicode(l.Name) for l in doc.Layers])
        st["drawing_sheets"] = _safe(lambda: doc.DrawingSheets.Count)
        st["materials"] = _safe(lambda: [unicode(k) for k in doc.Materials.Keys])
        st["body_materials"] = _safe(lambda: dict((unicode(b.Name), unicode(master(b).Material.Name)) for _, b in acc["bodies"] if master(b).Material is not None))
        st["units_system"] = _safe(lambda: unicode(doc.Units.ActiveUnitsSystem))
        st["units_length"] = _safe(lambda: unicode(_safe(lambda: doc.Units.Length.Symbol) or _safe(lambda: doc.Units.Length.Name) or doc.Units.Length))
    st["named_selections"] = _safe(lambda: [unicode(g.Name) for g in GetActiveWindow().Groups])
    st["view_mode"] = _safe(lambda: unicode(ViewHelper.GetViewMode()))
    return st


def _cmp_expect(expect, actual):
    bad = {}
    for k, v in (expect or {}).items():
        if k not in actual:
            continue
        a = actual[k]
        if isinstance(v, float) or k.endswith("_mm3") or k.endswith("_mm2"):
            ok = a is not None and abs(a - v) <= max(1e-3, 1e-4 * abs(v))
        else:
            ok = (a == v)
        if not ok:
            bad[k] = {"expected": v, "actual": a}
    return bad


# ---------------------------------------------------------------- case / batch runner
class Ctx(object):
    def __init__(self, rec):
        self.rec = rec
        self.data = rec["data"]

    def note(self, key, value):
        self.rec["notes"].append({key: value})

    def cmd(self, name):
        self.rec["commands"].append(name)

    def attempt(self, key, fn):
        """Run one sub-item in its own try/except; result recorded under rec['items'][key]."""
        t = time.time()
        try:
            r = fn()
            self.rec["items"][key] = {"ok": True, "result": _safe(lambda: unicode(r)), "s": round(time.time() - t, 2)}
            return r
        except Exception:
            self.rec["items"][key] = {"ok": False, "error": tb(), "s": round(time.time() - t, 2)}
            return None

    def ok(self, key):
        return self.rec["items"].get(key, {}).get("ok", False)


class Batch(object):
    def __init__(self, name, result_path, mode="headless"):
        self.path = result_path
        self.mode = mode
        self.t0 = time.time()
        self.res = {"batch": name, "mode": mode, "stage": "running", "started_at": now(),
                    "framework": FW_VERSION, "spaceclaim_version": SC_VERSION, "cases": []}
        self.flush()

    def add(self, rec):
        self.res["cases"].append(rec)

    def flush(self):
        self.res["elapsed_s"] = round(time.time() - self.t0, 2)
        summ = {}
        for c in self.res["cases"]:
            _inc(summ, c.get("status", "?"))
        self.res["summary"] = summ
        write_text(self.path, js(self.res))

    def done(self):
        self.res["stage"] = "done"
        self.res["finished_at"] = now()
        self.flush()


def run_case(batch, case, build, out_dir, script_path=None):
    cid = case["case_id"]
    rec = {"case_id": cid, "category": case.get("category"), "feature": case.get("feature"),
           "title": case.get("title"), "params": case.get("params", {}), "expect": case.get("expect", {}),
           "commands": list(case.get("commands", [])), "status": "running", "items": {}, "notes": [],
           "data": {}, "mode": batch.mode, "started_at": now(), "script": script_path, "out_dir": out_dir,
           "spaceclaim_version": SC_VERSION, "framework": FW_VERSION}
    batch.add(rec)
    batch.flush()
    t0 = time.time()
    scdoc = System.IO.Path.Combine(out_dir, cid + ".scdoc")
    if not System.IO.Directory.Exists(out_dir):
        System.IO.Directory.CreateDirectory(out_dir)
    _safe(lambda: System.IO.File.Delete(scdoc))
    built = False
    try:
        DocumentHelper.CreateNewDocument()
        build(Ctx(rec))
        built = True
    except Exception:
        rec["error"] = tb()
    try:
        rec["actual"] = doc_stats()
    except Exception:
        rec["stats_error"] = tb()
    saved = False
    if built or case.get("save_on_error"):
        try:
            DocumentSave.Execute(scdoc)
            saved = System.IO.File.Exists(scdoc)
        except Exception:
            rec["save_error"] = tb()
        if not saved:
            try:
                DocumentHelper.GetActiveDocument().SaveAs(scdoc)
                saved = System.IO.File.Exists(scdoc)
                rec["saved_via"] = "Document.SaveAs"
            except Exception:
                rec["save_error"] = rec.get("save_error", "") + tb()
    rec["scdoc"] = scdoc if saved else None
    rec["scdoc_size"] = System.IO.FileInfo(scdoc).Length if saved else None
    rec["expect_mismatch"] = _cmp_expect(rec["expect"], rec.get("actual") or {})
    if built and saved:
        rec["status"] = "mismatch" if rec["expect_mismatch"] else "ok"
    else:
        rec["status"] = "failed"
    rec["elapsed_s"] = round(time.time() - t0, 2)
    rec["generated_at"] = now()
    try:
        d = DocumentHelper.GetActiveDocument()
        _safe(lambda: setattr(d, "IsModified", False))
        DocumentHelper.CloseDocument()
    except Exception:
        rec["close_error"] = tb()
    _safe(lambda: write_text(System.IO.Path.Combine(out_dir, cid + ".json"), js(rec)))
    batch.flush()
    return rec


def load_case(path):
    ns = dict(globals())
    ns["SCDM_BATCH"] = True
    ns["__file__"] = path
    execfile(path, ns)
    return ns["CASE"], ns["build"]


def run_case_files(batch_name, files, result_path, mode="headless", out_dir=None):
    b = Batch(batch_name, result_path, mode)
    for f in files:
        f = f.strip()
        if not f or f.startswith("#"):
            continue
        try:
            case, build = load_case(f)
        except Exception:
            b.add({"case_id": System.IO.Path.GetFileNameWithoutExtension(f), "status": "failed",
                   "error": "load: " + tb(), "script": f, "mode": mode})
            b.flush()
            continue
        od = out_dir or case.get("out_dir") or System.IO.Path.GetDirectoryName(f)
        run_case(b, case, build, od, f)
    b.done()
    return b


def run_list_file(batch_name, list_path, result_path, mode="headless", out_dir=None):
    files = [l for l in System.IO.File.ReadAllLines(list_path)]
    return run_case_files(batch_name, files, result_path, mode, out_dir)


def run_standalone(case, build, script_path):
    od = case.get("out_dir") or System.IO.Path.GetDirectoryName(script_path)
    b = Batch("single_" + case["case_id"], System.IO.Path.Combine(od, case["case_id"] + "_single_result.json"), "single")
    run_case(b, case, build, od, script_path)
    b.done()


# ---------------------------------------------------------------- v1.2 extensions (phase B)
FW_VERSION = "1.2"
for _n in ["RectangleProfile", "CircleProfile", "PolygonProfile", "Profile"]:
    _v = getattr(API, _n, None)
    if _v is not None and _n not in globals():
        globals()[_n] = _v
        RAW_API_INJECTED.append(_n)


def bodies_now(part=None):
    return list((part or GetRootPart()).Bodies)


def new_since(before, part=None):
    return [b for b in bodies_now(part) if not any(b == x for x in before)]


def curves_now(part=None):
    return list((part or GetRootPart()).Curves)


def vol(b):
    return _safe(lambda: round(shape_of(b).Volume * 1e9, 6))


def largest(bodies=None):
    bs = bodies if bodies is not None else bodies_now()
    return max(bs, key=lambda b: vol(b) or 0.0)


def is_sheet(b):
    return not _safe(lambda: bool(shape_of(b).IsClosed), True)


def delete_sheets(ctx=None):
    sh = [b for b in bodies_now() if is_sheet(b)]
    if sh:
        Delete.Execute(sel(sh))
    if ctx is not None:
        ctx.data["deleted_sheets"] = len(sh)
    return len(sh)


def name_bodies(names, bodies=None):
    bs = bodies if bodies is not None else bodies_now()
    for i, b in enumerate(bs):
        n = names[i] if i < len(names) else "%s_%d" % (names[-1], i + 1)
        set_name(b, n)
    return bs


def _ascii(s):
    try:
        unicode(s).encode("ascii")
        return True
    except Exception:
        return False


def ensure_english_names(ctx=None):
    """Rename any body/component/curve whose name is empty or non-ASCII (e.g. Chinese UI defaults)."""
    acc = {"bodies": [], "components": []}
    _walk(GetRootPart(), [], acc)
    ren = []
    groups = [("Body", [b for _, b in acc["bodies"]]), ("Component", [c for _, c in acc["components"]]),
              ("Curve", _safe(lambda: curves_now(), []))]
    for prefix, objs in groups:
        for i, o in enumerate(objs):
            n = _safe(lambda: unicode(o.Name), u"")
            if not n or not _ascii(n):
                new = "%s_%d" % (prefix, i + 1)
                if _safe(lambda: set_name(o, new)) is not None:
                    ren.append([n, new])
    if ctx is not None and ren:
        ctx.data["auto_renamed"] = ren
    return ren


def _wrap_build(build):
    def build_named(ctx):
        try:
            build(ctx)
        finally:
            _safe(lambda: ensure_english_names(ctx))
    return build_named


_load_case_v11 = load_case


def load_case(path):
    c, b = _load_case_v11(path)
    return c, _wrap_build(b)


_run_standalone_v11 = run_standalone


def run_standalone(case, build, script_path):
    return _run_standalone_v11(case, _wrap_build(build), script_path)


def setp(ctx, obj, pairs, tag="setp"):
    """Set properties one by one; record the members of obj and the failures (API discovery aid)."""
    ctx.data.setdefault(tag + "_members", [n for n in dir(obj) if not n.startswith("_")])
    bad = []
    for k, v in pairs:
        try:
            setattr(obj, k, v)
        except Exception as e:
            bad.append([k, unicode(e)])
    if bad:
        ctx.data[tag + "_failed"] = bad
    return obj


def first_ok(ctx, key, fns):
    """Try alternative call forms in order; record which one worked (index) and the errors."""
    errs = []
    for i, fn in enumerate(fns):
        try:
            r = fn()
            ctx.data[key + "_form"] = i
            if errs:
                ctx.data[key + "_errors"] = errs
            return r
        except Exception as e:
            errs.append(unicode(e)[:300])
    ctx.data[key + "_errors"] = errs
    raise Exception("%s: all %d forms failed: %s" % (key, len(fns), errs))


# ---------------------------------------------------------------- geometry builders (mm in)
def V(x, y, z):
    return Vector.Create(MM(x), MM(y), MM(z))


def _xdir(n):
    n = _unit(n)
    if abs(n[2]) > 0.999:
        return (1.0, 0.0, 0.0)
    return _perp(n)


def frame_at(c, n=(0, 0, 1), xdir=None):
    x = _unit(xdir) if xdir else _xdir(n)
    y = _cross(_unit(n), x)
    return Frame.Create(P(*c), D(*x), D(*y))


def plane_at(c=(0, 0, 0), n=(0, 0, 1), xdir=None):
    return Plane.Create(frame_at(c, n, xdir))


def plane_xy(z=0):
    return plane_at((0, 0, z), (0, 0, 1), (1, 0, 0))


def plane_xz(y=0):
    # x along X, y along Z (normal -Y)
    return Plane.Create(Frame.Create(P(0, y, 0), D(1, 0, 0), D(0, 0, 1)))


def seg(p0, p1):
    return CurveSegment.Create(P(*p0), P(*p1))


def circle_curve(c, r, n=(0, 0, 1)):
    return CurveSegment.Create(Circle.Create(frame_at(c, n), MM(r)))


def arc_curve(c, r, a0, a1, n=(0, 0, 1), xdir=None):
    return CurveSegment.Create(Circle.Create(frame_at(c, n, xdir), MM(r)), Interval.Create(math.radians(a0), math.radians(a1)))


def spline_curve(pts, closed=False):
    l = List[Point]()
    for p in pts:
        l.Add(P(*p))
    return CurveSegment.Create(NurbsCurve.CreateThroughPoints(closed, l, 1e-5))


def poly_curves(pts, closed=True):
    n = len(pts)
    return [seg(pts[i], pts[(i + 1) % n]) for i in range(n if closed else n - 1)]


def rect_curves(x0, y0, x1, y1, z=0):
    return poly_curves([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)])


def planar(curves, plane=None, name=None):
    l = List[ITrimmedCurve]()
    for c in curves:
        l.Add(c)
    r = PlanarBody.Create(plane or Plane.PlaneXY, l)
    b = r.CreatedBody
    if b is None:
        raise Exception("PlanarBody.Create returned no body")
    return set_name(b, name) if name else b


def sheet_rect(x0, y0, x1, y1, z=0, name=None):
    return planar(rect_curves(x0, y0, x1, y1, z), plane_xy(z), name)


def sheet_circle(c, r, name=None, n=(0, 0, 1)):
    return planar([circle_curve(c, r, n)], plane_at(c, n), name)


def face0(b):
    return list(b.Faces)[0]


def dcurve(segment, name=None):
    c = first_ok(Ctx({"data": {}, "items": {}, "notes": []}), "dcurve", [
        lambda: DesignCurve.Create(GetRootPart(), segment),
        lambda: DesignCurve.Create(master(GetRootPart()), segment)])
    if name:
        _safe(lambda: set_name(c, name))
    return c


def extrude(f, d, direction=None, etype=None, sym=False):
    o = ExtrudeFaceOptions()
    if etype is not None:
        o.ExtrudeType = etype
    if sym:
        o.PullSymmetric = True
    if direction is not None:
        return ExtrudeFaces.Execute(sel(f), D(*direction), MM(d), o)
    return ExtrudeFaces.Execute(sel(f), MM(d), o)


def revolve(f, axis_p, axis_d, deg, etype=None):
    o = RevolveFaceOptions()
    if etype is not None:
        o.ExtrudeType = etype
    return RevolveFaces.Execute(sel(f), Line.Create(P(*axis_p), D(*axis_d)), DEG(deg), o)


def axis_line(p=(0, 0, 0), d=(0, 0, 1)):
    return Line.Create(P(*p), D(*d))


def subtract(ctx, target, tool, keep_cutter=False):
    """SpaceClaim subtract = Combine.Intersect + remove the tool-side regions (keep the biggest target region)."""
    tool_vol = vol(tool)
    o = MakeSolidsOptions()
    if keep_cutter:
        o.KeepCutter = True
    Combine.Intersect(sel(target), sel(tool), o)
    bs = bodies_now()
    ctx.data["regions_after_intersect"] = [[_safe(lambda: unicode(b.Name)), vol(b)] for b in bs]
    keep = [largest(bs)]
    if keep_cutter:
        keep += [b for b in bs if tool_vol and vol(b) and abs(vol(b) - tool_vol) <= 1e-6 * tool_vol + 1e-6 and not any(b == k for k in keep)]
    rm = [b for b in bs if not any(b == k for k in keep)]
    if rm:
        ctx.attempt("RemoveRegions", lambda: Combine.RemoveRegions(sel(rm)))
    left = [b for b in bodies_now() if not any(b == k for k in keep)]
    if left:
        Delete.Execute(sel(left))
    return keep


def intersect_keep(ctx, target, tool):
    """Boolean intersection: split with Combine.Intersect and keep the region nearest the common bbox centre."""
    (a0, a1), (b0, b1) = bbox(target), bbox(tool)
    c = tuple((max(a0[i], b0[i]) + min(a1[i], b1[i])) / 2.0 for i in range(3))
    Combine.Intersect(sel(target), sel(tool), MakeSolidsOptions())
    bs = bodies_now()
    ctx.data["regions_after_intersect"] = [[bbox_center(b), vol(b)] for b in bs]
    keep = min(bs, key=lambda b: _dist(bbox_center(b), c))
    rm = [b for b in bs if not (b == keep)]
    if rm:
        ctx.attempt("RemoveRegions", lambda: Combine.RemoveRegions(sel(rm)))
    left = [b for b in bodies_now() if not (b == keep)]
    if left:
        Delete.Execute(sel(left))
    return keep


def sketch_mode(plane=None):
    return ViewHelper.SetSketchPlane(plane or Plane.PlaneXY)


def solid_mode():
    try:
        return ViewHelper.SetViewMode(InteractionMode.Solid)
    except Exception:
        return ViewHelper.SetViewMode(InteractionMode.Solid, None)


def finish_sketch(ctx, name=None):
    """Leave sketch mode (closed loops become surface bodies, open curves stay as design curves)."""
    before = bodies_now()
    solid_mode()
    nb = new_since(before)
    if name and nb:
        name_bodies([name], nb)
    for i, c in enumerate(curves_now()):
        _safe(lambda: set_name(c, "%s_Curve_%d" % (name or "Sketch", i + 1)))
    ctx.data["sketch_result"] = {"new_bodies": len(nb), "root_curves": len(curves_now()),
                                 "curve_types": [gtype(c) for c in curves_now()]}
    return nb


def P2L(pts):
    l = List[Point2D]()
    for p in pts:
        l.Add(P2(*p))
    return l


def cc(r):
    """CreatedCurves of a SketchCurveResult as a list."""
    return _safe(lambda: list(r.CreatedCurves), [])


CYL_ORDER = [None]


def cylinder(base, top, r, name=None):
    """Solid cylinder axis base->top, radius r (mm). CylinderBody.Create(center, start, end): tries the
    documented form (base centre, radius point on base, radius point on top) first; validates volume + position."""
    ax = tuple(top[i] - base[i] for i in range(3))
    h = math.sqrt(_dot(ax, ax))
    pp = _perp(ax)
    rb = tuple(base[i] + r * pp[i] for i in range(3))
    rt = tuple(top[i] + r * pp[i] for i in range(3))
    mid = tuple((base[i] + top[i]) / 2.0 for i in range(3))
    want = math.pi * r * r * h
    orders = [("center,rbase,rtop", (base, rb, rt)), ("base,top,rbase", (base, top, rb)),
              ("base,rbase,top", (base, rb, top)), ("base,top,rtop", (base, top, rt))]
    if CYL_ORDER[0]:
        orders.sort(key=lambda o: o[0] != CYL_ORDER[0])
    ap = DocumentHelper.GetActivePart()
    tried = []
    for key, pts in orders:
        n0 = ap.Bodies.Count
        try:
            b = _created(CylinderBody.Create(P(*pts[0]), P(*pts[1]), P(*pts[2]), ExtrudeType.ForceIndependent), ap, n0)
        except Exception as e:
            tried.append((key, unicode(e)))
            continue
        v = _safe(lambda: shape_of(b).Volume * 1e9)
        cen = _safe(lambda: bbox_center(b))
        if v is not None and abs(v - want) <= 1e-3 * want and cen is not None and _dist(cen, mid) <= 1e-3 * max(h, r) + 1e-4:
            CYL_ORDER[0] = key
            return set_name(b, name) if name else b
        tried.append((key, v, cen))
        _safe(lambda: Delete.Execute(Selection.Create(b)))
    raise Exception("cylinder: no CylinderBody.Create order matched (want vol %.3f centre %s): %s" % (want, mid, tried))


def edge_by_mid(body, pt, kind=None):
    return edge_nearest(body, pt, kind)


def edges_at_z(body, z, kind=None, tol=1e-3):
    return [e for e in edges(body, kind) if abs(edge_mid(e)[2] - z) <= tol]


# ---------------------------------------------------------------- v1.2.1: robust write_text
# (the PowerShell runner polls the result JSON with Get-Content; Delete/Move can hit a sharing violation)
def write_text(path, s):
    d = System.IO.Path.GetDirectoryName(path)
    if d and not System.IO.Directory.Exists(d):
        System.IO.Directory.CreateDirectory(d)
    tmp = path + ".tmp"
    last = None
    for _i in range(40):
        try:
            System.IO.File.WriteAllText(tmp, s, _U8)
            if System.IO.File.Exists(path):
                System.IO.File.Delete(path)
            System.IO.File.Move(tmp, path)
            return
        except Exception as e:
            last = e
            System.Threading.Thread.Sleep(250)
    raise last


FW_VERSION = "1.2.1"


# ---------------------------------------------------------------- v1.2.2: intersect_keep by point containment
def _inside(body, pt):
    s = shape_of(body)
    return bool(s.ContainsPoint(P(*pt)))


def _sample_inside(body, n=6):
    (a, b) = bbox(body)
    for i in range(n):
        for j in range(n):
            for k in range(n):
                pt = tuple(a[q] + (b[q] - a[q]) * ((i, j, k)[q] + 0.5) / n for q in range(3))
                if _inside(body, pt):
                    return pt
    return None


def intersect_keep(ctx, target, tool):
    """Boolean intersection: Combine.Intersect splits the target; keep the target region(s) lying inside the tool
    (tested with Body.ContainsPoint on a sample point of each region), delete the tool and the other regions."""
    tool_vol = vol(tool)
    (a0, a1), (b0, b1) = bbox(target), bbox(tool)
    c = tuple((max(a0[i], b0[i]) + min(a1[i], b1[i])) / 2.0 for i in range(3))
    Combine.Intersect(sel(target), sel(tool), MakeSolidsOptions())
    bs = bodies_now()
    info, keep, tools = [], [], []
    for b in bs:
        v = vol(b)
        is_tool = bool(tool_vol and v and abs(v - tool_vol) <= 1e-6 * tool_vol + 1e-6)
        pt = _safe(lambda: _sample_inside(b))
        ins = None
        if pt is not None and not is_tool:
            ins = _safe(lambda: _inside(tool, pt))
        info.append([bbox_center(b), v, is_tool, pt, ins])
        if is_tool:
            tools.append(b)
        elif ins:
            keep.append(b)
    ctx.data["regions_after_intersect"] = info
    if not keep:
        cand = [b for b in bs if not any(b == t for t in tools)] or bs
        keep = [min(cand, key=lambda b: _dist(bbox_center(b), c))]
        ctx.data["intersect_fallback"] = "nearest-centre"
    rm = [b for b in bs if not any(b == k for k in keep)]
    if rm:
        ctx.attempt("RemoveRegions", lambda: Combine.RemoveRegions(sel(rm)))
    left = [b for b in bodies_now() if not any(b == k for k in keep)]
    if left:
        Delete.Execute(sel(left))
    return keep[0]


FW_VERSION = "1.2.2"


# ---------------------------------------------------------------- v1.2.3: find_type (API classes not in the RunScript namespace)
def find_type(ctx, name, prefer=("V18", "V19")):
    import clr
    found = []
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        try:
            ts = asm.GetExportedTypes()
        except Exception:
            continue
        for t in ts:
            if t.Name == name and (t.Namespace or "").startswith("SpaceClaim.Api"):
                found.append(t)
    if not found:
        raise Exception("type %s not found in loaded assemblies" % name)
    found.sort(key=lambda t: ([i for i, p in enumerate(prefer) if p in t.Namespace] + [99])[0])
    if ctx is not None:
        ctx.data["type_" + name] = [t.FullName for t in found]
    return clr.GetPythonType(found[0])


FW_VERSION = "1.2.3"




# ---------------------------------------------------------------- v1.3: intent checks, not-feasible status, misc helpers
class NotFeasible(Exception):
    pass


_INTENT = {"fail": {}, "log": []}


def intent(name, actual, expected, tol=None, rel=1e-4):
    """Cheap intent check (volume / face count / bbox ...). Failures turn an 'ok' case into 'mismatch'."""
    if tol is None and isinstance(expected, float):
        tol = max(1e-3, rel * abs(expected))
    try:
        if tol is not None:
            ok = actual is not None and abs(actual - expected) <= tol
        else:
            ok = actual == expected
    except Exception:
        ok = False
    _INTENT["log"].append([name, _safe(lambda: unicode(actual)), _safe(lambda: unicode(expected)), bool(ok)])
    if not ok:
        _INTENT["fail"]["intent:" + name] = {"expected": expected, "actual": actual}
    return ok


def intent_range(name, actual, lo, hi):
    ok = actual is not None and lo <= actual <= hi
    _INTENT["log"].append([name, _safe(lambda: unicode(actual)), "[%s, %s]" % (lo, hi), bool(ok)])
    if not ok:
        _INTENT["fail"]["intent:" + name] = {"expected": [lo, hi], "actual": actual}
    return ok


_cmp_expect_v12 = _cmp_expect


def _cmp_expect(expect, actual):
    bad = _cmp_expect_v12(expect, actual)
    bad.update(_INTENT["fail"])
    return bad


def _wrap_build(build):
    def build_named(ctx):
        _INTENT["fail"] = {}
        _INTENT["log"] = []
        ctx.data["intent_checks"] = _INTENT["log"]
        try:
            build(ctx)
        finally:
            _safe(lambda: ensure_english_names(ctx))
    return build_named


_run_case_v12 = run_case


def run_case(batch, case, build, out_dir, script_path=None):
    _INTENT["fail"] = {}
    rec = _run_case_v12(batch, case, build, out_dir, script_path)
    err = rec.get("error") or ""
    if "NotFeasible" in err:
        rec["status"] = "not_feasible"
        rec["not_feasible_reason"] = [l for l in err.strip().splitlines() if l.strip()][-1][:400]
        _safe(lambda: write_text(System.IO.Path.Combine(out_dir, rec["case_id"] + ".json"), js(rec)))
        batch.flush()
    return rec


def comp_bodies(c):
    return list(_safe(lambda: c.Content.Bodies, None) or _safe(lambda: master(c).Template.Bodies, []))


def total_volume():
    st = doc_stats()
    return st["volume_mm3"]


def face_count(b):
    return shape_of(b).Faces.Count


def spoint(curve, u):
    """SelectionPoint on a design curve at raw curve parameter u (recorded-journal form)."""
    sp = globals().get("SelectionPoint") or find_type(None, "SelectionPoint")
    return sp.Create(curve, u)


def root_curve_near(pt, tol=1e-3):
    best = None
    for c in curves_now():
        d = _safe(lambda: _dist(edge_mid(c), pt), 1e9)
        if best is None or d < best[0]:
            best = (d, c)
    return best[1] if best else None


FW_VERSION = "1.3"


def _keep_unicode(ctx):
    return bool(ctx.data.get("keep_unicode_names"))


def _wrap_build(build):
    def build_named(ctx):
        _INTENT["fail"] = {}
        _INTENT["log"] = []
        ctx.data["intent_checks"] = _INTENT["log"]
        try:
            build(ctx)
        finally:
            if not _keep_unicode(ctx):
                _safe(lambda: ensure_english_names(ctx))
    return build_named


def _sigstr(c):
    return "(" + ", ".join("%s %s" % (p.ParameterType.Name, p.Name) for p in c.GetParameters()) + ")"


def auto_new(ctx, key, cls, pool):
    """Construct cls with the first constructor whose parameter types can be filled from pool
    (list of (TypeName, value)); records the constructor list and errors (API discovery aid)."""
    import clr
    t = cls if isinstance(cls, System.Type) else clr.GetClrType(cls)
    ctors = list(t.GetConstructors())
    ctx.data[key + "_ctors"] = [_sigstr(c) for c in ctors]
    errs = []
    for c in sorted(ctors, key=lambda c: -len(c.GetParameters())):
        args, ok = [], True
        for p in c.GetParameters():
            tn = p.ParameterType.Name
            hit = [v for k, v in pool if k == tn]
            if hit:
                args.append(hit[0])
            elif p.IsOptional:
                args.append(System.Type.Missing)
            else:
                ok = False
                break
        if not ok:
            continue
        try:
            o = c.Invoke(System.Array[object](args))
            ctx.data[key + "_ctor_used"] = _sigstr(c)
            return o
        except Exception as e:
            errs.append(_sigstr(c) + ": " + unicode(e)[:200])
    ctx.data[key + "_errors"] = errs
    raise Exception("auto_new %s: no usable constructor: %s" % (t.Name, errs))


def rawt(name):
    """Raw API type by name (V18 runtime namespace first)."""
    v = getattr(API, name, None)
    return v if v is not None else find_type(None, name)


def ctor_sigs(ctx, name):
    """Record the constructor signatures of an API type (by name) into ctx.data['ctors_<name>']."""
    import clr
    t = clr.GetClrType(rawt(name))
    s = [_sigstr(c) for c in t.GetConstructors()]
    if ctx is not None:
        ctx.data["ctors_" + name] = s
    return s

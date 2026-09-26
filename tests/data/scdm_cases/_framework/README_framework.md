# scdm_cases batch framework (phase A/B)

Files (all inside `D:\training\caedecoder\scdm_cases\_framework\`):

| file | runs in | purpose |
|---|---|---|
| `scdm_fw.py` | SpaceClaim IronPython (`execfile`) | helpers + case/batch runner |
| `run_batch.ps1` | PowerShell 5 | launch SpaceClaim headless over a case list; busy-wait, timeout/stall/exit-grace kill, optional GUI retry of failures |
| `fw_post.py` | CPython 3 (anaconda) | validate `.scdoc` zips, sha256, merge the manifest, write the failed list |

## Case script contract
A case is one `.py` named `<category>_<feature>_<NNN>_<keyparams>.py` in its category folder:

```python
CASE = {"case_id": "...", "category": "04_edge", "feature": "edge_round", "title": "...",
        "params": {...}, "expect": {"bodies": 1, "faces": 7, "volume_mm3": 23922.74}, "commands": [...],
        "out_dir": r"...optional..."}
def build(ctx):          # a new document is already open; the framework saves/closes it
    b = block((0,0,0), (40,30,20), "Block_A")          # bodies always named in English
    e = edge_nearest(b, (20,30,20), "Line")            # select by geometry, never by index
    ConstantRound.Execute(sel(e), MM(3), ConstantRoundOptions())
```
Standalone footer: `if "SCDM_BATCH" not in globals(): execfile(FW); run_standalone(CASE, build, <path>)`.

`run_case` per case: CreateNewDocument -> build(ctx) in try/except -> doc_stats() -> DocumentSave.Execute(<out>\<case_id>.scdoc) -> `<case_id>.json` metadata (params, expect, actual counts: bodies/faces/edges/vertices/volume/area/surface & curve types/components/part_defs/layers/named selections/materials/units, items, errors, timings) -> CloseDocument. Status: `ok` | `mismatch` (saved, but expect != actual) | `failed`.
`ctx.attempt(key, fn)` records sub-items (ok/traceback) without aborting the case; `ctx.data[...]` holds free-form diagnostics.

Helpers: `P, P2, D, mm, sel, block, cylinder, sphere, component, set_name, body_named, faces, edges, top_face, bottom_face, face_extreme, face_nearest, edge_nearest, edges_parallel, common_edges, edge_mid, bbox, bbox_center, gtype, master, raw, enum_pick, doc_stats, all_bodies`.

## Running a batch
```
powershell -ExecutionPolicy Bypass -File D:\training\caedecoder\scdm_cases\_framework\run_batch.ps1 `
  -BatchName B01_primitives -CaseList D:\training\caedecoder\scdm_cases\_batches\B01_primitives.txt `
  -ResultDir D:\training\caedecoder\scdm_cases\_batches [-Manifest ...\manifest.json] [-GuiRetryFailed]
```
The runner refuses to start while any SpaceClaim.exe is running (waits up to `-BusyWaitMin` 15), writes `<batch>_<mode>_driver.py`, `<batch>_<mode>_result.json` (live, rewritten after every case), `<batch>_<mode>_run.json`, then runs `fw_post.py` to update the manifest.

## v1.1 notes (pilot findings, 2026-09-26)
- RunScript objects are SpaceClaim.Api.V18.*; scdm_fw.py injects raw API types (DocumentMaterial, DrawingSheet,
  DrawingView, Note, DatumPlane, *Condition, UnitsSystemType, MetricLengthUnit, LocationPoint, ...) from that namespace (module alias API).
- Occurrence bodies (inside components): Shape is a TrimmedSpace; use shape_of()/bbox() helpers (master shape + transform).
- cylinder() validates volume and auto-detects the CylinderBody.Create 3-point order (old order produced a bad body).
- Shell.RemoveFaces: +t grows outward, -t is inward.
- Note.Create needs a master annotation parent (datum plane OK; pass master(face) for faces).
- Units: ActiveUnitsSystem Metric/Imperial settable; MetricUnits.Length is read-only -> assign a new MetricUnits(len, mass, angle).
- run_batch.ps1: SpaceClaim must be absent for 2 checks QuietSec (60 s) apart; licence failures (exit 19 / "License check Failed",
  e.g. racing the repo pytest SpaceClaim) are retried up to LicenseRetries (2) times.

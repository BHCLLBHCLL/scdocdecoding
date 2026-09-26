# scdm_cases - corpus summary

Updated 2026-09-26 09:16 UTC+8. SpaceClaim 2019 R3 (2019.3.38912), headless RunScript, V19 API. Source of truth: `manifest.json` (field `counts` has the same numbers).

## Counts per category

| category | ok | mismatch | failed | not_feasible | total |
|---|---|---|---|---|---|
| 00_smoke | 1 | 0 | 0 | 0 | 1 |
| 01_primitives | 17 | 0 | 0 | 0 | 17 |
| 02_sketch | 27 | 0 | 0 | 1 | 28 |
| 03_pull | 24 | 0 | 0 | 0 | 24 |
| 04_edge | 9 | 0 | 0 | 0 | 9 |
| 05_boolean | 12 | 0 | 0 | 0 | 12 |
| 06_move_pattern | 15 | 0 | 0 | 0 | 15 |
| 07_shell_offset | 11 | 0 | 0 | 0 | 11 |
| 08_sheetmetal | 3 | 0 | 0 | 0 | 3 |
| 09_beam | 6 | 0 | 0 | 0 | 6 |
| 10_assembly | 12 | 0 | 0 | 0 | 12 |
| 11_doc_attrs | 24 | 0 | 0 | 0 | 24 |
| 12_repair_prepare | 10 | 0 | 1 | 0 | 11 |
| 13_surface_curve | 10 | 0 | 0 | 0 | 10 |
| 14_holes_threads | 4 | 0 | 0 | 0 | 4 |
| 15_mesh_facet | 3 | 0 | 0 | 0 | 3 |
| 20_combo | 31 | 0 | 1 | 0 | 32 |
| **total** | **219** | **0** | **2** | **1** | **222** |

Total scdoc volume: 328 MB (of which ~312 MB is the single case `15_mesh_reduce_001_50pct`).

## Remaining non-ok cases

| case | status | reason | suggested next step |
|---|---|---|---|
| `02_sketch_round2d_001_rect_corner_r4` | not_feasible | `Sketch2DRound.Create(SelectionPoint, SelectionPoint, r)` throws NullReference headless in every tried form (curve+param, param array, reversed order, CreateCurve); needs the interactive sketch context | record in the GUI if needed |
| `12_prepare_volumeextract_001_pipe` | failed (4 attempts) | pipe is correct (5654.7 mm3), but `VolumeExtract.Create` with cap faces or cap sheet bodies reports "not all ends closed" (or NullReference with the pipe body as secondary) | try edge-loop selection or GUI recording |
| `20_combo_wrap_026_cylinder_wrap_text_pull` | failed (4 attempts) | `Wrap.Create(target body, sheet face)` works but V19 Wrap creates a separate wrapped sheet (`Wrap_RectWrapped`) + curves, no imprint on the cylinder, so there is no patch to pull | find the WrapOptions imprint switch, or imprint the wrapped sheet (Project/Imprint) before the pull |

`13_wrap_001_rect_onto_cylinder` is ok since R3 (manifest `status_override`): the wrap works, it produces the wrapped sheet `Wrap_RectWrapped` instead of an imprint; its case JSON still records the original imprint-intent mismatch.

The 3 formerly failing retry cases `03_pull_profile_001/002` (ExtrudeProfile with `RectangleProfile/CircleProfile(Plane, ..., PointUV.Create(0,0), 0.0)`) and `07_replaceface_001` now pass.

## Caveats (read before using the corpus as ground truth)

- **Assembly conditions are stored, not solved headless**: `10_assembly_align_001`, `10_assembly_tangent_001`, `10_assembly_rigid_001`, `10_assembly_anchor_001` and `20_combo_asm_017` contain the condition objects (counted by `mating_conditions`) but the components are not moved to satisfy them.
- **Component names read back empty** through the API (`IComponent.Name == ""`); the display name lives on the component template (`Component.Template.Name`). `20_combo_asm_014` verifies a name via Template.Name. Stats/case JSON show auto names `Component_N` in `data.auto_renamed`.
- **Coordinate systems**: the stats count the document default coordinate system too (a case with one user coordinate system reports `coordinate_systems: 2`).
- **Reinterpreted cases**: `07_replaceface_001` (V19 ReplaceFacesWithFace only merges faces: top split in two, then merged), `13_convertsolid_001_closed_sheets` (ConvertToSolid only accepts meshes: block -> facet mesh -> solid), `08_sheetmetal_flange_001` (L-solid + ConvertToSheetMetal + CreateMissingBends; there is no scripted flange command), `20_combo_edit_030` (boss faces patterned; patterning a whole body creates pattern *components*), `20_combo_mesh_032` (second cylinder modelled directly; headless Copy/Paste produced no body), `20_combo_helix_023` (end pieces picked by volume: helical-sweep bounding boxes are loose).
- **Huge file**: `15_mesh_reduce_001_50pct.scdoc` is ~312 MB (FacetReduce with TriangleReduction 0.5 ran ~430 s); facet counts are not readable via DesignMesh.Shape, so the reduction is unverified. Exclude it from default parser tests.
- **STL import** puts the mesh into a new component (`15_mesh_stl_import_001`: root has 0 meshes, 1 component with the mesh).
- **Inputs generated inside the corpus**: STEP/STL inputs were exported by the cases themselves into `10_assembly\_inputs` and `15_mesh_facet\_inputs`.
- **Bodies are renamed to English** by the framework (auto names like the Chinese UI default would be locale dependent); only `11_doc_rename_002_unicode_name` keeps its non-ASCII name on purpose.
- `_probe\` (API signature dump) and `_pilot\` are not corpus cases and are not in the manifest.
- **Supersession**: `_gen\specs\R1_fixes.py` supersedes 8 case definitions of the B02/B03/B06/B07 specs and `_gen\specs\R2_fixes.py` supersedes 14 of B11-B14; regenerating the older specs would overwrite those case files with the superseded versions.
- Per-case `status: ok` means the build ran, the document was saved and re-validated (zip + Document.xml), inventory expectations matched and the cheap intent checks (volume / face count / named checks, see `data.intent_checks` in each case JSON) passed.

## Launch log (phase B)

| launch | cases | result | SpaceClaim wall time |
|---|---|---|---|
| B01-B07 + r1 (first half) | 116 | 112 ok, 4 failed | see _batches |
| L1_B08_B10 | 45 | 34 ok, 4 mismatch, 7 failed | 3 min |
| L2_B11_B12 | 28 | 19 ok, 5 mismatch, 4 failed | 9.3 min |
| L3_B13_B14 | 32 | 27 ok, 4 mismatch, 1 failed | 3.7 min |
| R2_combined (all reruns) | 33 | 29 ok, 1 not_feasible, 3 failed | 10.1 min |
| R3_fixes | 3 | 1 wrap ok (override), 2 failed | 2.6 min |

Superseded per-batch `*_failed.txt` files are in `_batches\_archive\`; `_batches\R3_fixes_failed.txt` is the last one.

`15_mesh_reduce_001_50pct.scdoc` (~312 MB) is excluded from the exported/repo corpus (`excluded_from_repo: true` in the manifest); its .py and .json are included.

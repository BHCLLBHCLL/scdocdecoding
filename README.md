# scdocdecoding

Reverse-engineered **SpaceClaim-style** direct modeler, built as a **viewer + geometry modeler**.
Target product: ANSYS SpaceClaim 2019 R3 (Chinese UI). No SpaceClaim binary is shipped or re-used:
the geometry kernel is Open CASCADE (OCCT) via pythonocc-core, and SpaceClaim's .NET API was
only reverse-engineered to capture the *behavioral* specification (see `scdm_api_types.md`).

## What it does

- Opens `.scdoc` (via `scdoc_parser`: OPC + document.xml + SAB + facets) and STEP/BRP/STL.
- SpaceClaim-style Ribbon + left three-stack (structure tree / options / properties) + 3D viewport.
- Direct modeling with a unified tool state machine (Select / Pull / Move / Fill / Combine / Split...),
  backed by the OCCT kernel (`scdm/kernel.py`).
- Undo/redo by shape snapshot; saves to a native project package (`.scdm` zip of BREPs) or STEP/STL.

## Runtime environment

The modeling kernel is **pythonocc-core** (Open CASCADE via OCCT). Pinned dependencies live in
`environment.yml` (conda) with `requirements.txt` as the pip-flavoured note — the proven combo
is Python 3.11 + pythonocc-core 7.9.3 + OCCT 7.9.3 + numpy 2.4.6 + vtk 9.6.1 + PyQt5 5.15.11 +
pytest (2026-09-06 full-suite run: 212 passed / 1 skipped).

Two commands reproduce the **non-official gate** (P0-3; CI runs the same two):

```bat
conda env create -f environment.yml
conda run -n scdm python -m pytest tests/ -m "not official" -q
```

The **official gate** (SabSatConverter / SpaceClaim RunScript sentinels) has its own entry:

```bat
python -m pytest tests/ -m official_gate -q   :: written SAB accepted by official converter
python -m pytest tests/ -m official_open -q   :: written .scdoc opens in official SpaceClaim
```

Capability tiers (tests/conftest.py): `kernel` (OCC) / `gui` (PyQt5) / `official_gate`
(SabSatConverter) / `official_open` (SpaceClaim.exe) — absent tiers degrade to skips,
never collection errors.

To (re)create a pythonocc-core environment on any machine (conda; needs network to
conda-forge + PyPI):

```bat
setup_env.bat            :: creates the 'scdm' env (pythonocc-core + numpy + vtk + PyQt5 + pytest)
conda activate scdm
```

Without OCCT the GUI still opens in read-only mode (M1 commands only; M2-M5 commands report
"未实现" until `kernel.available()` is true).

## Layout

| module | role |
| --- | --- |
| `scdoc_parser/*` | read-only importer: OPC / document.xml / SAB / facets |
| `scdm/kernel.py` | OCCT wrapper: booleans, pull, fill, fillet, shell, STEP/BRP I/O, tessellate |
| `scdm/import_sab.py` | SAB topology -> TopoDS |
| `scdm/document.py` | session document, layers, units, dirty flag |
| `scdm/kdoc.py` | kernel doc: bodies + sketches |
| `scdm/history.py` | undo/redo snapshots |
| `scdm/selection.py` | selection filters / highlight |
| `scdm/tools/*` | tool state machine (Select/Pull/Move/Fill/Combine/Split...) |
| `scdm_gui.py` + `scdm/gui/*` | Ribbon, tree, viewport, status |

## Milestones (DEV_PLAN.md)

M1 session shell * M2 direct modeling * M3 sketch * M4 extensions * M5 scdoc write-back
See `DEV_PLAN.md` for the full work-package table and per-milestone acceptance criteria.

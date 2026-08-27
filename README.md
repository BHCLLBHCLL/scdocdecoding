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

The modeling kernel is **pythonocc-core** (Open CASCADE via OCCT). Install it (conda,
Windows) — either into the base env (so plain `python` works) or into a dedicated env:

```bat
:: option A: into the base environment (this machine: already done)
conda install -c conda-forge pythonocc-core -y
:: option B: dedicated env via setup_env.bat
setup_env.bat
:: then: conda activate scdm

:: GUI deps (pip, if not present):
pip install PyQt5 scipy trimesh pytest
```

Run the GUI and tests from the project root:

```bat
cd D:\training\caedecoder\scdocdecoding
set PYTHONPATH=%CD%
python scdm_gui.py box.scdoc
python -X utf8 tests/test_kernel.py
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

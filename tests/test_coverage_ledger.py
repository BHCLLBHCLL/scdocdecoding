"""P1 guard: command coverage ledger.

The 2026-09-12 audit found that only 26/130 catalog commands were even
*mentioned* by the suite. Action: tests/test_command_behavior.py now asserts
real behaviour for the kernel/runtime commands, and this ledger makes the
remaining untested commands **explicit** instead of silent.

Rule: every command id in scdm.catalog.all_commands() must be either
  1. referenced by some test file (crude proxy, same as the audit), or
  2. listed in EXEMPT with a one-line reason.
Adding a command therefore fails this test until it is covered or declared.
This file is excluded from its own mention scan.
"""
from __future__ import annotations

from pathlib import Path

from scdm.catalog import all_commands

ROOT = Path(__file__).resolve().parent.parent

# command id -> why no behaviour test can/does stand in for it.
# GUI = needs a live Qt viewport/interactor; HOST = needs an external product;
# PLACEHOLDER = not implemented by design; SHARED = covered by a sibling
# command's test (same routine).
EXEMPT = {
    # backstage file operations: real user paths (dialogs, host export)
    "file.open": "GUI file dialog",
    "file.recent": "GUI recent list (QSettings)",
    "file.close": "GUI document lifetime",
    "file.save": "GUI save dialog (write path covered by scdoc/interop tests)",
    "file.save_as": "GUI save dialog",
    "file.recover": "GUI autosave/recover wiring",
    "file.print": "GUI print/print-preview",
    "file.image": "GUI PNG export",
    "file.export": "GUI export dialog (each writer covered by interop tests)",
    "file.options": "GUI options dialog",
    "file.exit": "GUI application exit",
    # clip / undo / camera
    "edit.undo": "GUI history (scdm.history covered by e2e chain)",
    "edit.redo": "GUI history",
    "edit.paste": "GUI clipboard",
    "edit.cut": "GUI clipboard",
    "edit.copy": "GUI clipboard",
    "view.spin": "GUI camera",
    "view.pan": "GUI camera",
    "view.zoom": "GUI camera",
    "view.prev": "GUI camera stack",
    "view.home": "GUI camera preset",
    "view.iso": "GUI camera preset",
    "view.pos_x": "GUI camera preset",
    "view.pos_y": "GUI camera preset",
    "view.pos_z": "GUI camera preset",
    # sketch primitives whose geometry lives in the GUI drawing code
    "sketch.rect3": "GUI three-click rect (no library routine)",
    "sketch.ellipse": "GUI ellipse drawing (no library routine)",
    "sketch.layout": "GUI sketch layout aid",
    "sketch.grid": "GUI grid toggle",
    # datum display
    "insert.origin": "GUI origin datum display (tested via Session flags in GUI tests)",
    "insert.axis": "GUI axis datum display",
    # visibility / style toggles
    "show.edges": "GUI scene visibility toggle",
    "show.vertices": "GUI scene visibility toggle",
    "show.planes": "GUI scene visibility toggle",
    "show.axes": "GUI scene visibility toggle",
    "style.shaded_edges": "GUI render style",
    "style.shaded": "GUI render style",
    "style.wire": "GUI render style",
    "style.transp": "GUI render style",
    "gfx.silhouette": "GUI feature-edge extraction (VTK)",
    # assembly interactions
    "asm.insert": "GUI insert-component dialog",
    "asm.create": "GUI component creation (kdoc.add_component covered)",
    "asm.move": "GUI drag handles",
    "asm.anchor": "GUI anchor toggle (flag covered in behaviour tests)",
    "asm.explode": "GUI explosion offset",
    "asm.light": "GUI lightweight-display toggle",
    # placeholders / host-bound
    "prep.small": "placeholder (not live; repair.small covers the feature)",
    "wb.publish": "GUI file dialog + JSON payload (schema mirrored by params tests)",
    "ks.render": "HOST: KeyShot integration",
    # detailing dialogs
    "det.note": "GUI note dialog",
    "det.params": "GUI parameter editor dialog (ParamTable covered)",
    "det.bom": "GUI BOM dialog",
    # tools dialogs
    "tools.script": "GUI script editor (scdm.scripting covered)",
    "tools.record": "GUI recorder toggle (Recorder covered)",
    "tools.customize": "GUI ribbon customization (QSettings)",
}


def _mentioned() -> set:
    text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted((ROOT / "tests").glob("test_*.py"))
        if p.name != Path(__file__).name)
    return {c.id for c in all_commands() if c.id in text}


def test_every_command_is_covered_or_declared():
    ids = {c.id for c in all_commands()}
    missing = sorted(ids - _mentioned() - set(EXEMPT))
    assert not missing, (
        "commands neither covered by a test nor declared in EXEMPT: "
        + ", ".join(missing))


def test_exempt_list_has_no_stale_entries():
    ids = {c.id for c in all_commands()}
    stale = sorted(set(EXEMPT) - ids)
    assert not stale, "EXEMPT names unknown command ids: " + ", ".join(stale)


def test_exempt_entries_carry_a_reason():
    thin = sorted(k for k, v in EXEMPT.items() if len(v.strip()) < 8)
    assert not thin, "EXEMPT entries need a real reason: " + ", ".join(thin)

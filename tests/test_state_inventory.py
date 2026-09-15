"""R101: the state inventory tool cannot drift from the catalog it describes.

The review numbers in docs/CODE_STATE_R101_ANALYSIS.md come from
tools/state_inventory.py; this file pins that tool to the live catalog and to
the GUI dispatch it measures, in the same spirit as tests/test_snapshot_tool.py.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from scdm.catalog import TABS, all_commands

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "state_inventory.py"

spec = importlib.util.spec_from_file_location("state_inventory", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# ids the GUI handles in dedicated branches instead of a _do_* handler
BRANCH_HANDLED = {"measure.dist", "mode.sketch", "mode.section", "mode.3d"}
INTENTIONAL = {"safety.tab"}


def test_command_face_matches_the_catalog():
    face = mod.command_face()
    ribbon = [t for t in TABS if t.kind == "ribbon"]
    entries = [c for t in ribbon for g in t.groups for c in g.commands]
    distinct = {c.id for c in entries}
    assert face["ribbon_tabs"] == len(ribbon)
    assert face["backstage_tabs"] == len([t for t in TABS if t.kind == "backstage"])
    # R105: a command may appear on two tabs (Design + Edit Sketch)
    assert face["ribbon_commands"] == len(distinct)
    assert face["ribbon_entries"] == len(entries) >= face["ribbon_commands"]
    assert face["all_commands"] == len(all_commands())
    # per_tab counts the buttons on each tab, so it sums to the entry count
    assert sum(face["per_tab"].values()) == face["ribbon_entries"]


def test_live_cells_are_two_different_measurements():
    face = mod.command_face()
    assert 0 < face["live_kernel_unavailable"] < face["live_kernel_available"]
    assert face["live_kernel_unavailable"] == len(set(__import__("scdm.catalog",
        fromlist=["M1_LIVE"]).M1_LIVE))
    assert face["placeholders"] == ["safety.tab"]


def test_handler_accounting_has_no_orphans():
    gui = mod.gui_face()
    assert gui["orphan_handlers"] == []
    homeless = set(gui["catalog_ids_without_handler"])
    allowed = BRANCH_HANDLED | INTENTIONAL
    unexpected = sorted(h for h in homeless
                        if not h.startswith(("tool.", "show.", "style."))
                        and h not in allowed)
    assert not unexpected, "catalog id with neither handler nor branch: " + repr(unexpected)


def test_rows_are_markdown_and_deterministic():
    data = mod.inventory()
    first = mod.rows(data)
    assert first == mod.rows(mod.inventory())
    assert all(r.startswith("|") for r in first)
    body = "\n".join(first)
    for key in ("ribbon 页签", "内核不可用", "内核可用", "占位"):
        assert key in body


def test_cli_json_matches_the_library_call():
    out = subprocess.run([sys.executable, str(TOOL), "--json"], cwd=str(ROOT),
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    here = mod.inventory()
    assert payload["commands"] == here["commands"]
    assert payload["tests"]["def_test"] == here["tests"]["def_test"]


def test_tool_does_not_pull_in_the_geometry_kernel():
    src = TOOL.read_text(encoding="utf-8")
    assert "from OCC" not in src and "import OCC" not in src
    assert "scdm.kernel" not in src

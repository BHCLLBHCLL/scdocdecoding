"""P12: the DEV_PLAN snapshot block cannot silently drift again."""
from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

from scdm.catalog import TABS, live_commands

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "gen_devplan_snapshot", ROOT / "tools" / "gen_devplan_snapshot.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _tmp_doc(text):
    fd, path = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    p = Path(path)
    p.write_text(text, encoding="utf-8")
    return p


def test_snapshot_update_is_idempotent():
    doc = _tmp_doc("# plan\n\n" + mod.BEGIN + "\nstale rows\n" + mod.END
                   + "\n\ntail\n")
    try:
        assert mod.update_file(doc) is True          # stale -> rewritten
        assert mod.is_current(doc) is True
        assert mod.update_file(doc) is False         # idempotent
        body = doc.read_text(encoding="utf-8")
        assert "| UI 命令面 |" in body and "| 测试 |" in body
        assert body.endswith(mod.END + "\n\ntail\n")
    finally:
        os.unlink(doc)


def test_snapshot_check_detects_edits():
    doc = _tmp_doc(mod.snapshot_block() + "\n")
    try:
        assert mod.is_current(doc) is True
        edited = doc.read_text(encoding="utf-8").replace("| 测试 |",
                                                         "| 测试(旧) |")
        doc.write_text(edited, encoding="utf-8")
        assert mod.is_current(doc) is False
    finally:
        os.unlink(doc)


def test_repo_snapshot_command_face_matches_live_catalog():
    """The dangerous drift (pages / commands / live / placeholders) is caught here.

    Full byte-level currency (which also tracks the test count) is the
    tools/gen_devplan_snapshot.py --check gate.
    """
    text = (ROOT / "DEV_PLAN.md").read_text(encoding="utf-8")
    assert mod.BEGIN in text and mod.END in text
    rows = "\n".join(mod.snapshot_rows())
    ribbon = [t for t in TABS if t.kind == "ribbon"]
    cmds = [c for t in ribbon for g in t.groups for c in g.commands]
    assert "{} ribbon 页签".format(len(ribbon)) in rows
    assert "{} 命令".format(len(cmds)) in rows
    assert "{} live".format(len(live_commands())) in rows


def test_repo_snapshot_block_is_wellformed():
    text = (ROOT / "DEV_PLAN.md").read_text(encoding="utf-8")
    block = text.split(mod.BEGIN, 1)[1].split(mod.END, 1)[0]
    assert block.count("|") >= 8
    assert "test_coverage_ledger.py" in block

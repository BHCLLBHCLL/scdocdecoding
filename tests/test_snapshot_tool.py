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
    cmds = mod.ribbon_commands()          # R105: distinct ids, one source
    assert "{} ribbon 页签".format(len(ribbon)) in rows
    assert "{} 命令".format(len(cmds)) in rows
    assert "{} live".format(len(live_commands())) in rows


def test_repo_snapshot_block_is_wellformed():
    text = (ROOT / "DEV_PLAN.md").read_text(encoding="utf-8")
    block = text.split(mod.BEGIN, 1)[1].split(mod.END, 1)[0]
    assert block.count("|") >= 8
    assert "test_coverage_ledger.py" in block

def test_live_unavailable_cell_is_interpreter_independent(monkeypatch):
    """R101 D1: the 内核不可用 cell answers about the kernel, not the runner.

    Before the fix the cell was len(live_commands()) - so it read 177 whenever
    the tool ran under the OCC env and `--check` then failed under any
    interpreter without OCC. The unavailable live set is M1_LIVE by
    construction, which this test measures both ways.
    """
    import scdm.kernel as kernel
    from scdm.catalog import M1_LIVE
    monkeypatch.setattr(kernel, "available", lambda: False)
    assert live_commands() == set(M1_LIVE)
    before = mod.live_counts()[0]
    monkeypatch.setattr(kernel, "available", lambda: True)
    assert mod.live_counts()[0] == before == len(set(M1_LIVE))


def test_live_cells_disagree_and_both_are_recorded():
    """The two cells must be two measurements, not one repeated twice."""
    unavailable, available = mod.live_counts()
    assert 0 < unavailable < available
    assert available == len(live_commands())   # kernel-available 口径
    rows = "\n".join(mod.snapshot_rows())
    assert "{} live（内核不可用）".format(unavailable) in rows
    assert "{} live（内核可用）".format(available) in rows

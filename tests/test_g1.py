"""G1-01: catalog consistency guard.

Every ribbon/backstage command must be dispatchable by the GUI (dedicated
dispatch branch or a `_do_*` handler), or must NOT be marked live. This
prevents the 'marked live but reports 未实现' misalignment.
"""
from __future__ import annotations

from pathlib import Path

from scdm.catalog import (M1_LIVE, M2_LIVE, M3_LIVE, M4_LIVE, M5_LIVE,
                          all_commands)

ROOT = Path(__file__).resolve().parent.parent
GUI_SRC = (ROOT / "scdm_gui.py").read_text(encoding="utf-8")

# commands handled by dedicated dispatch branches in on_command() instead of a
# _do_* handler: tool tools, display toggles, styles, measure & mode trio
BRANCH_HANDLED = {
    "measure.dist", "mode.sketch", "mode.section", "mode.3d",
}

# intentionally not implemented (empty shell by design, DEV_PLAN.md §17)
INTENTIONAL = {"safety.tab"}


def _full_live() -> set:
    return set(M1_LIVE) | set(M2_LIVE) | set(M3_LIVE) | set(M4_LIVE) | set(M5_LIVE)


def _dispatchable(cmd_id: str) -> bool:
    if cmd_id in BRANCH_HANDLED or cmd_id in INTENTIONAL:
        return True
    if cmd_id.startswith(("tool.", "show.", "style.")):
        return True
    return "def _do_" + cmd_id.replace(".", "_") + "(" in GUI_SRC


def test_live_commands_are_dispatchable():
    live = _full_live()
    stuck = sorted(c.id for c in all_commands()
                   if c.id in live and not _dispatchable(c.id))
    assert not stuck, f"marked live but no handler: {stuck}"


def test_placeholder_commands_stay_out_of_live():
    """Commands without a handler must not claim to be live."""
    for c in all_commands():
        if not _dispatchable(c.id):
            assert c.id not in _full_live(), c.id

# -*- coding: utf-8 -*-
"""P1-4: regenerate the DEV_PLAN §21.1 snapshot block.

Usage::

    python tools/gen_devplan_snapshot.py

Prints the §21.1 table rows (markdown, paste-ready).  Numbers come from
the live catalog + test scan — no manual counting.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scdm.catalog import TABS, live_commands  # noqa: E402


def _test_count() -> int:
    n = 0
    root = Path(__file__).resolve().parents[1] / "tests"
    for p in sorted(root.glob("test_*.py")):
        src = p.read_text(encoding="utf-8", errors="replace")
        n += len(re.findall(r"\bdef test_", src))
    return n


def main() -> None:
    ribbon = [t for t in TABS if t.kind == "ribbon"]
    cmds = [c for t in ribbon for g in t.groups for c in g.commands]
    live = live_commands()
    live_ok = len(live)
    # kernel-available count: union of all wave sets
    from scdm import catalog  # noqa: E402
    full = set(catalog.M1_LIVE)
    for n in ("M2_LIVE", "M3_LIVE", "M4_LIVE", "M5_LIVE"):
        full |= getattr(catalog, n, set())
    placeholder = [c for c in cmds if c.id not in full]
    print("| UI 命令面 | {tabs} 页签 / {cmds} 命令 / "
          "**{live_ok} live（内核不可用）** / "
          "**{live_full} live（内核可用）**；占位 {ph}"
          .format(tabs=len(ribbon), cmds=len(cmds),
                  live_ok=live_ok, live_full=len(full),
                  ph="、".join(c.id for c in placeholder)))
    print("| 测试 | {} 条（def test_ 扫描） |".format(_test_count()))


if __name__ == "__main__":
    main()

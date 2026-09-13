# -*- coding: utf-8 -*-
"""P1-4 / P3 / P12: DEV_PLAN snapshot block generator.

Usage::

    python tools/gen_devplan_snapshot.py            # print the rows
    python tools/gen_devplan_snapshot.py --update   # rewrite the block in DEV_PLAN.md
    python tools/gen_devplan_snapshot.py --check    # exit 1 when the block is stale

Numbers come from the live catalog + test scan - no manual counting. The block
is delimited by SNAPSHOT markers in DEV_PLAN.md, which is what stops the
counts from drifting again (P3 found kernel=71/tests=195 stale for weeks).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scdm.catalog import TABS, all_commands, live_commands  # noqa: E402

BEGIN = "<!-- SNAPSHOT:BEGIN -->"
END = "<!-- SNAPSHOT:END -->"
DEFAULT_DOC = ROOT / "DEV_PLAN.md"


def _utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _tests() -> list:
    return sorted((ROOT / "tests").glob("test_*.py"))


def _test_count() -> int:
    return sum(len(re.findall(r"\bdef test_", p.read_text(encoding="utf-8",
                                                   errors="replace")))
               for p in _tests())


def _command_test_coverage() -> tuple:
    """(mentioned, total) using the same string proxy as the audit."""
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                      for p in _tests()
                      if p.name != "test_coverage_ledger.py")
    ids = [c.id for c in all_commands()]
    return sum(1 for i in ids if i in text), len(ids)


def snapshot_rows() -> list:
    ribbon = [t for t in TABS if t.kind == "ribbon"]
    cmds = [c for t in ribbon for g in t.groups for c in g.commands]
    live = live_commands()
    from scdm import catalog  # noqa: E402
    full = set(catalog.M1_LIVE)
    for n in ("M2_LIVE", "M3_LIVE", "M4_LIVE", "M5_LIVE"):
        full |= getattr(catalog, n, set())
    placeholder = [c for c in cmds if c.id not in full]
    covered, total = _command_test_coverage()
    return [
        "| 层 | 实测状态 |",
        "| --- | --- |",
        "| UI 命令面 | {tabs} ribbon 页签（+1 backstage）/ {cmds} 命令 / "
        "**{live_ok} live（内核不可用）** / **{live_full} live（内核可用）**；占位 {ph} |"
        .format(tabs=len(ribbon), cmds=len(cmds), live_ok=len(live),
                live_full=len(full),
                ph="、".join(c.id for c in placeholder)),
        "| 测试 | {n} 条（def test_ 扫描）；命令级测试提及 {c}/{t}"
        "（其余逐条在 tests/test_coverage_ledger.py 声明理由） |"
        .format(n=_test_count(), c=covered, t=total),
    ]


def snapshot_block() -> str:
    return "\n".join([BEGIN] + snapshot_rows() + [END])


def _pattern() -> re.Pattern:
    return re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)


def update_file(path: Path = DEFAULT_DOC) -> bool:
    """Rewrite the marked block; returns True when the file changed."""
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"snapshot markers not found in {path}")
    new = _pattern().sub(lambda _m: snapshot_block(), text, count=1)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def is_current(path: Path = DEFAULT_DOC) -> bool:
    text = path.read_text(encoding="utf-8")
    m = _pattern().search(text)
    return bool(m) and m.group(0) == snapshot_block()


def main(argv=None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="rewrite the marked block in the document")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when the block is stale")
    ap.add_argument("--path", default=str(DEFAULT_DOC))
    args = ap.parse_args(argv)
    path = Path(args.path)
    if args.update:
        print("updated" if update_file(path) else "unchanged")
        return 0
    if args.check:
        ok = is_current(path)
        print("snapshot current" if ok else "snapshot STALE - run --update")
        return 0 if ok else 1
    print("\n".join(snapshot_rows()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
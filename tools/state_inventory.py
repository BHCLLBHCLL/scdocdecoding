# -*- coding: utf-8 -*-
"""R101: read-only code-state inventory - one 口径 (scope) per number.

Usage::

    python tools/state_inventory.py            # markdown rows on stdout
    python tools/state_inventory.py --json     # the same numbers, machine-readable

Why this exists (R101 review, 2026-09-12): the same facts were quoted by hand in
several documents and had drifted - DEV_PLAN.md 21.1 still said kernel=80
functions / 33 script ops while the code had 106 / 52, and the auto snapshot
block recorded 177 in the "kernel unavailable" live cell because the generator
answered for *its own* interpreter. Every number below therefore carries its
scope: which files, which direction of the comparison, which kernel state.

It imports only scdm.catalog (never the OCC kernel), never writes to the repo,
and is pinned by tests/test_state_inventory.py.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scdm import catalog  # noqa: E402

PACKAGES = ("scdm", "scdoc_parser", "tools", "tests", "references")
LIVE_LISTS = ("M1_LIVE", "M2_LIVE", "M3_LIVE", "M4_LIVE", "M5_LIVE")


def _files(rel: str) -> list:
    d = ROOT / rel
    return sorted(d.rglob("*.py")) if d.exists() else []


def _lines(paths) -> int:
    """Physical lines, blank lines included (the scope every doc row uses)."""
    return sum(p.read_text(encoding="utf-8", errors="ignore").count(chr(10)) + 1
               for p in paths)


def _public_functions(path: Path) -> list:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    return [n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")]


def _live_union() -> set:
    s = set()
    for name in LIVE_LISTS:
        s |= set(getattr(catalog, name, set()))
    return s


def code_face() -> dict:
    per = {}
    for name in PACKAGES:
        f = _files(name)
        per[name] = {"files": len(f), "lines": _lines(f)}
    root_py = sorted(ROOT.glob("*.py"))
    per["(root modules)"] = {"files": len(root_py), "lines": _lines(root_py)}
    scdm_files = _files("scdm")
    candidates = scdm_files + root_py + _files("scdoc_parser")
    biggest = max(candidates, key=lambda p: _lines([p]))
    return {
        "packages": per,
        "python_files": sum(v["files"] for v in per.values()),
        "python_lines": sum(v["lines"] for v in per.values()),
        "largest_module": {"module": str(biggest.relative_to(ROOT)),
                           "lines": _lines([biggest])},
        "scdm_public_functions": sum(len(_public_functions(p)) for p in scdm_files),
        "kernel_public_functions": len(_public_functions(ROOT / "scdm" / "kernel.py")),
        "script_ops": len([n for n in _public_functions(ROOT / "scdm" / "scripting.py")
                           if n.startswith("op_")]),
    }


def command_face() -> dict:
    ribbon = [t for t in catalog.TABS if t.kind == "ribbon"]
    cmds = [c for t in ribbon for g in t.groups for c in g.commands]
    union = _live_union()
    return {
        "ribbon_tabs": len(ribbon),
        "backstage_tabs": len([t for t in catalog.TABS if t.kind == "backstage"]),
        "ribbon_commands": len(cmds),
        "backstage_commands": len(catalog.BACKSTAGE),
        "qat_commands": len(catalog.QAT),
        "all_commands": len(catalog.all_commands()),
        "live_kernel_unavailable": len(set(catalog.M1_LIVE)),
        "live_kernel_available": len(union),
        "placeholders": [c.id for c in cmds if c.id not in union],
        "per_tab": {t.id: sum(len(g.commands) for g in t.groups) for t in catalog.TABS},
    }


def gui_face() -> dict:
    src = (ROOT / "scdm_gui.py").read_text(encoding="utf-8")
    handlers = set(re.findall(r"def (_do_[A-Za-z0-9_]+)", src))
    reachable = {"_do_" + i.replace(".", "_") for i in _live_union()}
    return {
        "gui_lines": src.count(chr(10)) + 1,
        "dispatch_handlers": len(handlers),
        "orphan_handlers": sorted(h for h in handlers if h not in reachable),
        "catalog_ids_without_handler": sorted(
            c.id for c in catalog.all_commands()
            if "_do_" + c.id.replace(".", "_") not in handlers),
    }


def test_face() -> dict:
    files = sorted((ROOT / "tests").glob("test_*.py"))
    defs = sum(len(re.findall(r"\bdef test_",
                             p.read_text(encoding="utf-8", errors="replace")))
               for p in files)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in files if p.name != "test_coverage_ledger.py")
    ids = [c.id for c in catalog.all_commands()]
    exempt = 0
    try:
        tree = ast.parse((ROOT / "tests" / "test_coverage_ledger.py")
                         .read_text(encoding="utf-8"))
        for nd in tree.body:
            if isinstance(nd, ast.Assign) and getattr(nd.targets[0], "id", "") == "EXEMPT":
                exempt = len(ast.literal_eval(nd.value))
    except Exception:
        exempt = 0
    return {"files": len(files),
            "lines": _lines(files),
            "def_test": defs,
            "mentioned": sum(1 for i in ids if i in text),
            "mentioned_of": len(ids),
            "exempt_declared": exempt}


def doc_face() -> dict:
    return {"docs_md": len(list((ROOT / "docs").glob("*.md"))),
            "repo_md": len([p for p in ROOT.rglob("*.md") if "_tmp" not in str(p)])}


def inventory() -> dict:
    return {"code": code_face(), "commands": command_face(), "gui": gui_face(),
            "tests": test_face(), "docs": doc_face()}


def rows(data: dict) -> list:
    c, cmd, gui, t, d = (data["code"], data["commands"], data["gui"],
                         data["tests"], data["docs"])
    big = c["largest_module"]
    return [
        "| 口径 | 实测（本次运行，含空行） |",
        "| --- | --- |",
        "| Python 总量（scdm + scdoc_parser + tools + tests + references + 根模块）"
        " | {} 文件 / {} 行 |".format(c["python_files"], c["python_lines"]),
        "| scdm 包 | {} 文件 / {} 行；模块级公开函数 {} 个 |".format(
            c["packages"]["scdm"]["files"], c["packages"]["scdm"]["lines"],
            c["scdm_public_functions"]),
        "| kernel.py / scripting.py | 公开函数 {} 个 / 脚本 op {} 条 |".format(
            c["kernel_public_functions"], c["script_ops"]),
        "| 命令面 | {} ribbon 页签 + {} backstage；ribbon 命令 {}、"
        "目录全集 {}（含 backstage {} + QAT {}，去重 3） |".format(
            cmd["ribbon_tabs"], cmd["backstage_tabs"], cmd["ribbon_commands"],
            cmd["all_commands"], cmd["backstage_commands"], cmd["qat_commands"]),
        "| live | 内核不可用 {} / 内核可用 {}；占位 {} |".format(
            cmd["live_kernel_unavailable"], cmd["live_kernel_available"],
            "、".join(cmd["placeholders"])),
        "| GUI 派发 | scdm_gui.py {} 行；_do_* 处理器 {} 个；孤儿 {} 个 |".format(
            gui["gui_lines"], gui["dispatch_handlers"],
            len(gui["orphan_handlers"])),
        "| 测试 | {} 文件 / {} 行；def test_ {} 条；命令级提及 {}/{}，"
        "豁免声明 {} 条 |".format(t["files"], t["lines"], t["def_test"],
                                  t["mentioned"], t["mentioned_of"],
                                  t["exempt_declared"]),
        "| 文档 | docs/*.md {} 篇；仓库 *.md {} 篇 |".format(
            d["docs_md"], d["repo_md"]),
        "| 最大模块 | {}（{} 行） |".format(big["module"], big["lines"]),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="read-only code-state inventory")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    data = inventory()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("\n".join(rows(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

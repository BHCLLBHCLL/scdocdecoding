"""R125 A-9 + A-10: the tooling has to prove itself.

A-9:  a reference image now claims more than a mode chip - the sidecar also
      records how many rows the structure tree shows, what is selected, how many
      anchors are marked and how many bodies exist - and CI runs `--check`.
A-10: `tools/regress_batch.txt` is the regression batch.  Every path in it must
      exist and be collected, and every sketch round file must be in it, so a
      forgotten append fails here instead of quietly shrinking the batch.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MANIFEST = os.path.join(_ROOT, "tools", "regress_batch.txt")
_TOOL = os.path.join(_ROOT, "tools", "gui_screenshot.py")
_SHOTS = os.path.join(_ROOT, "docs", "screenshots")
_CI = os.path.join(_ROOT, ".github", "workflows", "ci.yml")

_FACTS = ("file", "demo", "model", "size", "chip", "health", "tree_rows",
          "sketch_sel", "anchors", "bodies", "3d")


def _manifest():
    with open(_MANIFEST, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh
                if ln.strip() and not ln.strip().startswith("#")]


def _defs(path):
    """The tests a file *claims* to have (pytest collection may add more)."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))


def _run_tool(*args, timeout=900):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, _TOOL] + list(args), cwd=_ROOT,
                          env=env, capture_output=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


# --- A-10: the batch manifest ------------------------------------------------

def test_every_listed_batch_file_exists():
    listed = _manifest()
    assert listed, "the batch manifest lists nothing"
    assert len(listed) == len(set(listed)), "the manifest lists a file twice"
    assert all(p.startswith("tests/") and p.endswith(".py") for p in listed)
    missing = [p for p in listed if not os.path.isfile(os.path.join(_ROOT, p))]
    assert missing == [], "listed but missing: %s" % missing


def test_no_sketch_round_file_is_missing_from_the_batch():
    """Every `test_sketch_*` file belongs to the batch - a new round's file that
    nobody appends would otherwise be tested by nobody."""
    listed = set(_manifest())
    on_disk = {"tests/" + n                      # the manifest uses forward slashes
               for n in os.listdir(os.path.join(_ROOT, "tests"))
               if n.startswith("test_sketch_") and n.endswith(".py")}
    assert sorted(on_disk - listed) == [], "not in the batch: %s" % sorted(
        on_disk - listed)


def test_the_manifest_is_what_pytest_collects():
    """One collection run: every listed path comes back with tests, and the total
    is the sum of the parts - a file that collects nothing is the failure."""
    listed = _manifest()
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only",
                           "-q", "-p", "no:cacheprovider"] + listed,
                          cwd=_ROOT, env=env, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=900)
    assert proc.returncode == 0, (proc.stdout[-800:], proc.stderr[-800:])
    counted = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"^(tests/[^:]+)::", line.strip())
        if m:
            counted[m.group(1)] = counted.get(m.group(1), 0) + 1
    empty = [p for p in listed if not counted.get(p)]
    assert empty == [], "listed but collects nothing: %s" % empty
    total = re.search(r"(\d+) tests? collected", proc.stdout)
    assert total, proc.stdout[-400:]
    assert sum(counted.values()) == int(total.group(1))
    short = {p: (counted[p], _defs(os.path.join(_ROOT, p)))
             for p in listed if counted[p] < _defs(os.path.join(_ROOT, p))}
    assert short == {}, "fewer collected than defined: %s" % short


# --- A-9: the reference images ----------------------------------------------

def test_the_committed_sidecars_record_the_widened_facts():
    names = [n for n in sorted(os.listdir(_SHOTS)) if n.endswith(".json")]
    assert names, "no recorded screenshots at all"
    for name in names:
        with open(os.path.join(_SHOTS, name), encoding="utf-8") as fh:
            facts = json.load(fh)
        assert facts.get("file"), name
        for key in _FACTS:
            assert key in facts, "%s does not record %s" % (name, key)


def test_a_drifted_tree_count_is_caught():
    """The widened facts must actually gate: keep chip/health/selection right and
    change only the tree row count - the image is stale."""
    room = os.path.join(_ROOT, "_tmp", "shots_r125")
    os.makedirs(room, exist_ok=True)
    png = os.path.join(room, "drifted.png")
    made = _run_tool("--out", png, "--demo", "solid", "--size", "600x400")
    assert made.returncode == 0, made.stderr[-500:]
    side = os.path.join(room, "drifted.json")
    with open(side, encoding="utf-8") as fh:
        facts = json.load(fh)
    facts["tree_rows"] = int(facts["tree_rows"]) + 1      # the only lie
    with open(side, "w", encoding="utf-8") as fh:
        json.dump(facts, fh, ensure_ascii=False)
    proc = _run_tool("--check", "--dir", room)
    assert proc.returncode == 1, (proc.stdout, proc.stderr[-500:])
    assert "tree_rows" in proc.stdout, proc.stdout
    assert "chip" not in proc.stdout, proc.stdout


def test_ci_runs_the_screenshot_check():
    with open(_CI, encoding="utf-8") as fh:
        text = fh.read()
    assert "gui_screenshot.py --check" in text, "CI does not check the images"
    assert "gen_devplan_snapshot.py --check" in text, "the snapshot check was lost"

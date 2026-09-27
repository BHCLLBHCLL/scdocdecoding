r"""R128/A-20: the official SpaceClaim corpus is the yardstick this parser is held to.

`D:\training\caedecoder\scdm_cases` holds 222 documents written by SpaceClaim
2019 R3 itself plus the counts it read back.  `tools/scdm_cases_check.py` parses
them with `scdoc_parser` and compares; these tests pin what that run found, so a
regression shows up as a number instead of an opinion.

The corpus is read-only and may be absent (CI): then everything here skips.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOL = os.path.join(_ROOT, "tools", "scdm_cases_check.py")
_CASES = os.environ.get("SCDM_CASES", r"D:\training\caedecoder\scdm_cases")
_MANIFEST = os.path.join(_CASES, "manifest.json")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(_MANIFEST), reason="官方语料库不在本机（SCDM_CASES）")

#: the cases whose numbers we match exactly - a pin, not a promise about the rest
PINNED = (
    "00_smoke_box_001_20x20x20",
    "01_primitives_block_001_10x20x30",
    "01_primitives_planar_001_rect_40x20",
    "02_sketch_arc_001_center_r20_90deg",
    "03_pull_cut_001_pocket_rect_depth5",
    "04_edge_chamfer_001_block_1edge_d2",
    "08_sheetmetal_convert_001_block_t2",
    "09_beam_create_001_line_I",
    "11_doc_color_001_body_red",
    "13_convertsolid_001_closed_sheets",
)

#: the two documents our parser still cannot read (facet mesh formats) - pinned so
#: a *new* crash cannot hide behind them
KNOWN_UNREADABLE = {"15_mesh_stl_import_001", "20_combo_mesh_032_mesh_plus_solid"}

#: agreement measured at R128 (95 of 218); the floor only goes up
FLOOR = 95


def _run(*args, timeout=1800):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, _TOOL] + list(args), cwd=_ROOT,
                          env=env, capture_output=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def test_the_corpus_is_the_official_one():
    with open(_MANIFEST, encoding="utf-8") as fh:
        man = json.load(fh)
    assert man.get("schema", "").startswith("scdm_cases/manifest")
    ok = [c for c in man["cases"] if c.get("status") == "ok"]
    assert len(man["cases"]) >= 200 and len(ok) >= 200, len(man["cases"])
    assert all("SpaceClaim" not in c["case_id"] for c in man["cases"])


def test_a_pinned_sample_matches_spaceclaim():
    args = []
    for case_id in PINNED:
        args += ["--only", case_id]
    proc = _run(*args, "--check", "--json",
                os.path.join("_tmp", "cases_pinned.json"))
    assert proc.returncode == 0, proc.stdout[-800:]
    assert "一致" in proc.stdout, proc.stdout[-400:]


def test_the_whole_corpus_parses_and_never_agrees_less_than_before():
    out = os.path.join("_tmp", "cases_all_test.json")
    proc = _run("--all", "--json", out)
    assert proc.returncode == 0, proc.stderr[-500:]
    with open(os.path.join(_ROOT, out), encoding="utf-8") as fh:
        data = json.load(fh)
    crashes = {r["case_id"] for r in data["rows"] if r.get("reason")}
    assert crashes <= KNOWN_UNREADABLE, "new parse failures: %s" % (
        crashes - KNOWN_UNREADABLE)
    assert data["summary"]["cases"] >= 200, data["summary"]
    assert data["summary"]["ok"] >= FLOOR, data["summary"]
    assert data["summary"]["seconds"] < 120, data["summary"]


def test_the_tool_refuses_to_write_into_the_corpus():
    target = os.path.join(_CASES, "_should_not_be_written.json")
    proc = _run("--only", PINNED[0], "--json", target)
    assert proc.returncode != 0, proc.stdout
    assert not os.path.exists(target), "写了语料库！"

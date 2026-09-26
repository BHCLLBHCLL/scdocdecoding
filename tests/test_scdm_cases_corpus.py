"""Manifest-driven corpus suite for SpaceClaim 2019 R3 ground-truth .scdoc files.

Parametrizes over ``tests/data/scdm_cases/manifest.json`` ``ok`` cases, parses
each ``.scdoc`` with ``scdoc_parser`` (no SpaceClaim install required), and
compares against the case JSON ``actual`` block.

Core gate categories (00-07 + 20_combo) assert topology counts strictly.
Volume / area / richer doc fields use per-category or per-field xfails where
the parser still has known gaps, so the suite stays green as a regression gate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from scdoc_parser.corpus import build_corpus_view

CORPUS_ROOT = Path(__file__).resolve().parent / "data" / "scdm_cases"
MANIFEST_PATH = CORPUS_ROOT / "manifest.json"

REL_TOL = 1e-6
ABS_TOL = 1e-6

# Categories that form the strict topology regression gate.
CORE_CATEGORIES = {
    "00_smoke",
    "01_primitives",
    "02_sketch",
    "03_pull",
    "04_edge",
    "05_boolean",
    "06_move_pattern",
    "07_shell_offset",
    "20_combo",
}

# Volume/area is reliable for planar + analytic cylinder/sphere/cone/torus
# primitives, but blends / booleans / sheet-metal / holes / splines still
# need better face metrics — xfail those categories for mass properties.
XFAIL_VOLUME_CATEGORIES = {
    "03_pull",
    "04_edge",
    "05_boolean",
    "06_move_pattern",
    "07_shell_offset",
    "08_sheetmetal",
    "09_beam",
    "13_surface_curve",
    "14_holes_threads",
    "20_combo",
}

# Cases whose volume still fails inside otherwise-good categories.
XFAIL_VOLUME_CASES = {
    "01_primitives_cone_002_frustum_r10_r5_h15",
    "01_primitives_torus_002_partial_180deg",
    "01_primitives_tube_001_line_r2_l50",
    "01_primitives_tube_002_poly_r3",
    "01_primitives_tube_002_arc_r3",
    "01_primitives_tube_003_spline_r1",
    "10_assembly_align_001_axis_axis",
}

XFAIL_AREA_CATEGORIES = set(XFAIL_VOLUME_CATEGORIES) | {"02_sketch"}
XFAIL_AREA_CASES = set(XFAIL_VOLUME_CASES) | {
    "12_prepare_sharetopology_001_two_blocks",
    "12_prepare_sharetopology_002_imprinted",
    "12_prepare_midsurface_001_plate_t2",
    "12_prepare_midsurface_002_L_bracket_t3",
}

# Topology count exceptions (design-tree vs SpaceClaim instance expansion).
XFAIL_COUNTS_CASES = {
    # Unfolded sheet-metal keeps flat-pattern bodies SpaceClaim counts separately.
    "08_sheetmetal_unfold_001",
    "20_combo_sm_018_sheetmetal_bracket",
    # Mid-surface adds a sheet body the design tree still lists once.
    "12_prepare_midsurface_001_plate_t2",
    "12_prepare_midsurface_002_L_bracket_t3",
    "20_combo_prep_020_midsurface_share_topology",
    # Spline-patch vertices live only on the SAB seam.
    "13_fill_002_patch_4_splines",
}

XFAIL_NAMES_CASES = set(XFAIL_COUNTS_CASES)

# ComponentDef is not expanded for pattern instances yet.
XFAIL_COMPONENTS_CASES = {
    "06_pattern_circular_002_bodies_4_180",
    "06_pattern_linear_001_cyl_1d_5x10",
    "06_pattern_linear_003_body_copy_3",
}

# STL import reports MeshDef in XML but GetMeshes() returned 0 in the harness.
XFAIL_MESHES_CASES = {
    "15_mesh_stl_import_001",
}

# Sheet-metal unfold stores an auxiliary DatumDef SpaceClaim does not tally.
XFAIL_DOC_ITEMS_CASES = {
    "08_sheetmetal_unfold_001",
    "20_combo_sm_018_sheetmetal_bracket",
}


def _load_manifest() -> Dict[str, Any]:
    assert MANIFEST_PATH.is_file(), f"corpus manifest missing: {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _case_actual(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(meta.get("actual"), dict):
        return meta["actual"]
    exp = meta.get("expected")
    if isinstance(exp, dict) and "bodies" in exp:
        return exp
    return None


def _iter_ok_cases() -> List[Tuple[str, Dict[str, Any]]]:
    man = _load_manifest()
    out = []
    for entry in man.get("cases", []):
        if entry.get("status") != "ok":
            continue
        if entry.get("excluded_from_repo"):
            continue
        scdoc = CORPUS_ROOT / entry["scdoc"]
        if not scdoc.is_file():
            continue
        meta_path = CORPUS_ROOT / entry["meta"]
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        actual = _case_actual(meta)
        if actual is None:
            continue
        out.append((entry["case_id"], {
            "entry": entry,
            "meta": meta,
            "actual": actual,
            "scdoc": scdoc,
        }))
    return out


OK_CASES = _iter_ok_cases()
CASE_IDS = [c[0] for c in OK_CASES]
CASE_MAP = {c[0]: c[1] for c in OK_CASES}


def _close(got: float, exp: float) -> bool:
    return math.isclose(got, exp, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def _xfail(cond: bool, reason: str) -> None:
    if cond:
        pytest.xfail(reason)


@pytest.fixture(scope="module")
def corpus_views() -> Dict[str, Dict[str, Any]]:
    """Parse every ok case once per test module."""
    views = {}
    for case_id, info in OK_CASES:
        views[case_id] = build_corpus_view(str(info["scdoc"]))
    return views


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_corpus_topology_counts(case_id: str, corpus_views: Dict[str, Dict[str, Any]]):
    info = CASE_MAP[case_id]
    actual = info["actual"]
    view = corpus_views[case_id]
    cat = info["entry"]["category"]

    _xfail(case_id in XFAIL_COUNTS_CASES,
           f"known topology gap for {case_id}")

    for key in ("bodies", "faces", "edges", "vertices"):
        if key not in actual:
            continue
        assert view.get(key) == actual[key], (
            f"{case_id} [{cat}] {key}: parser={view.get(key)} actual={actual[key]}")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_corpus_volume_area(case_id: str, corpus_views: Dict[str, Dict[str, Any]]):
    info = CASE_MAP[case_id]
    actual = info["actual"]
    view = corpus_views[case_id]
    cat = info["entry"]["category"]

    need_vol = "volume_mm3" in actual
    need_area = "area_mm2" in actual
    vol_xfail = (cat in XFAIL_VOLUME_CATEGORIES) or (case_id in XFAIL_VOLUME_CASES)
    area_xfail = (cat in XFAIL_AREA_CATEGORIES) or (case_id in XFAIL_AREA_CASES)

    if need_vol and vol_xfail:
        if not _close(view["volume_mm3"], actual["volume_mm3"]):
            pytest.xfail(f"volume metrics gap in {cat}/{case_id}")
    if need_area and area_xfail:
        if not _close(view["area_mm2"], actual["area_mm2"]):
            pytest.xfail(f"area metrics gap in {cat}/{case_id}")

    if need_vol:
        assert _close(view["volume_mm3"], actual["volume_mm3"]), (
            f"{case_id} volume: {view['volume_mm3']} != {actual['volume_mm3']}")
    if need_area:
        assert _close(view["area_mm2"], actual["area_mm2"]), (
            f"{case_id} area: {view['area_mm2']} != {actual['area_mm2']}")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_corpus_body_names(case_id: str, corpus_views: Dict[str, Dict[str, Any]]):
    info = CASE_MAP[case_id]
    actual = info["actual"]
    view = corpus_views[case_id]
    body_list = actual.get("body_list") or []
    exp = sorted(b.get("name") or "" for b in body_list if b.get("name"))
    if not exp:
        pytest.skip("no named bodies in ground truth")
    _xfail(case_id in XFAIL_NAMES_CASES,
           f"extra sheet/unfold bodies not yet listed for {case_id}")
    got = sorted(view.get("body_names") or [])
    assert got == exp, f"{case_id} names: {got} != {exp}"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_corpus_doc_items(case_id: str, corpus_views: Dict[str, Dict[str, Any]]):
    info = CASE_MAP[case_id]
    actual = info["actual"]
    view = corpus_views[case_id]

    _xfail(case_id in XFAIL_COMPONENTS_CASES,
           "pattern component instances not expanded from ComponentDef")
    _xfail(case_id in XFAIL_MESHES_CASES,
           "STL MeshDef present but harness reported meshes=0")
    _xfail(case_id in XFAIL_DOC_ITEMS_CASES,
           "sheet-metal auxiliary DatumDef not filtered")

    checks = []
    for key in (
        "components", "part_defs", "beams", "mating_conditions",
        "datum_planes", "coordinate_systems", "meshes", "drawing_sheets",
    ):
        if key in actual:
            checks.append((key, view.get(key), actual[key]))
    if not checks:
        pytest.skip("no doc-item fields in ground truth")

    for key, got, exp in checks:
        assert got == exp, f"{case_id} {key}: {got} != {exp}"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_corpus_units_layers_ns(case_id: str, corpus_views: Dict[str, Dict[str, Any]]):
    info = CASE_MAP[case_id]
    actual = info["actual"]
    view = corpus_views[case_id]
    saw = False

    if "units_length" in actual:
        saw = True
        assert view.get("units_length") == actual["units_length"]
        if "units_system" in actual:
            assert view.get("units_system") == actual["units_system"]
    if "layers" in actual:
        saw = True
        assert sorted(view.get("layers") or []) == sorted(actual["layers"])
    if "named_selections" in actual:
        saw = True
        assert sorted(view.get("named_selections") or []) == sorted(
            actual["named_selections"])
    if not saw:
        pytest.skip("no units/layers/ns in ground truth")


def test_manifest_schema_and_exclusions():
    man = _load_manifest()
    assert man.get("schema") == "scdm_cases/manifest v1"
    excluded = man.get("counts", {}).get("excluded_from_repo") or []
    assert "15_mesh_reduce_001_50pct" in excluded
    missing = CORPUS_ROOT / "15_mesh_facet" / "15_mesh_reduce_001_50pct.scdoc"
    assert not missing.exists()
    # ok cases that are present should be collected
    assert len(OK_CASES) >= 200
    core = [c for c in OK_CASES if c[1]["entry"]["category"] in CORE_CATEGORIES]
    assert len(core) >= 100


def test_unicode_summary_without_pythonioencoding(tmp_path):
    """Text summary must not crash on non-ASCII names without PYTHONIOENCODING."""
    import io
    import sys
    from scdoc_parser.report import build_report
    from scdoc_parser.__main__ import _configure_stdio, _print_summary

    scdoc = (CORPUS_ROOT / "11_doc_attrs" /
             "11_doc_rename_002_unicode_name.scdoc")
    assert scdoc.is_file()
    rep = build_report(str(scdoc))
    assert any("主体" in (b.get("name") or "") for b in rep["document"]["bodies"])

    buf = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict")
    old = sys.stdout
    try:
        sys.stdout = buf
        _configure_stdio()
        # After configure, encoding should accept UTF-8 (or replace).
        _print_summary(rep)
    finally:
        sys.stdout = old
    buf.seek(0)
    # Either reconfigure succeeded (utf-8) or errors='replace' — no raise.
    text = buf.buffer.getvalue()
    assert text, "summary produced no output"

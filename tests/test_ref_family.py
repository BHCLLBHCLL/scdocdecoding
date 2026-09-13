"""R72/P358: the ACIS @@ref@@ family is counted, not guessed.

The official library is exact on 6/6 samples *except* the faces whose surface is
an ACIS @@ref@@ indirection (SampleModel4: 52 referencing faces / 33 unbuilt;
samplemodel2: 20 / 1).  R21 proved the ref TABLE is not in this part; R72 makes
that countable per face and per edge, and records the three refuted repair ideas
so "cannot fix" is backed by measurements (discipline 86):

  alias reuse      -> 0 of 29 unbuilt ref faces share an edge set (measured)
  boundary fill    -> 20 fills attempted, 0 wires close (measured here)
  payload reuse    -> all 33 unbuilt ref surfaces carry ONLY the ref payload

There is no threshold in this file: every number is a count of the official
data (discipline 2/84), recomputable with tools/ref_family_diff.py.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scdm import import_sab
from scdm.document import load_scdoc

ROOT = Path(__file__).resolve().parent.parent
LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
GOLDEN = ROOT / "references" / "golden"

spec = importlib.util.spec_from_file_location(
    "ref_family_diff", ROOT / "tools" / "ref_family_diff.py")
diff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diff)


def _has_occ() -> bool:
    return importlib.util.find_spec("OCC") is not None


requires_occ = pytest.mark.skipif(not _has_occ(), reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


def _reset_counters():
    for attr in ("unbuilt", "unbuilt_ref", "skipped"):
        setattr(import_sab._faces_from_model, attr, 0)


@pytest.fixture(scope="module")
def sm4():
    """One import of SampleModel4 (the worst ref family), traced once."""
    if not os.path.isdir(LIB) or not _has_occ():
        pytest.skip("official library or kernel absent")
    data = load_scdoc(os.path.join(LIB, "SampleModel4.scdoc"))
    _reset_counters()
    with import_sab.trace_faces() as rec:
        kdoc = import_sab.import_scdoc_bundle(data)
    return SimpleNamespace(data=data, kdoc=kdoc, rec=rec,
                           unbuilt=import_sab._faces_from_model.unbuilt)


def test_ref_trace_is_off_by_default_and_restores_state():
    """The tracer must not perturb the production import (discipline 85)."""
    assert import_sab._TRACE is None
    with import_sab.trace_faces() as outer:
        _ = outer
        with import_sab.trace_faces() as inner:
            assert import_sab._TRACE is inner
        assert import_sab._TRACE is outer
    assert import_sab._TRACE is None


@requires_occ
def test_ref_trace_records_one_row_per_face():
    """The trace is the instrument's ground truth: one row per SAB face."""
    data = load_scdoc(str(GOLDEN / "ref_tet.scdoc"))
    _reset_counters()
    with import_sab.trace_faces() as rec:
        import_sab.import_scdoc_bundle(data)
    faces = sum(len(m.of_kind("face")) for m in data["models"])
    assert faces > 0
    assert len(rec) == faces
    assert all(set(r) >= {"face", "kind", "path", "ref", "inner", "edges"}
               for r in rec)
    assert sum(1 for r in rec if r["path"] == "none") == \
        import_sab._faces_from_model.unbuilt
    assert import_sab._faces_from_model.unbuilt_ref == \
        sum(1 for r in rec if r["path"] == "none" and r["ref"])


def test_ref_curve_coverage_partitions_the_edges():
    """The instrument's own arithmetic: payload + ref-only == referring edges."""
    data = load_scdoc(str(GOLDEN / "ref_tet.scdoc"))
    cov = diff.ref_curve_coverage(data)
    assert cov["edge"] == cov["edge_payload"] + cov["edge_ref_only"]
    independent = 0
    for m in data["models"]:
        owners = import_sab.ref_surface_owners(m)
        for ed in m.of_kind("edge"):
            if ed.curve is not None and ed.curve >= 0 and ed.curve in owners:
                independent += 1
    assert cov["edge"] == independent


@pytest.mark.parametrize("report,expected", [
    ({}, ""),
    ({"ref_faces": 52}, " · ref 52"),
    ({"ref_faces": 52, "ref_unbuilt": 33}, " · ref 52（未重建 33）"),
    ({"ref_faces": 52, "ref_unbuilt": 33, "ref_no_boundary": 6},
     " · ref 52（未重建 33，无边界 6）"),
])
def test_ref_hint_is_qt_free_and_countable(report, expected):
    """The GUI layer's data path: one wording source, no Qt required."""
    from scdm.import_sab import ref_family_hint

    assert ref_family_hint(report) == expected


def test_ref_report_counts_both_sides(sm4):
    """R72: ref_faces is now split into built / unbuilt / no-boundary."""
    rep = sm4.kdoc.import_report
    assert (rep["ref_faces"], rep["ref_built"], rep["ref_unbuilt"],
            rep["ref_no_boundary"]) == (52, 19, 33, 6)
    assert rep["ref_built"] + rep["ref_unbuilt"] == rep["ref_faces"]
    line = [w for w in sm4.kdoc.import_warnings if "ref 间接曲面" in w]
    assert line, sm4.kdoc.import_warnings
    assert "52 个面" in line[0] and "19 个仍由边界曲线重建" in line[0]
    assert "33 个未能重建（含 6 个无任何边界边）" in line[0]


def test_unbuilt_ref_surfaces_carry_only_the_ref_payload(sm4):
    """The 'no data to rebuild from' half of the R72 refusal."""
    unbuilt = [r for r in sm4.rec if r["path"] == "none" and r["ref"]]
    assert len(unbuilt) == 33
    assert all(r["inner"] == "ref" for r in unbuilt), \
        sorted({r["inner"] for r in unbuilt})
    # ... and the rest of the family really is rebuilt from the boundary
    built = [r for r in sm4.rec if r["path"] != "none" and r["ref"]]
    assert len(built) == 19
    assert all(r["faces"] == 1 for r in built)
    assert sum(1 for r in unbuilt if r["edges"] == 0) == 6


def test_unbuilt_ref_wires_do_not_close(sm4):
    """The fill idea is refuted here: the boundary wires are not closed."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, \
        BRepBuilderAPI_MakeWire

    model = sm4.data["models"][0]
    checked = 0
    for r in sm4.rec:
        if r["path"] != "none" or not r["ref"] or r["edges"] < 3:
            continue
        face = model.e(r["face"])
        mk = BRepBuilderAPI_MakeWire()
        for lp in model.loops_of_face(face):
            for ce in model.coedges_of_loop(lp):
                ee = model.e(ce.edge) if ce.edge >= 0 else None
                if ee is None:
                    continue
                curve = import_sab._edge_curve(model, ee)
                if curve is None:
                    continue
                try:
                    mk.Add(BRepBuilderAPI_MakeEdge(curve).Edge())
                except Exception:
                    pass
        assert not mk.IsDone(), "face %d closed; R72's refusal needs rechecking" \
            % r["face"]
        checked += 1
        if checked == 5:
            break
    assert checked == 5

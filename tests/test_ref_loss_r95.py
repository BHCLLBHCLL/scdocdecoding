"""R95/P430: the last 27 ref faces are blocked by DATA - and the report says so.

The round tried the "sister face" idea (reconstruct a missing face from a built
neighbour's surface) and refuted it per face:

  * 2 of the 27 have every boundary edge referenced by some built face, but even
    those edges' curves do not decode (the built faces used other data);
  * 6 have no boundary edges at all, 4 share no edge with any built face,
    15 share only part of their boundary - and every unshared edge is one whose
    curve is missing.

Measured reason split of the 27 unbuilt ref faces (SampleModel4):
  no-boundary 6 | all-curves-missing 10 | some-curves-missing 11 |
  curves-ok-but-not-built 0        <- nothing left that OUR code could build

The refusal therefore became a countable product fact: import_report now has
ref_no_curve (unbuilt ref faces whose boundary exists but whose curves are
incomplete) next to ref_no_boundary, with the invariant

    ref_no_boundary + ref_no_curve == ref_unbuilt

which the tests assert on two samples AND across two imports in one process
(R73's counter-leak trap repeated itself here and is now covered).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

LIB = r"C:\\Program Files\\ANSYS Inc\\v195\\scdm\\Library\\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")

MEASURED = {
    "SampleModel4.scdoc": (52, 25, 27, 6, 21),
    "samplemodel2.scdoc": (20, 19, 1, 0, 1),
}


@requires_occ
@requires_lib
def test_the_loss_is_split_by_data_and_boundary():
    from scdm import import_sab
    from scdm.document import load_scdoc

    for name, want in sorted(MEASURED.items()):
        kdoc = import_sab.import_scdoc_bundle(
            load_scdoc(os.path.join(LIB, name)))
        rep = kdoc.import_report
        got = (rep["ref_faces"], rep["ref_built"], rep["ref_unbuilt"],
               rep["ref_no_boundary"], rep["ref_no_curve"])
        assert got == want, (name, got)
        assert (rep["ref_no_boundary"] + rep["ref_no_curve"]
                == rep["ref_unbuilt"]), name
        line = [w for w in kdoc.import_warnings if "ref 间接曲面" in w][0]
        assert ("%d 个无任何边界边、%d 个边界曲线不全"
                % (rep["ref_no_boundary"], rep["ref_no_curve"])) in line


@requires_occ
@requires_lib
def test_the_counters_are_per_import_not_per_process():
    """R95 repeated R73's leak: the new counter must be reset too."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    first = import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "SampleModel4.scdoc")))
    assert first.import_report["ref_no_curve"] == 21
    second = import_sab.import_scdoc_bundle(
        load_scdoc(os.path.join(LIB, "samplemodel2.scdoc")))
    assert second.import_report["ref_no_curve"] == 1, \
        second.import_report["ref_no_curve"]


@requires_occ
@requires_lib
def test_no_unbuilt_ref_face_has_a_complete_boundary():
    """The refutation, per face: nothing is blocked by OUR code (R95)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "SampleModel4.scdoc"))
    import_sab._faces_from_model.unbuilt = 0
    import_sab._faces_from_model.unbuilt_ref = 0
    import_sab._faces_from_model.unbuilt_ref_no_curve = 0
    with import_sab.trace_faces() as rec:
        import_sab.import_scdoc_bundle(data)
    unbuilt = [r for r in rec if r["path"] == "none" and r["ref"]]
    models = {id(m): m for m in data["models"]}
    complete = 0
    for r in unbuilt:
        m = models[r["model"]]
        f = m.e(r["face"])
        if import_sab._face_curves_ok(m, f):
            complete += 1
    assert len(unbuilt) == 27
    assert complete == 0, complete      # a candidate would show up here
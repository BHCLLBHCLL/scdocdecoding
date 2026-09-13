"""R81: the last curve-decode gap - two-knot nubs records - and what is left.

The R78 endpoint-multiplicity fix was written as `len(raw) > 2`, which skipped
exactly the TWO-knot records (a single cubic span, mults [3, 3]).  OCCT then
rejected them with "Poles and degree mismatch" (swallowed by the except), so
5 ref-family edges never decoded.  With the guard relaxed to >= 2:

  SampleModel4 faces 147 -> 149, ref built 23 -> 25, ref unbuilt 29 -> 27
  samplemodel2 gaps 1395 -> 1393, loops 374 -> 372
  SampleModel1/3/5/6 unchanged

What is left in the ref family is now fully decomposed: 51 failing edges (of the
27 unbuilt ref faces) ALL have a curve head whose only payload is `ref` - the
shared-curve-library case that is not in this part (R21/R72/R81 agree, now with
a per-edge count instead of a family-level claim).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")
requires_lib = pytest.mark.skipif(not os.path.isdir(LIB),
                                  reason="SpaceClaim library absent")


@requires_occ
@requires_lib
def test_two_knot_nubs_records_decode():
    """Every nubs-bearing intcurve decodes now, whatever its knot count."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "SampleModel4.scdoc"))
    total = ok = two_knot = two_knot_ok = 0
    for m in data["models"]:
        for f in m.of_kind("face"):
            for lp in m.loops_of_face(f):
                for ce in m.coedges_of_loop(lp):
                    ee = m.e(ce.edge) if ce.edge >= 0 else None
                    if ee is None or ee.curve is None or ee.curve < 0:
                        continue
                    c = m.e(ee.curve)
                    if c is None or c.kind != "intcurve":
                        continue
                    nubs = import_sab._inner_of_kind(m, c, "nubs")
                    if nubs is None or not nubs.bs_poles:
                        continue
                    total += 1
                    decodes = import_sab._edge_curve(m, ee, f) is not None
                    ok += 1 if decodes else 0
                    if len(nubs.bs_mults) == 2:
                        two_knot += 1
                        two_knot_ok += 1 if decodes else 0
    assert total > 0
    assert ok == total, "%d of %d nubs curves decode" % (ok, total)
    assert two_knot > 0 and two_knot_ok == two_knot


@requires_occ
@requires_lib
def test_the_remaining_ref_failures_are_ref_only():
    """R81: per-EDGE evidence for the refusal (51 edges, all ref-only)."""
    from scdm import import_sab
    from scdm.document import load_scdoc

    data = load_scdoc(os.path.join(LIB, "SampleModel4.scdoc"))
    import_sab._faces_from_model.unbuilt = 0
    import_sab._faces_from_model.unbuilt_ref = 0
    with import_sab.trace_faces() as rec:
        import_sab.import_scdoc_bundle(data)
    unbuilt = [r for r in rec if r["path"] == "none" and r["ref"]]
    assert len(unbuilt) == 27
    models = {id(m): m for m in data["models"]}
    failing = ref_only = with_payload = 0
    for r in unbuilt:
        m = models[r["model"]]
        f = m.e(r["face"])
        for lp in m.loops_of_face(f):
            for ce in m.coedges_of_loop(lp):
                ee = m.e(ce.edge) if ce.edge >= 0 else None
                if ee is None or ee.curve is None or ee.curve < 0:
                    continue
                c = m.e(ee.curve)
                if c is None or import_sab._edge_curve(m, ee, f) is not None:
                    continue
                failing += 1
                inner = {e.kind for e in m.inner if e.cluster_owner == c.idx}
                if inner == {"ref"}:
                    ref_only += 1
                else:
                    with_payload += 1
    assert failing == 51, failing
    assert ref_only == failing, (ref_only, with_payload)

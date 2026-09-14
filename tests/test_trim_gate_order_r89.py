"""R89/P419: the trim gates are ordered cheap-first, and tori stay refused.

Measured cost per call (samplemodel2 torus faces): BRepCheck 0.003 s, the
model-bbox test ~0.000 s, GProp (K.area) 0.049 s.  The area gate therefore runs
LAST, once a candidate has passed everything cheap - a rejected candidate must
not pay for it at all (that is what the first test pins down).

R89 also re-opened R85's torus refusal and closed it again with better numbers:
the trim itself is ~0.18 s per face, but a torus has TWO candidate surfaces
(major/minor and the swap) and every FALLING one then runs the torus-only
SAMPLED window check, so the round cost is 0.54 s per face = 19.5 s for the 36
torus faces of samplemodel2 (import 6.8 s -> 25 s) for just 12 fewer gaps
(1002 -> 990).  Refused on cost/benefit; the whitelist stays cylinder+sphere.

Import-level GProp call counts (measured, for the record): SampleModel1 79,
samplemodel2 702.
"""
from __future__ import annotations

import importlib.util

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")


@requires_occ
def test_a_cheap_gate_failure_never_reaches_gprop(monkeypatch):
    from scdm import import_sab
    from scdm import kernel as K

    calls = []
    real = K.area

    def counted(face):
        calls.append(face)
        return real(face)

    monkeypatch.setattr(K, "area", counted)
    face = K.explore(K.make_box(0.02, 0.02, 0.02), "face")[0]
    far = ((-10.0, -10.0, -10.0), (-9.0, -9.0, -9.0))
    near = ((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0))
    # the model-bbox gate rejects it first: no GProp call
    assert import_sab._trim_gates_ok(face, None, far, strict_bbox=False) is False
    assert calls == []
    # ... and a candidate that passes the cheap gates does reach GProp
    assert import_sab._trim_gates_ok(face, None, near, strict_bbox=False) is True
    assert len(calls) == 1


@requires_occ
def test_the_whitelist_is_cylinders_and_spheres_only():
    from scdm import import_sab
    from scdm import kernel as K

    face = K.explore(K.make_box(0.02, 0.02, 0.02), "face")[0]
    assert not import_sab._trim_surface_allowed(face)      # a plane is not
    assert not import_sab._trim_surface_allowed("not a surface")


@requires_occ
def test_an_invalid_face_is_still_refused():
    """The cheap-first order must not weaken the gate itself."""
    from scdm import import_sab
    from scdm import kernel as K

    face = K.explore(K.make_box(0.02, 0.02, 0.02), "face")[0]
    near = ((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0))
    assert import_sab._trim_gates_ok(face, None, near, strict_bbox=False) is True
    # an empty compound is not a valid face
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    empty = TopoDS_Compound()
    BRep_Builder().MakeCompound(empty)
    assert import_sab._trim_gates_ok(empty, None, near, strict_bbox=False) is False
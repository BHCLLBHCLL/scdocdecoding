"""P291/R53: polyline beams, weldment groups and weld-symbol metadata.

Closed forms: the members never overlap, so the group volume is exactly
area * sum(length) - no boolean double counting to reason about.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import beams as B  # noqa: E402
from scdm import kernel as K  # noqa: E402

I_DIMS = {"h": 100.0, "b": 50.0, "tw": 5.0, "tf": 7.0}


def _i_m():
    return {k: v / 1000.0 for k, v in I_DIMS.items()}


def test_p291_polyline_members_match_the_segment_closed_form():
    pts = [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.1, 0.08, 0.0)]
    dims = _i_m()
    area = B.closed_form("i", **dims)["area"]
    solids = B.beam_polyline("i", pts, **dims)
    lengths = B.segment_lengths(pts)
    assert len(solids) == len(lengths) == 2
    assert lengths == [pytest.approx(0.1), pytest.approx(0.08)]
    total = 0.0
    for solid, seg in zip(solids, ((pts[0], pts[1]), (pts[1], pts[2]))):
        L = math.dist(seg[0], seg[1])
        vol = K.volume(solid)
        assert vol == pytest.approx(area * L, rel=1e-9)
        mid = [K.inertia(solid)["cog"][i] for i in range(3)]
        for i in range(3):
            assert mid[i] == pytest.approx((seg[0][i] + seg[1][i]) / 2.0,
                                           rel=1e-9, abs=1e-12)
        total += vol
    assert total == pytest.approx(area * sum(lengths), rel=1e-9)
    # one body per member: no boolean ever touched them
    for solid in solids:
        assert len(K.explore(solid, "solid")) == 1


def test_p291_weldment_shared_section_and_members():
    weld = B.Weldment(profile="pipe", dims={"d": 60.0, "t": 3.0})
    assert weld.spec().startswith("圆管")
    assert weld.add_member((0.0, 0.0, 0.0), (0.2, 0.0, 0.0)) == "M1"
    assert weld.add_member((0.2, 0.0, 0.0), (0.2, 0.15, 0.0)) == "M2"
    area1 = B.closed_form("pipe", d=0.06, t=0.003)["area"]
    assert weld.total_length() == pytest.approx(0.35, rel=1e-15)
    assert weld.total_volume() == pytest.approx(area1 * 0.35, rel=1e-12)
    # the shared section drives every member: changing it rebuilds all of them
    weld.set_section(profile="flat", b=40.0, h=10.0)
    area2 = B.closed_form("flat", b=0.04, h=0.01)["area"]
    assert weld.area() == pytest.approx(area2, rel=1e-15)
    assert weld.total_volume() == pytest.approx(area2 * 0.35, rel=1e-12)
    for name, solid in weld.shapes():
        L = math.dist(weld.member(name)["p0"], weld.member(name)["p1"])
        assert K.volume(solid) == pytest.approx(area2 * L, rel=1e-9), name
    # removing a member follows through to length/volume and drops its symbols
    weld.add_symbol(kind="fillet", size=5.0, length=20.0, member="M2")
    assert len(weld.symbols) == 1
    assert weld.remove_member("M2") is True
    assert weld.total_length() == pytest.approx(0.2, rel=1e-15)
    assert weld.total_volume() == pytest.approx(area2 * 0.2, rel=1e-12)
    assert weld.symbols == []
    assert weld.remove_member("nope") is False
    assert len(weld.shapes()) == 1


def test_p291_weld_symbol_metadata_round_trips():
    weld = B.Weldment(profile="l", dims={"a": 50.0, "b": 40.0, "t": 5.0})
    weld.add_member((0.0, 0.0, 0.0), (0.1, 0.0, 0.0), name="M1")
    weld.add_symbol(kind="fillet", size=5.0, length=20.0, pitch=50.0,
                    member="M1", position=(0.05, 0.0, 0.0))
    weld.add_symbol(kind="groove", size=8.0, member="M1")
    data = weld.to_dict()
    back = B.Weldment.from_dict(data)
    assert back.to_dict() == data
    assert back.symbols[0].kind == "fillet"
    assert back.symbols[0].position == (0.05, 0.0, 0.0)
    assert back.total_volume() == pytest.approx(weld.total_volume(), rel=1e-15)
    # illegal symbols: unknown kind, non-positive size, pitch without length,
    # and a symbol pointing at a member that does not exist
    with pytest.raises(K.KernelError):
        weld.add_symbol(kind="laser", size=3.0)
    with pytest.raises(K.KernelError):
        weld.add_symbol(kind="fillet", size=0.0)
    with pytest.raises(K.KernelError):
        weld.add_symbol(kind="fillet", size=3.0, pitch=50.0)
    with pytest.raises(K.KernelError):
        weld.add_symbol(kind="fillet", size=3.0, member="M9")
    with pytest.raises(K.KernelError):
        B.WeldSymbol(kind="fillet", size=-1.0).validate()


def test_p291_polyline_rejects_degenerate_input():
    dims = _i_m()
    with pytest.raises(K.KernelError):        # single point
        B.beam_polyline("i", [(0.0, 0.0, 0.0)], **dims)
    with pytest.raises(K.KernelError):        # repeated point
        B.beam_polyline("i", [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)], **dims)
    with pytest.raises(K.KernelError):        # unknown section
        B.beam_polyline("zz", [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0)], b=0.04, h=0.01)
    with pytest.raises(K.KernelError):        # unknown section on the group
        B.Weldment(profile="zz")
    weld = B.Weldment(profile="i", dims=I_DIMS)
    with pytest.raises(K.KernelError):        # zero-length member
        weld.add_member((1.0, 1.0, 1.0), (1.0, 1.0, 1.0))
    with pytest.raises(K.KernelError):        # duplicate member name
        weld.add_member((0.0, 0.0, 0.0), (0.1, 0.0, 0.0), name="M1")
        weld.add_member((0.0, 0.0, 0.0), (0.2, 0.0, 0.0), name="M1")
    with pytest.raises(K.KernelError):        # bad shared section
        weld.set_section(profile="pipe", d=60.0, t=30.0)


def test_p291_project_round_trip_keeps_weldments():
    import os
    import tempfile

    from scdm.io_project import load_scdm, save_scdm
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    weld = B.Weldment(profile="i", dims=I_DIMS, material="steel")
    pts = [(0.0, 0.0, 0.0), (0.12, 0.0, 0.0), (0.12, 0.09, 0.0)]
    for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
        name = weld.add_member(p0, p1, name="M%d" % (i + 1))
        doc.add_body(weld.shape(name), name=name)
    weld.add_symbol(kind="fillet", size=6.0, length=30.0, member="M1")
    doc.weldments.append(weld)
    # tempfile.mkdtemp (not the tmp_path fixture): pytest's temp root is not
    # writable in this environment, mkdtemp is what the rest of the suite uses
    tmp = tempfile.mkdtemp(prefix="p291_")
    try:
        path = os.path.join(tmp, "weld.scdm")
        save_scdm(path, doc)
        back = load_scdm(path)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    assert len(back.weldments) == 1
    assert back.weldments[0].to_dict() == weld.to_dict()
    assert back.weldments[0].total_volume() == pytest.approx(weld.total_volume(),
                                                             rel=1e-15)
    assert len(back.bodies) == 2

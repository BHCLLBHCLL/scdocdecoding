"""P287/R52: drawing snap targets - closed form, priority, tolerance, rebuild.

A snap must land EXACTLY on the target it claims: "close" would silently pull a
dimension line off the geometry it measures, so the assertions below compare at
1e-12 and check integral grid multiples rather than a pixel-ish tolerance.
"""
from __future__ import annotations

import pytest

from scdm import snaptools as SNAP


def _plus_view():
    """A 'plus': a horizontal segment crossed in its interior by a vertical one."""
    return [("前视", [[(0.0, 0.0), (0.04, 0.0)],
                      [(0.01, -0.01), (0.01, 0.02)]])]


def test_p287_endpoints_midpoints_and_crossings_are_exact():
    idx = SNAP.SnapIndex(_plus_view())
    tol = 1e-3
    # endpoint of the horizontal segment
    p, kind = idx.snap((0.04 + 2e-4, 1e-5), tol)
    assert kind == "end"
    assert p[0] == 0.04 and abs(p[1]) < 1e-15
    # midpoint of the horizontal segment = ((0+0.04)/2, 0) - exact division
    p, kind = idx.snap((0.02 + 3e-4, 2e-4), tol)
    assert kind == "mid"
    assert p == (0.02, 0.0)
    # interior crossing at x = 0.01, y = 0 (t = 0.25 along the horizontal)
    p, kind = idx.snap((0.0102, 0.0002), tol)
    assert kind == "cross"
    assert p[0] == pytest.approx(0.01, abs=1e-15)
    assert abs(p[1]) < 1e-15
    # the crossing is a real target: midpoint of the vertical is (0.01, 0.005),
    # so a point near y=0 can only be the crossing
    assert SNAP.segment_crossing((0.0, 0.0), (0.04, 0.0),
                                 (0.01, -0.01), (0.01, 0.02)) == (0.01, 0.0)


def test_p287_priority_prefers_the_more_specific_target():
    # a shared corner is both an endpoint and a crossing -> endpoint wins
    idx = SNAP.SnapIndex([("v", [[(0.0, 0.0), (0.02, 0.0)],
                                 [(0.02, 0.0), (0.02, 0.02)]])])
    p, kind = idx.snap((0.02 + 1e-5, 1e-5), 1e-3)
    assert kind == "end" and p == (0.02, 0.0)
    # collinear touching segments: the midpoint of one is an endpoint of the
    # other - again the endpoint is the better statement
    idx = SNAP.SnapIndex([("v", [[(0.0, 0.0), (0.01, 0.0)],
                                 [(0.01, 0.0), (0.03, 0.0)]])])
    p, kind = idx.snap((0.01 + 1e-5, 1e-5), 1e-3)
    assert kind == "end" and p == (0.01, 0.0)


def test_p287_tolerance_and_grid_are_closed_form():
    idx = SNAP.SnapIndex(_plus_view())
    # outside the tolerance nothing is snapped: the input point comes back
    p, kind = idx.snap((0.0215, 0.0005), 1e-4)
    assert kind == "" and p == (0.0215, 0.0005)
    # grid snapping is unconditional once a grid is set, and lands on an exact
    # multiple of the step
    grid = SNAP.SnapIndex(_plus_view(), grid=0.005)
    p, kind = grid.snap((0.0126, 0.0074), 1e-9)
    assert kind == "grid"
    assert p[0] / 0.005 == pytest.approx(3.0, rel=1e-12)
    assert p[1] / 0.005 == pytest.approx(1.0, rel=1e-12)
    # ... but a real target still wins inside the tolerance
    p, kind = grid.snap((0.0102, 0.0002), 1e-3)
    assert kind == "cross"


def test_p287_a_deleted_edge_stops_attracting_the_snap():
    """The illegal case from the R52 plan: after the edge is gone the old
    endpoint must not keep pulling the dimension handle."""
    views = [("前视", [[(0.0, 0.0), (0.02, 0.0), (0.02, 0.02), (0.0, 0.02),
                        (0.0, 0.0)],
                       [(0.005, 0.005), (0.015, 0.005)]])]
    idx = SNAP.SnapIndex(views)
    p, kind = idx.snap((0.015 + 3e-4, 0.005 + 3e-4), 1e-3)
    assert kind == "end" and p == (0.015, 0.005)
    idx.rebuild([("前视", [views[0][1][0]])])
    p, kind = idx.snap((0.015 + 3e-4, 0.005 + 3e-4), 1e-3)
    assert kind == ""
    assert p == (0.0153, 0.0053)
    # the surviving geometry still snaps
    p, kind = idx.snap((0.02 + 1e-4, 1e-4), 1e-3)
    assert kind == "end" and p == (0.02, 0.0)

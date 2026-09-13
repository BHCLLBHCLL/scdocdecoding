"""P343/R66: the accuracy route - state the convergence against the right scale.

R65 withdrew a loose "second order" claim; this round names the scale (rule 82):
the fill's volume error is second order in the BOUNDARY ELEMENT SIZE h (the mean
boundary triangle edge), not in the cell and not in the deflection.  Measured on a
r=10 mm sphere at a fixed 5 mm cell:

    h = 2.75e-3 -> rel 1.12e-2      h = 1.78e-3 -> rel 4.37e-3
    h ratio 1.55   error ratio 2.57   (h**2 predicts 2.40)

so err ~ C*h**2 with a stable C, while the deflection only moves h once it beats
the mesher's angular criterion (4e-4 and 2e-3 give identical h and error).
"""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import mesh as ME  # noqa: E402


def _stats(deflection: float, cell: float = 0.005):
    sphere = K.make_sphere(0.01)
    return ME.tet_stats(ME.tet_fill(sphere, cell, boundary="tets",
                                    deflection=deflection), shape=sphere)


def test_p343_error_is_second_order_in_the_element_size():
    coarse = _stats(1e-4)
    fine = _stats(2.5e-5)
    h_ratio = coarse["mean_edge"] / fine["mean_edge"]
    err_ratio = coarse["volume_rel_error"] / fine["volume_rel_error"]
    assert h_ratio > 1.3                       # the refinement really moved h
    assert err_ratio > 2.0                     # and the error dropped faster
    # ... by roughly h**2, which is the whole claim
    assert err_ratio == pytest.approx(h_ratio ** 2, rel=0.4)
    # the implied constant is stable between the two points, i.e. the law holds
    c_coarse = coarse["volume_rel_error"] / coarse["mean_edge"] ** 2
    c_fine = fine["volume_rel_error"] / fine["mean_edge"] ** 2
    assert c_coarse == pytest.approx(c_fine, rel=0.4)


def test_p343_deflection_is_floored_by_the_angular_criterion():
    """Below the sagitta of the angular deflection, asking for less does nothing:
    the budget table has to say so, and the stats expose h to prove it."""
    a = _stats(2e-3)
    b = _stats(4e-4)
    assert a["mean_edge"] == pytest.approx(b["mean_edge"], rel=1e-12)
    assert a["volume_rel_error"] == pytest.approx(b["volume_rel_error"], rel=1e-12)


def test_p343_the_route_choice_is_visible_in_the_numbers():
    """exact clipped volumes (no elements) vs a chord fan (elements, O(h**2)) -
    the trade-off the round selects between, measured side by side."""
    sphere = K.make_sphere(0.01)
    clip = ME.tet_stats(ME.tet_fill(sphere, 0.005, boundary="clip"), shape=sphere)
    tets = ME.tet_stats(ME.tet_fill(sphere, 0.005, boundary="tets",
                                    deflection=2.5e-5), shape=sphere)
    voxel = ME.tet_stats(ME.tet_fill(sphere, 0.005), shape=sphere)
    # accuracy order: voxel < tets(fine h) < clip
    assert voxel["volume_rel_error"] > 1e-2
    assert tets["volume_rel_error"] < voxel["volume_rel_error"] / 3.0
    assert clip["volume_clip_rel_error"] < tets["volume_rel_error"]
    # element counts: only the two meshing routes have them
    assert tets["tets"] > 0 and clip["boundary_tets"] == 0
    # the budget table's inputs are all in the stats
    for key in ("mean_edge", "max_edge", "boundary_cells", "boundary_volume",
                "volume", "volume_clip", "volume_rel_error",
                "volume_clip_rel_error"):
        assert key in tets and key in clip

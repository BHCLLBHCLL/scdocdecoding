"""P335/R64: boundary-conforming volume fill - the boundary band is clipped
exactly instead of being counted whole or dropped.

Measured on a r=10 mm sphere: the voxel fill is 4.5% off at both cell sizes,
while clipping the boundary band gives 5.6e-4 at 5 mm cells (80x better) and
3.9e-3 at 2.5 mm (11x better).  The residual comes from the boolean volume of the
thin clipped slivers (~0.8% of the band) and the band seeding, so this round
claims "an order of magnitude better at the same cell size" - second-order
convergence needs a real tetrahedralisation of the clipped pieces and is left to
the next batch, stated here rather than implied.
"""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import mesh as ME  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scripting import OPS  # noqa: E402


def test_p335_clip_is_an_order_of_magnitude_better_than_voxel():
    sphere = K.make_sphere(0.01)
    for cell, factor in ((0.005, 10.0), (0.0025, 5.0)):
        voxel = ME.tet_stats(ME.tet_fill(sphere, cell), shape=sphere)
        clip = ME.tet_stats(ME.tet_fill(sphere, cell, boundary="clip"),
                            shape=sphere)
        assert clip["boundary"] == "clip"
        assert clip["boundary_cells"] > 0
        assert clip["boundary_volume"] > 0
        assert clip["volume_clip"] == pytest.approx(clip["volume"]
                                                    + clip["boundary_volume"],
                                                    rel=1e-15)
        assert clip["volume_clip_rel_error"] < voxel["volume_rel_error"] / factor
        # the clipped total is still an approximation, and it says so
        assert clip["volume_clip_rel_error"] > 0.0


def test_p335_clip_keeps_the_grid_aligned_case_exact():
    box = K.make_box(0.02, 0.02, 0.02)
    voxel = ME.tet_stats(ME.tet_fill(box, 0.005), shape=box)
    clip = ME.tet_stats(ME.tet_fill(box, 0.005, boundary="clip"), shape=box)
    assert voxel["volume_rel_error"] == pytest.approx(0.0, abs=1e-15)
    assert clip["volume_clip_rel_error"] == pytest.approx(0.0, abs=1e-14)
    # the clipped run genuinely used the boundary path: the padded bbox leaves a
    # rim of cells that stick out of the box and must be clipped
    assert clip["boundary_cells"] > 0
    assert clip["tets"] == clip["cells"] * 6


def test_p335_kept_boundary_shapes_sum_to_the_reported_volume():
    sphere = K.make_sphere(0.01)
    fill = ME.tet_fill(sphere, 0.005, boundary="clip", keep_boundary_shapes=True)
    shapes = fill["boundary_shapes"]
    assert len(shapes) == fill["boundary_cells"]
    total = sum(K.volume(s) for s in shapes)
    assert total == pytest.approx(fill["boundary_volume"], rel=1e-12)
    with pytest.raises(K.KernelError):
        ME.tet_fill(sphere, 0.005, boundary="banana")


def test_p335_volume_op_exposes_the_clip_mode():
    doc = KernelDoc()
    body = doc.add_body(K.make_sphere(0.01), name="球")
    _out, msg = OPS["mesh.volume"](doc, {"target": "last", "cell": 5.0,
                                         "boundary": "clip"}, 1000.0)
    stats = doc.meshes[body.id]["volume"]
    assert stats["boundary"] == "clip" and stats["boundary_cells"] > 0
    assert "贴体" in msg and "边界格" in msg
    assert stats["volume_clip_rel_error"] < stats["volume_rel_error"] / 5.0
    # the default stays voxel so the R62 numbers do not move
    _out2, msg2 = OPS["mesh.volume"](doc, {"target": "last", "cell": 5.0}, 1000.0)
    assert doc.meshes[body.id]["volume"]["boundary"] == "voxel"
    assert "贴体" not in msg2


def test_p335_clip_replay_is_reproducible():
    from scdm.scripting import replay
    steps = [{"cmd": "mesh.volume",
              "opts": {"target": "last", "cell": 5.0, "boundary": "clip"}}]
    stats = []
    for _ in range(2):
        doc = KernelDoc()
        body = doc.add_body(K.make_sphere(0.01), name="球")
        replay(steps, doc, 1000.0)
        stats.append(doc.meshes[body.id]["volume"])
    assert stats[0]["cells"] == stats[1]["cells"]
    assert stats[0]["boundary_cells"] == stats[1]["boundary_cells"]
    assert stats[0]["volume_clip"] == stats[1]["volume_clip"]   # bitwise

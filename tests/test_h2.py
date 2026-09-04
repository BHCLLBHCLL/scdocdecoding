"""H2: direct-modeling depth (variable fillet, multi-thickness shell,
neutral-face draft, path/fill patterns, pull auto-dispatch)."""
from __future__ import annotations

import math

import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")

BOX = 0.02  # 20 mm cube


def _box():
    return K.make_box(BOX, BOX, BOX)


def _box_and_parts():
    b = _box()
    return b, K.explore(b, "edge"), K.explore(b, "face")


def test_fillet_variable_per_edge():
    b, edges, _ = _box_and_parts()
    r = K.fillet_variable(b, [(edges[0], 0.001), (edges[1], 0.002)])
    # equal-radius two-edge fillet for reference
    r2 = K.fillet_edges(b, 0.001, [edges[0], edges[1]])
    # different radii must remove a different amount of material
    assert K.volume(r) != K.volume(r2)
    assert BOX ** 3 > K.volume(r) > 0


def test_fillet_variable_along_edge():
    b, edges, _ = _box_and_parts()
    r = K.fillet_variable(b, [(edges[0], [(0.0, 0.0005), (1.0, 0.002)])])
    # between the volumes of the 0.5 mm and 2 mm single-edge fillets
    v_small = K.volume(K.fillet_edges(b, 0.0005, [edges[0]]))
    v_big = K.volume(K.fillet_edges(b, 0.002, [edges[0]]))
    assert v_small > K.volume(r) > v_big


def test_shell_multi_thicknesses():
    b, _, faces = _box_and_parts()
    r = K.shell_multi(b, [(faces[0:1], 0.002)], default_thickness=0.001)
    v = K.volume(r)
    # one 2 mm wall + five 1 mm walls: between the two uniform shells
    v_thin = K.volume(K.shell_solid(b, 0.001, [faces[0]]))
    v_thick = K.volume(K.shell_solid(b, 0.002, [faces[0]]))
    assert v_thin < v < v_thick


def test_draft_neutral_plane():
    b, _, faces = _box_and_parts()
    r = K.draft_neutral(b, faces[0], math.radians(5), faces[2])
    assert K.volume(r) > 0
    assert K.volume(r) != BOX ** 3


def test_pattern_path_distribution():
    b, edges, _ = _box_and_parts()
    copies = K.pattern_path(b, edges[0], 5)
    assert len(copies) == 5
    # first copy sits at the original position
    assert abs(K.volume(copies[0]) - BOX ** 3) < 1e-12


def test_pattern_fill_grid():
    b = _box()
    # 0.1 region, 0.02 elements, 0.01 gaps -> 3x3 = 9
    copies = K.pattern_fill(b, 0.1, 0.1, 0.02, 0.02, gap=0.01)
    assert len(copies) == 9


def test_pull_auto_dispatch():
    b, edges, faces = _box_and_parts()
    kind, r = K.pull_auto(b, faces[0], (0, 0, 1), 0.005)
    assert kind == "extrude" and K.volume(r) > BOX ** 3
    # pick the +Z face (normal (0,0,1)) and pull INTO the material
    top = next(f for f in faces
               if abs(K.face_normal_center(f)[0][2] - 1.0) < 1e-9)
    kind, r = K.pull_auto(b, top, (0, 0, -1), 0.005)
    assert kind == "offset-cut" and K.volume(r) < BOX ** 3
    kind, r = K.pull_auto(b, edges[0], None, 0.001)
    assert kind == "fillet" and K.volume(r) < BOX ** 3
    kind, r = K.pull_auto(b, edges[0], None, 0.001, mode="chamfer")
    assert kind == "chamfer"


def test_scripting_h2_ops():
    from scdm.kdoc import KernelDoc
    from scdm.scripting import replay

    doc = KernelDoc()
    doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    msgs = replay([
        {"cmd": "create.blend_variable",
         "opts": {"edges": [0], "radii": [1.0, 2.0]}},
        {"cmd": "create.shell_multi",
         "opts": {"groups": [{"faces": [1], "thickness": 1.0}]}},
        {"cmd": "create.draft_neutral",
         "opts": {"faces": [1], "neutral": "planar", "angle": 5.0}},
        {"cmd": "create.pattern", "opts": {"mode": "fill",
                                           "elem": 5.0, "gap": 1.0,
                                           "region": 30.0}},
        {"cmd": "tool.pull_auto", "opts": {"what": "face", "index": 0,
                                           "distance": 1.0}},
    ], doc, scale=1000.0)
    assert all("跳过" not in m for m in msgs), msgs
    assert len(doc.bodies) >= 2

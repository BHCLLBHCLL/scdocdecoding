"""P4: feature family - standard holes and a round boss.

Exact-volume assertions: every feature is built from an analytic primitive and
a boolean, so the removed/added volume is known in closed form.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402

V0 = 0.02 ** 3


def _top_face(shape):
    faces = K.explore(shape, "face")
    return [f for f in faces
            if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9]


def test_hole_simple_through_removes_pi_r2_t():
    box = K.make_box(0.02, 0.02, 0.02)
    out = K.hole_simple(box, _top_face(box)[0], 0.005)
    expect = V0 - math.pi * 0.0025 ** 2 * 0.02
    assert K.volume(out) == pytest.approx(expect, rel=1e-6)
    # a through hole must actually break both faces: 1 face becomes 2 (annulus)
    assert len(K.explore(out, "face")) == 7


def test_hole_simple_blind_removes_pi_r2_depth():
    box = K.make_box(0.02, 0.02, 0.02)
    out = K.hole_simple(box, _top_face(box)[0], 0.005, depth=0.005)
    expect = V0 - math.pi * 0.0025 ** 2 * 0.005
    assert K.volume(out) == pytest.approx(expect, rel=1e-6)


def test_hole_counterbore_two_stage_volume():
    box = K.make_box(0.02, 0.02, 0.02)
    out = K.hole_counterbore(box, _top_face(box)[0],
                             diameter=0.005, depth=0.01,
                             cbore_diameter=0.01, cbore_depth=0.002)
    removed = (math.pi * 0.005 ** 2 * 0.002
               + math.pi * 0.0025 ** 2 * (0.01 - 0.002))
    assert K.volume(out) == pytest.approx(V0 - removed, rel=1e-6)


def test_hole_countersink_frustum_volume():
    box = K.make_box(0.02, 0.02, 0.02)
    r, R, depth = 0.0025, 0.005, 0.01
    out = K.hole_countersink(box, _top_face(box)[0],
                             diameter=0.005, depth=depth,
                             sink_diameter=0.01, angle_deg=90.0)
    h = (R - r) / math.tan(math.radians(45.0))
    removed = (math.pi * h / 3.0 * (R * R + R * r + r * r)
               + math.pi * r * r * (depth - h))
    assert K.volume(out) == pytest.approx(V0 - removed, rel=1e-6)
    # a sink narrower than the pilot is rejected
    with pytest.raises(K.KernelError):
        K.hole_countersink(box, _top_face(box)[0], 0.005, depth,
                           sink_diameter=0.004)


def test_boss_round_adds_pi_r2_h():
    box = K.make_box(0.02, 0.02, 0.02)
    out = K.boss_round(box, _top_face(box)[0], 0.006, 0.004)
    expect = V0 + math.pi * 0.003 ** 2 * 0.004
    assert K.volume(out) == pytest.approx(expect, rel=1e-6)


def test_feature_ops_replay():
    """create.hole / create.boss are replayable script ops (record -> replay)."""
    from scdm import scripting as SCR
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    steps = [{"cmd": "create.hole",
              "opts": {"target": "last", "face_i": 5, "diameter": 5.0,
                       "depth": 0.0}},
             {"cmd": "create.boss",
              "opts": {"target": "last", "face_i": 4, "diameter": 6.0,
                       "height": 4.0}}]
    report = SCR.replay(steps, doc)
    assert report == ["OK create.hole", "OK create.boss"], report
    # hole (through, d=5mm) removed, boss (d=6mm, h=4mm) added
    expect = (V0 - math.pi * 0.0025 ** 2 * 0.02
              + math.pi * 0.003 ** 2 * 0.004)
    assert K.volume(doc.bodies[0].shape) == pytest.approx(expect, rel=1e-6)

def test_hole_cbore_and_csink_ops_replay():
    """create.hole_cbore / create.hole_csink are replayable script ops too."""
    from scdm import scripting as SCR
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    doc.add_body(K.make_box(0.02, 0.02, 0.02), name="B")
    steps = [{"cmd": "create.hole_cbore",
              "opts": {"target": "last", "face_i": 5, "diameter": 5.0,
                       "depth": 10.0, "cbore_diameter": 10.0,
                       "cbore_depth": 2.0}},
             {"cmd": "create.hole_csink",
              "opts": {"target": "last", "face_i": 4, "diameter": 5.0,
                       "depth": 10.0, "sink_diameter": 10.0, "angle": 90.0}}]
    report = SCR.replay(steps, doc)
    assert report == ["OK create.hole_cbore", "OK create.hole_csink"], report
    removed = (math.pi * 0.005 ** 2 * 0.002
               + math.pi * 0.0025 ** 2 * (0.01 - 0.002))
    r, R, depth = 0.0025, 0.005, 0.01
    h = (R - r) / math.tan(math.radians(45.0))
    removed += math.pi * h / 3.0 * (R * R + R * r + r * r)
    removed += math.pi * r * r * (depth - h)
    assert K.volume(doc.bodies[0].shape) == pytest.approx(V0 - removed,
                                                          rel=1e-4)
    # the ops are registered under their catalog ids
    assert "create.hole_cbore" in SCR.OPS and "create.hole_csink" in SCR.OPS


def test_feature_history_replays_on_parameter_change():
    """P5: a hole/boss feature survives a parametric rebuild at the new size."""
    from scdm import features as FEAT
    from scdm import params as P
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    parametric = P.param_box("板", w=20.0, h=20.0, d=20.0)
    body = doc.add_parametric(parametric)

    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    doc.record_feature(body.id, "hole",
                       selector=FEAT.selector_for(body.shape, top),
                       diameter=5.0, depth=0.0)          # through hole
    body.shape = doc.feature_stack(body.id).apply(body.shape)  # -> history in effect
    assert len(doc.feature_stack(body.id)) == 1
    assert K.volume(body.shape) == pytest.approx(
        0.02 ** 3 - math.pi * 0.0025 ** 2 * 0.02, rel=1e-6)

    # double the height parameter: the rebuild must replant the hole through
    # the new 40mm thickness at the same face
    parametric.set(D=40.0)
    doc.rebuild_parametric(parametric)
    assert K.volume(body.shape) == pytest.approx(
        0.02 * 0.02 * 0.04 - math.pi * 0.0025 ** 2 * 0.04, rel=1e-5)


def test_feature_stack_roundtrip():
    """P5: the feature stack serialises (project persistence)."""
    from scdm.features import FeatureStack

    stack = FeatureStack.from_dict([
        {"op": "hole", "params": {"selector": {"normal": [0, 0, 1],
                                               "pick": "max"},
                                  "diameter": 5.0, "depth": 0.0}},
        {"op": "boss", "params": {"selector": {"normal": [0, 0, 1],
                                               "pick": "max"},
                                  "diameter": 6.0, "height": 4.0}},
    ])
    assert stack.ops() == ["hole", "boss"]
    assert stack.as_dict()[1]["params"]["height"] == 4.0
    assert len(stack) == 2

def test_feature_history_covers_shell_fillet_chamfer():
    """P9: shell / fillet / chamfer replay on a parametric rebuild too."""
    from scdm import features as FEAT
    from scdm import params as P
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    parametric = P.param_box("板", w=20.0, h=20.0, d=20.0)
    body = doc.add_parametric(parametric)
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]

    base = parametric.build(1000.0)          # replay always starts from base
    doc.record_feature(body.id, "shell",
                       selectors=[FEAT.selector_for(base, top)],
                       thickness=1.0)
    v_shell = K.volume(doc.feature_stack(body.id).apply(base))
    assert 0 < v_shell < 8e-6

    # NOTE: the radius must stay below the 1mm wall - filleting a thin shelled
    # wall crashes OCCT natively (no Python exception), so the chain is kept
    # geometrically sane here. A pre-flight guard is on the next-round plan.
    doc.record_feature(body.id, "fillet", radius=0.25)
    v_fillet = K.volume(doc.feature_stack(body.id).apply(base))
    assert 0 < v_fillet < v_shell
    assert doc.feature_stack(body.id).ops() == ["shell", "fillet"]

    # parameter change replays the whole chain on the new base body
    parametric.set(W=30.0, H=30.0)
    doc.rebuild_parametric(parametric)
    assert doc.feature_stack(body.id).ops() == ["shell", "fillet"]
    assert 0 < K.volume(body.shape) < 0.03 * 0.03 * 0.02


def test_feature_history_replays_chamfer_on_a_solid():
    """P9: chamfer is recorded and replayable on a plain (un-shelled) body."""
    from scdm import params as P
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    parametric = P.param_box("块", w=20.0, h=20.0, d=20.0)
    body = doc.add_parametric(parametric)
    base = parametric.build(1000.0)
    doc.record_feature(body.id, "chamfer", distance=1.0)
    assert doc.feature_stack(body.id).ops() == ["chamfer"]
    out = doc.feature_stack(body.id).apply(base)
    assert 0 < K.volume(out) < K.volume(base)
    parametric.set(D=30.0)
    doc.rebuild_parametric(parametric)
    assert 0 < K.volume(body.shape) < 0.02 * 0.02 * 0.03

def test_fillet_guard_rejects_thin_wall_instead_of_crashing():
    """P14: a radius at the wall thickness is refused, not a native crash."""
    box = K.make_box(0.02, 0.02, 0.02)
    top = [f for f in K.explore(box, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    shell = K.shell_solid(box, 0.001, [top])          # 1mm wall
    v0 = K.volume(shell)

    # 1mm radius on a 1mm wall used to kill the process (OCCT AV)
    with pytest.raises(K.KernelError) as e1:
        K.fillet_edges(shell, 0.001)
    assert "被拒绝" in str(e1.value)
    with pytest.raises(K.KernelError):
        K.chamfer_edges(shell, 0.001)

    # a radius below half the shortest edge is still allowed
    ok = K.fillet_edges(shell, 0.00025)
    assert 0 < K.volume(ok) < v0


def test_fillet_guard_rejects_nonpositive_radius():
    box = K.make_box(0.02, 0.02, 0.02)
    with pytest.raises(K.KernelError):
        K.fillet_edges(box, 0.0)
    with pytest.raises(K.KernelError):
        K.chamfer_edges(box, -0.001)


def test_fillet_guard_allows_normal_solid_radius():
    """A 1mm radius on a 20mm solid must pass the guard and apply."""
    box = K.make_box(0.02, 0.02, 0.02)
    out = K.fillet_edges(box, 0.001)
    assert 0 < K.volume(out) < K.volume(box)


def test_variable_fillet_guard_is_per_edge():
    """P14: the variable fillet checks each entry against its own edge."""
    box = K.make_box(0.02, 0.02, 0.02)
    edges = K.explore(box, "edge")
    out = K.fillet_variable(box, [(edges[0], [(0.0, 0.001), (1.0, 0.002)])])
    assert 0 < K.volume(out) < K.volume(box)
    with pytest.raises(K.KernelError):
        K.fillet_variable(box, [(edges[0], 0.02)])

def test_feature_labels_are_human_readable():
    """P16: the tree shows named features, not op codes."""
    from scdm.features import FeatureStack

    stack = FeatureStack.from_dict([
        {"op": "hole", "params": {"diameter": 5.0, "depth": 0.0}},
        {"op": "shell", "params": {"thickness": 1.0}},
        {"op": "fillet", "params": {"radius": 0.25}},
        {"op": "draft", "params": {"angle": 5.0}},
    ])
    assert [f.label() for f in stack.features] == [
        "孔 Ø5mm", "抽壳 1mm", "倒圆 R0.25mm", "拔模 5°"]
    # an unknown op degrades to its op code instead of raising
    assert FeatureStack.from_dict([{"op": "weird"}]).features[0].label() == "weird"


def test_feature_history_replays_pull_chain():
    """P16: pull is part of the history and replays at the new parameters."""
    from scdm import features as FEAT
    from scdm import params as P
    from scdm.kdoc import KernelDoc

    doc = KernelDoc()
    parametric = P.param_box("块", w=20.0, h=20.0, d=20.0)
    body = doc.add_parametric(parametric)
    base = parametric.build(1000.0)
    top = [f for f in K.explore(base, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    doc.record_feature(body.id, "pull",
                       selector=FEAT.selector_for(base, top), distance=5.0)

    shape = doc.feature_stack(body.id).apply(base)
    # 20x20x20 pulled +5mm on the top face -> 20x20x25
    assert K.volume(shape) == pytest.approx(0.02 * 0.02 * 0.025, rel=1e-6)

    # parameter change replays the pull on the new base body
    parametric.set(W=30.0)
    doc.rebuild_parametric(parametric)
    assert K.volume(body.shape) == pytest.approx(0.03 * 0.02 * 0.025, rel=1e-6)
    assert doc.feature_stack(body.id).ops() == ["pull"]

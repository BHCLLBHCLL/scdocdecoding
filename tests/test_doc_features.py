"""P22: document-level feature history (multi-body ops) + replay/delete."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.features import FeatureHistory  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _box(n=0.01):
    return K.make_box(n, n, n)


def test_doc_pattern_replay_keeps_original_and_copies():
    h = FeatureHistory()
    h.add("pattern_linear", [0], vec_mm=(20.0, 0.0, 0.0), count=3)
    out = h.replay([_box()])
    assert len(out) == 3
    assert all(K.volume(s) == pytest.approx(1e-6, rel=1e-9) for s in out)
    assert h.ops() == ["pattern_linear"]
    assert h.features[0].label() == "线性阵列 ×3"


def test_doc_fuse_consumes_both_inputs():
    h = FeatureHistory()
    h.add("fuse", [0, 1])
    a = _box()
    b = K.translate(_box(), (0.005, 0.0, 0.0))     # half overlap
    out = h.replay([a, b])
    assert len(out) == 1                            # two inputs -> one body
    assert K.volume(out[0]) == pytest.approx(1.5e-6, rel=1e-9)


def test_doc_circular_pattern_and_mirror():
    h = FeatureHistory()
    h.add("pattern_circular", [0], axis=(0, 0, 1), angle_deg=90.0, count=4)
    h.add("mirror", [0], origin=(0, 0, 0), normal=(0, 0, 1))
    out = h.replay([_box()])
    assert len(out) == 4 + 1                        # 3 copies + 1 mirror + base


def test_doc_feature_delete_then_replay():
    h = FeatureHistory()
    h.add("pattern_linear", [0], vec_mm=(20.0, 0.0, 0.0), count=3)
    h.add("fuse", [0, 1])
    assert len(h.replay([_box()])) == 2             # fuse collapsed two slots
    assert h.remove_at(0) is True                   # drop the pattern
    assert len(h.replay([_box()])) == 1
    assert h.remove_at(9) is False


def test_doc_history_roundtrip():
    h = FeatureHistory.from_dict([
        {"op": "pattern_linear", "inputs": [0],
         "params": {"vec_mm": [20.0, 0.0, 0.0], "count": 3}},
        {"op": "cut", "inputs": [0, 2], "params": {}},
    ])
    assert h.ops() == ["pattern_linear", "cut"]
    data = h.as_dict()
    assert data[1]["inputs"] == [0, 2]
    assert FeatureHistory.from_dict(data).as_dict() == data


def test_replay_document_uses_parametrics_and_stacks():
    """P22: replay_document chains base -> per-body features -> doc features."""
    from scdm import features as FEAT
    from scdm import params as P

    doc = KernelDoc()
    parametric = P.param_box("板", w=20.0, h=20.0, d=20.0)
    body = doc.add_parametric(parametric)
    base = parametric.build(1000.0)
    top = [f for f in K.explore(base, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    doc.record_feature(body.id, "hole",
                       selector=FEAT.selector_for(base, top),
                       diameter=5.0, depth=0.0)
    doc.record_doc_feature("pattern_linear", [0], vec_mm=(30.0, 0.0, 0.0),
                           count=2)
    shapes = doc.replay_document()
    expect = 0.02 * 0.02 * 0.02 - 3.14159265358979 * 0.0025 ** 2 * 0.02
    assert len(shapes) == 2
    assert K.volume(shapes[0]) == pytest.approx(expect, rel=1e-5)

    # parameter change -> replay keeps the hole and the pattern
    parametric.set(D=40.0)
    shapes = doc.replay_document()
    expect2 = 0.02 * 0.02 * 0.04 - 3.14159265358979 * 0.0025 ** 2 * 0.04
    assert K.volume(shapes[0]) == pytest.approx(expect2, rel=1e-5)

    # apply=True replaces the bodies
    doc.replay_document(apply=True)
    assert len(doc.bodies) == 2

def test_scdm_roundtrip_keeps_feature_history_and_assembly_state():
    """P22: .scdm keeps per-body features, doc features, components, instances."""
    import os
    import tempfile

    from scdm import features as FEAT
    from scdm.io_project import load_scdm, save_scdm

    doc = KernelDoc()
    body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="板")
    top = [f for f in K.explore(body.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    doc.record_feature(body.id, "hole",
                       selector=FEAT.selector_for(body.shape, top),
                       diameter=5.0, depth=0.0)
    doc.record_doc_feature("pattern_linear", [0], vec_mm=(30.0, 0.0, 0.0),
                           count=2)
    doc.add_component("装配A", [body.id])
    doc.add_instance(body.id, transform=((1, 0, 0, 0.03), (0, 1, 0, 0),
                                         (0, 0, 1, 0), (0, 0, 0, 1)))

    fd, path = tempfile.mkstemp(suffix=".scdm")
    os.close(fd)
    try:
        save_scdm(path, doc)
        back = load_scdm(path)
    finally:
        os.unlink(path)

    # the instance was materialised as its own body, so both are saved
    assert len(back.bodies) == 2
    assert back.feature_stack(body.id).ops() == ["hole"]
    assert back.document_features.ops() == ["pattern_linear"]
    assert len(back.components) == 1 and back.components[0].name == "装配A"
    assert len(back.instances) == 1
    assert back.instances[0]["transform"][0][3] == 0.03
    # and the reloaded history replays (2 base bodies + 1 pattern copy)
    shapes = back.replay_document()
    assert len(shapes) == 3

def test_delete_a_body_feature_and_replay():
    """P32: deleting one per-body feature (hole) and replaying keeps the rest."""
    from scdm import features as FEAT
    from scdm import params as P

    doc = KernelDoc()
    parametric = P.param_box("板", w=20.0, h=20.0, d=20.0)
    body = doc.add_parametric(parametric)
    base = parametric.build(1000.0)
    top = [f for f in K.explore(base, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    sel = FEAT.selector_for(base, top)
    doc.record_feature(body.id, "hole", selector=sel, diameter=5.0, depth=0.0)
    doc.record_feature(body.id, "boss", selector=sel, diameter=6.0, height=4.0)

    with_hole = K.volume(doc.replay_document()[0])
    stack = doc.feature_stack(body.id)
    assert stack.ops() == ["hole", "boss"]
    del stack.features[0]                       # the tree menu does exactly this
    shapes = doc.replay_document(apply=True)
    assert doc.feature_stack(body.id).ops() == ["boss"]
    expect = 0.02 ** 3 + 3.14159265358979 * 0.003 ** 2 * 0.004
    assert K.volume(shapes[0]) == pytest.approx(expect, rel=1e-5)
    assert with_hole < K.volume(shapes[0])

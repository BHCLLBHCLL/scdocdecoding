"""P23: assembly configurations (named visibility/suppression states)."""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _doc():
    doc = KernelDoc()
    a = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="A")
    b = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    ca = doc.add_component("组件A", [a.id])
    cb = doc.add_component("组件B", [b.id])
    return doc, a, b, ca, cb


def test_configuration_captures_and_restores_visibility():
    """asm.config / asm.config_apply -> named states flip visibility back."""
    doc, a, b, ca, cb = _doc()
    ca.visible = False            # user hides component A
    cfg = doc.capture_configuration("仅B")
    assert cfg.hidden_components == [ca.id]
    assert doc.active_configuration is None      # capture does not apply

    ca.visible = True             # user shows it again
    changed = doc.apply_configuration("仅B")
    assert changed >= 1
    assert ca.visible is False and cb.visible is True
    assert doc.active_configuration == cfg.id

    # applying by id works too, and an unknown name changes nothing
    assert doc.apply_configuration(cfg.id) >= 0
    assert doc.apply_configuration("不存在") == 0


def test_configuration_suppresses_bodies_and_overrides_transforms():
    doc, a, b, ca, cb = _doc()
    mat = ((1, 0, 0, 0.05), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    cfg = doc.add_configuration("爆炸", hidden_components=[],
                                suppressed_bodies=[b.id],
                                transforms={ca.id: mat})
    doc.apply_configuration(cfg.name)
    assert b.visible is False and a.visible is True
    assert ca.transform == mat


def test_configurations_survive_scdm_roundtrip():
    """P23: named configurations are part of the saved project."""
    from scdm.io_project import load_scdm, save_scdm

    doc, a, b, ca, cb = _doc()
    ca.visible = False
    doc.capture_configuration("仅B")
    doc.apply_configuration("仅B")
    fd, path = tempfile.mkstemp(suffix=".scdm")
    os.close(fd)
    try:
        save_scdm(path, doc)
        back = load_scdm(path)
    finally:
        os.unlink(path)
    assert [c.name for c in back.configurations] == ["仅B"]
    assert back.active_configuration == back.configurations[0].id
    assert back.configurations[0].hidden_components == [ca.id]
    assert back.component_by_id(ca.id).visible is False

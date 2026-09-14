"""R91/P423: prep.small is the geometry-check wizard, not a placeholder.

The catalog used to list prep.small (小特征 / Defeaturing) without a live entry
and without a handler, so the snapshot counted it as one of two placeholders.
Small-face detection and repair were already covered by repair.check's full H4
check, so this round routes BOTH commands to ONE implementation:

  scdm/scripting.py : op_repair_check and op_prep_small both call _geometry_check
  scdm_gui.py       : _do_repair_check and _do_prep_small both call
                      _run_geometry_check(prefix) - the prefix is the only
                      difference (status wording and the recorded step name)
  scdm/catalog.py   : prep.small joins M4_LIVE

The placeholder list is now exactly ["safety.tab"], which is intentionally an
empty shell (see tests/test_g1.py INTENTIONAL).
"""
from __future__ import annotations

import importlib.util

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")


def test_prep_small_is_live_and_has_one_implementation():
    from scdm.catalog import all_commands, live_commands
    from scdm.scripting import OPS

    ids = {c.id for c in all_commands()}
    assert "prep.small" in ids
    assert "prep.small" in live_commands()      # a set of ids
    assert "prep.small" in OPS and "repair.check" in OPS
    # both are thin wrappers around ONE shared implementation
    from scdm import scripting as S

    for cmd in ("prep.small", "repair.check"):
        assert "_geometry_check" in OPS[cmd].__code__.co_names, cmd
    assert callable(S._geometry_check)


def test_the_only_placeholder_left_is_the_intentional_one():
    from scdm.catalog import all_commands, live_commands

    ids = {c.id for c in all_commands()}
    live = set(live_commands())                  # a set of ids
    assert sorted(ids - live) == ["safety.tab"]


@requires_occ
def test_both_commands_report_the_same_findings():
    """Same body, same counts - only the wording prefix differs (R91)."""
    from scdm import kernel as K
    from scdm.kdoc import KernelDoc
    from scdm.scripting import OPS

    def check(cmd, prefix):
        doc = KernelDoc()
        body = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="盒")
        out, msg = OPS[cmd](doc, {"target": "last"}, 1000.0)
        assert out is body
        assert msg.startswith(prefix + "："), msg
        return msg.split("：", 1)[1]

    a = check("repair.check", "检查几何")
    b = check("prep.small", "小特征")
    assert a == b, (a, b)


@requires_occ
def test_prep_small_replays():
    from scdm import kernel as K
    from scdm.kdoc import KernelDoc
    from scdm.scripting import replay

    doc = KernelDoc()
    doc.add_body(K.make_box(0.02, 0.02, 0.02), name="盒")
    msgs = replay([{"cmd": "prep.small", "opts": {"target": "last"}}],
                  doc, 1000.0)
    assert msgs and msgs[0] == "OK prep.small", msgs
"""P347/R67: weld symbols become a live command - the placeholder is retired.

The model (@@WeldSymbol@@ on a @@Weldment@@) shipped in R53; this round wires the
command, checks that the symbol rides the .scdm manifest, and proves the
placeholder count went from 3 to 2 (a countable snapshot fact).
"""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import beams as BEAMS  # noqa: E402
from scdm import kernel as K  # noqa: E402


def _weldment():
    w = BEAMS.Weldment(profile="i", dims={"h": 100.0, "b": 50.0, "tw": 5.0,
                                          "tf": 7.0})
    w.add_member((0.0, 0.0, 0.0), (0.2, 0.0, 0.0), name="M1")
    w.add_member((0.2, 0.0, 0.0), (0.2, 0.15, 0.0), name="M2")
    return w


def test_p347_the_command_is_live_and_the_placeholder_is_retired():
    from scdm import catalog
    from scdm.catalog import TABS, all_commands, live_commands
    assert "weld.symbol" in live_commands()
    cmd = [c for c in all_commands() if c.id == "weld.symbol"][0]
    assert "占位" not in (cmd.note or "")
    full = set(catalog.M1_LIVE)
    for name in ("M2_LIVE", "M3_LIVE", "M4_LIVE", "M5_LIVE"):
        full |= getattr(catalog, name, set())
    cmds = [c for t in TABS if t.kind == "ribbon"
            for g in t.groups for c in g.commands]
    placeholders = sorted(c.id for c in cmds if c.id not in full)
    assert placeholders == ["prep.small", "safety.tab"]      # was 3, now 2


def test_p347_symbol_rides_the_weldment_and_the_project():
    from scdm.io_project import load_scdm, save_scdm
    from scdm.kdoc import KernelDoc
    doc = KernelDoc()
    weld = _weldment()
    for name, solid in weld.shapes():
        doc.add_body(solid, name=name)
    doc.weldments.append(weld)
    sym = weld.add_symbol(kind="fillet", size=6.0, length=30.0, pitch=100.0,
                          member="M2")
    assert len(weld.symbols) == 1 and sym.kind == "fillet"
    tmp = tempfile.mkdtemp(prefix="p347_")
    try:
        path = os.path.join(tmp, "weld.scdm")
        save_scdm(path, doc)
        back = load_scdm(path)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    out = back.weldments[0]
    assert len(out.symbols) == 1
    assert out.symbols[0].to_dict() == sym.to_dict()
    assert out.symbols[0].member == "M2"
    assert out.symbols[0].pitch == 100.0


def test_p347_symbol_must_point_at_a_real_member():
    weld = _weldment()
    with pytest.raises(K.KernelError):
        weld.add_symbol(kind="fillet", size=5.0, member="M9")
    with pytest.raises(K.KernelError):
        weld.add_symbol(kind="laser", size=5.0, member="M1")
    empty = BEAMS.Weldment()
    with pytest.raises(K.KernelError):
        empty.add_symbol(kind="fillet", size=5.0, member="M1")
    # a valid symbol attaches to the member and can be counted
    weld.add_symbol(kind="groove", size=8.0, member="M1")
    assert [s.member for s in weld.symbols] == ["M1"]
    assert [s.kind for s in weld.symbols] == ["groove"]

"""FA: reverse-engineered ACIS save-worklist (FIFO) emitter tests.

The official writer (SpaACIS.dll api_save_entity_list) keeps a FIFO worklist;
a FIFO simulation seeded at the body reproduces the official box.scdoc record
order exactly (see references/disasm/verify_sab_order.py).  These tests
verify the emitter's own streams reproduce that invariant, and that the
round-trip still opens (self-read).
"""
from __future__ import annotations

import io
import os
import tempfile

import pytest

from scdm import kernel as K
from scdm import sab_emit
from scdm import scdoc_write as W
from scdm.document import load_scdoc
from scdm.import_sab import import_scdoc_bundle

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def _items_for(shapes):
    items = []
    for s in shapes:
        info = W._cyl_info(s)
        if info is not None:
            items.append(("cyl", info))
        else:
            items.append(("planar",) + W._extract_solid(s))
    return items


def _assert_fifo_invariant(sab_bytes, label):
    """Records written in index order == FIFO pop order; the official writer
    seeds the worklist with every body (api_save_entity_list), one per body."""
    from scdoc_parser import sab as sab_mod
    sf = sab_mod.tokenize(sab_bytes)
    recs = sf.records
    refs = [[t.value for t in r.tokens if t.kind == "ptr"] for r in recs]
    n = len(recs)
    seeds = [i for i, r in enumerate(recs) if r.kind == "body"]
    assert seeds, f"{label}: no body record found"
    visited = set(seeds)
    queue = list(seeds)
    seq = []
    while queue:
        cur = queue.pop(0)
        seq.append(cur)
        for m in refs[cur]:
            if 0 <= m < n and m not in visited:
                visited.add(m)
                queue.append(m)
    expected = list(range(n))
    assert seq == expected, (
        f"{label}: FIFO pop order != record order; first mismatch at "
        f"{next((i for i, (a, b) in enumerate(zip(seq, expected)) if a != b), None)}")


def test_box_stream_is_fifo():
    sab_bytes, _, _ = W._build_sab(_items_for([K.make_box(0.01, 0.01, 0.01)]))
    _assert_fifo_invariant(sab_bytes, "box")


def test_cyl_stream_is_fifo():
    sab_bytes, _, _ = W._build_sab(_items_for([K.make_cylinder(0.005, 0.01)]))
    _assert_fifo_invariant(sab_bytes, "cyl")


def test_mixed_stream_is_fifo():
    items = _items_for([K.make_box(0.01, 0.01, 0.01),
                        K.make_cylinder(0.005, 0.01)])
    sab_bytes, _, _ = W._build_sab(items)
    _assert_fifo_invariant(sab_bytes, "mixed")


def test_write_scdoc_roundtrip_box():
    from scdm.kdoc import KernelDoc
    doc = KernelDoc()
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        W.write_scdoc(path, doc, name="box")
        k2 = import_scdoc_bundle(load_scdoc(path))
        assert len(k2.bodies) == 1
        v = K.volume(k2.bodies[0].shape)
        assert abs(v - 1e-6) < 1e-9
    finally:
        os.remove(path)


def test_planar_layout_emitter_matches_handwritten():
    """Phase 1: data-driven LayoutEmitter must reproduce the hand-written
    Makers.make byte stream for a planar body (regression guard)."""
    from scdm import sab_emit as SE

    box = K.make_box(0.01, 0.01, 0.01)
    items = [("planar",) + W._extract_solid(s)
             for s in (K.explore(box, "solid") or [box])]
    ref = SE.Worklist().run([("body", 0)], SE.Makers(items))
    layouts = SE._planar_layouts()
    out = SE.Worklist().run([("body", 0)],
                            SE.LayoutEmitter(SE.Makers(items), layouts))
    assert ref == out, "LayoutEmitter diverged from Makers.make"
    # the emitter must cover all planar topology kinds
    for k in ("body", "lump", "shell", "face", "loop", "coedge", "edge",
              "vertex", "point", "plane", "straight"):
        assert k in layouts, f"planar layout missing for {k}"


def _roundtrip_bodies(fn):
    from scdm.document import load_scdoc as _ls
    from scdm.import_sab import import_scdoc_bundle as _ib
    from scdm.kdoc import KernelDoc
    import tempfile
    doc = KernelDoc()
    doc.add_body(fn(), name="S")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        W.write_scdoc(path, doc, name="s")
        k2 = _ib(_ls(path))
        return len(k2.bodies)
    finally:
        os.remove(path)


def test_sphere_and_torus_roundtrip_via_facets():
    """Phase 2: closed-surface bodies fall back to a facet-mesh body on
    self-read (official SpaceClaim opens them as true B-rep bodies)."""
    assert _roundtrip_bodies(lambda: K.make_sphere(0.01)) == 1
    assert _roundtrip_bodies(lambda: K.make_torus(0.02, 0.005)) == 1

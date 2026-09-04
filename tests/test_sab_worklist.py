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


def test_intcurve_cluster_structure():
    """Phase 3/4: the B-spline edge-curve cluster reproduces the official
    intcurve-curve token pattern (loft.scdoc reference)."""
    from scdm import sab_emit as SE
    from scdoc_parser import sab as sab_mod, opc
    import zipfile

    # official reference cluster (loft: degree-1 seam curve, 2 poles)
    z = zipfile.ZipFile("references/golden/ref_tet.scdoc")  # header donor
    data = None
    import os
    loft = "references/golden/loft.scdoc"
    if os.path.exists(loft):
        data = zipfile.ZipFile(loft).read(
            "SpaceClaim/Geometry/part1bodies.sab")
    assert data is not None, "loft reference missing (generate via make_official_ref)"
    sf = sab_mod.tokenize(data)
    ic = next(r for r in sf.records if r.kind == "intcurve")
    nxt = min((r for r in sf.records if r.index > ic.index
               and r.kind not in ("intcurve", "exactcur", "nubs",
                                  "null_surface", "nullbs", "ref", "spline",
                                  "pcurve", "exppc")),
              key=lambda r: r.index)
    header = data[:sf.records[0].offset]
    END = bytes([0x0D, 16]) + b"End-of-ACIS-data"

    ours = SE.intcurve_cluster_bytes(
        1, [0.0, 1.0], [1, 1],
        [(1e-05, 0.0, 0.0), (2e-05, 0.0, 2e-05)], exactcur_int=0)
    sf2 = sab_mod.tokenize(header + ours + END)
    r2 = sf2.records[0]
    assert r2.kind == "intcurve"
    t = [(x.kind, x.value if not isinstance(x.value, tuple) else
          tuple(round(v, 9) for v in x.value)) for x in r2.tokens]
    # flattened official prefix (tokenizer stops at 0x0F mark)
    assert t[:6] == [('ptr', -1), ('int', -1), ('int', -1), ('ptr', -1),
                     ('flag_b', None), ('mark0f', None)]
    # nested subtypes are visible as records in the flattened view
    kinds = [x.kind for x in sf2.records]
    assert kinds[:6] == ["intcurve", "exactcur", "nubs", "null_surface",
                         "null_surface", "nullbs"], kinds[:6]
    # nubs payload: degree 1, open, 2 knots (0,1),(1,1), 2 poles
    nubs = next(x for x in sf2.records if x.kind == "nubs")
    nt = [x.value for x in nubs.tokens]
    assert nt[0] == 1 and nt[2] == 2           # degree, #knots
    assert (nt[3], nt[4]) == (0.0, 1) and (nt[5], nt[6]) == (1.0, 1)
    assert len(nt) == 9 and nt[7] == (1e-05, 0.0, 0.0)
    assert nt[8] == (2e-05, 0.0, 2e-05)        # poles as vec3 pairs


def test_spline_surface_cluster_replay():
    """Phase 4: the spline-surface cluster builder reproduces the official
    both record (spline.scdoc face surface) token-for-token, including the
    knot mult convention (stored endpoint mult = standard - 1), the pole grid
    (v-slowest, x,y,z,w) and the fitol/crossing tail."""
    from scdm import sab_emit as SE
    from scdoc_parser import sab as sab_mod, opc
    import zipfile

    z = zipfile.ZipFile("references/golden/spline.scdoc")
    data = z.read("SpaceClaim/Geometry/part1bodies.sab")
    sff = sab_mod.tokenize(data)
    header = data[:sff.records[0].offset]
    END = bytes([0x0D, 16]) + b"End-of-ACIS-data"
    off_both = next(r for r in sff.records if r.kind == "both")
    tk = off_both.tokens
    nu, nv = tk[4].value, tk[5].value
    i = 6
    uk, um, vk, vm = [], [], [], []
    for _ in range(nu):
        uk.append(tk[i].value); um.append(tk[i+1].value); i += 2
    for _ in range(nv):
        vk.append(tk[i].value); vm.append(tk[i+1].value); i += 2
    n_poles = (sum(um) - 2 + 1) * (sum(vm) - 1 + 1)  # deg_u=2, deg_v=1
    poles = []
    for _ in range(n_poles):
        poles.append((tk[i].value, tk[i+1].value, tk[i+2].value, tk[i+3].value))
        i += 4
    assert tk[i].kind == "double" and tk[i].value == 0.0  # fitol marker
    ours = SE.spline_surface_cluster_bytes(2, 1, uk, um, vk, vm, poles,
                                           sense=0x0A)
    sf2 = sab_mod.tokenize(header + ours + END)
    my = [(t.kind, t.value if not isinstance(t.value, tuple) else
           tuple(round(x, 15) for x in t.value)) for t in
          next(r for r in sf2.records if r.kind == "both").tokens]
    off = [(t.kind, t.value if not isinstance(t.value, tuple) else
            tuple(round(x, 15) for x in t.value)) for t in off_both.tokens]
    assert my == off


def test_tolerant_topology_records():
    """Pass-through classes: tvertex/tedge/tcoedge builders reproduce the
    official SampleModel4 tolerant-topology token layout."""
    from scdm import sab_emit as SE
    from scdoc_parser import sab as sab_mod, opc
    import zipfile

    src = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels\SampleModel4.scdoc"
    if not __import__("os").path.exists(src):
        import pytest
        pytest.skip("SampleModel4 not installed")
    data = zipfile.ZipFile(src).read("SpaceClaim/Geometry/allpartbodies.sab")
    sf = sab_mod.tokenize(data)
    header = data[:sf.records[0].offset]
    END = bytes([0x0D, 16]) + b"End-of-ACIS-data"

    class FakeWL:
        def __init__(self, m):
            self.m = m

        def ref(self, k):
            return self.m.get(k, -1)

    # tvertex replay
    tv = next(r for r in sf.records if r.kind == "tvertex")
    m = {"e": tv.tokens[4].value, "p": tv.tokens[5].value}
    ours = SE.tvertex_record(FakeWL(m), "e", "p", tv.tokens[6].value)
    r2 = sab_mod.tokenize(header + ours + END).records[0]
    assert [(t.kind, t.value) for t in r2.tokens] == \
        [(t.kind, t.value) for t in tv.tokens]
    assert r2.chain == [("tvertex", SE.CID_TVERTEX)]

    # tcoedge: chain + coedge tokens + pcurve ptr + (t0, t1) + flag
    tc = next(r for r in sf.records if r.kind == "tcoedge")
    toks = tc.tokens
    assert toks[10].kind == "ptr"          # pcurve slot
    assert toks[11].kind == "double" and toks[12].kind == "double"
    assert toks[13].kind == "flag_b"       # trailing flag
    # parser decode: t_range populated
    from scdoc_parser import topology
    model = topology.SabModel(sf)
    tce = next(e for e in model.of_kind("tcoedge"))
    assert tce.t_range is not None and len(tce.t_range) == 2
    tve = next(e for e in model.of_kind("tvertex"))
    assert tve.tolerance is not None
    ted = next(e for e in model.of_kind("tedge"))
    assert ted.tolerance is not None and ted.v1 is not None

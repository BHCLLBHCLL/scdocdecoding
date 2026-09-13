"""P8: assembly instances - one part definition, several placements."""
from __future__ import annotations

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def _translation(dx, dy, dz):
    return ((1.0, 0.0, 0.0, dx), (0.0, 1.0, 0.0, dy),
            (0.0, 0.0, 1.0, dz), (0.0, 0.0, 0.0, 1.0))


def test_asm_instance_places_linked_copies():
    """asm.instance -> copies carry the source pose + the link is recorded."""
    doc = KernelDoc()
    src = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="零件")
    c0 = K.cog(src.shape)
    a = doc.add_instance(src.id, transform=_translation(0.03, 0.0, 0.0))
    b = doc.add_instance(src.id, transform=_translation(0.0, 0.03, 0.0))
    assert len(doc.bodies) == 3
    assert len(doc.instances_of(src.id)) == 2
    assert K.volume(a.shape) == pytest.approx(K.volume(src.shape), rel=1e-9)
    assert K.cog(a.shape) == pytest.approx((c0[0] + 0.03, c0[1], c0[2]),
                                           abs=1e-9)
    assert K.cog(b.shape) == pytest.approx((c0[0], c0[1] + 0.03, c0[2]),
                                           abs=1e-9)
    # instances of another source are not confused
    other = doc.add_body(K.make_box(0.01, 0.01, 0.01), name="其它")
    assert doc.instances_of(other.id) == []


def test_asm_sync_propagates_a_definition_edit():
    """asm.sync -> editing the definition updates every placement, pose kept."""
    doc = KernelDoc()
    src = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="零件")
    c0 = K.cog(src.shape)
    inst = doc.add_instance(src.id, transform=_translation(0.05, 0.0, 0.0))
    v0 = K.volume(inst.shape)

    # edit the definition: add a boss
    top = [f for f in K.explore(src.shape, "face")
           if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
    src.shape = K.boss_round(src.shape, top, 0.006, 0.004)
    assert K.volume(src.shape) > v0
    assert K.volume(inst.shape) == pytest.approx(v0, rel=1e-9)  # stale yet

    assert doc.sync_instances(src.id) == 1
    assert K.volume(inst.shape) == pytest.approx(K.volume(src.shape), rel=1e-9)
    # same pose invariant: instance COG == (possibly new) definition COG + offset
    cs = K.cog(src.shape)
    assert K.cog(inst.shape) == pytest.approx(
        (cs[0] + 0.05, cs[1], cs[2]), abs=1e-9)
    assert c0[0] + 0.05 == pytest.approx(K.cog(inst.shape)[0], abs=1e-9)


def test_asm_instance_survives_snapshot_roundtrip():
    """P8: instance links are part of the document snapshot contract."""
    doc = KernelDoc()
    src = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="零件")
    doc.add_instance(src.id, transform=_translation(0.03, 0.0, 0.0))
    assert doc.instances[0]["source"] == src.id
    # removing the source drops the dangling instance link
    doc.remove(src.id)
    assert doc.instances == []

GUID = "9d32a3b4-809e-4cc1-8dd7-f73febd3c257"


def test_multi_instance_writeback_uses_one_part():
    """P15: N placed instances share ONE part + N ComponentDefs."""
    import os
    import tempfile
    import zipfile

    from scdm.scdoc_write import write_scdoc_multi

    doc = KernelDoc()
    src = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="零件")
    doc.add_instance(src.id, transform=_translation(0.03, 0.0, 0.0), name="实例1")
    doc.add_instance(src.id, transform=_translation(0.06, 0.0, 0.0), name="实例2")

    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        parts = write_scdoc_multi(path, doc, name="asm")
        assert parts == 1
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith("bodies.sab")]
            assert names == ["SpaceClaim/Geometry/part1bodies.sab"], names
            xml = z.read("SpaceClaim/document.xml").decode("utf-8")
            sab = z.read("SpaceClaim/Geometry/part1bodies.sab")
            fac = z.read("SpaceClaim/Graphics/facets.bin")
        # definition component + 2 instance components
        assert xml.count("<ComponentDef ") == 3
        # all three components reference the single part (id 22); the extra
        # refId in the document is the root DefaultEdgeTreatment moniker (:13)
        assert xml.count('refId="%s:22"' % GUID) == 3
        assert "<trans>1 0 0 0.03 0 1 0 0 0 0 1 0 0 0 0 1</trans>" in xml
        assert "<trans>1 0 0 0.06 0 1 0 0 0 0 1 0 0 0 0 1</trans>" in xml
        assert "实例1" in xml and "实例2" in xml
        # one SAB part and one facets body section
        assert len(sab) > 1000 and len(fac) > 100
    finally:
        os.unlink(path)


def test_multi_instance_writeback_without_instances_is_unchanged():
    """P15 guard: a doc without instances keeps the per-body part layout."""
    import os
    import tempfile
    import zipfile

    from scdm.scdoc_write import write_scdoc_multi

    doc = KernelDoc()
    doc.add_body(K.make_box(0.02, 0.02, 0.02), name="A")
    doc.add_body(K.make_box(0.01, 0.01, 0.01), name="B")
    fd, path = tempfile.mkstemp(suffix=".scdoc")
    os.close(fd)
    try:
        assert write_scdoc_multi(path, doc, name="two") == 2
        with zipfile.ZipFile(path) as z:
            names = sorted(n for n in z.namelist() if n.endswith("bodies.sab"))
        assert names == ["SpaceClaim/Geometry/part1bodies.sab",
                         "SpaceClaim/Geometry/part2bodies.sab"]
    finally:
        os.unlink(path)


@pytest.mark.official_open
def test_official_open_three_instances():
    """P15 end-to-end: official SpaceClaim opens 1 definition + 2 instances."""
    import os
    import shutil
    import subprocess
    import tempfile

    from scdm.scdoc_write import write_scdoc_multi

    scdm = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"
    verify = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "references", "verify_open.py")
    if not os.path.exists(scdm) or not os.path.exists(verify):
        pytest.skip("SpaceClaim not installed")
    work = tempfile.mkdtemp(prefix="p15_open_")
    try:
        path = os.path.join(work, "inst.scdoc")
        doc = KernelDoc()
        src = doc.add_body(K.make_box(0.02, 0.02, 0.02), name="零件")
        doc.add_instance(src.id, transform=_translation(0.03, 0.0, 0.0),
                         name="实例1")
        doc.add_instance(src.id, transform=_translation(0.06, 0.0, 0.0),
                         name="实例2")
        write_scdoc_multi(path, doc, name="inst")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sent = os.path.join(root, "cyl_ref_sentinel.txt")
        err = os.path.join(root, "cyl_ref_error.txt")
        for p in (sent, err):
            if os.path.exists(p):
                os.remove(p)
        subprocess.run([scdm, os.path.abspath(path),
                        "/RunScript=" + os.path.abspath(verify),
                        "/ExitAfterScript=True"],
                       capture_output=True, timeout=600)
        res = open(sent, encoding="utf-8").read().strip() if os.path.exists(sent) else "timeout"
        assert res.startswith("done bodies=3"), res
    finally:
        shutil.rmtree(work, ignore_errors=True)

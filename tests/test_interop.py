"""H1: interoperability format matrix (kernel-level).

Every format writer gets a reader roundtrip check; the scdoc writer's SAB is
additionally checked against the official SabSatConverter when present.
"""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def _box():
    return K.make_box(0.01, 0.02, 0.03)


@pytest.fixture()
def tmp_dir():
    d = tempfile.mkdtemp(prefix="scdm_it_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_iges_roundtrip(tmp_dir):
    p = str(os.path.join(tmp_dir, "b.igs"))
    K.write_iges(_box(), p)
    b = K.read_iges(p)
    assert abs(K.volume(b) - 6e-6) < 1e-12


def test_obj_roundtrip(tmp_dir):
    p = str(os.path.join(tmp_dir, "b.obj"))
    K.write_obj(_box(), p)
    ob = K.read_obj(p)
    assert len(K.explore(ob, "face")) >= 6


def test_3mf_roundtrip(tmp_dir):
    p = str(os.path.join(tmp_dir, "b.3mf"))
    K.write_3mf(_box(), p)
    t = K.read_3mf(p)
    assert len(K.explore(t, "face")) >= 6


def test_stl_roundtrip(tmp_dir):
    p = str(os.path.join(tmp_dir, "b.stl"))
    K.write_stl(_box(), p)
    t = K.read_stl(p)
    assert len(K.explore(t, "face")) >= 6


def test_vrml_write(tmp_dir):
    p = str(os.path.join(tmp_dir, "b.wrl"))
    K.write_vrml(_box(), p)
    assert os.path.getsize(p) > 100


@pytest.mark.official_gate
def test_scdoc_official_restore(tmp_dir):
    """Our SAB stream must restore in the official SabSatConverter when
    SpaceClaim is installed."""
    conv = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
    if not os.path.exists(conv):
        pytest.skip("SabSatConverter not installed")
    import subprocess
    import zipfile

    from scdm.kdoc import KernelDoc
    from scdm.scdoc_write import write_scdoc

    doc = KernelDoc()
    doc.add_body(_box(), name="B")
    p = str(os.path.join(tmp_dir, "b.scdoc"))
    write_scdoc(p, doc, name="b")
    sab = zipfile.ZipFile(p).read("SpaceClaim/Geometry/part1bodies.sab")
    ps = str(os.path.join(tmp_dir, "b.sab"))
    open(ps, "wb").write(sab)
    out = str(os.path.join(tmp_dir, "b.sat"))
    subprocess.run([conv, "-i", ps, "-o", out], capture_output=True)
    assert os.path.exists(out), "official restore failed"


def _official_sab_restore(tmp_dir, shape, name):
    """Write shape -> .scdoc, extract the SAB, run the official
    SabSatConverter (ACIS kernel) on it: rc=0 and a non-empty SAT mean the
    official kernel accepted the stream."""
    conv = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
    if not os.path.exists(conv):
        pytest.skip("SabSatConverter not installed")
    import subprocess
    import zipfile

    from scdm.kdoc import KernelDoc
    from scdm.scdoc_write import write_scdoc

    doc = KernelDoc()
    doc.add_body(shape, name=name)
    p = str(os.path.join(tmp_dir, name + ".scdoc"))
    write_scdoc(p, doc, name=name)
    sab = zipfile.ZipFile(p).read("SpaceClaim/Geometry/part1bodies.sab")
    ps = str(os.path.join(tmp_dir, name + ".sab"))
    open(ps, "wb").write(sab)
    out = str(os.path.join(tmp_dir, name + ".sat"))
    r = subprocess.run([conv, "-i", ps, "-o", out], capture_output=True)
    assert os.path.exists(out) and os.path.getsize(out) > 500, (
        "official restore failed: rc=%s %s" % (
            r.returncode, r.stderr.decode(errors="ignore")[:200]))


@pytest.mark.official_gate
def test_official_restore_filleted_box(tmp_dir):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE
    box = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
    ex = TopExp_Explorer(box, TopAbs_EDGE)
    f = BRepFilletAPI_MakeFillet(box)
    for _ in range(4):
        f.Add(3.0, ex.Current())
        ex.Next()
    _official_sab_restore(tmp_dir, f.Shape(), "fillet")


@pytest.mark.official_gate
def test_official_restore_holed_box(tmp_dir):
    from OCC.Core.BRepPrimAPI import (BRepPrimAPI_MakeBox,
                                      BRepPrimAPI_MakeCylinder)
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.gp import gp_Ax2, gp_Pnt, gp_Dir
    cut = BRepAlgoAPI_Cut(
        BRepPrimAPI_MakeBox(20, 20, 20).Shape(),
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(10, 10, -10), gp_Dir(0, 0, 1)), 3.0, 40.0).Shape())
    _official_sab_restore(tmp_dir, cut.Shape(), "hole")


@pytest.mark.official_gate
def test_official_restore_cone(tmp_dir):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
    _official_sab_restore(tmp_dir,
                          BRepPrimAPI_MakeCone(8.0, 3.0, 30.0).Shape(),
                          "cone")


@pytest.mark.official_gate
def test_official_restore_loft_bcur(tmp_dir):
    """Smooth loft: intcurve clusters (bcur edges) through the official
    ACIS kernel."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCC.Core.gp import gp_Pnt
    w1 = BRepBuilderAPI_MakePolygon(
        gp_Pnt(0, 0, 0), gp_Pnt(10, 0, 0), gp_Pnt(10, 10, 0),
        gp_Pnt(0, 10, 0), True).Wire()
    w2 = BRepBuilderAPI_MakePolygon(
        gp_Pnt(5, 5, 25), gp_Pnt(15, 5, 25), gp_Pnt(15, 15, 25),
        gp_Pnt(5, 15, 25), True).Wire()
    loft = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    loft.AddWire(w1)
    loft.AddWire(w2)
    _official_sab_restore(tmp_dir, loft.Shape(), "loft")

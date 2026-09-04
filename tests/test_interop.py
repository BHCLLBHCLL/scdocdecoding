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

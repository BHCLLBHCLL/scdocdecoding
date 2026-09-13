"""P0: single-body official-open regression. TODO-9 covered the assembly case
only; the single-body claim lived in DEV_SUMMARY as a manual note.

Marked ``official_open`` -> deselected by default (needs SpaceClaim.exe, ~2 min)."""
from __future__ import annotations

import os
import subprocess
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402
from scdm.scdoc_write import write_scdoc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCDM = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"
VERIFY = os.path.join(ROOT, "references", "verify_open.py")
SENT = os.path.join(ROOT, "cyl_ref_sentinel.txt")
ERR = os.path.join(ROOT, "cyl_ref_error.txt")


@pytest.mark.official_open
def test_official_open_single_body_bodies_one():
    """A single-box .scdoc written by us must open in official SpaceClaim
    with exactly one body (the DEV_SUMMARY claim, now under regression)."""
    if not os.path.exists(SCDM) or not os.path.exists(VERIFY):
        pytest.skip("SpaceClaim not installed")
    work = tempfile.mkdtemp(prefix="scdm_open1_")
    try:
        path = os.path.join(work, "box.scdoc")
        doc = KernelDoc()
        doc.add_body(K.make_box(0.01, 0.01, 0.01), name="box")
        write_scdoc(path, doc, name="box")
        for p in (SENT, ERR):
            if os.path.exists(p):
                os.remove(p)
        subprocess.run([SCDM, os.path.abspath(path),
                        "/RunScript=" + os.path.abspath(VERIFY),
                        "/ExitAfterScript=True"],
                       capture_output=True, timeout=600)
        res = open(SENT, encoding="utf-8").read().strip() if os.path.exists(SENT) else "timeout"
        assert res.startswith("done bodies=1"), res
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)

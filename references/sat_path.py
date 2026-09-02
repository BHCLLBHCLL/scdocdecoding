# -*- coding: utf-8 -*-
"""SAT-path: write SAT text -> official SabSatConverter -> SAB -> scdoc.

This is the officially-compatible scdoc writing path. SabSatConverter.exe
(SpaceClaim installation) does a full ACIS restore + re-save, so the SAB it
emits is in the official save-traversal order — no need to replicate the
binary interning/ordering rules by hand.

Usage:
  from references.sat_path import write_scdoc_via_sat
  write_scdoc_via_sat(kdoc, 'out.scdoc', name='design')

Verified (SpaceClaim 2019 R3 official open, verify_open.py):
  - box (planar) ................ bodies=1
  - box + cylinder (mixed) ...... bodies=1
  - cylinder (cone layout) ...... coedge topology needs adjustment (todo)
"""
from __future__ import annotations

import os
import subprocess
import zipfile
from typing import Optional

SAB_SAT_CONVERTER = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
TEMPLATE = "box.scdoc"  # official scdoc used for the non-geometry package parts


def converter_available() -> bool:
    return os.path.exists(SAB_SAT_CONVERTER)


def sat_to_sab(sat_text: str, workdir: Optional[str] = None) -> bytes:
    """Convert SAT text to SAB bytes via the official SabSatConverter."""
    wd = workdir or os.getcwd()
    sat_path = os.path.join(wd, "_satpath_tmp.sat")
    sab_path = os.path.join(wd, "_satpath_tmp.sab")
    with open(sat_path, "w") as f:
        f.write(sat_text)
    if os.path.exists(sab_path):
        os.remove(sab_path)
    r = subprocess.run([SAB_SAT_CONVERTER, "-i", sat_path, "-o", sab_path],
                       capture_output=True, text=True, timeout=60)
    if not os.path.exists(sab_path):
        raise RuntimeError("SabSatConverter failed: %s" % r.stdout[-200:])
    with open(sab_path, "rb") as f:
        data = f.read()
    os.remove(sat_path)
    os.remove(sab_path)
    return data


def write_scdoc_via_sat(kdoc, path: str, name: str = "design",
                        template: Optional[str] = None) -> None:
    """Write a native .scdoc through the SAT -> SabSatConverter path."""
    from scdm.sat_write import write_sat
    tpl = template or TEMPLATE
    if not os.path.exists(tpl):
        # fall back to the golden reference next to this file
        here = os.path.dirname(os.path.abspath(__file__))
        tpl = os.path.join(here, "golden", "ref_tet.scdoc")
    sat = write_sat(kdoc, name=name)
    sab = sat_to_sab(sat)
    src = zipfile.ZipFile(tpl)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            if n.endswith(".sab"):
                out.writestr(n, sab)
            else:
                out.writestr(n, src.read(n))

"""Capability gates so the suite degrades to skips (never collection
errors) on machines without the optional engines (P0-3).

Kernel tests gate themselves via `pytest.importorskip("OCC")` or
`pytestmark = skipif(not K.available())`; this conftest adds:
  * the `official_gate` marker — skips unless the installed SpaceClaim
    2019 R3 SabSatConverter.exe is present (headless official-kernel
    acceptance of written SAB streams);
  * a defensive skip for any test explicitly marked `kernel`.
"""
import os

import pytest

OFFICIAL_CONV = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "official_gate: needs installed SpaceClaim SabSatConverter")
    config.addinivalue_line(
        "markers", "kernel: needs pythonocc-core (OCC)")


def pytest_collection_modifyitems(config, items):
    has_conv = os.path.exists(OFFICIAL_CONV)
    try:
        import OCC  # noqa: F401
        has_occ = True
    except Exception:
        has_occ = False
    for item in items:
        if not has_conv and "official_gate" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason="SabSatConverter not installed"))
        if not has_occ and "kernel" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason="pythonocc-core (OCC) not installed"))

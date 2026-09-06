"""Capability gates so the suite degrades to skips (never collection
errors) on machines without the optional engines (P0-3).

Four capability tiers, each with a marker:
  * ``kernel``         — pythonocc-core (OCC) geometry engine
  * ``gui``            — PyQt5 (offscreen-capable widget tests)
  * ``official_gate``  — installed SpaceClaim 2019 R3 SabSatConverter.exe
  * ``official_open``  — installed SpaceClaim.exe (+ RunScript sentinel)

The umbrella ``official`` marker matches any of the two official tiers —
CI runs ``-m "not official"`` so the official-tool gates stay out of the
default pipeline (P0-3: two commands for the non-official gate).
"""
import os

import pytest

OFFICIAL_CONV = r"C:\Program Files\ANSYS Inc\v195\scdm\SabSatConverter.exe"
OFFICIAL_SCDM = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "kernel: needs pythonocc-core (OCC)")
    config.addinivalue_line(
        "markers", "gui: needs PyQt5 (offscreen)")
    config.addinivalue_line(
        "markers", "official_gate: needs installed SpaceClaim SabSatConverter")
    config.addinivalue_line(
        "markers", "official_open: needs installed SpaceClaim.exe "
                   "(RunScript sentinel)")
    config.addinivalue_line(
        "markers", "official: umbrella for official_gate + official_open "
                   "(CI excludes with -m 'not official')")


def _capabilities():
    try:
        import OCC  # noqa: F401
        occ = True
    except Exception:
        occ = False
    try:
        import PyQt5  # noqa: F401
        qt = True
    except Exception:
        qt = False
    return {
        "kernel": occ,
        "gui": qt,
        "official_gate": os.path.exists(OFFICIAL_CONV),
        "official_open": os.path.exists(OFFICIAL_SCDM),
    }


def pytest_collection_modifyitems(config, items):
    caps = _capabilities()
    for item in items:
        # umbrella marker: any official-tier keyword counts
        if ("official_gate" in item.keywords
                or "official_open" in item.keywords):
            item.add_marker(pytest.mark.official)
        for tier, present in caps.items():
            if not present and tier in item.keywords:
                item.add_marker(pytest.mark.skip(
                    reason=f"{tier} capability not installed"))

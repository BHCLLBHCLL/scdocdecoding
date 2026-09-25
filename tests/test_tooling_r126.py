"""R126 A-12: the screenshot check also insists that the viewport is not empty.

A recorded image promises to show geometry.  Until now the sidecar said
`3d: true` and nothing checked that anything was drawn - a blank render would
have been recorded just as happily.  `_viewport_ink` counts the pixels that are
not the flat viewport background, the sidecar records the number, and a recorded
image whose viewport was empty is stale by definition.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOL = os.path.join(_ROOT, "tools", "gui_screenshot.py")
_SHOTS = os.path.join(_ROOT, "docs", "screenshots")


def _sidecars():
    for name in sorted(os.listdir(_SHOTS)):
        if name.endswith(".json"):
            with open(os.path.join(_SHOTS, name), encoding="utf-8") as fh:
                yield name, json.load(fh)


def _run_tool(*args, timeout=900):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, _TOOL] + list(args), cwd=_ROOT,
                          env=env, capture_output=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def test_a_flat_viewport_has_no_ink_and_a_drawn_one_has():
    """The measurement itself, without a GL context."""
    pytest.importorskip("PyQt5.QtGui")
    from PyQt5.QtGui import QImage
    sys.path.insert(0, _ROOT)
    from tools.gui_screenshot import _viewport_ink

    flat = QImage(60, 40, QImage.Format_RGB32)
    flat.fill(0xFFEFEFEF)
    assert _viewport_ink(flat, (0, 0, 60, 40)) == 0
    assert _viewport_ink(flat, (0, 0, 0, 40)) == 0            # a degenerate rect

    drawn = QImage(60, 40, QImage.Format_RGB32)
    drawn.fill(0xFFEFEFEF)
    for x in range(10, 30):
        for y in range(10, 30):
            drawn.setPixel(x, y, 0xFF1020A0)                  # a blue blob
    ink = _viewport_ink(drawn, (0, 0, 60, 40))
    assert ink == 400, ink
    assert _viewport_ink(drawn, (0, 0, 5, 5)) == 0            # outside the blob


def test_every_recorded_image_says_how_much_it_shows():
    seen = 0
    for name, facts in _sidecars():
        assert "ink" in facts, "%s does not record the viewport ink" % name
        if facts.get("3d"):
            assert facts["ink"] > 0, "%s claims 3D and shows nothing" % name
            seen += 1
    assert seen, "no recorded image claims to have a 3D viewport"


def test_a_recorded_empty_viewport_is_stale():
    room = os.path.join(_ROOT, "_tmp", "shots_r126")
    os.makedirs(room, exist_ok=True)
    png = os.path.join(room, "blank.png")
    made = _run_tool("--out", png, "--demo", "solid", "--size", "600x400")
    assert made.returncode == 0, made.stderr[-500:]
    side = os.path.join(room, "blank.json")
    with open(side, encoding="utf-8") as fh:
        facts = json.load(fh)
    facts["3d"] = True                 # it claims a 3D viewport ...
    facts["ink"] = 0                   # ... that shows nothing
    with open(side, "w", encoding="utf-8") as fh:
        json.dump(facts, fh, ensure_ascii=False)
    proc = _run_tool("--check", "--dir", room)
    assert proc.returncode == 1, (proc.stdout, proc.stderr[-500:])
    assert "视口是空的" in proc.stdout, proc.stdout

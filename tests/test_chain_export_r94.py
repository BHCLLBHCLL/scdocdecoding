"""R94/P431: the two chain labels and the chain line reach BOTH exporters.

R90 put the worst/RSS labels and the chain line on the sheet; the exporters
render dimensions through drawing.dim_text (one source for the wording) and
annotations through annotation.annotation_geometry.  This round pins the
end-to-end path: export a sheet that carries all three objects and read the
files back, asserting the exact tolerance texts and the chain-line text.

Geometry must be untouched by any of it - the body is not even passed to the
exporters, which is the structural reason a label can never move a solid.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")


def _sheet():
    """A tiny view plus the R90 chain objects for one chain."""
    from scdm import dimchain as DC
    from scdm.drawing import Dimension

    dims = [Dimension(view="前", axis="h", value_mm=10.0,
                      a=(0.0, 0.0), b=(0.010, 0.0), tol=0.1),
            Dimension(view="前", axis="h", value_mm=20.0,
                      a=(0.010, 0.0), b=(0.030, 0.0), tol=0.2),
            Dimension(view="前", axis="h", value_mm=30.0,
                      a=(0.030, 0.0), b=(0.060, 0.0), tol=0.3)]
    made = DC.chain_annotations(dims)
    views = [("前", [[(0.0, 0.0), (0.060, 0.0), (0.060, 0.020),
                     (0.0, 0.020), (0.0, 0.0)]])]
    return views, dims, made


def _tmp(suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def test_dxf_carries_both_labels_and_the_chain_line():
    from scdm import drawing as D

    views, dims, made = _sheet()
    path = _tmp(".dxf")
    try:
        D.write_dxf(views, path, dimensions=dims + [made["worst"], made["rss"]],
                    annotations=[made["line"]])
        text = open(path, encoding="utf-8").read()
    finally:
        os.unlink(path)
    assert "60.0 ±0.6" in text, text[:400]
    assert "60.0 ±0.374" in text
    assert "尺寸链 3 段" in text
    # the chain line lands on the NOTE layer, dimensions do not use it
    assert "NOTE" in text


def test_svg_carries_both_labels_and_the_chain_line():
    from scdm import drawing as D

    views, dims, made = _sheet()
    path = _tmp(".svg")
    try:
        D.svg_sheet(views, path, dimensions=dims + [made["worst"], made["rss"]],
                    annotations=[made["line"]], title="链")
        text = open(path, encoding="utf-8").read()
    finally:
        os.unlink(path)
    assert "60.0 ±0.6" in text
    assert "60.0 ±0.374" in text
    assert "尺寸链 3 段" in text


@requires_occ
def test_exporting_never_touches_the_body():
    from scdm import dimchain as DC
    from scdm import drawing as D
    from scdm import kernel as K

    body = K.make_box(0.06, 0.02, 0.01)
    before = (K.volume(body), K.bounding_box(body))
    views, _dims, made = _sheet()
    path = _tmp(".svg")
    try:
        D.svg_sheet(views, path, annotations=[made["line"]])
    finally:
        os.unlink(path)
    after = (K.volume(body), K.bounding_box(body))
    assert after[0] == pytest.approx(before[0], rel=1e-12)
    for i in range(3):
        assert after[1][0][i] == pytest.approx(before[1][0][i], abs=1e-12)
        assert after[1][1][i] == pytest.approx(before[1][1][i], abs=1e-12)
"""R90/P422: one chain, two stacked labels (worst + RSS) and a chain line.

dimchain.stack_up already produced both tolerances; this round puts them ON
THE SHEET: dim_text renders each label (rule 84), the two labels share the
chain sum and differ only in tolerance, they are offset so they do not overlap,
and the chain line is an annotation LEADER - NOTE layer, no geometry, so the
body's bounding box and volume cannot change because of it.
"""
from __future__ import annotations

import importlib.util
import math

import pytest

requires_occ = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, reason="kernel absent")


def _chain():
    from scdm.drawing import Dimension

    # three contiguous segments, 10 / 20 / 30 mm with +-0.1 / 0.2 / 0.3 mm
    return [Dimension(view="前", axis="h", value_mm=10.0,
                      a=(0.0, 0.0), b=(0.010, 0.0), tol=0.1),
            Dimension(view="前", axis="h", value_mm=20.0,
                      a=(0.010, 0.0), b=(0.030, 0.0), tol=0.2),
            Dimension(view="前", axis="h", value_mm=30.0,
                      a=(0.030, 0.0), b=(0.060, 0.0), tol=0.3)]


def test_two_labels_carry_the_two_stack_modes():
    from scdm import dimchain as DC
    from scdm.drawing import dim_text

    made = DC.chain_annotations(_chain())
    worst, rss = made["worst"], made["rss"]
    # the two closed forms, recomputed here: limits 0.6, RSS sqrt(0.14)
    assert worst.tol == pytest.approx(0.6, rel=1e-12)
    assert rss.tol == pytest.approx(math.sqrt(0.1 ** 2 + 0.2 ** 2 + 0.3 ** 2),
                                    rel=1e-12)
    assert worst.value_mm == rss.value_mm == pytest.approx(60.0, rel=1e-12)
    texts = made["texts"]
    assert texts[0] == dim_text(worst) and texts[1] == dim_text(rss)
    assert texts[0] != texts[1]
    assert "60.0" in texts[0] and "±0.6" in texts[0]
    assert "±0.374" in texts[1]
    assert made["count"] == 3
    assert made["span_mm"] == pytest.approx(60.0, rel=1e-9)


def test_the_labels_do_not_overlap_and_the_line_is_an_annotation():
    from scdm import dimchain as DC
    from scdm.annotation import annotation_geometry, annotation_layer

    made = DC.chain_annotations(_chain(), gap_mm=8.0)
    worst, rss, line = made["worst"], made["rss"], made["line"]
    assert rss.offset - worst.offset == pytest.approx(0.008, rel=1e-12)
    assert annotation_layer(line) == "NOTE"
    segs, text, at, style = annotation_geometry(line)   # 4-tuple (R56)
    assert "尺寸链 3 段" == text
    assert style["arrow"] == "none" and style["layer"] == "NOTE"
    # the line spans the chain in x and sits above it (y offset > 0)
    xs = [p[0] for seg in segs for p in seg]
    ys = [p[1] for seg in segs for p in seg]
    assert min(xs) == pytest.approx(0.0, abs=1e-12)
    assert max(xs) >= 0.060 - 1e-12
    assert min(ys) > 0.0


def test_a_broken_chain_is_refused_with_the_verdict_numbers():
    from scdm import dimchain as DC
    from scdm.drawing import Dimension

    broken = _chain()
    broken[1].a = (0.020, 0.0)          # 10 mm gap after the first segment
    with pytest.raises(ValueError) as err:
        DC.chain_annotations(broken)
    assert "尺寸链不成立" in str(err.value)
    with pytest.raises(ValueError):
        DC.chain_annotations(_chain(), modes=("worst",))


@requires_occ
def test_annotations_never_touch_the_geometry():
    """The chain line and labels live outside the body (R90 acceptance)."""
    from scdm import dimchain as DC
    from scdm import kernel as K

    body = K.make_box(0.06, 0.02, 0.01)
    before_box = K.bounding_box(body)
    before_vol = K.volume(body)
    made = DC.chain_annotations(_chain())
    # labelling is pure data: nothing here takes the shape as an argument
    assert set(made) == {"worst", "rss", "line", "texts", "span_mm", "count"}
    assert K.volume(body) == pytest.approx(before_vol, rel=1e-12)
    after_box = K.bounding_box(body)
    for i in range(3):
        assert after_box[0][i] == pytest.approx(before_box[0][i], abs=1e-12)
        assert after_box[1][i] == pytest.approx(before_box[1][i], abs=1e-12)
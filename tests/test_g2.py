"""G2 series unit tests (kernel-level, GUI-agnostic)."""
from __future__ import annotations

import numpy as np
import pytest

from scdm import kernel as K

pytestmark = pytest.mark.skipif(not K.available(), reason="pythonocc-core required")


def test_edge_polyline_box_edge():
    box = K.make_box(10 / 1000, 10 / 1000, 10 / 1000)
    edges = K.explore(box, "edge")
    assert edges
    pts = K.edge_polyline(edges[0], deflection=1e-4)
    assert len(pts) >= 2
    d = [abs(a - b) for a, b in zip(pts[0], pts[-1])]
    assert max(d) > 1e-3 or len(pts) > 2  # endpoints differ (non-degenerate)


def test_edge_polyline_invalid_returns_empty():
    assert K.edge_polyline(None) == []

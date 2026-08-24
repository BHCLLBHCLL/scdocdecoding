"""M3 sketch tests: 2D constraint solver + closed-loop extrusion."""
from __future__ import annotations

import unittest

import scdm.sketch as S
from scdm import kernel as K


class ConstraintSolverTests(unittest.TestCase):
    def test_distance(self):
        pts = [[0.0, 0.0], [10.0, 0.0]]
        S.solve_constraints(pts, [(S.DIST, 0, 1, 5.0)])
        d = ((pts[1][0] - pts[0][0]) ** 2 + (pts[1][1] - pts[0][1]) ** 2) ** 0.5
        self.assertAlmostEqual(d, 5.0, places=6)

    def test_horizontal(self):
        pts = [[0.0, 5.0], [10.0, 0.0]]
        S.solve_constraints(pts, [(S.HORIZONTAL, 0, 1, None)])
        self.assertAlmostEqual(pts[0][1], pts[1][1], places=6)

    def test_vertical(self):
        pts = [[0.0, 5.0], [10.0, 0.0]]
        S.solve_constraints(pts, [(S.VERTICAL, 0, 1, None)])
        self.assertAlmostEqual(pts[0][0], pts[1][0], places=6)

    def test_coincident(self):
        pts = [[3.0, 4.0], [9.0, 8.0]]
        S.solve_constraints(pts, [(S.COINCIDENT, 0, 1, None)])
        self.assertAlmostEqual(pts[0][0], pts[1][0], places=6)
        self.assertAlmostEqual(pts[0][1], pts[1][1], places=6)

    def test_outline_rect(self):
        out = S.sketch_outline([("rect", (0, 0, 0), (10, 10, 0))])
        self.assertEqual(len(out), 4)
        self.assertEqual([int(p[0]) for p in out], [0, 10, 10, 0])

    def test_outline_line_loop(self):
        segs = [
            ("line", (0, 0, 0), (10, 0, 0)),
            ("line", (10, 0, 0), (10, 10, 0)),
            ("line", (10, 10, 0), (0, 10, 0)),
            ("line", (0, 10, 0), (0, 0, 0)),
        ]
        out = S.sketch_outline(segs)
        self.assertIsNotNone(out)
        self.assertEqual(len(out), 4)


@unittest.skipUnless(K.available(), "pythonocc-core not installed")
class SketchExtrudeTests(unittest.TestCase):
    def test_extrude_rect(self):
        sh = S.extrude_sketch([("rect", (0, 0, 0), (0.01, 0.01, 0))], 0.01, "xy")
        self.assertGreater(K.volume(sh), 1e-7)

    def test_extrude_line_loop(self):
        segs = [
            ("line", (0, 0, 0), (0.01, 0, 0)),
            ("line", (0.01, 0, 0), (0.01, 0.01, 0)),
            ("line", (0.01, 0.01, 0), (0, 0.01, 0)),
            ("line", (0, 0.01, 0), (0, 0, 0)),
        ]
        sh = S.extrude_sketch(segs, 0.01, "xy")
        self.assertAlmostEqual(K.volume(sh), 1e-6, places=8)


if __name__ == "__main__":
    unittest.main()

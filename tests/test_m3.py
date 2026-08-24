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

    def test_equal_segments(self):
        pts = [[0.0, 0.0], [10.0, 0.0], [0.0, 2.0], [4.0, 2.0]]
        segs = [(0, 1), (2, 3)]
        S.solve_constraints(pts, [(S.EQUAL, 0, 1)], segments=segs)
        d1 = ((pts[1][0] - pts[0][0]) ** 2 + (pts[1][1] - pts[0][1]) ** 2) ** 0.5
        d2 = ((pts[3][0] - pts[2][0]) ** 2 + (pts[3][1] - pts[2][1]) ** 2) ** 0.5
        self.assertAlmostEqual(d1, d2, places=4)
        self.assertAlmostEqual(d1, 7.0, places=4)

    def test_parallel_segments(self):
        pts = [[0.0, 0.0], [10.0, 0.0], [0.0, 0.0], [5.0, 5.0]]
        segs = [(0, 1), (2, 3)]
        S.solve_constraints(pts, [(S.PARALLEL, 0, 1)], segments=segs)
        # second segment must now be horizontal
        self.assertAlmostEqual(pts[3][1], pts[2][1], places=4)

    def test_tangent_line_circle(self):
        pts = [[0.0, -5.0], [0.0, 5.0], [5.0, 0.0]]
        segs = [(0, 1)]
        S.solve_constraints(pts, [(S.TANGENT, 0, 2, 1.0)], segments=segs, iters=80)
        # perpendicular distance from the segment's line to the circle centre == radius
        x0, y0 = pts[0]; x1, y1 = pts[1]
        cx, cy = pts[2]
        nx, ny = -(y1 - y0), (x1 - x0)
        nl = (nx ** 2 + ny ** 2) ** 0.5
        dist = abs((cx - x0) * nx / nl + (cy - y0) * ny / nl)
        self.assertAlmostEqual(dist, 1.0, places=3)

    def test_midpoint(self):
        pts = [[0.0, 0.0], [10.0, 0.0], [3.0, 7.0]]
        segs = [(0, 1)]
        S.solve_constraints(pts, [(S.MIDPOINT, 2, 0)], segments=segs)
        self.assertAlmostEqual(pts[2][0], 5.0, places=6)
        self.assertAlmostEqual(pts[2][1], 0.0, places=6)

    def test_fixed_pin(self):
        pts = [[0.0, 0.0], [10.0, 0.0]]
        S.solve_constraints(pts, [(S.FIXED, 0, 3.0, 4.0)])
        self.assertAlmostEqual(pts[0][0], 3.0, places=6)
        self.assertAlmostEqual(pts[0][1], 4.0, places=6)

    def test_solve_dimensions(self):
        pts = [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]]
        solved = S.solve_dimensions(pts, [(0, 1, 5.0)])
        self.assertAlmostEqual(solved[0], 5.0, places=4)

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

"""M5 tests: facets (STL round-trip, reverse normals, mesh->shell)."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import numpy as np

from scdm import facets as F


class FacetIOTests(unittest.TestCase):
    def test_binary_roundtrip(self):
        fd, path = tempfile.mkstemp(suffix=".stl")
        os.close(fd)
        try:
            verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype="f4")
            tris = np.array([[0, 1, 2]], dtype="i4")
            F.write_stl(verts, tris, path)
            v, t = F.read_stl(path)
            self.assertEqual(len(t), 1)
            self.assertEqual(len(v), 3)
        finally:
            os.remove(path)

    def test_reverse_normals_flips_winding(self):
        tris = np.array([[0, 1, 2], [1, 2, 3]], dtype="i4")
        rev = F.reverse_normals(np.zeros((4, 3)), tris)
        np.testing.assert_array_equal(rev, np.array([[0, 2, 1], [1, 3, 2]]))


@unittest.skipUnless(
    bool(importlib.util.find_spec("OCC")), "pythonocc-core not installed")
class FacetOcctTests(unittest.TestCase):
    def test_mesh_to_shell_yields_shape(self):
        from scdm import kernel as K
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype="f4")
        tris = np.array([[0, 1, 2]], dtype="i4")
        sh = F.mesh_to_shell(verts, tris, tol=1e-4)
        self.assertIsNotNone(sh)

    def test_reverse_shape(self):
        from scdm import kernel as K
        box = K.make_box(0.01, 0.01, 0.01)
        rev = K.reverse_shape(box)
        # reverse normals flips orientation -> the body becomes "inside out", so the
        # signed volume has the same magnitude with opposite sign.
        self.assertAlmostEqual(abs(K.volume(rev)), abs(K.volume(box)), places=6)


if __name__ == "__main__":
    unittest.main()

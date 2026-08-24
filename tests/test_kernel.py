"""Kernel unit tests. Skip when pythonocc-core is missing."""
from __future__ import annotations

import os
import tempfile
import unittest

from scdm import kernel as K


@unittest.skipUnless(K.available(), "pythonocc-core not installed")
class KernelTests(unittest.TestCase):
    def test_box_volume(self):
        box = K.make_box(0.01, 0.01, 0.01)
        self.assertAlmostEqual(K.volume(box), 1e-6, places=12)

    def test_cylinder_and_fuse(self):
        c1 = K.make_cylinder(0.005, 0.02)
        c2 = K.translate(K.make_cylinder(0.005, 0.02), (0.004, 0, 0))
        fused = K.fuse(c1, c2)
        self.assertGreater(K.volume(fused), K.volume(c1))

    def test_cut_reduces_volume(self):
        box = K.make_box(0.01, 0.01, 0.01)
        cyl = K.make_cylinder(0.002, 0.02, origin=(0.005, 0.005, -0.005))
        hollow = K.cut(box, cyl)
        self.assertLess(K.volume(hollow), K.volume(box))

    def test_pull_face_grows_box(self):
        box = K.make_box(0.01, 0.01, 0.01)
        faces = K.explore(box, "face")
        target = None
        for f in faces:
            n, _c = K.face_normal_center(f)
            if n[2] > 0.9:
                target = f
                break
        self.assertIsNotNone(target)
        pulled = K.pull_face(box, target, 0.01)
        self.assertAlmostEqual(K.volume(pulled), 2e-6, places=10)

    def test_move_translate(self):
        box = K.make_box(0.01, 0.01, 0.01)
        moved = K.translate(box, (0.1, 0, 0))
        c = K.cog(moved)
        self.assertGreater(c[0], 0.05)

    def test_split_plane(self):
        box = K.make_box(0.01, 0.01, 0.01)
        parts = K.split_by_plane(box, (0.005, 0.005, 0.005), (1, 0, 0))
        self.assertGreaterEqual(len(parts), 2)

    def test_fillet(self):
        box = K.make_box(0.01, 0.01, 0.01)
        fil = K.fillet_edges(box, 0.001)
        self.assertLess(K.volume(fil), K.volume(box))

    def test_mirror_pattern(self):
        box = K.make_box(0.01, 0.01, 0.01)
        mir = K.mirror(box, (0, 0, 0), (1, 0, 0))
        self.assertAlmostEqual(K.volume(mir), K.volume(box), places=12)
        pats = K.pattern_linear(box, (0.02, 0, 0), 3)
        self.assertEqual(len(pats), 3)

    def test_step_roundtrip(self):
        box = K.make_box(0.01, 0.01, 0.01)
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        try:
            K.write_step(box, path)
            sh = K.read_step(path)
            self.assertAlmostEqual(K.volume(sh), 1e-6, places=9)
        finally:
            os.remove(path)

    def test_brep_roundtrip(self):
        sph = K.make_sphere(0.005)
        blob = K.dumps_brep(sph)
        sh = K.loads_brep(blob)
        self.assertAlmostEqual(K.volume(sh), K.volume(sph), places=9)

    def test_sketch_prism(self):
        face = K.face_from_polygon([(0, 0, 0), (0.01, 0, 0), (0.01, 0.01, 0), (0, 0.01, 0)])
        solid = K.prism(face, (0, 0, 0.01))
        self.assertAlmostEqual(K.volume(solid), 1e-6, places=10)

    def test_mass_props_cog(self):
        box = K.make_box(0.01, 0.01, 0.01)
        c = K.cog(box)
        self.assertAlmostEqual(c[0], 0.005, places=9)
        self.assertGreater(K.area(box), 0)

    def test_interference(self):
        a = K.make_box(0.01, 0.01, 0.01)
        b = K.translate(K.make_box(0.01, 0.01, 0.01), (0.005, 0, 0))
        self.assertGreater(K.interference_volume(a, b), 0)


@unittest.skipUnless(K.available(), "pythonocc-core not installed")
class ImportSabTests(unittest.TestCase):
    def test_box_scdoc(self):
        from scdm.document import load_scdoc
        from scdm.import_sab import import_scdoc_bundle
        root = os.path.join(os.path.dirname(__file__), "..", "box.scdoc")
        data = load_scdoc(os.path.abspath(root))
        doc = import_scdoc_bundle(data)
        self.assertTrue(doc.bodies)
        vol = K.volume(doc.bodies[0].shape)
        self.assertGreater(vol, 0)


if __name__ == "__main__":
    unittest.main()

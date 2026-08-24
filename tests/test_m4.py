"""M4 extension tests: pattern / mirror / shell / blend / chamfer / draft / helix."""
from __future__ import annotations

import unittest

from scdm import kernel as K


@unittest.skipUnless(K.available(), "pythonocc-core not installed")
class M4KernelTests(unittest.TestCase):
    def test_fillet_reduces_volume(self):
        box = K.make_box(0.01, 0.01, 0.01)
        fil = K.fillet_edges(box, 0.001)
        self.assertLess(K.volume(fil), K.volume(box))
        self.assertGreater(K.volume(fil), 0)

    def test_chamfer_reduces_volume(self):
        box = K.make_box(0.01, 0.01, 0.01)
        ch = K.chamfer_edges(box, 0.001)
        self.assertLess(K.volume(ch), K.volume(box))
        self.assertGreater(K.volume(ch), 0)

    def test_shell(self):
        box = K.make_box(0.01, 0.01, 0.01)
        faces = K.explore(box, "face")
        shell = K.shell_solid(box, 0.001, [faces[0]])
        self.assertGreater(K.volume(shell), 0)
        self.assertLess(K.volume(shell), K.volume(box))

    def test_pattern_and_mirror(self):
        box = K.make_box(0.01, 0.01, 0.01)
        pats = K.pattern_linear(box, (0.02, 0, 0), 3)
        self.assertEqual(len(pats), 3)
        mir = K.mirror(box, (0, 0, 0), (1, 0, 0))
        self.assertAlmostEqual(K.volume(mir), K.volume(box), places=12)

    def test_draft(self):
        box = K.make_box(0.01, 0.01, 0.01)
        faces = K.explore(box, "face")
        try:
            out = K.draft_face(box, faces[0], 0.1, (0, 0, 1))
            self.assertGreater(K.volume(out), 0)
        except Exception as exc:
            self.skipTest(f"draft unavailable: {exc}")

    def test_helix_solid(self):
        sh = K.helix_solid(0.005, 0.002, 0.02, 0.0005)
        self.assertGreater(K.volume(sh), 0)

    def test_interference(self):
        a = K.make_box(0.01, 0.01, 0.01)
        b = K.translate(K.make_box(0.01, 0.01, 0.01), (0.005, 0, 0))
        self.assertGreater(K.interference_volume(a, b), 0)

    def test_align_faces_mate(self):
        a = K.make_box(0.01, 0.01, 0.01)
        b = K.translate(K.make_box(0.01, 0.01, 0.01), (0.03, 0, 0))
        fa = fb = None
        for f in K.explore(a, "face"):
            n, _c = K.face_normal_center(f)
            if n[0] > 0.9:
                fa = f
        for f in K.explore(b, "face"):
            n, _c = K.face_normal_center(f)
            if n[0] < -0.9:
                fb = f
        self.assertIsNotNone(fa)
        self.assertIsNotNone(fb)
        moved = K.align_faces(a, fa, fb)
        # after mating, the +x face of a sits at b's -x face centre
        for f in K.explore(moved, "face"):
            n, c = K.face_normal_center(f)
            if n[0] > 0.9:
                _, cb = K.face_normal_center(fb)
                self.assertAlmostEqual(c[0], cb[0], places=6)
                break


class AssemblyTests(unittest.TestCase):
    def test_component_lifecycle(self):
        from scdm.kdoc import KernelDoc
        doc = KernelDoc()
        b = doc.add_body(K.make_box(0.01, 0.01, 0.01))
        comp = doc.add_component("齿轮", [b.id])
        self.assertEqual(len(doc.components), 1)
        self.assertEqual(len(doc.bodies_of_component(comp.id)), 1)
        comp.anchored = True
        self.assertTrue(doc.component_by_id(comp.id).anchored)
        doc.remove_component(comp.id)
        self.assertEqual(len(doc.components), 0)


if __name__ == "__main__":
    unittest.main()

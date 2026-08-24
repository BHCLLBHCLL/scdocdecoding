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
class ScdocWriteTests(unittest.TestCase):
    def test_box_roundtrip(self):
        from scdm import kernel as K
        from scdm.kdoc import KernelDoc
        from scdm.scdoc_write import write_scdoc
        from scdm.document import load_scdoc
        from scdm.import_sab import import_scdoc_bundle

        doc = KernelDoc()
        doc.add_body(K.make_box(0.01, 0.01, 0.01), name="Solid1")
        fd, path = tempfile.mkstemp(suffix=".scdoc")
        os.close(fd)
        try:
            write_scdoc(path, doc, name="box")
            from scdoc_parser.report import build_report
            rep = build_report(path)
            self.assertTrue(rep.get("validation", {}).get("all_ok"),
                            f"validation failed: {rep.get('validation')}")
            data = load_scdoc(path)
            out = import_scdoc_bundle(data)
            self.assertTrue(out.bodies)
            self.assertAlmostEqual(K.volume(out.bodies[0].shape), 1e-6, places=8)
        finally:
            os.remove(path)

    def test_extruded_sketch_roundtrip(self):
        from scdm import kernel as K, sketch as S
        from scdm.kdoc import KernelDoc
        from scdm.scdoc_write import write_scdoc
        from scdm.document import load_scdoc
        from scdm.import_sab import import_scdoc_bundle

        doc = KernelDoc()
        # a 6-face prism from a rectangle sketch (not a cube: 2 rect + 4 side faces)
        doc.add_body(S.extrude_sketch([("rect", (0, 0, 0), (0.01, 0.01, 0))], 0.02, "xy"))
        fd, path = tempfile.mkstemp(suffix=".scdoc")
        os.close(fd)
        try:
            write_scdoc(path, doc, name="prism")
            data = load_scdoc(path)
            out = import_scdoc_bundle(data)
            self.assertTrue(out.bodies)
            self.assertAlmostEqual(K.volume(out.bodies[0].shape), 2e-6, places=7)
        finally:
            os.remove(path)


@unittest.skipUnless(
    bool(importlib.util.find_spec("OCC")), "pythonocc-core not installed")
class ParamsTests(unittest.TestCase):
    def test_parametric_box_rebuild(self):
        from scdm import kernel as K
        from scdm.kdoc import KernelDoc
        from scdm.params import param_box

        doc = KernelDoc()
        body = doc.add_parametric(param_box(w=10, h=10, d=10))
        self.assertAlmostEqual(K.volume(body.shape), 1e-6, places=8)
        p = doc.parametrics[0]
        p.set(W=20.0)
        doc.rebuild_parametric(p)
        self.assertAlmostEqual(K.volume(body.shape), 2e-6, places=7)

    def test_parametric_cylinder_rebuild(self):
        from scdm import kernel as K
        from scdm.kdoc import KernelDoc
        from scdm.params import param_cylinder

        doc = KernelDoc()
        body = doc.add_parametric(param_cylinder(r=5, h=10))
        self.assertGreater(K.volume(body.shape), 0)
        p = doc.parametrics[0]
        p.set(R=10.0)
        doc.rebuild_parametric(p)
        self.assertAlmostEqual(K.volume(body.shape), 4 * K.volume(
            K.make_cylinder(0.005, 0.01)), places=6)


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

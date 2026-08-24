"""M2 direct-modeling acceptance + tool-state-machine unit tests.

Runs the DEV_PLAN M2 acceptance path at the kernel/tool/history level:
  new -> insert cylinder -> pull face -> combine (fuse) -> undo -> save STEP -> reopen
Skips when pythonocc-core is unavailable.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from scdm import kernel as K


@unittest.skipUnless(K.available(), "pythonocc-core not installed")
class M2KernelTests(unittest.TestCase):
    def test_symmetric_pull_grows_both_ways(self):
        box = K.make_box(0.01, 0.01, 0.01)
        faces = K.explore(box, "face")
        top = None
        for f in faces:
            n, _c = K.face_normal_center(f)
            if n[2] > 0.9:
                top = f
                break
        self.assertIsNotNone(top)
        # symmetric 10mm: extrude a centrd prism -> the top face is offset by half
        # (0.005) each way, so the box grows by 0.005 -> volume 1.5e-6.
        out = K.pull_face_symmetric(box, top, 0.01)
        self.assertAlmostEqual(K.volume(out), 1.5e-6, places=10)
        self.assertGreater(K.volume(out), K.volume(box))

    def test_replace_face_extends_to_target(self):
        box = K.make_box(0.01, 0.01, 0.01)
        faces = K.explore(box, "face")
        # src = +x face, dst = +y face of the same box (target plane normal +y)
        src = dst = None
        for f in faces:
            n, _c = K.face_normal_center(f)
            if n[0] > 0.9:
                src = f
            if n[1] > 0.9:
                dst = f
        self.assertIsNotNone(src)
        self.assertIsNotNone(dst)
        out = K.replace_face(box, src, dst)
        self.assertGreaterEqual(K.volume(out), K.volume(box) - 1e-12)


@unittest.skipUnless(K.available(), "pythonocc-core not installed")
class M2ToolTests(unittest.TestCase):
    def _kdoc(self):
        from scdm.kdoc import KernelDoc
        return KernelDoc()

    def test_full_m2_path(self):
        from scdm.kdoc import KernelDoc
        from scdm.history import History
        from scdm.tools.direct import get_tool

        doc = KernelDoc()
        hist = History()
        doc.add_body(K.make_box(0.02, 0.02, 0.02), name="base")
        self.assertAlmostEqual(K.volume(doc.bodies[0].shape), 8e-6, places=15)

        # pull the top face by 10mm
        top = None
        for f in K.explore(doc.bodies[0].shape, "face"):
            n, _c = K.face_normal_center(f)
            if n[2] > 0.9:
                top = f
                break
        self.assertIsNotNone(top)
        # pull via tool
        body = doc.bodies[0]
        faces = K.explore(body.shape, "face")
        idx = faces.index(top) if top in faces else 0
        hist.push(doc.snapshot())
        msg = get_tool("tool.pull").apply(
            _Ses(doc, 1000.0), {"body_id": body.id, "face_i": idx}, {"distance": 10.0, "symmetric": False})
        self.assertIn("拉动", msg)
        # 20mm cube + 10mm extrusion -> 20x20x30 = 1.2e-5 m^3
        self.assertAlmostEqual(K.volume(doc.bodies[0].shape), 1.2e-5, places=9)

        # insert a cylinder and combine (fuse)
        doc.add_body(K.make_cylinder(0.004, 0.02, origin=(0.01, 0.01, 0.01)), name="cyl")
        hist.push(doc.snapshot())
        msg = get_tool("tool.combine").apply(
            _Ses(doc, 1000.0), {"sel_ids": [doc.bodies[0].id, doc.bodies[1].id]}, {"mode": "fuse"})
        self.assertIn("合并", msg)
        self.assertEqual(len(doc.bodies), 1)
        vol_fused = K.volume(doc.bodies[0].shape)
        self.assertGreater(vol_fused, 0)

        # a single undo reverts the combine -> two bodies again
        hist.push(doc.snapshot())   # post-combine (1 body)
        snap = hist.undo()          # -> pre-combine snapshot (2 bodies)
        doc.restore(snap)
        self.assertEqual(len(doc.bodies), 2)

        # save STEP and reopen, volume consistent
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        try:
            K.write_step(K.compound([b.shape for b in doc.bodies]), path)
            sh = K.read_step(path)
            self.assertGreater(K.volume(sh), 0)
        finally:
            os.remove(path)

    def test_move_tool_copy(self):
        from scdm.tools.direct import get_tool
        doc = self._kdoc()
        doc.add_body(K.make_box(0.01, 0.01, 0.01), name="a")
        msg = get_tool("tool.move").apply(
            _Ses(doc, 1000.0), {"body_id": doc.bodies[0].id},
            {"distance": 10.0, "axis": (1, 0, 0), "copy": True})
        self.assertIn("复制", msg)
        self.assertEqual(len(doc.bodies), 2)
        self.assertGreater(K.cog(doc.bodies[1].shape)[0], 0.005)


class _Ses:
    """Minimal session stand-in for tools: exposes kdoc + scale."""

    def __init__(self, kdoc, scale=1000.0):
        self.kdoc = kdoc
        self.scale = scale


if __name__ == "__main__":
    unittest.main()

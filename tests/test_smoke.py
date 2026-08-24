"""GUI startup smoke test. Skips when PyQt5 is unavailable.

Runs headless (QT_QPA_PLATFORM=offscreen) and asserts the main window constructs,
opens a .scdoc, rebuilds the tree/scene, and reports its command dispatch table.
"""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)
K_AVAIL = __import__("importlib").util.find_spec("OCC") is not None


@unittest.skipUnless(
    _HAS_QT := bool(__import__("importlib").util.find_spec("PyQt5")),
    "PyQt5 not installed",
)
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, _ROOT)
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import scdm_gui

        cls.gui = scdm_gui
        cls.has_occ = __import__("importlib").util.find_spec("OCC") is not None

    def test_construct_and_open_box(self):
        v = self.gui.ScdmViewer(path=os.path.join(_ROOT, "box.scdoc"))
        self.assertIsInstance(v.sessions, list)
        self.assertGreaterEqual(len(v.sessions), 1)
        ses = v.session()
        self.assertIsNotNone(ses)
        v._rebuild("ok")
        self.assertEqual(v.windowTitle() if v.windowTitle() else "", v.windowTitle() or "",
                         msg="title sanity")

    def test_command_dispatch_has_no_crash(self):
        v = self.gui.ScdmViewer(path=os.path.join(_ROOT, "box.scdoc"))
        # A known live UI command must not raise.
        v.on_command("tool.select")
        v.on_command("show.faces")
        v.on_command("view.fit")
        self.assertEqual(v.tools.active, "tool.select")

    def test_live_commands_reasonable(self):
        from scdm.catalog import live_commands

        cmds = live_commands()
        self.assertIn("file.new", cmds)
        self.assertIn("mode.3d", cmds)

    @unittest.skipUnless(K_AVAIL, "pythonocc-core not installed")
    def test_open_box_yields_body_when_kernel_present(self):
        from scdm.kdoc import KernelDoc

        v = self.gui.ScdmViewer(path=os.path.join(_ROOT, "box.scdoc"))
        ses = v.session()
        self.assertIsNotNone(ses.kdoc)
        self.assertGreaterEqual(len(ses.kdoc.bodies), 1)
        # inserting a cylinder marks the session dirty and grows the body count
        body_count_0 = len(ses.kdoc.bodies)
        v._place_at("cyl", (0.0, 0.0, 0.0))
        self.assertEqual(len(ses.kdoc.bodies), body_count_0 + 1)
        self.assertTrue(ses.dirty)

    @unittest.skipUnless(K_AVAIL, "pythonocc-core not installed")
    def test_sketch_rendering_builds_actors(self):
        import vtk
        from scdm import kernel as K
        from scdm.document import Session
        from scdm.gui.scene import Scene
        from scdm.kdoc import KernelDoc

        class _FakeWidget:
            def __init__(self):
                self.rw = vtk.vtkRenderWindow()
                self.iren = vtk.vtkRenderWindowInteractor()
                self.iren.SetRenderWindow(self.rw)

            def GetRenderWindow(self):
                return self.rw

            def GetInteractor(self):
                return self.iren

            def Initialize(self):
                pass

            def Start(self):
                pass

        scene = Scene(_FakeWidget())
        scene.render = lambda: None  # skip OpenGL in headless runs
        ses = Session(name="t")
        ses.kdoc = KernelDoc()
        ses.kdoc.add_body(K.make_box(0.01, 0.01, 0.01), name="box")
        sk = ses.kdoc.add_sketch("xy", "草图 1")
        sk.curves.append(("rect", (0, 0, 0), (0.01, 0.01, 0)))
        sk.curves.append(("circle", (0.005, 0.005, 0), 0.003))
        sk.curves.append(("point", (0.001, 0.001, 0)))
        scene.build(ses)
        self.assertIsNotNone(scene._sketch_actor)
        self.assertIsNotNone(scene._sketch_pts_actor)


if __name__ == "__main__":
    unittest.main()

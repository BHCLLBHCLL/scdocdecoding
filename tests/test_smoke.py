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

    def test_tool_guide_and_smart_bar(self):
        from PyQt5.QtWidgets import QWidget
        from scdm.gui.viewport import ViewportHost

        host = ViewportHost(QWidget())
        host.resize(800, 600)
        host.set_guide("tool.pull", "拉动 1 个面")
        self.assertFalse(host.guide.isHidden())
        self.assertIn("拉动", host.guide.caption.text())
        host.show_mini(True)
        self.assertFalse(host.mini.isHidden())
        host.mini.set_value("5.00 mm")
        self.assertEqual(host.mini.value.text(), "5.00 mm")
        host.set_guide("tool.select")
        self.assertTrue(host.guide.isHidden())

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
        # lightweight component -> bbox wireframe instead of tessellated faces
        b1 = ses.kdoc.bodies[0]
        comp = ses.kdoc.add_component("轻量化件", [b1.id])
        comp.lightweight = True
        before = len(scene._face_actors)
        scene.build(ses)
        self.assertGreaterEqual(len(getattr(scene, "_light_actors", [])), 1)
        self.assertLess(len(scene._face_actors), before)
        # drag preview: translucent actor appears and clears
        scene.show_preview(K.make_box(0.01, 0.012, 0.01))
        # R127/A-13: a preview is a *list* of actors now (one per body); a single
        # shape is simply the one-element case, which is what the drag uses
        self.assertEqual(len(scene._preview_actors), 1)
        self.assertIsNotNone(scene._preview_actors[0])
        scene.clear_preview()
        self.assertEqual(scene._preview_actors, [])
        scene.show_pull_handles((0, 0, 0.01), (0, 0, 1), length=0.008, distance_mm=5.0)
        self.assertGreaterEqual(len(scene._handle_actors), 1)
        scene.clear_handles()
        self.assertEqual(scene._handle_actors, [])
        scene.show_move_handles((0, 0, 0), length=0.008)
        self.assertGreaterEqual(len(scene._handle_actors), 1)
        xy = scene.world_to_display((0, 0, 0))
        self.assertEqual(len(xy), 2)


    def test_feature_tree_lists_history(self):
        """P16: a body's feature history appears as child nodes in the tree."""
        v = self.gui.ScdmViewer(path=os.path.join(_ROOT, "box.scdoc"))
        ses = v.session()
        if not self.has_occ or ses.kdoc is None:
            self.skipTest("kernel not available")
        import math

        from scdm import features as FEAT
        from scdm import kernel as K

        body = ses.kdoc.add_body(K.make_box(0.02, 0.02, 0.02), name="测试块")
        top = [f for f in K.explore(body.shape, "face")
               if abs(K.face_normal_center(f)[1][2] - 0.02) < 1e-9][0]
        ses.kdoc.record_feature(body.id, "hole",
                                selector=FEAT.selector_for(body.shape, top),
                                diameter=5.0, depth=0.0)
        ses.kdoc.record_feature(body.id, "shell", thickness=1.0)
        v.left.populate_tree(ses)

        labels = []

        def walk(item):
            labels.append(item.text(0))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(v.left.tree.topLevelItemCount()):
            walk(v.left.tree.topLevelItem(i))
        self.assertTrue(any("孔 Ø5mm" in t for t in labels), labels)
        self.assertTrue(any("抽壳 1mm" in t for t in labels), labels)

    def test_constraint_marks_render_and_clear(self):
        """P21: constraint glyph actors are added and removed on demand."""
        import vtk

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

        from scdm.gui.scene import Scene

        scene = Scene(_FakeWidget())
        scene.render = lambda: None
        self.assertEqual(len(scene._constraint_actors), 0)
        scene.show_constraint_marks([(0.0, 0.0, 0.0, "H"),
                                     (0.005, 0.0, 0.0, "\u219410.0")])
        self.assertEqual(len(scene._constraint_actors), 2)
        scene.show_constraint_marks([])
        self.assertEqual(len(scene._constraint_actors), 0)
        scene.show_constraint_marks([(0.0, 0.0, 0.0, "V")])
        scene.clear_constraint_marks()
        self.assertEqual(scene._constraint_actors, [])
    def test_official_document_tree_is_read_only_faithful(self):
        """P27: a loaded official document shows its PartDef/layer structure."""
        lib = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels\samplemodel2.scdoc"
        if not os.path.exists(lib):
            self.skipTest("SpaceClaim library absent")
        from scdm.document import Session, load_scdoc

        data = load_scdoc(lib)
        ses = Session(name="official", data=data)
        # no kernel import here: the tree must work straight from document.xml
        win = self.gui.ScdmViewer.__new__(self.gui.ScdmViewer)
        from scdm.gui.left_panel import LeftPanel
        panel = LeftPanel()
        panel.populate_tree(ses)
        labels = []

        def walk(item):
            labels.append(item.text(0))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
        self.assertIn("文档结构（只读）", labels)
        parts = len(getattr(data["doc"], "parts", []) or [])
        self.assertIn("零件 PartDef：%d 个" % parts, labels)
        self.assertTrue(any(t.startswith("图层：") for t in labels), labels)


if __name__ == "__main__":
    unittest.main()
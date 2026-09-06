"""Lightweight-mode GUI regressions (P0-3 follow-up).

The GUI must degrade into an explicit lightweight mode when pythonocc-core
is missing: kernel-only ribbon buttons disabled, a startup status hint, and
an honest "lightweight" reason on tool activation — NOT the misleading
"M2 未实现" (the M2 tools are implemented; that env just lacks OCC).
"""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

QT = __import__("importlib").util.find_spec("PyQt5") is not None


@unittest.skipUnless(QT, "PyQt5 not installed")
class LightweightModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        import scdm_gui
        cls.gui = scdm_gui
        from scdm.catalog import M2_LIVE, M3_LIVE, M4_LIVE, M5_LIVE
        cls.kernel_tool_ids = M2_LIVE | M3_LIVE | M4_LIVE | M5_LIVE

    def _status(self, v):
        return v._prompt.text()

    def _viewer_without_kernel(self, act=None):
        """Viewer (and optional follow-up action) with the kernel patched
        out — scdm.kernel.available is the single capability switch."""
        import scdm.kernel as K
        real = K.available
        K.available = lambda: False
        try:
            v = self.gui.ScdmViewer(path=None)
            if act is not None:
                act(v)
            return v
        finally:
            K.available = real

    def test_kernel_tools_disabled_and_hinted(self):
        v = self._viewer_without_kernel()
        pulled = [self.kernel_tool_ids & {"tool.pull"}]
        b = v.ribbon.button("tool.pull")
        self.assertIsNotNone(b)
        self.assertFalse(b.isEnabled(), "kernel tool must be greyed out")
        self.assertIn("轻量模式", self._status(v))

    def test_activation_reason_is_lightweight_not_m2(self):
        def act(v):
            v.on_command("tool.pull")
        v = self._viewer_without_kernel(act)
        msg = self._status(v)
        self.assertIn("轻量模式", msg)
        self.assertIn("run_scdm.bat", msg)
        self.assertNotIn("未实现", msg)
        self.assertEqual(v.tools.active, "tool.pull")

    def test_kernel_present_keeps_tools_enabled(self):
        from scdm import kernel as K
        if not K.available():
            self.skipTest("OCC not installed")
        v = self.gui.ScdmViewer(path=None)
        b = v.ribbon.button("tool.pull")
        self.assertIsNotNone(b)
        self.assertTrue(b.isEnabled())
        v.on_command("tool.pull")
        self.assertEqual(v.tools.active, "tool.pull")
        self.assertNotIn("未实现", self._status(v))

    def test_tool_manager_reason_plumbing(self):
        from scdm.tools.base import ToolManager
        msgs = []
        tm = ToolManager(msgs.append)
        tm.activate("tool.pull", "拉动", "M2", False, "hud",
                    reason="轻量模式：拉动需要内核")
        self.assertEqual(msgs[-1], "轻量模式：拉动需要内核")
        tm.activate("tool.move", "移动", "M2", False, "hud")
        self.assertIn("未实现", msgs[-1])  # legacy fallback text preserved

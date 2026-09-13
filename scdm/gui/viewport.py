"""Viewport host: VTK fill + prompt strip + tool guide + smart mini-bar."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QFrame, QLabel, QToolButton, QWidget, QHBoxLayout, QVBoxLayout,
)

from scdm.gui.icons import make_icon

HUD_QSS = """
QLabel#ViewPrompt {
    color: #3A3A3A;
    background: #FAFAFA;
    padding: 3px 14px;
    font-size: 12px;
    border: none;
    border-bottom: 1px solid #E2E2E2;
}
"""

GUIDE_QSS = """
QWidget#ToolGuide {
    background: rgba(250, 250, 250, 235);
    border: 1px solid rgba(176, 176, 176, 170);
    border-radius: 4px;
}
QLabel#GuideCaption {
    color: #333; font-size: 12px; padding: 6px 8px 2px 8px;
}
QToolButton {
    border: 1px solid transparent; border-radius: 3px; padding: 2px;
    background: transparent;
}
QToolButton:hover { background: #E5F1FB; border-color: #C0D4EA; }
QToolButton:checked { background: #CDE4F7; border-color: #0078D7; }
"""

SMART_QSS = """
QWidget#MiniBar {
    background: rgba(252, 252, 252, 236);
    border: 1px solid rgba(170, 170, 170, 170);
    border-radius: 4px;
}
QToolButton {
    padding: 3px; border: 1px solid transparent; border-radius: 2px;
}
QToolButton:hover { background: #E5F1FB; border-color: #C0D4EA; }
QToolButton:checked { background: #CDE4F7; border-color: #0078D7; }
QLabel#SmartValue {
    color: #5A3A00; font-size: 12px; padding: 0 8px; min-width: 56px;
}
"""

# Vertical tool-guide buttons (original glyphs, SpaceClaim-like layout).
TOOL_GUIDES = {
    "tool.pull": (
        ("tool.select", "select", "选择"),
        ("tool.pull", "pull", "沿法向拉动"),
        ("opt.to_face", "offace", "到面"),
        ("opt.symmetric", "mirror", "对称"),
        ("done", "done", "完成"),
    ),
    "tool.move": (
        ("tool.select", "select", "选择"),
        ("tool.move", "move", "移动"),
        ("opt.copy", "copy", "复制"),
        ("done", "done", "完成"),
    ),
    "tool.fill": (
        ("tool.select", "select", "选择"),
        ("tool.fill", "fill", "填充"),
        ("done", "done", "完成"),
    ),
    "tool.combine": (
        ("tool.select", "select", "选择"),
        ("tool.combine", "combine", "合并"),
        ("opt.cut", "split", "减去"),
        ("done", "done", "完成"),
    ),
    "tool.split_body": (
        ("tool.select", "select", "选择"),
        ("tool.split_body", "split", "分割实体"),
        ("done", "done", "完成"),
    ),
    "tool.replace": (
        ("tool.select", "select", "选择"),
        ("tool.replace", "replace", "替换"),
        ("done", "done", "完成"),
    ),
}


class ToolGuide(QWidget):
    action = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolGuide")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(GUIDE_QSS)
        self._btns = {}
        self._tool = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 6)
        root.setSpacing(2)
        self.caption = QLabel("工具")
        self.caption.setObjectName("GuideCaption")
        self.caption.setAlignment(Qt.AlignHCenter)
        root.addWidget(self.caption)
        self._box = QVBoxLayout()
        self._box.setSpacing(3)
        root.addLayout(self._box)
        self.hide()

    def set_tool(self, tool_id: str, caption: str = ""):
        spec = TOOL_GUIDES.get(tool_id)
        if not spec:
            self._tool = ""
            self.hide()
            return
        if tool_id != self._tool:
            self._rebuild(spec)
            self._tool = tool_id
        self.caption.setText(caption or spec[1][2])
        for act, btn in self._btns.items():
            btn.setChecked(act == tool_id)
        self.show()
        self.adjustSize()

    def _rebuild(self, spec):
        while self._box.count():
            item = self._box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._btns.clear()
        for i, (act, icon, tip) in enumerate(spec):
            if act == "done" and i > 0:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setStyleSheet("color: #D8D8D8; max-height: 1px;")
                self._box.addWidget(line)
            b = QToolButton()
            b.setIcon(make_icon(icon, 24 if i else 28))
            b.setIconSize(QSize(24 if i else 28, 24 if i else 28))
            b.setFixedSize(34 if i else 38, 34 if i else 38)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setCheckable(act.startswith("tool.") or act.startswith("opt."))
            b.clicked.connect(lambda _=False, a=act: self.action.emit(a))
            self._box.addWidget(b, 0, Qt.AlignHCenter)
            self._btns[act] = b

    def set_option_checked(self, act: str, on: bool):
        b = self._btns.get(act)
        if b and b.isCheckable():
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)


class MiniBar(QWidget):
    """In-canvas smart bar that follows the selection (near the manipulator)."""
    command = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MiniBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(SMART_QSS)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 3, 5, 3)
        lay.setSpacing(3)
        self.value = QLabel("")
        self.value.setObjectName("SmartValue")
        self.value.hide()
        lay.addWidget(self.value)
        for cid, key, name in (
            ("tool.pull", "pull", "拉动"),
            ("tool.move", "move", "移动"),
            ("tool.fill", "fill", "填充"),
            ("tool.combine", "combine", "合并"),
            ("opt.copy", "copy", "复制"),
        ):
            b = QToolButton()
            b.setIcon(make_icon(key, 22))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(30, 30)
            b.setToolTip(name)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, i=cid: self.command.emit(i))
            lay.addWidget(b)
        self.adjustSize()

    def set_value(self, text: str):
        self.value.setText(text)
        self.value.setVisible(bool(text))
        self.adjustSize()


class ViewportHost(QWidget):
    def __init__(self, vtk_widget, parent=None):
        super().__init__(parent)
        self.vtk_widget = vtk_widget
        vtk_widget.setParent(self)
        self.hud = QLabel(self)
        self.hud.setObjectName("ViewPrompt")
        self.hud.setStyleSheet(HUD_QSS)
        self.hud.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hud.setText("单击选择对象；双击选环边；三击选实体")
        self.guide = ToolGuide(self)
        self.mini = MiniBar(self)
        self.mini.hide()
        self._prompt_h = 26

    def set_hud(self, text: str):
        self.hud.setText(text)

    def set_guide(self, tool_id: str, caption: str = ""):
        self.guide.set_tool(tool_id, caption)
        self._place_guide()

    def show_mini(self, on: bool):
        self.mini.setVisible(on)
        if on:
            self._place_mini()

    def place_smart(self, vtk_x, vtk_y):
        """Park the smart bar near a VTK display point (origin = vtk bottom-left)."""
        if not self.mini.isVisible():
            return
        vw = self.vtk_widget.width()
        vh = self.vtk_widget.height()
        x = int(vtk_x) - self.mini.width() // 2
        y = self._prompt_h + (vh - int(vtk_y)) - self.mini.height() - 16
        x = max(12, min(x, max(12, self.width() - self.mini.width() - 12)))
        y = max(self._prompt_h + 8, min(y, max(self._prompt_h + 8,
                                               self.height() - self.mini.height() - 12)))
        self.mini.move(x, y)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        bar_h = self._prompt_h
        self.hud.setGeometry(0, 0, self.width(), bar_h)
        self.vtk_widget.setGeometry(0, bar_h, self.width(), max(1, self.height() - bar_h))
        self._place_guide()
        self._place_mini()

    def _place_guide(self):
        self.guide.move(12, self._prompt_h + 10)

    def _place_mini(self):
        if not self.mini.isVisible():
            return
        # default: just right of the selection / toward the model center
        self.mini.move(max(56, self.width() // 2 - self.mini.width() // 2),
                       self._prompt_h + 48)

    def sizeHint(self):
        return QSize(800, 600)

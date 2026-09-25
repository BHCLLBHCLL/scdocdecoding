"""Render the GUI to a PNG, reproducibly (R122/C).

The 3D viewport is a GL surface, which a Qt widget grab does **not** capture -
that is why a plain `grab()` gives a screenshot with a black viewport.  This
tool renders the window and then paints the render window's own pixels into the
viewport rectangle, so one file shows the whole application.

Usage (from the repository root):

    python tools/gui_screenshot.py --out _tmp/shot.png --file box.scdoc \
        --demo sketch --size 1500x950

An existing QT_QPA_PLATFORM is respected; without one the native platform is used
so the 3D view really renders (offscreen has no GL context and the viewport stays
blank, which is still useful for widget-level checks).
"""
from __future__ import annotations

import argparse
import os
import sys
import time


def _demo_sketch(viewer, doc, sketch, constrained):
    """A sketch that shows the diagnostics: a redundant row and a dangling one."""
    from scdm import sketch as S
    viewer.on_command("mode.sketch")
    sk = doc.sketches[-1]
    sk.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0], [0.020, 0.012],
                               [0.0, 0.012]]))
    sk.constraints.extend([(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1),
                           (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                           (S.VERTICAL, 3, 0), (S.DIST, 0, 1, 0.020),
                           (S.DIST, 1, 2, 0.012)])
    sk.constraints.append((S.DIST, 0, 1, 0.020))          # redundant duplicate
    sk.constraints.append((S.DIST, 2, 3, "S9_dim5"))      # dangling reference
    doc.named.append({"name": "上表面", "items": [("face", "B9:0")]})
    viewer._refresh_sketch_dof()
    viewer._rebuild()


def _demo_conflict(viewer, doc, sketch, constrained):
    """A sketch whose diagnostics are all present: conflict, redundancy, dangling.

    The chip then reads 自由度 / 冗余 / 冲突 / 悬空 in one line - what the interface
    shows when a sketch is genuinely over-constrained *and* has a broken reference.
    """
    from scdm import sketch as S
    viewer.on_command("mode.sketch")
    sk = doc.sketches[-1]
    sk.curves.append(("poly", [[0.0, 0.0], [0.020, 0.0], [0.020, 0.012],
                               [0.0, 0.012]]))
    sk.constraints.extend([(S.FIXED, 0, 0.0, 0.0), (S.HORIZONTAL, 0, 1),
                           (S.VERTICAL, 1, 2), (S.HORIZONTAL, 2, 3),
                           (S.VERTICAL, 3, 0), (S.DIST, 0, 1, 0.020),
                           (S.DIST, 1, 2, 0.012)])
    sk.constraints.append((S.DIST, 0, 1, 0.026))          # conflicts with 20mm
    sk.constraints.append((S.DIST, 1, 2, 0.012))          # redundant duplicate
    sk.constraints.append((S.DIST, 2, 3, "S9_dim5"))      # dangling reference
    doc.named.append({"name": "上表面", "items": [("face", "B9:0")]})
    viewer._refresh_sketch_dof()
    viewer._rebuild()


def _demo_mate(viewer, doc, sketch, constrained):
    """Solid mode with a mate whose component was deleted (a health report)."""
    from scdm import kernel as K
    b1 = doc.add_body(K.make_box(0.02, 0.02, 0.01), name="基座")
    b2 = doc.add_body(K.translate(K.make_box(0.02, 0.02, 0.01), (0.03, 0.0, 0.0)),
                      name="从动件")
    c1 = doc.add_component("C1", [b1.id])
    c2 = doc.add_component("C2", [b2.id])
    doc.add_mate("rigid", c1.id, c2.id)
    doc.components = [c for c in doc.components if c.id != c2.id]
    doc.named.append({"name": "底面", "items": [("face", "B9:0")]})
    viewer._rebuild()


def _demo_picks(viewer, doc, sketch, constrained):
    """Solid mode with a selection, so the highlight and chrome are visible."""
    if doc.bodies:
        viewer.sel.items = [("body", doc.bodies[0].id)]
        viewer._refresh_selection_highlights()
        viewer.left.set_selection_list(["体 %s" % doc.bodies[0].id])


DEMOS = {"solid": None, "sketch": _demo_sketch, "picks": _demo_picks,
         "conflict": _demo_conflict, "mate": _demo_mate}


def grab(out: str, path=None, demo: str = "sketch", size=(1500, 950),
         settle: float = 0.12, rounds: int = 12) -> dict:
    """Render the GUI and write `out`; returns {"out", "size", "chip", "3d"}."""
    os.environ.setdefault("QT_QPA_PLATFORM", "")
    if not os.environ.get("QT_QPA_PLATFORM"):
        os.environ.pop("QT_QPA_PLATFORM", None)   # native: the 3D view renders
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)     # run me from anywhere
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    import scdm_gui
    viewer = scdm_gui.ScdmViewer(path=path)
    try:
        doc = viewer.session().kdoc
        fn = DEMOS.get(demo, _demo_sketch)
        if fn is not None and doc is not None:
            fn(viewer, doc, None, None)
        viewer.show()
        viewer.resize(int(size[0]), int(size[1]))   # after show: the layout may
        # still demand more, and the report says what was actually saved
        for _ in range(rounds):
            app.processEvents()
            time.sleep(settle)
        try:
            viewer.on_command("view.fit")
        except Exception:
            pass
        for _ in range(6):
            app.processEvents()
            time.sleep(settle)
        from PyQt5.QtCore import QPoint
        from PyQt5.QtGui import QImage, QPainter
        pm = viewer.grab()
        if getattr(viewer, "_enable_3d", False) and viewer.vtk_widget is not None:
            from vtkmodules.vtkIOImage import vtkPNGWriter
            from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter
            rw = viewer.vtk_widget.GetRenderWindow()
            rw.Render()
            w2i = vtkWindowToImageFilter()
            w2i.SetInput(rw)
            w2i.SetInputBufferTypeToRGB()
            w2i.ReadFrontBufferOff()
            w2i.Update()
            tmp = out + ".view.png"
            wr = vtkPNGWriter()
            wr.SetFileName(tmp)
            wr.SetInputConnection(w2i.GetOutputPort())
            wr.Write()
            painter = QPainter(pm)
            painter.drawImage(viewer.vtk_widget.mapTo(viewer, QPoint(0, 0)),
                              QImage(tmp).scaled(viewer.vtk_widget.width(),
                                                 viewer.vtk_widget.height()))
            painter.end()
            try:
                os.remove(tmp)
            except OSError:
                pass
        parent = os.path.dirname(os.path.abspath(out))
        if parent:
            os.makedirs(parent, exist_ok=True)
        ok = pm.save(out, "PNG")
        warns = []
        try:
            from scdm import health as HEALTH
            warns = HEALTH.document_warnings(doc, viewer.session().scale)
        except Exception:
            warns = []
        return {"out": out, "ok": bool(ok), "size": [pm.width(), pm.height()],
                "chip": viewer._mode_chip.text(), "health": len(warns),
                "3d": bool(getattr(viewer, "_enable_3d", False))}
    finally:
        try:
            viewer.close()
        except RuntimeError:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="render the GUI to a PNG")
    ap.add_argument("--out", default=os.path.join("_tmp", "shot.png"))
    ap.add_argument("--file", default="box.scdoc",
                    help="document to open (default: box.scdoc)")
    ap.add_argument("--demo", default="sketch", choices=sorted(DEMOS),
                    help="what to show: solid / sketch / picks")
    ap.add_argument("--size", default="1500x950", help="WxH")
    args = ap.parse_args(argv)
    w, _, h = args.size.partition("x")
    rep = grab(args.out, args.file, args.demo, (int(w or 1500), int(h or 950)))
    print("saved %(out)s %(size)s chip=%(chip)s health=%(health)s 3d=%(3d)s" % rep)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

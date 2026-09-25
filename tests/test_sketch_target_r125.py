"""R125 A-1: the retarget target is chosen on the option page.

R119/R120/R122 could point a dangling dimension at another sketch, a parameter or
an expression - but only from a script: the page offered one sketch number.  Now
the page asks *what kind* of target it is (sketch number / parameter / expression)
and takes its text, and whatever is in the box is what the library is handed - so
a typo is refused by the library and the row is left exactly as it was.

The first choice is the sketch number, which is what the page did before this
round: a default is only worth having if it is the historical behaviour.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("OCC")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scdm import sketch as S  # noqa: E402
from scdm.params import ParamTable  # noqa: E402

Qt = pytest.importorskip("PyQt5.QtCore").Qt  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BOX = os.path.join(_ROOT, "box.scdoc")
_APP = None          # module-global: a local QApplication is collected, killing widgets

KIND_SKETCH, KIND_PARAM, KIND_EXPR = 0, 1, 2


def _ensure_app():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    return _APP


def _viewer(path=None):
    _ensure_app()
    import scdm_gui
    return scdm_gui.ScdmViewer(path=path or _BOX)


def _rect(sk, u0=0.0, width=0.020, height=0.008, width_dim=None):
    sk.curves.append(("poly", [[u0, 0.0], [u0 + width, 0.0],
                               [u0 + width, height], [u0, height]]))
    sk.constraints.extend([
        (S.FIXED, 0, u0, 0.0), (S.HORIZONTAL, 0, 1), (S.VERTICAL, 1, 2),
        (S.HORIZONTAL, 2, 3), (S.VERTICAL, 3, 0),
        (S.DIST, 0, 1, width_dim if width_dim is not None else width),
        (S.DIST, 1, 2, height)])


def _document(v):
    """A dangling width dimension (it names sketch S9) + a parameter table."""
    doc = v.session().kdoc
    doc.param_table = ParamTable()
    doc.param_table.set("d", "5")
    sk = doc.add_sketch("xy")
    _rect(sk, 0.0, 0.020, 0.008, width_dim="S9_dim5")      # row 5 is dangling
    other = doc.add_sketch("xy")
    _rect(other, 0.040, 0.010, 0.008)                      # S2: 10mm wide
    return doc, sk, other


def _retarget(v, kind, text="", spin=1.0):
    v.left.show_options("repair.refs")
    v.left.set_checked("repair.refs", 1, True)             # 尺寸改指向
    v.left.set_choice("repair.refs", 0, kind)
    v.left.set_text("repair.refs", 0, text)
    v.left._opt_pages["repair.refs"][2][0].setValue(float(spin))
    v.on_command("repair.refs")
    return v._prompt.text()


# --- A-1: what the page offers ----------------------------------------------

def test_the_page_defaults_to_the_sketch_number():
    _ensure_app()
    v = _viewer()
    try:
        v.left.show_options("repair.refs")
        assert v.left.choice_value("repair.refs", 0) == KIND_SKETCH
        assert v.left.text_value("repair.refs", 0) == "1"
        assert v.left.is_checked("repair.refs", 1) is False      # nothing retargets
        page = v.left._opt_pages["repair.refs"]
        assert len(page[1]) == 3 and len(page[2]) == 1           # WYSIWYG: unchanged
        labels = [rb.text() for rb in page[4][0]]
        assert len(labels) == 3 and all("改指向" in s for s in labels), labels
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_a_dimension_can_be_retargeted_at_a_parameter_from_the_gui():
    _ensure_app()
    v = _viewer()
    try:
        _doc, sk, _other = _document(v)
        text = _retarget(v, KIND_PARAM, "d")
        assert "参数 d" in text, text
        assert sk.constraints[5][3] == "d", sk.constraints[5]
        from scdm import health as HEALTH
        assert HEALTH.document_warnings(v.session().kdoc, 1000.0) == []
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_a_dimension_can_be_retargeted_at_an_expression_from_the_gui():
    _ensure_app()
    v = _viewer()
    try:
        _doc, sk, _other = _document(v)
        text = _retarget(v, KIND_EXPR, "2*d")
        assert "算式 2*d" in text, text
        assert sk.constraints[5][3] == "2*d", sk.constraints[5]
        from scdm import sketchmode as SKM
        rows = {d["index"]: d for d in SKM.dimensions(v.session().kdoc, sk.id,
                                                      1000.0)}
        assert rows[5]["value_mm"] == pytest.approx(10.0)     # 2 * d(=5mm)
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_the_sketch_number_is_still_the_default_target():
    _ensure_app()
    v = _viewer()
    try:
        _doc, sk, other = _document(v)
        text = _retarget(v, KIND_SKETCH, "", spin=2.0)
        assert "草图 S2" in text, text
        assert sk.constraints[5][3] == "S2_dim5", sk.constraints[5]
        assert other.id == "S2"
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


# --- A-1: the wrong premise changes nothing ---------------------------------

def test_an_unknown_parameter_is_refused_and_the_row_is_untouched():
    _ensure_app()
    v = _viewer()
    try:
        _doc, sk, _other = _document(v)
        text = _retarget(v, KIND_PARAM, "nope")
        assert "参数表里没有 nope" in text, text
        assert sk.constraints[5][3] == "S9_dim5", sk.constraints[5]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_an_empty_expression_is_refused():
    _ensure_app()
    v = _viewer()
    try:
        _doc, sk, _other = _document(v)
        text = _retarget(v, KIND_EXPR, "   ")
        assert "算式目标为空" in text, text
        assert sk.constraints[5][3] == "S9_dim5", sk.constraints[5]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass


def test_an_unknown_sketch_is_refused():
    _ensure_app()
    v = _viewer()
    try:
        _doc, sk, _other = _document(v)
        text = _retarget(v, KIND_SKETCH, "", spin=9.0)
        assert "目标草图 S9 已不存在" in text, text
        assert sk.constraints[5][3] == "S9_dim5", sk.constraints[5]
    finally:
        try:
            v.close()
        except RuntimeError:
            pass

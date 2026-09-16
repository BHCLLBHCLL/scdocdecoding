"""R103/A-3: the parameter dialog and its logic, separated from the window.

The dialog edits two kinds of parameters:

* the expression table (`ParamTable`) that drives the parametric bodies;
* the recorded **feature** parameters of every body (R102) - one line per
  (body, feature index, parameter); a body whose history no longer reproduces
  its shape is listed as a comment carrying the measured reason, never as an
  editable row.

`feature_lines` / `parse_table_lines` / `apply_param_text` / `apply_single_edit`
are Qt-free and unit-tested; `ParamDialog` is the Qt shell around them.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QPlainTextEdit,
                             QVBoxLayout)

from scdm import features as FEAT
from scdm.params import ParamTable

DEFAULT_TABLE_TEXT = "width = 20" + chr(10) + "height = width * 2"
FEATURE_HINT = "特征参数（每行：实体 特征序号 参数 = 值，例如 B1 0 diameter = 8）"


def body_ids(kdoc) -> List[str]:
    return [b.id for b in kdoc.bodies]


def feature_lines(kdoc, scale: float = 1000.0) -> List[str]:
    """The feature block of the dialog: editable rows + reason comments."""
    lines: List[str] = []
    for b in kdoc.bodies:
        stack = kdoc.features.get(b.id)
        if stack is None or not len(stack):
            continue
        lines.append("# %s %s：%s" % (b.id, b.name, " + ".join(stack.ops())))
        ok, why = kdoc.can_replay(b.id, scale)
        if not ok:
            lines.append("#   不可重放 — %s" % why)
            continue
        for row in stack.editable():
            lines.append("%s %d %s = %g" % (b.id, row["index"], row["param"],
                                            row["value"]))
    return lines


def parse_table_lines(text) -> ParamTable:
    """@@name = expression@@ lines -> a resolved ParamTable.

    Raises ValueError naming the offending line; the caller commits nothing
    until this has succeeded (a bad table must not half-apply).
    """
    table = ParamTable()
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if "=" not in ln:
            raise ValueError("缺 '='：%s" % ln)
        name, expr = ln.split("=", 1)
        table.set(name.strip(), expr.strip())
    table.resolve()
    return table


def apply_param_text(kdoc, table_text: str, feat_text: str,
                     scale: float = 1000.0) -> dict:
    """Apply both blocks; nothing is touched when either block is invalid.

    Returns {"table", "edits", "reports", "errors", "done", "failed"}.
    """
    out = {"table": None, "edits": [], "reports": [], "errors": [],
           "done": [], "failed": [], "redrive": None}
    edits, errors = FEAT.parse_edit_lines(feat_text, body_ids(kdoc))
    out["edits"] = edits
    if errors:
        out["errors"] = list(errors)
        return out
    try:
        table = parse_table_lines(table_text)
    except Exception as exc:
        out["errors"] = ["参数表：%s" % exc]
        return out
    kdoc.param_table = table
    # R110/A-2: a changed parameter re-resolves every expression dimension, and
    # the bodies built from those sketches follow
    from scdm import sketchmode as SKM
    redrive = SKM.redrive_expressions(kdoc, scale)
    if redrive["redriven"]:
        for sk in list(getattr(kdoc, "sketches", []) or []):
            SKM.sync_sketch_bodies(kdoc, sk.id, scale)
    out["redrive"] = redrive
    for p in list(getattr(kdoc, "parametrics", []) or []):
        p.table = table
        try:
            kdoc.rebuild_parametric(p, scale)
        except Exception as exc:
            out["errors"].append("参数化重建失败：%s" % exc)
    reports = FEAT.apply_edits(kdoc, edits, scale)
    out["table"] = table
    out["reports"] = reports
    out["done"] = [r for r in reports if r["ok"]]
    out["failed"] = [r for r in reports if not r["ok"]]
    return out


def apply_single_edit(kdoc, body_id: str, index: int, param: str, value,
                      scale: float = 1000.0) -> dict:
    """One feature-parameter edit (the tree double-click path)."""
    return kdoc.edit_feature(body_id, index, param, value, scale)


class ParamDialog(QDialog):
    """The two-editor dialog (expression table + feature parameters)."""

    def __init__(self, parent, table_text: str, feat_lines: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("参数（表达式支持：height = width * 2）")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("每行一个参数：名称 = 数值或表达式"))
        self.table_edit = QPlainTextEdit()
        self.table_edit.setPlainText(table_text or DEFAULT_TABLE_TEXT)
        self.table_edit.setMinimumSize(420, 170)
        lay.addWidget(self.table_edit)
        lay.addWidget(QLabel(FEATURE_HINT))
        self.feat_edit = QPlainTextEdit()
        self.feat_edit.setPlainText(chr(10).join(feat_lines or []))
        self.feat_edit.setMinimumSize(420, 170)
        lay.addWidget(self.feat_edit)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                        | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)

    def texts(self) -> Tuple[str, str]:
        return self.table_edit.toPlainText(), self.feat_edit.toPlainText()

    def set_texts(self, table_text: str, feat_text: str) -> None:
        self.table_edit.setPlainText(table_text)
        self.feat_edit.setPlainText(feat_text)

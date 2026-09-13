"""P352/R69: 尺寸链与公差叠加。

A chain is a run of contiguous dimensions along one direction (the next segment
starts where the previous one ends, within a gap tolerance).  Two closed forms
follow from that:

    chain sum   = total span from the first start to the last end   (exact)
    worst case  = sum(|tol_i|)                                      (limits)
    statistical = sqrt(sum(tol_i**2))                               (independent)

The chain checker returns a countable verdict (breaks with their gap sizes, and
axis violations) instead of silently adding up a broken run - the same style as
the mesh gates: a decision, not a boolean.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from scdm.drawing import Dimension

AXIS_INDEX = {"h": 0, "v": 1}
# Dimension.a/b live in view METRES while value_mm is millimetres: the chain
# reports spans and gap sizes in mm so they are comparable with the values (the
# first draft compared 0.1 with 100 and called every valid chain broken)
MM = 1000.0


def _start(d: Dimension) -> float:
    return float(d.a[AXIS_INDEX.get(d.axis, 0)])


def _end(d: Dimension) -> float:
    return float(d.b[AXIS_INDEX.get(d.axis, 0)])


def check_chain(dims: Sequence[Dimension], tol_gap: float = 1e-6,
                axis: Optional[str] = None) -> Dict[str, Any]:
    """Chain verdict: {ok, axis, order, sum, span, mismatch, breaks, violations}.

    All lengths in the verdict are mm, comparable with @@value_mm@@; @@tol_gap@@
    is the allowed contiguity gap in mm.
    """
    items = list(dims or ())
    if not items:
        raise ValueError("尺寸链：没有尺寸")
    for d in items:
        if d.value_mm < 0:
            raise ValueError("尺寸链：尺寸值不能为负")
        if float(getattr(d, "tol", 0.0)) < 0:
            raise ValueError("尺寸链：公差不能为负")
    axes = {d.axis for d in items}
    if axis is None:
        axis = items[0].axis
    if axis not in AXIS_INDEX:
        raise ValueError("尺寸链：方向只能是 h 或 v")
    violations: List[Dict[str, Any]] = []
    if len(axes) > 1:
        for i, d in enumerate(items):
            if d.axis != axis:
                violations.append({"index": i, "reason": "axis",
                                   "axis": d.axis})
    idx = AXIS_INDEX[axis]
    # order along the chain direction: by start, then by end
    order = sorted(range(len(items)),
                   key=lambda i: (round(float(items[i].a[idx]), 9),
                                  round(float(items[i].b[idx]), 9)))
    breaks: List[Dict[str, Any]] = []
    total = 0.0
    for k in range(1, len(order)):
        prev, cur = items[order[k - 1]], items[order[k]]
        gap = (float(cur.a[idx]) - float(prev.b[idx])) * MM
        if abs(gap) > tol_gap:
            breaks.append({"after": order[k - 1], "at": order[k],
                           "gap": gap})
        total += float(prev.value_mm)
    if len(order) == 1:
        total = float(items[order[0]].value_mm)
    else:
        total += float(items[order[-1]].value_mm)
    span = (abs(float(items[order[-1]].b[idx]) - float(items[order[0]].a[idx]))
            * MM if len(order) > 1 else float(items[order[0]].value_mm))
    return {"ok": not breaks and not violations, "axis": axis, "order": order,
            "sum": total, "span": span, "mismatch": abs(total - span),
            "breaks": breaks, "violations": violations, "count": len(order)}


def stack_up(dims: Sequence[Dimension], mode: str = "worst") -> Dict[str, Any]:
    """Tolerance stack-up: worst case (sum of limits) or RSS (independent)."""
    items = list(dims or ())
    if not items:
        raise ValueError("公差叠加：没有尺寸")
    tols = [float(getattr(d, "tol", 0.0)) for d in items]
    if any(t < 0 for t in tols):
        raise ValueError("公差叠加：公差不能为负")
    key = str(mode).lower()
    if key in ("worst", "limits", "极值"):
        tol = sum(tols)
        mode_name = "worst"
    elif key in ("rss", "statistical", "统计"):
        tol = math.sqrt(sum(t * t for t in tols))
        mode_name = "rss"
    else:
        raise ValueError("公差叠加：模式只能是 worst 或 rss")
    return {"mode": mode_name, "tol": tol, "count": len(items),
            "sum": sum(float(d.value_mm) for d in items),
            "max_tol": max(tols) if tols else 0.0}


def chain_dimension(dims: Sequence[Dimension], tol_gap: float = 1e-6,
                    mode: str = "worst") -> Dimension:
    """The overall dimension of a chain, carrying the stacked tolerance."""
    verdict = check_chain(dims, tol_gap=tol_gap)
    if not verdict["ok"]:
        raise ValueError("尺寸链不成立：断口 %d 处、方向违规 %d 处"
                         % (len(verdict["breaks"]), len(verdict["violations"])))
    items = list(dims)
    first = items[verdict["order"][0]]
    last = items[verdict["order"][-1]]
    stack = stack_up(items, mode=mode)
    total = Dimension(first.view, verdict["axis"],
                      float(first.value_mm) * 0.0 + verdict["sum"],
                      first.a, last.b, first.offset)
    total.tol = stack["tol"]
    return total


def describe(verdict: Dict[str, Any]) -> str:
    """One line for a status bar (single source for the wording, rule 84)."""
    if verdict.get("ok"):
        return ("尺寸链：%d 段，链和 %.3f mm（跨度 %.3f，偏差 %.3g）"
                % (verdict.get("count", 0), verdict.get("sum", 0.0),
                   verdict.get("span", 0.0), verdict.get("mismatch", 0.0)))
    return ("尺寸链不成立：断口 %d 处、方向违规 %d 处"
            % (len(verdict.get("breaks") or []),
               len(verdict.get("violations") or [])))

"""M5-06: Workbench-style parameters driving geometry rebuild.

A Parametric holds a builder plus named numeric parameters; editing a parameter
rebuilds the body shape through the OCCT kernel (no ANSYS process involved).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from scdm import kernel as K


class Parametric:
    """One parametric body definition.

    Parameter values may be numbers or expression strings (see ParamTable);
    expression parameters resolve against the optional global table plus the
    body's own numeric parameters.
    """

    def __init__(self, body_name: str, params: Dict[str, object],
                 builder: Callable[[Dict[str, float], float], object],
                 table: Optional["ParamTable"] = None):
        self.body_name = body_name
        self._raw = {k: v for k, v in params.items()}
        self.params: Dict[str, float] = {
            k: float(v) for k, v in params.items()}
        self.builder = builder
        self.table = table

    def set(self, **kw) -> None:
        for k, v in kw.items():
            if k in self._raw:
                self._raw[k] = v

    def resolve_params(self) -> Dict[str, float]:
        """Numeric params with expression params resolved (global table +
        own numeric params form the namespace).  `_raw` is authoritative:
        set() updates it, self.params is only the construction snapshot."""
        out: Dict[str, float] = {}
        exprs: Dict[str, str] = {}
        for k, v in self._raw.items():
            if isinstance(v, str):
                exprs[k] = v
            else:
                out[k] = float(v)
        glob = self.table.resolve() if self.table is not None else {}
        ns = dict(glob)
        ns.update(out)
        for k, v in exprs.items():
            out[k] = eval_expr(v, ns)
            ns[k] = out[k]
        return out

    def build(self, scale: float = 1000.0):
        return self.builder(self.resolve_params(), scale)


def box_builder(p: Dict[str, float], scale: float):
    return K.make_box(p["W"] / scale, p["H"] / scale, p["D"] / scale)


def cylinder_builder(p: Dict[str, float], scale: float):
    return K.make_cylinder(p["R"] / scale, p["H"] / scale)


def param_box(body_name: str = "参数盒", w: float = 10.0, h: float = 10.0,
              d: float = 10.0) -> Parametric:
    return Parametric(body_name, {"W": w, "H": h, "D": d}, box_builder)


def param_cylinder(body_name: str = "参数圆柱", r: float = 5.0,
                   h: float = 10.0) -> Parametric:
    return Parametric(body_name, {"R": r, "H": h}, cylinder_builder)


def param_box_at(body_name: str, w: float, h: float, d: float,
                 origin=(0.0, 0.0, 0.0)) -> Parametric:
    """Parametric box rebuilt at a fixed world origin (mm params)."""
    org = tuple(float(v) for v in origin)

    def builder(p, scale):
        return K.make_box(p["W"] / scale, p["H"] / scale, p["D"] / scale, origin=org)

    return Parametric(body_name, {"W": w, "H": h, "D": d}, builder)


def param_cylinder_at(body_name: str, r: float, h: float,
                      origin=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0)) -> Parametric:
    """Parametric cylinder rebuilt at a fixed origin/axis (mm params)."""
    org = tuple(float(v) for v in origin)
    ax = tuple(float(v) for v in axis)

    def builder(p, scale):
        return K.make_cylinder(p["R"] / scale, p["H"] / scale, origin=org, axis=ax)

    return Parametric(body_name, {"R": r, "H": h}, builder)


# ----------------------------------------------------------------------
# H7: global named-parameter table with expressions
# ----------------------------------------------------------------------
import re as _re

_IDENT = _re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_IDENT_FULL = _re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED = _re.compile(
    r"^\s*[0-9.+\-*/() eE_A-Za-z-]*$")  # digits, arith, identifiers


def eval_expr(expr: str, names: Dict[str, float]) -> float:
    """Evaluate a parameter expression against a name->value mapping.

    Only arithmetic (+ - * / parentheses, unary minus) and known parameter
    names are allowed; anything else raises ValueError.  Units: millimetres
    at the document scale (callers divide by scale for the kernel).
    """
    expr = str(expr).strip()
    if not expr:
        raise ValueError("空表达式")
    if not _ALLOWED.match(expr):
        raise ValueError(f"表达式含不允许的字符: {expr!r}")
    env: Dict[str, float] = {}
    for tok in _IDENT.findall(expr):
        import math as _math
        if tok in ("pi", "e"):
            env[tok] = _math.pi if tok == "pi" else _math.e
            continue
        if tok not in names:
            raise ValueError(f"未知参数 {tok!r}（表达式 {expr!r}）")
        env[tok] = names[tok]
    try:
        return float(eval(expr, {"__builtins__": {}}, env))
    except ZeroDivisionError:
        raise ValueError("除零")


class ParamTable:
    """Global named parameters (SpaceClaim 参数对话框 semantics).

    Values may be numbers or expression strings referencing other
    parameters; evaluation is dependency-ordered with cycle detection.
    """

    def __init__(self):
        self._defs: Dict[str, str] = {}     # name -> expression/number text

    def set(self, name: str, expr) -> None:
        name = str(name).strip()
        if not _IDENT_FULL.match(name):
            raise ValueError(f"非法参数名 {name!r}")
        self._defs[name] = str(expr).strip()

    def remove(self, name: str) -> None:
        self._defs.pop(name, None)

    def names(self) -> List[str]:
        return list(self._defs)

    def get(self, name: str) -> float:
        return self.resolve()[name]

    def defs(self) -> Dict[str, str]:
        return dict(self._defs)

    def resolve(self) -> Dict[str, float]:
        """Evaluate all parameters (topological order, cycle detection)."""
        out: Dict[str, float] = {}
        pending = dict(self._defs)
        guard = 0
        while pending:
            guard += 1
            if guard > 100:
                raise ValueError("参数存在循环引用")
            progressed = False
            for name in list(pending):
                expr = pending[name]
                try:
                    num = float(expr)
                    out[name] = num
                    del pending[name]
                    progressed = True
                    continue
                except ValueError:
                    pass
                # expression: try when all referenced names are resolved
                refs = _IDENT.findall(expr)
                if all(r in out or r in ("pi", "e") for r in refs):
                    try:
                        out[name] = eval_expr(expr, out)
                        del pending[name]
                        progressed = True
                    except ValueError as exc:
                        if "未知参数" in str(exc):
                            continue    # wait for dependency
                        raise
            if not progressed:
                unresolved = ", ".join(pending)
                raise ValueError(f"参数无法求解: {unresolved}")
        return out

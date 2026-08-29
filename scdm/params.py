"""M5-06: Workbench-style parameters driving geometry rebuild.

A Parametric holds a builder plus named numeric parameters; editing a parameter
rebuilds the body shape through the OCCT kernel (no ANSYS process involved).
"""
from __future__ import annotations

from typing import Callable, Dict, List

from scdm import kernel as K


class Parametric:
    """One parametric body definition."""

    def __init__(self, body_name: str, params: Dict[str, float],
                 builder: Callable[[Dict[str, float], float], object]):
        self.body_name = body_name
        self.params = {k: float(v) for k, v in params.items()}
        self.builder = builder

    def set(self, **kw) -> None:
        for k, v in kw.items():
            if k in self.params:
                self.params[k] = float(v)

    def build(self, scale: float = 1000.0):
        return self.builder(dict(self.params), scale)


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

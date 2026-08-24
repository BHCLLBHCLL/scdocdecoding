"""OCCT kernel adapter. Geometry ops land in M2; M1 only probes availability."""
from __future__ import annotations


def available() -> bool:
    try:
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox  # noqa: F401
        return True
    except Exception:
        return False

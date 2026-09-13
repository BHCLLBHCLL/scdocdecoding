"""P181: symbolic thread representation (nominal + pitch -> spec + lines).

A thread is metadata plus a rendering hint: the solid is cut at the TAP DRILL
diameter (see kernel.hole_tapped) and the thread itself is drawn as a saw-tooth
profile around the hole axis.  Keeping it symbolic means the volume never
depends on the thread, which is what the tests pin down.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from scdm.kernel import KernelError


def thread_spec(nominal: float, pitch: float) -> dict:
    """Validated metric thread spec: tap drill, major diameter, pitch."""
    if pitch <= 0 or nominal <= pitch:
        raise KernelError("螺纹参数非法：螺距必须为正且小于公称直径")
    return {"nominal": float(nominal), "pitch": float(pitch),
            "tap_drill": float(nominal) - float(pitch),
            # ISO 68-1 basic profile depth for reference/annotation only
            "depth_ratio": 0.61343}


def thread_lines(origin, axis, nominal: float, pitch: float, depth: float,
                 per_turn: int = 8) -> List[Tuple[Tuple[float, float, float],
                                                 Tuple[float, float, float]]]:
    """Saw-tooth thread profile as line segments around the hole axis.

    Pure annotation: the points sit between the tap-drill radius and the
    nominal radius, so the drawing stays inside the hole envelope and the cut
    volume is untouched.
    """
    spec = thread_spec(nominal, pitch)
    a = [float(v) for v in axis]
    n = math.sqrt(sum(v * v for v in a)) or 1.0
    a = [v / n for v in a]
    # an arbitrary perpendicular frame
    ref = [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0]
    u = [ref[i] - sum(ref[j] * a[j] for j in range(3)) * a[i] for i in range(3)]
    ul = math.sqrt(sum(v * v for v in u)) or 1.0
    u = [v / ul for v in u]
    v = [a[1] * u[2] - a[2] * u[1], a[2] * u[0] - a[0] * u[2],
         a[0] * u[1] - a[1] * u[0]]
    r_tap = spec["tap_drill"] / 2.0
    r_maj = spec["nominal"] / 2.0
    turns = max(1, int(round(float(depth) / spec["pitch"])))
    pts = []
    steps = turns * per_turn
    for i in range(steps + 1):
        t = float(depth) * i / steps if steps else 0.0
        ang = 2.0 * math.pi * i / per_turn
        # saw tooth: the radius ramps from tap to major and snaps back
        frac = (i % per_turn) / float(per_turn)
        r = r_tap + (r_maj - r_tap) * frac
        pts.append(tuple(origin[k] + a[k] * t + u[k] * r * math.cos(ang)
                         + v[k] * r * math.sin(ang) for k in range(3)))
    return list(zip(pts, pts[1:]))
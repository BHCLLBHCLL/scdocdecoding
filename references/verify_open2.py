# -*- coding: utf-8 -*-
import System
import traceback

SENT = r"D:\training\caedecoder\scdocdecoding\cyl_ref_sentinel.txt"
ERR = r"D:\training\caedecoder\scdocdecoding\cyl_ref_error.txt"

try:
    lines = []
    part = GetRootPart()
    lines.append("root bodies=%d" % len(part.GetBodies()))
    try:
        comps = list(part.GetAllComponents()) if hasattr(part, 'GetAllComponents') else list(part.GetComponents())
    except Exception as e0:
        comps = list(part.Components)
        lines.append("comps fallback: %s" % e0)
    lines.append("components=%d" % len(comps))
    for c in comps:
        try:
            bs = c.GetBodies()
            lines.append("comp GetBodies ok n=%d" % len(bs))
        except Exception as e1:
            lines.append("comp GetBodies EXC: %s" % e1)
    total = len(part.GetBodies())
    for c in comps:
        try:
            total += len(c.GetBodies())
        except Exception:
            pass
    lines.append("TOTAL=%d" % total)
    System.IO.File.WriteAllText(SENT, "\n".join(lines))
except Exception:
    System.IO.File.WriteAllText(ERR, traceback.format_exc())
    System.IO.File.WriteAllText(SENT, "error")

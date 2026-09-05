# -*- coding: utf-8 -*-
"""Build an official assembly sample INSIDE SpaceClaim:

1. Open our box+cyl STEP (already proven path via ImportOptions).
2. Create a Component and move both DesignBodies into it.
3. SaveAs assembly_sample.scdoc.

Sentinel: 'done ...' or 'error'.
"""
import System
import traceback

SENT = r"D:\training\caedecoder\scdocdecoding\_asm_sample_sentinel.txt"
ERR = r"D:\training\caedecoder\scdocdecoding\_asm_sample_error.txt"
STEP = r"D:\training\caedecoder\scdocdecoding\_asm_sample.step"
OUT = r"D:\training\caedecoder\scdocdecoding\references\golden\assembly_sample.scdoc"

try:
    import clr
    clr.AddReference('SpaceClaim.Api.V19')
    import SpaceClaim.Api.V19 as api

    wins = api.Document.Open(STEP, api.ImportOptions.Create())
    doc = wins[0].Document
    part = doc.MainPart

    bodies = list(part.Bodies)
    n = len(bodies)

    # sub-part template + component instance referencing it
    sub = api.Part.Create(doc, "Assembly1")
    comp = api.Component.Create(part, sub)
    moved = 0
    for b in bodies:
        try:
            b.MoveToComponent(comp)
            moved += 1
        except Exception:
            pass

    doc.SaveAs(OUT)
    System.IO.File.WriteAllText(SENT, "done bodies=%d moved=%d" % (n, moved))
except Exception:
    System.IO.File.WriteAllText(ERR, traceback.format_exc())
    System.IO.File.WriteAllText(SENT, "error")

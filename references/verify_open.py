# -*- coding: utf-8 -*-
"""Official SpaceClaim open-verification script (run INSIDE SpaceClaim).

Usage (from a shell, absolute paths are REQUIRED — relative paths make
/RunScript silently ignored):

  SpaceClaim.exe <file.scdoc> /RunScript=<abs>\\references\\verify_open.py /ExitAfterScript=True

Writes a sentinel to %TEMP%\\cyl_ref_sentinel.txt:
  done bodies=<n> volume=<v>   on success
  error                        on failure (details in %TEMP%\\cyl_ref_error.txt)

Verified knowledge (SpaceClaim 2019 R3):
  - /RunScript needs an ABSOLUTE path; the script host injects the journaling
    namespace (GetRootPart, GetActiveWindow, DesignBody, ...) — no imports needed.
  - For pure-API use: clr.AddReference("SpaceClaim.Api.V19");
    ImportOptions.Create() is the factory (no public ctor);
    Document.Open(path, options) returns a WINDOW ARRAY; the Document is
    window.Document.  A 1-arg Open is NOT exposed to IronPython.
"""
import System
import traceback

SENT = r"D:\training\caedecoder\scdocdecoding\cyl_ref_sentinel.txt"
ERR = r"D:\training\caedecoder\scdocdecoding\cyl_ref_error.txt"

try:
    part = GetRootPart()
    bodies = part.GetBodies()
    n = len(bodies)
    vol = 0.0
    for b in bodies:
        try:
            vol += b.MassProperties.Volume
        except Exception:
            pass
    System.IO.File.WriteAllText(SENT, "done bodies=%d volume=%.6g" % (n, vol))
except Exception:
    System.IO.File.WriteAllText(ERR, traceback.format_exc())
    System.IO.File.WriteAllText(SENT, "error")

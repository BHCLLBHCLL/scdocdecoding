# -*- coding: utf-8 -*-
"""Generate an OFFICIAL SpaceClaim-written .scdoc from one of our STEP files.

Pipeline: our OCCT shape -> STEP -> SpaceClaim /RunScript (IronPython) ->
official .scdoc. Used to harvest golden references for the SAB writer
(record order + per-class token layouts).

Usage:
  python references/make_official_ref.py <shape.step> <out_name>

Requires SpaceClaim 2019 R3 at the path below and network-free local run.
Writes <out_name>.scdoc next to the STEP file and prints the sentinel result.
"""
import os
import subprocess
import sys
import tempfile

SCDM = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"
HERE = os.path.dirname(os.path.abspath(__file__))


def make_ref(step_path: str, out_name: str) -> str:
    step_path = os.path.abspath(step_path)
    out_scdoc = os.path.abspath(out_name + ".scdoc")
    workdir = os.path.dirname(step_path)
    script = os.path.join(workdir, "_ref_conv.py")
    sentinel = os.path.join(workdir, "_ref_sentinel.txt")
    errfile = os.path.join(workdir, "_ref_error.txt")

    with open(script, "w", encoding="utf-8") as f:
        f.write(
            "# -*- coding: utf-8 -*-\n"
            "import System\nimport traceback\n"
            "SENT = %r\nERR = %r\n"
            "try:\n"
            "    import clr\n"
            "    clr.AddReference('SpaceClaim.Api.V19')\n"
            "    import SpaceClaim.Api.V19 as api\n"
            "    opts = api.ImportOptions.Create()\n"
            "    wins = api.Document.Open(%r, opts)\n"
            "    doc = wins[0].Document\n"
            "    doc.SaveAs(%r)\n"
            "    System.IO.File.WriteAllText(SENT, 'done')\n"
            "except Exception:\n"
            "    System.IO.File.WriteAllText(ERR, traceback.format_exc())\n"
            "    System.IO.File.WriteAllText(SENT, 'error')\n"
            % (sentinel, errfile, step_path, out_scdoc))

    for p in (sentinel, errfile, out_scdoc):
        if os.path.exists(p):
            os.remove(p)
    subprocess.Popen([SCDM, "/RunScript=" + script, "/ExitAfterScript=True"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time
    for _ in range(40):
        time.sleep(4)
        if os.path.exists(sentinel):
            with open(sentinel) as f:
                result = f.read()
            break
    else:
        result = "timeout"
    for p in (script, sentinel, errfile):
        if os.path.exists(p):
            os.remove(p)
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    print(make_ref(sys.argv[1], sys.argv[2]))

# -*- coding: utf-8 -*-
"""H1: import formats only SpaceClaim understands (X_T/X_B Parasolid, ...) via
the official batch pipeline: SpaceClaim /RunScript opens the file and saves a
.scdoc, which is then read by our own SAB parser.

Falls back with a clear error when SpaceClaim is not installed.
"""
import os
import subprocess
import tempfile
import time

SCDM = r"C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.exe"
SUPPORTED = (".x_t", ".x_b", ".xmt_txt", ".xmt_bin")


def _spaceclaim_available():
    return os.path.exists(SCDM)


def import_via_spaceclaim(path: str, out_scdoc: str = None) -> str:
    """Convert a SpaceClaim-importable file to .scdoc via the official app.

    Returns the .scdoc path.  Raises RuntimeError when SpaceClaim is missing
    or the conversion fails.
    """
    if not _spaceclaim_available():
        raise RuntimeError("未找到 SpaceClaim，无法转换该格式（" +
                           os.path.splitext(path)[1] + "）")
    path = os.path.abspath(path)
    if out_scdoc is None:
        out_scdoc = os.path.splitext(path)[0] + ".scdoc"
    out_scdoc = os.path.abspath(out_scdoc)
    workdir = os.path.dirname(out_scdoc)
    script = os.path.join(workdir, "_xt_conv.py")
    sentinel = os.path.join(workdir, "_xt_sentinel.txt")
    errfile = os.path.join(workdir, "_xt_error.txt")
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
            % (sentinel, errfile, path, out_scdoc))
    for p in (sentinel, errfile, out_scdoc):
        if os.path.exists(p):
            os.remove(p)
    subprocess.Popen([SCDM, "/RunScript=" + script, "/ExitAfterScript=True"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(4)
        if os.path.exists(sentinel):
            result = open(sentinel).read().strip()
            break
    else:
        result = "timeout"
    for p in (script, sentinel, errfile):
        if os.path.exists(p):
            os.remove(p)
    if result != "done":
        detail = ""
        if os.path.exists(errfile):
            detail = open(errfile).read()[-400:]
        raise RuntimeError("SpaceClaim 转换失败: %s %s" % (result, detail))
    return out_scdoc


def can_import_directly(ext: str) -> bool:
    """Formats our kernel reads without SpaceClaim."""
    return ext.lower() in (".step", ".stp", ".stl", ".igs", ".iges",
                           ".obj", ".3mf", ".scdoc")

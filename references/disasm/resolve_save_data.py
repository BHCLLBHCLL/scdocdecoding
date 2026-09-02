"""Resolve save_data targets from each class's exported save() thunk.

Thunk pattern: save_begin (1st call); save_data (2nd call); jmp save_end.
Usage: python resolve_save_data.py
"""
import subprocess
import re

DLL = r"C:/Program Files/ANSYS Inc/v195/scdm/SpaACIS.dll"
BASE = 0x180000000

CLASSES = ["BODY", "LUMP", "SHELL", "FACE", "LOOP", "COEDGE", "EDGE", "VERTEX",
           "TVERTEX", "APOINT", "WIRE", "PLANE", "STRAIGHT", "CONE", "ELLIPSE",
           "INTCURVE", "EE_LIST"]


def rva_of(class_name):
    out = subprocess.run(
        ["python", "references/disasm/pe_exports.py", DLL,
         "save@" + class_name + "@@UEBAXAEAVENTITY_LIST"],
        capture_output=True, text=True, cwd=".")
    m = re.match(r"([0-9A-F]{8}) ", out.stdout)
    return int(m.group(1), 16) if m else None


def disasm(start, stop):
    out = subprocess.run(
        ["objdump", "-d", f"--start-address={BASE+start:#x}",
         f"--stop-address={BASE+stop:#x}", "-M", "intel", DLL],
        capture_output=True, text=True)
    lines = []
    for ln in out.stdout.splitlines():
        m = re.match(r"\s+([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*\t(.*)", ln)
        if m:
            lines.append((int(m.group(1), 16) - BASE, m.group(2).strip()))
    return lines


for cls in CLASSES:
    rva = rva_of(cls)
    if rva is None:
        print(f"{cls}: NOT FOUND")
        continue
    # .pdata bounds
    out = subprocess.run(["python", "references/disasm/pdata.py", DLL, f"{rva:X}"],
                         capture_output=True, text=True, cwd=".")
    m = re.match(r"func ([0-9A-F]+)\.\.([0-9A-F]+)", out.stdout)
    s, e = int(m.group(1), 16), int(m.group(2), 16)
    lines = disasm(s, e)
    calls = [t for a, t in lines if "call" in t]
    jmps = [t for a, t in lines if re.match(r"jmp\s+0x", t)]
    print(f"{cls:8s} save={s:X} calls={[c.split()[-1] for c in calls]} jmp={[j.split()[-1] for j in jmps]}")

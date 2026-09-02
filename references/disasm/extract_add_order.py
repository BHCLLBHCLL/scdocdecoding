"""Extract the member-reference (add) order from each class's save_data.

Key functions:
  0x1811d4060  save_entity_pointer(list, ent, flag)  -> writes $index, adds to worklist
  0x181192bc0  attrib-chain common save (this, list)
Usage: python extract_add_order.py
"""
import subprocess
import re

DLL = r"C:/Program Files/ANSYS Inc/v195/scdm/SpaACIS.dll"
BASE = 0x180000000
SAVE_PTR = 0x1811d4060
ATTRIB_COMMON = 0x181192bc0

SAVE_DATA = {
    "BODY": 0x11F9E30, "LUMP": 0x120A8F0, "SHELL": 0x120D280, "FACE": 0x12048D0,
    "LOOP": 0x1207520, "COEDGE": 0x11FC7B0, "EDGE": 0x11FF410, "TVERTEX": 0x1215180,
    "WIRE": 0x1219360, "EE_LIST": 0x11C4510,
}
# geometry classes: save_data is inside their save thunk after a prologue
GEO_SAVE_DATA = {"PLANE": 0x11AF3E0, "STRAIGHT": 0x11A4660, "CONE": 0x11AF3E0,
                 "ELLIPSE": 0x11A4660, "INTCURVE": 0x11A4660}


def bounds(rva):
    out = subprocess.run(["python", "references/disasm/pdata.py", DLL, f"{rva:X}"],
                         capture_output=True, text=True, cwd=".")
    m = re.match(r"func ([0-9A-F]+)\.\.([0-9A-F]+)", out.stdout)
    return (int(m.group(1), 16), int(m.group(2), 16)) if m else (rva, rva + 0x200)


def disasm(s, e):
    out = subprocess.run(
        ["objdump", "-d", f"--start-address={BASE+s:#x}", f"--stop-address={BASE+e:#x}",
         "-M", "intel", DLL], capture_output=True, text=True)
    lines = []
    for ln in out.stdout.splitlines():
        m = re.match(r"\s+([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*\t(.*)", ln)
        if m:
            lines.append((int(m.group(1), 16) - BASE, m.group(2).strip()))
    return lines


def analyze(name, s, e):
    lines = disasm(s, e)
    events = []
    last_src = None
    for addr, text in lines:
        m = re.match(r"mov\s+(r[a-z0-9]+),QWORD PTR \[r[a-z]+\+?(0x[0-9a-f]+)?\]", text)
        if m and "QWORD PTR" in text:
            last_src = m.group(2) or "0"
        if f"{SAVE_PTR:x}" in text and "call" in text:
            events.append((addr, f"SAVE_PTR  member_off={last_src}"))
            last_src = None
        elif f"{ATTRIB_COMMON:x}" in text and "call" in text:
            events.append((addr, "ATTRIB_CHAIN"))
            last_src = None
    print(f"== {name}::save_data ({s:X}..{e:X}) ==")
    for a, ev in events:
        print(f"  {a:X}  {ev}")
    print()


for name, rva in SAVE_DATA.items():
    s, e = bounds(rva)
    analyze(name, s, e)
for name, rva in GEO_SAVE_DATA.items():
    s, e = bounds(rva)
    analyze(name, s, e)

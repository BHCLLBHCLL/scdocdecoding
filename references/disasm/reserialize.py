# -*- coding: utf-8 -*-
"""Reserialize a SAB stream from its token records with interning.

Usage: python reserialize.py <in.sab> <out.sab>
"""
import io
import struct
import sys

from scdoc_parser import sab as sab_mod

T_REC, T_CHAIN, T_TERM, T_ID = 0x0D, 0x0E, 0x11, 0x25
T_PTR, T_INT, T_DBL, T_STR = 0x0C, 0x04, 0x06, 0x07
T_V3, T_V3B, TA, TB, T15 = 0x13, 0x14, 0x0A, 0x0B, 0x15


def tok_bytes(t, rmap):
    if t.kind in ("ptr", "int", "int15"):
        v = t.value
        if t.kind == "ptr" and v >= 0 and rmap:
            v = rmap.get(v, v)
        return bytes([{"ptr": T_PTR, "int": T_INT, "int15": T15}[t.kind]]) + struct.pack("<i", v)
    if t.kind == "double":
        return bytes([T_DBL]) + struct.pack("<d", t.value)
    if t.kind == "string":
        raw = str(t.value).encode("latin-1")
        return bytes([T_STR, len(raw)]) + raw
    if t.kind in ("vec3", "vec3b"):
        return bytes([T_V3 if t.kind == "vec3" else T_V3B]) + struct.pack("<3d", *t.value)
    if t.kind == "flag_a":
        return bytes([TA])
    if t.kind == "flag_b":
        return bytes([TB])
    raise ValueError(t.kind)


def rec_bytes(r, rmap, seen):
    out = bytearray()
    chain = [] if r.name == "End-of-ACIS-data" else r.chain
    for cname, cid in chain:
        if cid is not None and cid >= 0 and seen.get(cname) == cid:
            out += bytes([T_CHAIN, 5, T_ID]) + struct.pack("<i", cid)
            continue
        hdr = len(cname) + (5 if cid is not None else 0)
        out += bytes([T_CHAIN, hdr]) + cname.encode("latin-1")
        if cid is not None:
            out += bytes([T_ID]) + struct.pack("<i", cid)
            seen[cname] = cid
    if r.rec_id is not None and seen.get(r.name) == r.rec_id:
        out += bytes([T_REC, 5, T_ID]) + struct.pack("<i", r.rec_id)
    else:
        hdr = len(r.name) + (5 if r.rec_id is not None else 0)
        out += bytes([T_REC, hdr]) + r.name.encode("latin-1")
        if r.rec_id is not None:
            out += bytes([T_ID]) + struct.pack("<i", r.rec_id)
            seen[r.name] = r.rec_id
    for t in r.tokens:
        out += tok_bytes(t, rmap)
    out += bytes([T_TERM])
    return bytes(out)


def main():
    src = io.open(sys.argv[1], "rb").read()
    sf = sab_mod.tokenize(src)
    out = bytearray(src[:sf.records[0].offset])
    seen = {}
    for r in sf.records:
        out += rec_bytes(r, {}, seen)
    tail_pos = src.find(b"\x0d\x10End-of-ACIS-data")
    if tail_pos < 0:
        tail_pos = src.find(b"End-of-ACIS-data") - 2
    out += src[tail_pos:]
    io.open(sys.argv[2], "wb").write(bytes(out))
    print("wrote", sys.argv[2], len(out), "of", len(src))


if __name__ == "__main__":
    main()

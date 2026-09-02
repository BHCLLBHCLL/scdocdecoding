# -*- coding: utf-8 -*-
"""Golden 141-record skeleton, with selected kinds replaced by our native
record CONTENT (ptrs remapped golden<->native via kind-bucket order).

Usage: python hybrid_native_golden.py <native.sab> <golden.sab> <out.sab> [kinds...]
If kinds omitted, replace all non-attrib kinds.
"""
import io
import struct
import sys

from scdoc_parser import sab as sab_mod

SKIP = {"attrib", "string_attrib", "wstring_attrib", "rgb_color"}


def load(path):
    return sab_mod.tokenize(io.open(path, "rb").read())


def buckets(recs):
    b = {}
    for r in recs:
        if r.kind in SKIP:
            continue
        b.setdefault(r.kind, []).append(r)
    return b


def rec_bytes(r, rmap, seen=None):
    out = bytearray()
    seen = {} if seen is None else seen
    for cname, cid in (r.chain if r.name != "End-of-ACIS-data" else []):
        if cid is not None and cid >= 0 and seen.get(cname) == cid:
            out += bytes([0x0E, 5, 0x25]) + struct.pack("<i", cid)
            continue
        hdr = len(cname) + (5 if cid is not None else 0)
        out += bytes([0x0E, hdr]) + cname.encode("latin-1")
        if cid is not None:
            out += bytes([0x25]) + struct.pack("<i", cid)
            seen[cname] = cid
    if r.rec_id is not None and seen.get(r.name) == r.rec_id:
        out += bytes([0x0D, 5, 0x25]) + struct.pack("<i", r.rec_id)
    else:
        hdr = len(r.name) + (5 if r.rec_id is not None else 0)
        out += bytes([0x0D, hdr]) + r.name.encode("latin-1")
        if r.rec_id is not None:
            out += bytes([0x25]) + struct.pack("<i", r.rec_id)
            seen[r.name] = r.rec_id
    for t in r.tokens:
        if t.kind in ("ptr", "int", "int15"):
            v = t.value
            if t.kind == "ptr" and v >= 0:
                v = rmap.get(v, v)
            out += bytes([{"ptr": 0x0C, "int": 0x04, "int15": 0x15}[t.kind]]) + struct.pack("<i", v)
        elif t.kind == "double":
            out += bytes([0x06]) + struct.pack("<d", t.value)
        elif t.kind == "string":
            raw = str(t.value).encode("latin-1")
            out += bytes([0x07, len(raw)]) + raw
        elif t.kind in ("vec3", "vec3b"):
            out += bytes([0x13 if t.kind == "vec3" else 0x14]) + struct.pack("<3d", *t.value)
        elif t.kind == "flag_a":
            out += bytes([0x0A])
        elif t.kind == "flag_b":
            out += bytes([0x0B])
        else:
            raise ValueError(t.kind)
    out += bytes([0x11])
    return bytes(out)


def main():
    native_p, golden_p, out_p = sys.argv[1], sys.argv[2], sys.argv[3]
    kinds = set(sys.argv[4:])
    nf = load(native_p)
    gf = load(golden_p)
    bn = buckets(nf.records)
    bg = buckets(gf.records)
    # native idx -> golden idx (per kind bucket order); indices are 1-based
    rmap = {}
    for k in bn:
        if k not in bg or len(bn[k]) != len(bg[k]):
            print("!! bucket mismatch", k, len(bn[k]), len(bg.get(k, [])))
            return
        for ni, gi in zip(bn[k], bg[k]):
            rmap[ni.index] = gi.index
    print("remap table size:", len(rmap))
    data = io.open(golden_p, "rb").read()
    out = bytearray()
    out += data[:gf.records[0].offset]
    nb = {k: list(bn[k]) for k in bn}
    seen = {}
    for r in gf.records:
        if r.kind in SKIP:
            out += rec_bytes(r, {}, seen)
            continue
        if kinds and r.kind not in kinds:
            out += rec_bytes(r, {}, seen)
            continue
        twins = [nr for nr in nb.get(r.kind, [])
                 if rmap.get(nr.index) == r.index]
        if not twins:
            print("!! no native twin for", r.kind, r.index)
            return
        out += rec_bytes(twins[0], rmap, seen)
    # tail: copy the original end-marker bytes verbatim
    tail = data[:].find(b"End-of-ACIS-data")
    if tail < 0:
        tail = data.find(b"End-of-ACIS-data")
        tail -= 2
    out += data[tail:]
    io.open(out_p, "wb").write(bytes(out))
    print("wrote", out_p, len(out))


if __name__ == "__main__":
    main()

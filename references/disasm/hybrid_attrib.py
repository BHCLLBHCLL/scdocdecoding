# -*- coding: utf-8 -*-
"""Hybrid: native non-attrib records + converter attrib records.

If official restore succeeds, the attribs are the culprit (and vice versa).
Usage: python hybrid_attrib.py <native.sab> <converter.sab> <out.sab>
"""
import io
import sys

from scdoc_parser import sab as sab_mod

SKIP = {"attrib", "string_attrib", "wstring_attrib", "rgb_color"}


def load(path):
    return sab_mod.tokenize(io.open(path, "rb").read())


def rec_bytes(r):
    out = bytearray()
    for cname, cid in r.chain:
        hdr = len(cname) + (5 if cid is not None else 0)
        out += bytes([0x0E, hdr]) + cname.encode("latin-1")
        if cid is not None:
            out += bytes([0x25]) + _p(cid)
    hdr = len(r.name) + (5 if r.rec_id is not None else 0)
    out += bytes([0x0D, hdr]) + r.name.encode("latin-1")
    if r.rec_id is not None:
        out += bytes([0x25]) + _p(r.rec_id)
    for t in r.tokens:
        out += tok(t)
    out += bytes([0x11])
    return bytes(out)


def _p(v):
    import struct
    return struct.pack("<i", v)


def tok(t):
    import struct
    if t.kind in ("ptr", "int", "int15"):
        return bytes([{"ptr": 0x0C, "int": 0x04, "int15": 0x15}[t.kind]]) + struct.pack("<i", t.value)
    if t.kind == "double":
        return bytes([0x06]) + struct.pack("<d", t.value)
    if t.kind == "string":
        raw = str(t.value).encode("latin-1")
        return bytes([0x07, len(raw)]) + raw
    if t.kind in ("vec3", "vec3b"):
        return bytes([0x13 if t.kind == "vec3" else 0x14]) + struct.pack("<3d", *t.value)
    if t.kind == "flag_a":
        return bytes([0x0A])
    if t.kind == "flag_b":
        return bytes([0x0B])
    raise ValueError(t.kind)


def main():
    native = load(sys.argv[1])
    conv = load(sys.argv[2])
    out_path = sys.argv[3]
    # header/tail from native; take records in native order but swap attrib
    # records with the converter's attrib records (by kind-bucket order).
    conv_attr = [r for r in conv.records if r.kind in SKIP]
    native_attr = [r for r in native.records if r.kind in SKIP]
    print(f"native={len(native.records)} attr={len(native_attr)} "
          f"conv={len(conv.records)} attr={len(conv_attr)}")
    if len(conv_attr) != len(native_attr):
        print("!! attrib count differs; abort")
        return
    ci = 0
    out = bytearray()
    # header: copy native bytes up to first record
    data = io.open(sys.argv[1], "rb").read()
    out += data[:native.records[0].offset]
    for r in native.records:
        if r.kind in SKIP:
            rr = conv_attr[ci]
            ci += 1
        else:
            rr = r
        out += rec_bytes(rr)
    # tail
    out += data[native.records[-1].offset + len(rec_bytes(native.records[-1])):]
    io.open(out_path, "wb").write(bytes(out))
    print("wrote", out_path, len(out))


if __name__ == "__main__":
    main()

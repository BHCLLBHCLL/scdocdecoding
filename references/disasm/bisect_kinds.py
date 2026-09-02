# -*- coding: utf-8 -*-
"""Bisect: take the CONVERTER SAB (restores fine) and replace selected record
kinds with OUR native record content, remapping pointers via kind-bucket
position.  Run SabSatConverter restore after each to find the breaking kind.

Usage: python bisect_kinds.py <ours.sab> <base.sab> <out.sab> [kinds...]
  no kinds -> replace nothing (sanity re-serialization must succeed)
"""
import io
import struct
import sys

from scdoc_parser import sab as sab_mod

SKIP = {"attrib", "string_attrib", "wstring_attrib", "rgb_color"}
REPLACABLE = {"body", "lump", "shell", "face", "loop", "plane", "coedge",
              "edge", "vertex", "straight", "point", "cone", "ellipse"}


def load(path):
    return sab_mod.tokenize(io.open(path, "rb").read())


def buckets(recs, attribs=False):
    b = {}
    for r in recs:
        if (r.kind in SKIP) != attribs:
            continue
        b.setdefault(r.kind, []).append(r)
    return b


def tok_bytes(t, rmap):
    if t.kind in ("ptr", "int", "int15"):
        v = t.value
        if t.kind == "ptr" and v >= 0:
            v = rmap.get(v, v)
        return bytes([{"ptr": 0x0C, "int": 0x04, "int15": 0x15}[t.kind]]) + struct.pack("<i", v)
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


def rec_bytes(r, rmap, seen):
    out = bytearray()
    for cname, cid in r.chain:
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
        out += tok_bytes(t, rmap)
    out += bytes([0x11])
    return bytes(out)


def main():
    ours_p, base_p, out_p = sys.argv[1], sys.argv[2], sys.argv[3]
    kinds = set(sys.argv[4:])
    nf, bf = load(ours_p), load(base_p)
    bn = buckets(nf.records)
    bg = buckets(bf.records)
    # full remap: every record kind including attribs
    del bn, bg
    rmap = {}
    allk = set()
    for r in nf.records:
        allk.add(r.kind)
    for r in bf.records:
        allk.add(r.kind)
    for k in allk:
        na = [r for r in nf.records if r.kind == k]
        nb = [r for r in bf.records if r.kind == k]
        if len(na) != len(nb):
            print("!! bucket mismatch", k, len(na), len(nb))
            return
        for a, b in zip(na, nb):
            rmap[a.index] = b.index
    print("remap:", len(rmap), "entries")
    base_data = io.open(base_p, "rb").read()
    # header: copy base up to first record
    first_off = bf.records[0].offset
    out = bytearray(base_data[:first_off])
    seen = {}
    replace_idx = {}
    if kinds:
        for k in kinds:
            if k in SKIP and "attrib" not in sys.argv[4:]:
                continue
            na = [r for r in nf.records if r.kind == k]
            nb = [r for r in bf.records if r.kind == k]
            for a, b in zip(na, nb):
                replace_idx[b.index] = a
    for r in bf.records:
        if r.index in replace_idx:
            out += rec_bytes(replace_idx[r.index], rmap, seen)
        else:
            out += rec_bytes(r, {}, seen)
    # tail: base end marker verbatim
    tail = base_data.find(b"End-of-ACIS-data")
    tail -= 2  # 0x0D 0x10
    out += base_data[tail:]
    io.open(out_p, "wb").write(bytes(out))
    print("wrote", out_p, len(out))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Replace the k-th record (in unified kind-bucket order) of base with our
corresponding record.  Unifies kind sequence and replaces a single record.

Usage: python record_swap.py <native.sab> <base.sab> <out.sab> <kind> [index]
If index omitting, replace ALL records of that kind... (unused).
"""
import io
import struct
import sys

from references.disasm.reserialize import rec_bytes, tok_bytes
from scdoc_parser import sab as sab_mod

SKIP = {"attrib", "string_attrib", "wstring_attrib", "rgb_color"}


def ordered(recs, kind):
    return [r for r in recs if r.kind == kind]


def main():
    native_p, base_p, out_p, kind = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    idx = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    nf = sab_mod.tokenize(io.open(native_p, "rb").read())
    bf = sab_mod.tokenize(io.open(base_p, "rb").read())
    na = ordered(nf.records, kind)
    nb = ordered(bf.records, kind)
    if len(na) != len(nb):
        print("!! count mismatch", len(na), len(nb))
        return
    # remap native idx->base idx for all kinds
    rmap = {}
    allk = set(r.kind for r in nf.records) | set(r.kind for r in bf.records)
    for k in allk:
        a = [r for r in nf.records if r.kind == k]
        b = [r for r in bf.records if r.kind == k]
        if len(a) != len(b):
            print("!! mismatch", k)
            return
        for x, y in zip(a, b):
            rmap[x.index] = y.index
    base_data = io.open(base_p, "rb").read()
    out = bytearray(base_data[:bf.records[0].offset])
    seen = {}
    for r in bf.records:
        if r.kind == kind and r is nb[idx]:
            out += rec_bytes(na[idx], rmap, seen)
        else:
            out += rec_bytes(r, {}, seen)
    tail = base_data.find(b"\x0d\x10End-of-ACIS-data")
    if tail < 0:
        tail = base_data.find(b"End-of-ACIS-data") - 2
    out += base_data[tail:]
    io.open(out_p, "wb").write(bytes(out))
    print("wrote", out_p, "kind", kind, "idx", idx)


if __name__ == "__main__":
    main()

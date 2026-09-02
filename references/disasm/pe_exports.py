"""Parse PE export table of a DLL: name -> (rva, file_offset).

Usage: python pe_exports.py <dll> [name_filter_regex]
Prints: rva  file_off  size_hint  name   (entries sorted by rva, with gap to next export as size hint)
"""
import re
import struct
import sys


def parse_pe(path):
    data = open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0"
    coff = e_lfanew + 4
    machine, num_sections, _, _, _, opt_size, _chars = struct.unpack_from("<HHIIIHH", data, coff)
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic == 0x20B:  # PE32+
        image_base = struct.unpack_from("<Q", data, opt + 24)[0]
        dd = opt + 112
    else:
        image_base = struct.unpack_from("<I", data, opt + 28)[0]
        dd = opt + 96
    exp_rva, exp_size = struct.unpack_from("<II", data, dd)
    sections = []
    sec_off = opt + opt_size
    for i in range(num_sections):
        name = data[sec_off:sec_off + 8].rstrip(b"\0").decode("latin-1")
        vsize, rva, rsize, roff = struct.unpack_from("<IIII", data, sec_off + 8)
        sections.append((name, rva, min(vsize, rsize), roff))
        sec_off += 40

    def r2o(rva):
        for name, srva, ssize, soff in sections:
            if srva <= rva < srva + ssize:
                return soff + (rva - srva)
        return None

    eo = r2o(exp_rva)
    _, _, _, _, name_rva, ord_base, n_funcs, n_names, aof, aon, aoo = struct.unpack_from("<IIHHIIIIIII", data, eo)
    funcs = struct.unpack_from("<%dI" % n_funcs, data, r2o(aof))
    names = struct.unpack_from("<%dI" % n_names, data, r2o(aon))
    ords = struct.unpack_from("<%dH" % n_names, data, r2o(aoo))
    out = []
    for i in range(n_names):
        nrva = names[i]
        o = r2o(nrva)
        end = data.index(b"\0", o)
        name = data[o:end].decode("utf-8", "replace")
        fn_rva = funcs[ords[i]]
        fo = r2o(fn_rva)
        out.append((fn_rva, fo, name))
    out.sort()
    return image_base, out, data


def main():
    path, filt = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None
    base, entries, _ = parse_pe(path)
    pat = re.compile(filt) if filt else None
    rows = [(rva, fo, name) for rva, fo, name in entries if not pat or pat.search(name)]
    rows.sort()
    for i, (rva, fo, name) in enumerate(rows):
        nxt = rows[i + 1][0] if i + 1 < len(rows) else 0
        gap = (nxt - rva) if nxt > rva else 0
        print(f"{rva:08X}  off={fo:08X}  gap={gap:5X}  {name}")
    print(f"; total={len(rows)} base={base:X}", file=sys.stderr)


if __name__ == "__main__":
    main()

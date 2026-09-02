"""Find exact function bounds from PE .pdata (x64 exception directory).

Usage: python pdata.py <dll> <hex_rva> [<hex_rva>...]
Prints: rva start..end (size) for the function starting at/before each rva.
"""
import struct
import sys


def load_pdata(path):
    data = open(path, "rb").read()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    coff = e + 4
    _m, nsec, _t, _s, _n, optsz, _c = struct.unpack_from("<HHIIIHH", data, coff)
    opt = coff + 20
    dd = opt + 112  # PE32+
    exp_rva, exp_size = struct.unpack_from("<II", data, dd + 3 * 8)  # entry 3 = Exception
    secs = []
    so = opt + optsz
    for _ in range(nsec):
        nm = data[so:so + 8].rstrip(b"\0").decode("latin-1")
        vsize, rva, rsize, roff = struct.unpack_from("<IIII", data, so + 8)
        secs.append((rva, min(vsize, rsize), roff))
        so += 40

    def r2o(rva):
        for srva, ssize, soff in secs:
            if srva <= rva < srva + ssize:
                return soff + (rva - srva)
        return None

    o = r2o(exp_rva)
    funcs = []
    for i in range(exp_size // 12):
        start, end, unw = struct.unpack_from("<III", data, o + i * 12)
        if start == 0:
            break
        funcs.append((start, end))
    funcs.sort()
    return funcs, data


def main():
    path = sys.argv[1]
    funcs, _ = load_pdata(path)
    for a in sys.argv[2:]:
        rva = int(a, 16)
        # function whose start equals rva, or the one containing it
        hit = None
        for start, end in funcs:
            if start == rva:
                hit = (start, end)
                break
            if start < rva < end and hit is None:
                hit = (start, end)
        if hit:
            s, e = hit
            print(f"func {s:X}..{e:X} size={e - s:X}")
        else:
            print(f"no .pdata entry for {rva:X}")


if __name__ == "__main__":
    main()

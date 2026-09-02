# -*- coding: utf-8 -*-
"""Field-level diff of our SAB stream against the official box.scdoc stream.

Pair non-attrib records in order (kinds must match), then compare token
sequences field by field.  Pointer values are compared as (target_kind)
roles; scalar tokens compared literally.
Usage: python diff_official.py <ours.sab-ish bytes?> -- ours comes from the
scdoc package built by _build_sab; official from references/golden/ref_tet.
"""
import io
import sys

sys.path.insert(0, ".")
from scdoc_parser import sab as sab_mod
from scdoc_parser.opc import parse_package

SKIP = {"attrib", "string_attrib", "wstring_attrib", "rgb_color"}
_REC_KIND = None


def load_sab(kind, path):
    if kind == "pkg":
        pkg = parse_package(path)
        data = pkg.read(pkg.find_geometry()[0].name)
    else:
        data = io.open(path, "rb").read()
    return sab_mod.tokenize(data).records


def pair(recs_a, recs_b):
    """Within each kind, pair records in order (interleave can differ)."""
    def buckets(recs):
        b = {}
        for r in recs:
            if r.kind in SKIP:
                continue
            b.setdefault(r.kind, []).append(r)
        return b

    ba = buckets(recs_a)
    bb = buckets(recs_b)
    if set(ba) != set(bb):
        print(f"!! kind sets differ: ours={sorted(ba)} official={sorted(bb)}")
        return None
    pairs = []
    for k in sorted(ba):
        if len(ba[k]) != len(bb[k]):
            print(f"!! count mismatch kind {k}: ours={len(ba[k])} off={len(bb[k])}")
            return None
        for x, y in zip(ba[k], bb[k]):
            if x.name != y.name:
                print(f"!! name mismatch kind {k}: {x.name} vs {y.name}")
                return None
            pairs.append((x, y))
    return pairs


def role_map(recs_pair, kind):
    """Map record index -> kind (for pointer role comparison)."""
    out = {}
    for r in recs_pair:
        out[id(r)] = r.kind
    return out


def fmt_tok(t):
    if t.kind == "ptr":
        return "$%d" % t.value
    if t.kind == "string":
        return repr(t.value)[:24]
    if t.kind == "vec3" or t.kind == "vec3b":
        return "(%s)" % ",".join("%.4g" % v for v in t.value)
    return str(t.value)


def compare(a_rec, b_rec, ri, similar, kind_of_a=None, kind_of_b=None):
    ta = a_rec.tokens
    tb = b_rec.tokens
    for i in range(min(len(ta), len(tb))):
        x, y = ta[i], tb[i]
        if x.kind != y.kind:
            similar.append(f"rec#{ri} {a_rec.kind}: token#{i} kind {x.kind} vs {y.kind}")
            continue
        if x.kind == "ptr":
            if (x.value >= 0) != (y.value >= 0):
                similar.append(f"rec#{ri} {a_rec.kind}: ptr#{i} nullness {x.value} vs {y.value}")
                continue
            if x.value >= 0 and kind_of_a and kind_of_b:
                ka = kind_of_a.get(x.value)
                kb = kind_of_b.get(y.value)
                if ka != kb:
                    similar.append(f"rec#{ri} {a_rec.kind}: ptr#{i} target {ka} vs {kb}")
            continue
        if x.kind in ("int", "double"):
            if x.value != y.value:
                similar.append(f"rec#{ri} {a_rec.kind}: {x.kind}#{i} {x.value} vs {y.value}")
        elif x.kind == "string":
            # name tag strings differ by design (value/decorate); values matter
            continue
        elif x.kind in ("flag_a", "flag_b"):
            continue
        elif x.kind in ("vec3", "vec3b"):
            if max(abs(x.value[k] - y.value[k]) for k in range(3)) > 1e-12:
                similar.append(f"rec#{ri} {a_rec.kind}: vec#{i} {x.value} vs {y.value}")
    if len(ta) != len(tb):
        similar.append(f"rec#{ri} {a_rec.kind}: token count {len(ta)} vs {len(tb)}")


def main():
    ours_path = sys.argv[1]   # our scdoc package or raw .sab
    off_path = sys.argv[2]    # official scdoc package or raw .sab
    ours = load_sab("raw" if ours_path.endswith(".sab") else "pkg", ours_path)
    off = load_sab("raw" if off_path.endswith(".sab") else "pkg", off_path)
    pairs = pair(ours, off)
    if pairs is None:
        return
    kind_of_a = {r.index: r.kind for r in ours}
    kind_of_b = {r.index: r.kind for r in off}
    diffs = []
    for ri, (a, b) in enumerate(pairs):
        compare(a, b, ri, diffs, kind_of_a, kind_of_b)
    print(f"paired {len(pairs)} records, {len(diffs)} field diffs")
    show = diffs[:40]
    for d in show:
        print(" ", d)
    if len(diffs) > 40:
        print(f"... {len(diffs) - 40} more")


if __name__ == "__main__":
    main()

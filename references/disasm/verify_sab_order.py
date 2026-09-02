"""Verify the ACIS save traversal (worklist) model directly on golden SAB data.

Model:
  - records are indexed 1..N in file order (= entity index, since SAT/SAB
    writer assigns index at first reference and writes the record in
    worklist order; for the golden file the two coincide)
  - record i's pointer tokens (in field order) are the save_entity_pointer
    calls of its save_data: each references an entity index, and any index
    not yet in the worklist is appended to the tail (FIFO, when the save
    driver iterates the list with a growing end).

If FIFO holds, popping 1,2,3,...,N exactly reproduces the file order.
Output: per-record pointer refs + FIFO/LIFO verdict + mismatch detail.
"""
import sys

from scdoc_parser import sab as sab_mod


def load_records(path):
    pkg = __import__("scdoc_parser.opc", fromlist=["parse_package"]).parse_package(path)
    d = pkg.read(pkg.find_geometry()[0].name)
    return sab_mod.tokenize(d).records, d


def main(path):
    recs, raw = load_records(path)
    n = len(recs)
    print(f"records={n}, sab bytes={len(raw)}")
    refs = []
    kinds = []
    for r in recs:
        ptrs = [x.value for x in r.tokens if x.kind == "ptr"]
        refs.append(ptrs)
        kinds.append(r.kind)
    # show first few records with refs for sanity
    for i in range(min(12, n)):
        print(f"#{i+1:3d} {kinds[i]:24s} refs={refs[i]}")

    def simulate(mode):
        visited = {0}  # record indices are 0-based; record 0 = body root
        queue = [0]
        seq = []
        while queue:
            cur = queue.pop(0) if mode == "fifo" else queue.pop()
            seq.append(cur)
            for m in refs[cur]:
                if m < 0 or m >= n:
                    continue
                if m not in visited:
                    visited.add(m)
                    queue.append(m)
        return seq

    for mode in ("fifo", "lifo"):
        seq = simulate(mode)
        expected = list(range(n))
        ok = seq == expected
        print(f"{mode.upper()}: pop order == 0..N-1 ? {ok}")
        if not ok:
            for i, (a, b) in enumerate(zip(seq, expected)):
                if a != b:
                    print(f"  first mismatch pop#{i+1}: got #{a} ({kinds[a]}) want #{b} ({kinds[b]})")
                    print(f"  got   window: {[kinds[x] for x in seq[max(0,i-2):i+9]]}")
                    print(f"  want  window: {[kinds[x] for x in range(max(0,b-2), min(n,b+7))]}")
                    break


if __name__ == "__main__":
    main(sys.argv[1])

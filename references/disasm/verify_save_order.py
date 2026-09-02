"""Prove the ACIS save traversal algorithm against an official SAT stream.

Model (from reverse engineering of SpaACIS.dll save methods):
  - api_save_entity_list seeds a worklist (ENTITY_LIST) with the top entity.
  - Each entity's save_data writes its record, and for every referenced
    ENTITY pointer calls save_entity_pointer(list, ent) which either returns
    the existing index (entity already in worklist/written) or assigns the
    NEXT free index and appends the entity to the worklist tail (FIFO).
  - Entity indices are thus assigned in first-reference order; records are
    written in worklist order.  In the SAT text, rows are records in index
    order (N-th entity record -> index N), and $M fields are references.

So: simulate FIFO worklist from the official SAT rows.  If the pop order is
1,2,3,...,N the FIFO model is confirmed; try LIFO otherwise.

Usage: python verify_save_order.py <file.sat>
"""
import re
import sys

TP_LIKE = ("attrib", "point", "vertex")


def parse_sat(path):
    rows = []  # (classname, refs_in_field_order)
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("2900 ") or line[0].isdigit():
            continue
        if line.startswith("End-of-ACIS-data"):
            break
        if line.startswith("T @"):
            continue
        # first token = class name (may include '-' like string_attrib-name_attrib-gen-attrib)
        parts = line.split(None, 2)
        cls = parts[0]
        rest = line[len(cls):].strip()
        refs = []
        # walk tokens: $N or $-1 are pointers; skip non-entity fields
        for tok in rest.split():
            if tok == "$-1":
                continue
            if tok == "$0":
                continue
            m = re.match(r"^\$(\d+)$", tok)
            if m:
                refs.append(int(m.group(1)))
        rows.append((cls, refs))
    return rows


def simulate(rows, queue_mode="fifo"):
    n = len(rows)
    visited = {1}
    queue = [1]
    seq = []
    while queue:
        if queue_mode == "fifo":
            cur = queue.pop(0)
        else:
            cur = queue.pop()
        seq.append(cur)
        cls, refs = rows[cur - 1]
        for m in refs:
            if m < 1 or m > n:
                continue
            if m not in visited:
                visited.add(m)
                queue.append(m)
    return seq


def main():
    path = sys.argv[1]
    rows = parse_sat(path)
    print(f"parsed {len(rows)} entity records from {path}")
    for mode in ("fifo", "lifo"):
        seq = simulate(rows, mode)
        expected = list(range(1, len(rows) + 1))
        ok = seq == expected
        print(f"{mode.upper():5s}: pop order == 1..N ? {ok}")
        if not ok:
            # show first mismatch
            for i, (a, b) in enumerate(zip(seq, expected)):
                if a != b:
                    print(f"   first mismatch at pop#{i+1}: got entity {a} ({rows[a-1][0]}) want {b} ({rows[b-1][0]})")
                    print(f"   mismatch window: {[rows[x-1][0] for x in seq[i:i+8]]}")
                    print(f"   expected window: {[rows[x-1][0] for x in expected[i:i+8]]}")
                    break
    # kind sequence summary of the stream itself
    print("\nkind sequence (per record):")
    k = [cls for cls, _ in rows]
    # compress
    out, last, cnt = [], None, 0
    for c in k:
        if c == last:
            cnt += 1
        else:
            if last:
                out.append(f"{last}x{cnt}" if cnt > 1 else last)
            last, cnt = c, 1
    if last:
        out.append(f"{last}x{cnt}" if cnt > 1 else last)
    print(" ".join(out[:40]), "... (compressed)")


if __name__ == "__main__":
    main()

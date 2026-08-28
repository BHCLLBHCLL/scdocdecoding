"""M5 facets: STL into the session + mesh facet operations.

Dependency-light (numpy only). Supports binary & ASCII STL, normal reversal, and
turning a triangle soup into an OCCT shell (via the kernel) so a mesh can join the
session as a facet body. Gated on pythonocc-core for the OCCT parts.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Sequence, Tuple

import numpy as np

Vec3 = Tuple[float, float, float]


def read_stl(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Read an STL (binary or ASCII) into (verts (N,3), tris (M,3) as vertex indices)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:5] == b"solid" and b"facet" in data[:512]:
        return _parse_ascii_stl(data)
    return _parse_binary_stl(data)


def _parse_binary_stl(data: bytes) -> Tuple[np.ndarray, np.ndarray]:
    n = struct.unpack_from("<I", data, 80)[0]
    off = 84
    verts = []
    tris = []
    for i in range(n):
        if off + 50 > len(data):
            break
        tri = np.frombuffer(data, dtype="<f4", count=9, offset=off + 12).reshape(3, 3)
        base = len(verts)
        verts.append(tri)
        tris.append((base, base + 1, base + 2))
        off += 50
    if not verts:
        return np.zeros((0, 3), dtype="f4"), np.zeros((0, 3), dtype="i4")
    return np.concatenate(verts, axis=0), np.asarray(tris, dtype="i4")


def _parse_ascii_stl(data: bytes) -> Tuple[np.ndarray, np.ndarray]:
    text = data.decode("ascii", errors="ignore")
    verts: List[Vec3] = []
    tris = []
    cur = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            parts = line.split()[1:4]
            verts.append((float(parts[0]), float(parts[1]), float(parts[2])))
            cur.append(len(verts) - 1)
        if line.startswith("endfacet") and cur:
            if len(cur) >= 3:
                tris.append(tuple(cur[:3]))
            cur = []
    return np.asarray(verts, dtype="f4").reshape(-1, 3), np.asarray(tris, dtype="i4")


def write_stl(verts: np.ndarray, tris: np.ndarray, path: str) -> None:
    """Write an ASCII STL from (verts (N,3), tris (M,3) indices)."""
    with open(path, "w", encoding="ascii") as f:
        f.write("solid meshexport\n")
        for t in tris:
            a, b, c = (np.asarray(verts[i], dtype="f8") for i in t)
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 1e-12 else np.zeros(3)
            f.write("  facet normal %.6g %.6g %.6g\n" % tuple(n))
            f.write("    outer loop\n")
            for p in (a, b, c):
                f.write("      vertex %.6g %.6g %.6g\n" % tuple(p))
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write("endsolid meshexport\n")


def reverse_normals(verts: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """Flip every triangle's winding (reverse normals). Returns new (M,3) indices."""
    out = np.empty_like(tris)
    out[:, 0] = tris[:, 0]
    out[:, 1] = tris[:, 2]
    out[:, 2] = tris[:, 1]
    return out


def decimate(verts: np.ndarray, tris: np.ndarray, tidx: Sequence[int]):
    """Return the triangles in tidx (simple face-pruning used by the Reduce tool)."""
    keep = np.asarray(list(tidx), dtype="i4")
    return verts, tris[keep]


def mesh_faces(verts: np.ndarray, tris: np.ndarray):
    """Turn a triangle soup into OCCT faces (requires kernel)."""
    from scdm import kernel as K
    faces = []
    for t in tris:
        v0 = tuple(float(x) for x in verts[t[0]])
        v1 = tuple(float(x) for x in verts[t[1]])
        v2 = tuple(float(x) for x in verts[t[2]])
        faces.append(K.face_from_polygon([v0, v1, v2]))
    return faces


def mesh_to_shell(verts: np.ndarray, tris: np.ndarray, tol: float = 1e-6):
    """Sew a triangle soup into an OCCT shell (mesh body)."""
    from scdm import kernel as K
    faces = mesh_faces(verts, tris)
    return K.sew_faces(faces, tol=tol)


# --- mesh edit operations (G2-07: smooth / reduce / fill) ----------------------

def weld(verts: np.ndarray, tris: np.ndarray, tol: float = 1e-6):
    """Merge coincident vertices on a `tol` grid; returns (verts, tris)."""
    verts = np.asarray(verts, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    step = max(tol, 1e-12)
    keys = np.round(verts / step).astype(np.int64)
    uniq, idx, inv = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    new_v = verts[idx]
    new_t = inv[tris]
    keep = ((new_t[:, 0] != new_t[:, 1]) & (new_t[:, 1] != new_t[:, 2])
            & (new_t[:, 0] != new_t[:, 2]))
    return new_v, new_t[keep]


def laplacian_smooth(verts: np.ndarray, tris: np.ndarray, iters: int = 3,
                     factor: float = 0.5) -> np.ndarray:
    """Umbrella Laplacian smoothing; returns new vertex positions."""
    v = np.asarray(verts, dtype=np.float64).copy()
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    for _ in range(max(iters, 1)):
        acc = np.zeros_like(v)
        cnt = np.zeros(len(v), dtype=np.int64)
        for k in range(3):
            np.add.at(acc, t[:, k], v[t[:, (k + 1) % 3]])
            np.add.at(acc, t[:, k], v[t[:, (k + 2) % 3]])
            np.add.at(cnt, t[:, k], 2)
        nz = cnt > 0
        v[nz] += factor * (acc[nz] / cnt[nz, None] - v[nz])
    return v


def reduce_grid(verts: np.ndarray, tris: np.ndarray, cell: float):
    """Vertex-clustering decimation: snap vertices onto a `cell` grid."""
    verts = np.asarray(verts, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    if cell <= 0 or len(verts) == 0:
        return verts, tris
    keys = np.floor(verts / cell).astype(np.int64)
    uniq, inv = np.unique(keys, axis=0, return_inverse=True)
    new_v = np.zeros((len(uniq), 3), dtype=np.float64)
    cnt = np.zeros(len(uniq), dtype=np.int64)
    np.add.at(new_v, inv, verts)
    np.add.at(cnt, inv, 1)
    new_v /= cnt[:, None]
    new_t = inv[tris]
    keep = ((new_t[:, 0] != new_t[:, 1]) & (new_t[:, 1] != new_t[:, 2])
            & (new_t[:, 0] != new_t[:, 2]))
    new_t = new_t[keep]
    if len(new_t):
        _, uidx = np.unique(np.sort(new_t, axis=1), axis=0, return_index=True)
        new_t = new_t[np.sort(uidx)]
    return new_v, new_t


def boundary_loops(tris: np.ndarray) -> List[List[int]]:
    """Chain edges used by a single triangle into boundary vertex loops."""
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    use = {}
    for a, b, c in t:
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(int(u), int(v)), max(int(u), int(v)))
            use[key] = use.get(key, 0) + 1
    adj = {}
    for (u, v), n in use.items():
        if n == 1:
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, []).append(u)
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            nxts = [n for n in adj.get(cur, []) if n != prev and n not in seen]
            if not nxts:
                break
            prev, cur = cur, nxts[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def fill_holes(verts: np.ndarray, tris: np.ndarray):
    """Fan-triangulate open boundary loops; returns (tris, holes_filled)."""
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    added = []
    for loop in boundary_loops(t):
        for i in range(1, len(loop) - 1):
            added.append((loop[0], loop[i], loop[i + 1]))
    if not added:
        return t, 0
    return np.vstack([t, np.asarray(added, dtype=np.int64)]), len(added)

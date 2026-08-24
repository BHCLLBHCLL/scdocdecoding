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

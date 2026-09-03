"""ACIS SAB emitter using the reverse-engineered official save algorithm.

The official writer (SpaACIS.dll: api_save_entity_list + each class's
save_data) keeps a FIFO worklist of entities.  Every entity's save_data
writes its record and, for each ENTITY pointer field, calls
save_entity_pointer(list, ent): that helper assigns the record index at
FIRST reference (appending the entity to the worklist's tail) and writes the
index into the stream.  Iteration ends when the list is exhausted.

Proof (references/disasm/verify_sab_order.py): a FIFO simulation seeded at
the body reproduces the official box.scdoc record order 0..140 exactly;
LIFO does not.  So no per-model interleaving template is needed -- the
official interleave is an emergent property of the pointer field order.

Record field layouts below are copies of the official box.scdoc / cylinder
reference streams (tokens, ints, flags, uv domains).
"""
from __future__ import annotations

import math
import struct
from typing import Dict, List, Optional, Tuple

T_INT = 0x04
T_DOUBLE = 0x06
T_STRING = 0x07
T_PTR = 0x0C
T_RECORD = 0x0D
T_CHAIN = 0x0E
T_TERM = 0x11
T_VEC3 = 0x13
T_VEC3B = 0x14
T_FLAG_A = 0x0A
T_FLAG_B = 0x0B
T_INT15 = 0x15
T_ID = 0x25

MAGIC = b"ACIS BinaryFileT"
END_NAME = "End-of-ACIS-data"


def _ri(v) -> bytes:
    return struct.pack("<i", int(v))


def _rd(v) -> bytes:
    return struct.pack("<d", float(v))


def _ti(v) -> bytes:
    return bytes([T_INT]) + _ri(v)


def _td(v) -> bytes:
    return bytes([T_DOUBLE]) + _rd(v)


def _s(v: str) -> bytes:
    b = v.encode("latin-1")
    return bytes([T_STRING, len(b)]) + b


def _p(i) -> bytes:
    return bytes([T_PTR]) + _ri(i)


def _v3(x, y, z) -> bytes:
    return bytes([T_VEC3]) + _rd(x) + _rd(y) + _rd(z)


def _v3b(x, y, z) -> bytes:
    return bytes([T_VEC3B]) + _rd(x) + _rd(y) + _rd(z)


class _Rec:
    def __init__(self, name: str, class_id: Optional[int], chain=()):
        self.name = name
        self.class_id = class_id
        self.chain = chain
        self.tokens = bytearray()

    def add(self, *tokens) -> "_Rec":
        for t in tokens:
            self.tokens += t
        return self

    def bytes(self, seen=None):
        seen = seen if seen is not None else {}
        out = bytearray()
        for cname, cid in self.chain:
            if cid is not None and seen.get(cname) == cid:
                out += bytes([T_CHAIN, 5, T_ID]) + _ri(cid)
                continue
            hdrlen = len(cname) + (5 if cid is not None else 0)
            out += bytes([T_CHAIN, hdrlen]) + cname.encode("latin-1")
            if cid is not None:
                out += bytes([T_ID]) + _ri(cid)
                seen[cname] = cid
        if self.class_id is not None and seen.get(self.name) == self.class_id:
            out += bytes([T_RECORD, 5, T_ID]) + _ri(self.class_id)
            out += self.tokens
            out += bytes([T_TERM])
            return bytes(out)
        hdrlen = len(self.name) + (5 if self.class_id is not None else 0)
        out += bytes([T_RECORD, hdrlen]) + self.name.encode("latin-1")
        if self.class_id is not None:
            out += bytes([T_ID]) + _ri(self.class_id)
            seen[self.name] = self.class_id
        out += self.tokens
        out += bytes([T_TERM])
        return bytes(out)


class Worklist:
    """save_entity_list mirror: index assignment at first reference + FIFO."""

    def __init__(self):
        self._idx: Dict[object, int] = {}
        self._q: List[object] = []
        self._qpos = 0

    def ref(self, key):
        if key is None:
            return -1
        i = self._idx.get(key)
        if i is None:
            i = len(self._idx)
            self._idx[key] = i
            self._q.append(key)
        return i

    def run(self, seeds, makers):
        seen = {}
        out = bytearray()
        for s in seeds:
            self.ref(s)
        while self._qpos < len(self._q):
            key = self._q[self._qpos]
            self._qpos += 1
            out += makers.make(key, self).bytes(seen)
        return bytes(out)


# ----------------------------------------------------------------------
# geometry helpers (shared with scdoc_write.py's extractor)
# ----------------------------------------------------------------------
def _bbox(verts, idxs=None):
    use = [verts[i] for i in idxs] if idxs is not None else verts
    xs = [p[0] for p in use]
    ys = [p[1] for p in use]
    zs = [p[2] for p in use]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _ortho(n):
    a = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    x = (n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2],
         n[0] * a[1] - n[1] * a[0])
    m = (x[0] ** 2 + x[1] ** 2 + x[2] ** 2) ** 0.5 or 1.0
    return (x[0] / m, x[1] / m, x[2] / m)


def _edge_of(edges, a, b):
    for i, (u, v) in enumerate(edges):
        if {u, v} == {a, b}:
            return i
    raise ValueError("edge not found")


def _circ_bbox(center, R, axis):
    ex = R * math.sqrt(max(0.0, 1.0 - axis[0] * axis[0]))
    ey = R * math.sqrt(max(0.0, 1.0 - axis[1] * axis[1]))
    ez = R * math.sqrt(max(0.0, 1.0 - axis[2] * axis[2]))
    return ((center[0] - ex, center[1] - ey, center[2] - ez),
            (center[0] + ex, center[1] + ey, center[2] + ez))


# ----------------------------------------------------------------------
# record builders
# ----------------------------------------------------------------------
class Makers:
    """Builds records for every entity key; keys are ('kind', bi, ...)."""

    def __init__(self, items, colors=None):
        self.items = items            # [('planar', verts, edges, faces) | ('cyl', info)]
        self.col = {
            bi: (colors[bi] if colors and bi < len(colors)
                 else (0.745, 0.902, 0.961))
            for bi in range(len(items))}
        self._idx_of = {}             # bi -> index into self.items
        for bi, it in enumerate(items):
            self._idx_of[bi] = bi
        self.fi = {}                  # ('face', bi, fi) -> dict
        self.lc = {}                  # ('loop', bi, fi) -> [coedge keys]
        self.ce = {}                  # ('coedge', bi, fi, k) -> dict
        self.coe = {}                 # ('edge', bi, ei) -> [coedge keys]
        self.ei = {}                  # ('edge', bi, ei) -> dict
        self.vp = {}                  # ('vertex', bi, vi) -> incident edge key
        self._build_model()

    def _build_model(self):
        for bi, it in enumerate(self.items):
            if it[0] != "planar":
                continue
            verts, edges, faces = it[1], it[2], it[3]
            F = len(faces)
            for fi, f in enumerate(faces):
                loop = f["loop"]
                n = len(loop)
                for k in range(n):
                    a, b = loop[k], loop[(k + 1) % n]
                    eidx = _edge_of(edges, a, b)
                    sense = T_FLAG_B if edges[eidx][0] == a else T_FLAG_A
                    ck = ("coedge", bi, fi, k)
                    self.ce[ck] = {"loop": ("loop", bi, fi), "sense": sense,
                                   "edge": ("edge", bi, eidx)}
                    self.coe.setdefault(("edge", bi, eidx), []).append(ck)
                self.lc[("loop", bi, fi)] = [("coedge", bi, fi, k)
                                             for k in range(n)]
                self.fi[("face", bi, fi)] = {
                    "loop": loop, "verts": verts, "edges": edges, "f": f,
                    "bi": bi, "fi": fi, "n_faces": F}
            for ei, (v1, v2) in enumerate(edges):
                self.ei[("edge", bi, ei)] = {"v1": v1, "v2": v2,
                                             "verts": verts, "bi": bi,
                                             "ei": ei, "F": F}
                self.vp.setdefault(("vertex", bi, v1), ("edge", bi, ei))
                self.vp.setdefault(("vertex", bi, v2), ("edge", bi, ei))

    def item(self, bi):
        return self.items[bi]

    def cyl(self, bi):
        return self.items[bi][1]

    # -- planar topology ------------------------------------------------
    def make(self, key, wl):
        kind = key[0]
        if kind == "body":
            bi = key[1]
            it = self.item(bi)
            smin, smax = (it[1]["bbox"] if it[0] == "cyl"
                          else _bbox(it[1]))
            return (_Rec("body", 1)
                    .add(_p(wl.ref(("attrib", "bname", bi))), _ti(-1), _ti(-1),
                         _p(-1), _ti(0), _p(wl.ref(("lump", bi))), _p(-1),
                         _p(-1), bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))
        if kind == "lump":
            bi = key[1]
            it = self.item(bi)
            smin, smax = (it[1]["bbox"] if it[0] == "cyl"
                          else _bbox(it[1]))
            return (_Rec("lump", 7)
                    .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                         _p(wl.ref(("shell", bi))), _p(wl.ref(("body", bi))),
                         bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))
        if kind == "shell":
            bi = key[1]
            it = self.item(bi)
            smin, smax = (it[1]["bbox"] if it[0] == "cyl"
                          else _bbox(it[1]))
            return (_Rec("shell", 9)
                    .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1), _p(-1),
                         _p(wl.ref(("face", bi, 0))), _p(-1),
                         _p(wl.ref(("lump", bi))),
                         bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))
        if kind == "face":
            return (self._face(key, wl) if self.item(key[1])[0] == "planar"
                    else self._cface(key, wl))
        if kind == "loop":
            return (self._loop(key, wl) if self.item(key[1])[0] == "planar"
                    else self._cloop(key, wl))
        if kind == "coedge":
            return (self._coedge(key, wl) if self.item(key[1])[0] == "planar"
                    else self._ccoedge(key, wl))
        if kind == "edge":
            return (self._edge(key, wl) if self.item(key[1])[0] == "planar"
                    else self._cedge(key, wl))
        if kind == "vertex":
            return (self._vertex(key, wl) if self.item(key[1])[0] == "planar"
                    else self._cvertex(key, wl))
        if kind == "point":
            return (self._point(key, wl) if self.item(key[1])[0] == "planar"
                    else self._cpoint(key, wl))
        if kind == "plane":
            return self._plane(key, wl)
        if kind == "cone":
            return self._cone(key, wl)
        if kind == "straight":
            bi, ei = key[1], key[2]
            return (self._straight(key, wl) if self.item(bi)[0] == "planar"
                    else self._cstraight(key, wl))
        if kind == "ellipse":
            return self._ellipse(key, wl)
        if kind == "attrib":
            return self._attrib(key, wl)
        raise ValueError("unknown entity key " + repr(key))

    def _face(self, key, wl):
        bi, fi = key[1], key[2]
        d = self.fi[key]
        fmin, fmax = _bbox(d["verts"], d["loop"])
        nxt = ("face", bi, fi + 1) if fi + 1 < d["n_faces"] else None
        # face orientation: our loops run CCW about the surface normal, so
        # every face is FORWARD (flag_b); the official box alternates only
        # because its own loop winding alternates.
        f1 = T_FLAG_B
        # UV parameter domain: the official box deviates per-face (centred
        # half-extents of the face's bbox in surface param space).
        dx = (fmax[0] - fmin[0]) / 2.0
        dy = (fmax[1] - fmin[1]) / 2.0
        if dx <= 0.0:
            dx = dy
        if dy <= 0.0:
            dy = dx
        return (_Rec("face", 10)
                .add(_p(wl.ref(("attrib", "fname", bi, fi))), _ti(-1),
                     _ti(-1), _p(-1), _p(wl.ref(nxt)), _p(wl.ref(("loop", bi, fi))),
                     _p(wl.ref(("shell", bi))), _p(-1),
                     _p(wl.ref(("plane", bi, fi))),
                     bytes([f1, T_FLAG_B, T_FLAG_A]),
                     _v3(*fmin), _v3(*fmax), bytes([T_FLAG_A]),
                     _td(-dx), _td(dx), _td(-dy), _td(dy)))

    def _loop(self, key, wl):
        bi, fi = key[1], key[2]
        d = self.fi[("face", bi, fi)]
        lmin, lmax = _bbox(d["verts"], d["loop"])
        coeds = self.lc[key]
        return (_Rec("loop", 11)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                     _p(wl.ref(coeds[0])), _p(wl.ref(("face", bi, fi))),
                     bytes([T_FLAG_A]), _v3(*lmin), _v3(*lmax),
                     bytes([T_INT15]) + _ri(0)))

    def _coedge(self, key, wl):
        bi, fi, k = key[1], key[2], key[3]
        info = self.ce[key]
        coeds = self.lc[("loop", bi, fi)]
        n = len(coeds)
        nxt = coeds[(k + 1) % n]
        prv = coeds[(k - 1) % n]
        partners = self.coe.get(info["edge"], [])
        # partner = the OTHER coedge on the same edge, or self for a
        # single-coedge (seamed) edge
        if len(partners) == 2:
            partner = partners[1] if key == partners[0] else partners[0]
        else:
            partner = partners[0]
        return (_Rec("coedge", 16)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(wl.ref(nxt)),
                     _p(wl.ref(prv)), _p(wl.ref(partner)), _p(wl.ref(info["edge"])),
                     bytes([info["sense"]]), _p(wl.ref(("loop", bi, fi))),
                     _p(-1)))

    def _edge(self, key, wl):
        bi, ei = key[1], key[2]
        d = self.ei[key]
        v1, v2, verts = d["v1"], d["v2"], d["verts"]
        p1, p2 = verts[v1], verts[v2]
        length = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2
                  + (p2[2] - p1[2]) ** 2) ** 0.5
        emin, emax = _bbox(verts, [v1, v2])
        coeds = self.coe.get(key, [])
        first_co = coeds[0] if coeds else None
        return (_Rec("edge", 17)
                .add(_p(wl.ref(("attrib", "ename", bi, ei))),
                     _ti(-1), _ti(-1), _p(-1),
                     _p(wl.ref(("vertex", bi, v1))), _td(0.0),
                     _p(wl.ref(("vertex", bi, v2))), _td(length),
                     _p(wl.ref(first_co)), _p(wl.ref(("straight", bi, ei))),
                     bytes([T_FLAG_B]), _s("unknown"),
                     bytes([T_FLAG_A]), _v3(*emin), _v3(*emax)))

    def _vertex(self, key, wl):
        bi, vi = key[1], key[2]
        return (_Rec("vertex", 18)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                     _p(wl.ref(self.vp.get(key))), _p(wl.ref(("point", bi, vi)))))

    def _point(self, key, wl):
        bi, vi = key[1], key[2]
        x, y, z = self.item(bi)[1][vi]
        return (_Rec("point", 21)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(x, y, z)))

    def _plane(self, key, wl):
        bi, fi = key[1], key[2]
        it = self.item(bi)
        if it[0] == "cyl":
            info = it[1]
            # official cylinder caps: both planes store +axis as normal; the
            # bottom face carries sense=flag_a to flip it outward.
            center, nrm = (info["cap_b"] if fi == 0 else info["cap_a"],
                           info["axis"])
            return (_Rec("surface", 13, chain=[("plane", 12)])
                    .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*center),
                         _v3b(*nrm), _v3b(*info["major_unit"]),
                         bytes([T_FLAG_B] * 5)))
        d = self.fi[("face", bi, fi)]
        f = d["f"]
        return (_Rec("surface", 13, chain=[("plane", 12)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*f["center"]),
                     _v3b(*f["normal"]), _v3b(*_ortho(f["normal"])),
                     bytes([T_FLAG_B] * 5)))

    def _straight(self, key, wl):
        bi, ei = key[1], key[2]
        d = self.ei[("edge", bi, ei)]
        p1 = d["verts"][d["v1"]]
        p2 = d["verts"][d["v2"]]
        dx, dy, dz = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        length = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
        return (_Rec("curve", 20, chain=[("straight", 19)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*p1),
                     _v3b(dx / length, dy / length, dz / length),
                     bytes([T_FLAG_A]), _td(0.0), bytes([T_FLAG_A]),
                     _td(length)))

    # -- cylindrical entity layout (from the official cylinder stream) --
    def _cface(self, key, wl):
        bi, fi = key[1], key[2]
        info = self.cyl(bi)
        R, h, axis = info["R"], info["h"], info["axis"]
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        lo, hi = info["bbox"]
        # official cylinder face orientation: side & top forward (flag_b),
        # bottom is reversed (flag_a) because its plane normal faces +axis.
        f1 = (T_FLAG_B, T_FLAG_B, T_FLAG_A)[fi]
        surf = ("cone", bi)
        if fi == 1:
            surf = ("plane", bi, 0)
            fmin, fmax = _circ_bbox(cap_b, R, axis)
        elif fi == 2:
            surf = ("plane", bi, 1)
            fmin, fmax = _circ_bbox(cap_a, R, axis)
        else:
            fmin, fmax = lo, hi
        uv = (0.0, h / R, -math.pi, math.pi) if fi == 0 else (-R, R, -R, R)
        nxt = ("face", bi, fi + 1) if fi < 2 else None
        return (_Rec("face", 10)
                .add(_p(wl.ref(("attrib", "fname", bi, fi))), _ti(-1),
                     _ti(-1), _p(-1), _p(wl.ref(nxt)),
                     _p(wl.ref(("loop", bi, fi))), _p(wl.ref(("shell", bi))),
                     _p(-1), _p(wl.ref(surf)),
                     bytes([f1, T_FLAG_B, T_FLAG_A]),
                     _v3(*fmin), _v3(*fmax), bytes([T_FLAG_A]),
                     _td(uv[0]), _td(uv[1]), _td(uv[2]), _td(uv[3])))

    def _cloop(self, key, wl):
        bi, fi = key[1], key[2]
        info = self.cyl(bi)
        R, axis = info["R"], info["axis"]
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        lo, hi = info["bbox"]
        # official loop membership: side(4 coedges, head=c0), top(1, head=c3),
        # bottom(1, head=c5)
        head = (("coedge", bi, 0), ("coedge", bi, 3), ("coedge", bi, 5))[fi]
        if fi == 0:
            lmin, lmax = lo, hi
        elif fi == 1:
            lmin, lmax = _circ_bbox(cap_b, R, axis)
        else:
            lmin, lmax = _circ_bbox(cap_a, R, axis)
        return (_Rec("loop", 11)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                     _p(wl.ref(head)), _p(wl.ref(("face", bi, fi))),
                     bytes([T_FLAG_A]), _v3(*lmin), _v3(*lmax),
                     bytes([T_INT15]) + _ri(0)))

    def _ccoedge(self, key, wl):
        bi, ci = key[1], key[2]
        # official 6-coedge ring, index-aligned to the 51-record cyl stream:
        #   c0 side/top-circle  next=c1 prev=c4 partner=c3 edge=e0 sense=a loop=side
        #   c1 side/seam         next=c2 prev=c0 partner=c4 edge=e1 sense=a loop=side
        #   c2 side/bottom-circle next=c4 prev=c1 partner=c5 edge=e2 sense=b loop=side
        #   c3 top-cap (self)     next=c3 prev=c3 partner=c0 edge=e0 sense=b loop=top
        #   c4 side/seam          next=c0 prev=c2 partner=c1 edge=e1 sense=b loop=side
        #   c5 bottom-cap (self)  next=c5 prev=c5 partner=c2 edge=e2 sense=a loop=bottom
        nxt = (1, 2, 4, 3, 0, 5)[ci]
        prv = (4, 0, 1, 3, 2, 5)[ci]
        partner = (3, 4, 5, 0, 1, 2)[ci]
        edge_i = (0, 1, 2, 0, 1, 2)[ci]
        sense = (T_FLAG_A, T_FLAG_A, T_FLAG_B, T_FLAG_B, T_FLAG_B, T_FLAG_A)[ci]
        loop_i = (0, 0, 0, 1, 0, 2)[ci]
        return (_Rec("coedge", 16)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                     _p(wl.ref(("coedge", bi, nxt))),
                     _p(wl.ref(("coedge", bi, prv))),
                     _p(wl.ref(("coedge", bi, partner))),
                     _p(wl.ref(("edge", bi, edge_i))), bytes([sense]),
                     _p(wl.ref(("loop", bi, loop_i))), _p(-1)))

    def _cedge(self, key, wl):
        bi, ei = key[1], key[2]
        info = self.cyl(bi)
        R, mu, axis = info["R"], info["major_unit"], info["axis"]
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        # e0 = top circle, e1 = seam, e2 = bottom circle (official int 4/5/6)
        if ei == 0:
            bmin, bmax = _circ_bbox(cap_b, R, axis)
            return (_Rec("edge", 17)
                    .add(_p(wl.ref(("attrib", "ename", bi, ei))), _ti(4),
                         _ti(-1), _p(-1), _p(wl.ref(("vertex", bi, 0))), _td(0.0),
                         _p(wl.ref(("vertex", bi, 0))), _td(2.0 * math.pi),
                         _p(wl.ref(("coedge", bi, 0))),
                         _p(wl.ref(("ellipse", bi, 0))),
                         bytes([T_FLAG_B]), _s("unknown"),
                         bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))
        if ei == 1:
            v0 = (cap_a[0] + mu[0] * R, cap_a[1] + mu[1] * R,
                  cap_a[2] + mu[2] * R)
            v1 = (cap_b[0] + mu[0] * R, cap_b[1] + mu[1] * R,
                  cap_b[2] + mu[2] * R)
            bmin = (min(v0[0], v1[0]), min(v0[1], v1[1]), min(v0[2], v1[2]))
            bmax = (max(v0[0], v1[0]), max(v0[1], v1[1]), max(v0[2], v1[2]))
            return (_Rec("edge", 17)
                    .add(_p(wl.ref(("attrib", "ename", bi, ei))), _ti(5),
                         _ti(-1), _p(-1), _p(wl.ref(("vertex", bi, 1))), _td(0.0),
                         _p(wl.ref(("vertex", bi, 0))), _td(info["h"]),
                         _p(wl.ref(("coedge", bi, 1))),
                         _p(wl.ref(("straight", bi, 0))),
                         bytes([T_FLAG_B]), _s("unknown"),
                         bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))
        bmin, bmax = _circ_bbox(cap_a, R, axis)
        return (_Rec("edge", 17)
                .add(_p(wl.ref(("attrib", "ename", bi, ei))), _ti(6),
                     _ti(-1), _p(-1), _p(wl.ref(("vertex", bi, 1))), _td(0.0),
                     _p(wl.ref(("vertex", bi, 1))), _td(2.0 * math.pi),
                     _p(wl.ref(("coedge", bi, 2))),
                     _p(wl.ref(("ellipse", bi, 1))),
                     bytes([T_FLAG_B]), _s("unknown"),
                     bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))

    def _cvertex(self, key, wl):
        bi, vi = key[1], key[2]
        # official binding: top vertex -> top circle edge(e0);
        # bottom vertex -> seam edge(e1)
        edge_key = ("edge", bi, 0) if vi == 0 else ("edge", bi, 1)
        return (_Rec("vertex", 18)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(wl.ref(edge_key)),
                     _p(wl.ref(("point", bi, vi)))))

    def _cpoint(self, key, wl):
        bi, vi = key[1], key[2]
        info = self.cyl(bi)
        R, mu = info["R"], info["major_unit"]
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        base = cap_a if vi == 0 else cap_b
        p = (base[0] + mu[0] * R, base[1] + mu[1] * R, base[2] + mu[2] * R)
        return (_Rec("point", 21)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*p)))

    def _cone(self, key, wl):
        bi = key[1]
        info = self.cyl(bi)
        R, axis, mu, org = (info["R"], info["axis"], info["major_unit"],
                            info["origin"])
        return (_Rec("surface", 13, chain=[("cone", 22)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*org),
                     _v3b(-axis[0], -axis[1], -axis[2]),
                     _v3b(mu[0] * R, mu[1] * R, mu[2] * R),
                     _td(1.0), bytes([T_FLAG_B, T_FLAG_B]),
                     _td(-0.0), _td(1.0), _td(R),
                     bytes([T_FLAG_A, T_FLAG_B, T_FLAG_B, T_FLAG_B,
                            T_FLAG_B])))

    def _ellipse(self, key, wl):
        bi, k = key[1], key[2]
        info = self.cyl(bi)
        R, mu, axis = info["R"], info["major_unit"], info["axis"]
        center = info["cap_b"] if k == 0 else info["cap_a"]
        return (_Rec("curve", 20, chain=[("ellipse", 23)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*center),
                     _v3b(*axis), _v3b(mu[0] * R, mu[1] * R, mu[2] * R),
                     _td(1.0), bytes([T_FLAG_B, T_FLAG_B])))

    def _cstraight(self, key, wl):
        bi = key[1]
        info = self.cyl(bi)
        R, mu, h = info["R"], info["major_unit"], info["h"]
        cap_a = info["cap_a"]
        p1 = (cap_a[0] + mu[0] * R, cap_a[1] + mu[1] * R,
              cap_a[2] + mu[2] * R)
        return (_Rec("curve", 20, chain=[("straight", 19)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*p1),
                     _v3b(0.0, 0.0, 0.001), bytes([T_FLAG_A]),
                     _td(0.0), bytes([T_FLAG_A]), _td(h)))

    # -- attributes ---------------------------------------------------
    def _attrib(self, key, wl):
        sub = key[1]
        if sub == "bname":
            owner = wl.ref(("body", key[2]))
            rec = _attrib(owner, "0:%d" % (23 + 60 * key[2]),
                          wl.ref(("attrib", "bpn", key[2])), None)
            return rec
        if sub == "bpn":
            owner = wl.ref(("body", key[2]))
            return _attrib(owner, "SC:0", None,
                           wl.ref(("attrib", "bname", key[2])),
                           name_tag="ATTRIB_XACIS_PNAME%8")
        if sub == "fname":
            bi, fi = key[2], key[3]
            owner = wl.ref(("face", bi, fi))
            return _attrib(owner, "0:%d" % (27 + 3 * fi + 60 * bi),
                           wl.ref(("attrib", "frgb", bi, fi)), None,
                           name_tag="%6")
        if sub == "frgb":
            bi, fi = key[2], key[3]
            owner = wl.ref(("face", bi, fi))
            col = self.col[bi]
            return (_Rec("attrib", 5, chain=[("rgb_color", 14), ("st", 15)])
                    .add(_p(-1), _ti(-1), _p(-1),
                         _p(wl.ref(("attrib", "fname", bi, fi))),
                         _p(wl.ref(("face", bi, fi))), _ti(14675654),
                         _td(col[0]), _td(col[1]), _td(col[2])))
        if sub == "ename":
            bi, ei = key[2], key[3]
            owner = wl.ref(("edge", bi, ei))
            return _attrib(owner, "0:%d" % (45 + 3 * ei + 60 * bi),
                           name_tag="%6")
        raise ValueError("attrib key " + repr(key))


def _attrib(owner_idx, value, nxt_idx=None, prv_idx=None, type_id=14675622,
            name_tag="ATTRIB_XACIS_NAME%6"):
    """Official attrib token layout: [t0=-1, t1=-1, t2=NEXT, t3=PREV,
    t4=OWNER, t5=type_id, t6=name_tag, t7=value]."""
    return (_Rec("attrib", 5, chain=[("string_attrib", 2),
                                     ("name_attrib", 3), ("gen", 4)])
            .add(_p(-1), _ti(-1), _p(-1 if nxt_idx is None else nxt_idx),
                 _p(-1 if prv_idx is None else prv_idx), _p(owner_idx),
                 _ti(type_id), _s(name_tag), _s(value)))


# ----------------------------------------------------------------------
# Phase 1: data-driven layout emitter
# ----------------------------------------------------------------------
class F:
    """A single field of a record layout.

    kind is the token kind (ptr/int/double/vec3/vec3b/flag_a/flag_b/int15/
    string).  make_value(ctx) -> value:
      * ptr: returns the referenced entity key, or None for a null pointer
      * int/double: the scalar
      * vec3/vec3b: a 3-tuple
      * string: the string
      * flag_*: ignored (the kind carries the byte)
    """

    __slots__ = ("kind", "make_value")

    def __init__(self, kind, make_value=None):
        self.kind = kind
        if kind == "ptr":
            # make_value (callable or None) yields the referenced key / None
            self.make_value = make_value
        elif callable(make_value):
            self.make_value = make_value
        else:
            self.make_value = (lambda ctx, _v=make_value: _v)
        # constant flag kinds carry no value
        if kind in ("flag_a", "flag_b"):
            self.make_value = None

    def emit(self, ctx):
        if self.kind in ("flag_a", "flag_b"):
            return bytes([T_FLAG_A if self.kind == "flag_a" else T_FLAG_B])
        v = self.make_value(ctx) if self.make_value is not None else None
        if self.kind == "ptr":
            return _p(ctx.wl.ref(v) if v is not None else -1)
        if self.kind == "int":
            return _ti(v)
        if self.kind == "int15":
            return bytes([T_INT15]) + _ri(v)
        if self.kind == "double":
            return _td(v)
        if self.kind == "vec3":
            return _v3(*v)
        if self.kind == "vec3b":
            return _v3b(*v)
        if self.kind == "string":
            return _s(v)
        if self.kind == "flag":
            return bytes([v])  # v is T_FLAG_A / T_FLAG_B
        raise ValueError("unknown field kind " + self.kind)


# shorthand constructors (pass the value through; F handles callable vs const)
def _P(make_value=None):
    return F("ptr", make_value)


def _I(v):
    return F("int", v)


def _D(v):
    return F("double", v)


def _V3(v):
    return F("vec3", v)


def _V3B(v):
    return F("vec3b", v)


def _S(v):
    return F("string", v)


def _FA():
    return F("flag_a")


def _FB():
    return F("flag_b")


class Layout:
    """A record layout: name + ordered fields (+ chain / class interning)."""

    def __init__(self, name, fields, class_id=None, chain=()):
        self.name = name
        self.fields = fields
        self.class_id = class_id
        self.chain = chain

    def render(self, key, wl, m):
        rec = _Rec(self.name, self.class_id, self.chain)
        ctx = _Ctx(key, wl, m)
        for f in self.fields:
            rec.add(f.emit(ctx))
        return rec


class _Ctx:
    """Per-record context passed to layout field make_value functions."""

    __slots__ = ("key", "wl", "m")

    def __init__(self, key, wl, m):
        self.key = key
        self.wl = wl
        self.m = m


class LayoutEmitter:
    """Drive the FIFO worklist with a data-driven layout table.

    `m` is a Makers instance (data/geometry accessor); `layouts` maps
    entity kind -> Layout.  Falls back to the hand-written Makers.make for
    kinds without a layout entry (used while migrating).
    """

    def __init__(self, m, layouts):
        self.m = m
        self.l = layouts

    def make(self, key, wl):
        l = self.l.get(key[0])
        if l is None:
            return self.m.make(key, wl)
        return l.render(key, wl, self.m)


# ----------------------------------------------------------------------
# planar record layouts (migrated from the hand-written Makers.make)
# ----------------------------------------------------------------------
def _flg(sense_val):
    """A dynamic flag field: make_value returns T_FLAG_A / T_FLAG_B."""
    return F("flag", lambda ctx: sense_val(ctx) if callable(sense_val)
             else sense_val)


def _planar_layouts():
    L = Layout
    layouts = {}

    def body_bbox(k, wl, m):
        it = m.item(k[1])
        smin, smax = (it[1]["bbox"] if it[0] == "cyl" else _bbox(it[1]))
        return smin, smax

    def face_bbox(ctx):
        # ctx.key may be ('face',bi,fi) or ('loop',bi,fi); both read the same
        # face geometry.
        k = ctx.key if ctx.key[0] == "face" else ("face", ctx.key[1], ctx.key[2])
        d = ctx.m.fi[k]
        return _bbox(d["verts"], d["loop"])

    def face_next(ctx):
        ff = ctx.m.fi[ctx.key]
        return (("face", ctx.key[1], ctx.key[2] + 1)
                if ctx.key[2] + 1 < ff["n_faces"] else None)

    def coedge_next_prev(ctx):
        coeds = ctx.m.lc[("loop", ctx.key[1], ctx.key[2])]
        n = len(coeds)
        k = ctx.key[3]
        return coeds[(k + 1) % n], coeds[(k - 1) % n]

    def coedge_partner(ctx):
        info = ctx.m.ce[ctx.key]
        partners = ctx.m.coe.get(info["edge"], [])
        if len(partners) == 2:
            return partners[1] if ctx.key == partners[0] else partners[0]
        return partners[0]

    def _edge_key(ctx):
        # maps ('edge'|'straight', bi, ei) -> the edge data key
        return ("edge", ctx.key[1], ctx.key[2])

    def edge_len(ctx):
        d = ctx.m.ei[_edge_key(ctx)]
        p1, p2 = d["verts"][d["v1"]], d["verts"][d["v2"]]
        return ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2
                + (p2[2] - p1[2]) ** 2) ** 0.5

    def edge_bbox(ctx):
        d = ctx.m.ei[_edge_key(ctx)]
        return _bbox(d["verts"], [d["v1"], d["v2"]])

    def vertex_inc(ctx):
        return ctx.m.vp.get(ctx.key)

    layouts["body"] = L("body", [
        _P(lambda ctx: ("attrib", "bname", ctx.key[1])),
        _I(-1), _I(-1), _P(), _I(0),
        _P(lambda ctx: ("lump", ctx.key[1])),
        _P(), _P(), _FA(),
        _V3(lambda ctx: body_bbox(ctx.key, ctx.wl, ctx.m)[0]),
        _V3(lambda ctx: body_bbox(ctx.key, ctx.wl, ctx.m)[1]),
    ], class_id=1)

    layouts["lump"] = L("lump", [
        _P(), _I(-1), _I(-1), _P(), _P(),
        _P(lambda ctx: ("shell", ctx.key[1])),
        _P(lambda ctx: ("body", ctx.key[1])),
        _FA(),
        _V3(lambda ctx: body_bbox(ctx.key, ctx.wl, ctx.m)[0]),
        _V3(lambda ctx: body_bbox(ctx.key, ctx.wl, ctx.m)[1]),
    ], class_id=7)

    layouts["shell"] = L("shell", [
        _P(), _I(-1), _I(-1), _P(), _P(), _P(),
        _P(lambda ctx: ("face", ctx.key[1], 0)),
        _P(),
        _P(lambda ctx: ("lump", ctx.key[1])),
        _FA(),
        _V3(lambda ctx: body_bbox(ctx.key, ctx.wl, ctx.m)[0]),
        _V3(lambda ctx: body_bbox(ctx.key, ctx.wl, ctx.m)[1]),
    ], class_id=9)

    def face_uvs(ctx):
        fmin, fmax = face_bbox(ctx)
        dx = (fmax[0] - fmin[0]) / 2.0
        dy = (fmax[1] - fmin[1]) / 2.0
        if dx <= 0.0:
            dx = dy
        if dy <= 0.0:
            dy = dx
        return (-dx, dx, -dy, dy)

    layouts["face"] = L("face", [
        _P(lambda ctx: ("attrib", "fname", ctx.key[1], ctx.key[2])),
        _I(-1), _I(-1), _P(), _P(face_next),
        _P(lambda ctx: ("loop", ctx.key[1], ctx.key[2])),
        _P(lambda ctx: ("shell", ctx.key[1])),
        _P(),
        _P(lambda ctx: ("plane", ctx.key[1], ctx.key[2])),
        _FB(), _FB(), _FA(),
        _V3(lambda ctx: face_bbox(ctx)[0]),
        _V3(lambda ctx: face_bbox(ctx)[1]),
        _FA(),
        _D(lambda ctx: face_uvs(ctx)[0]), _D(lambda ctx: face_uvs(ctx)[1]),
        _D(lambda ctx: face_uvs(ctx)[2]), _D(lambda ctx: face_uvs(ctx)[3]),
    ], class_id=10)

    layouts["loop"] = L("loop", [
        _P(), _I(-1), _I(-1), _P(), _P(),
        _P(lambda ctx: ctx.m.lc[ctx.key][0]),
        _P(lambda ctx: ("face", ctx.key[1], ctx.key[2])),
        _FA(),
        _V3(lambda ctx: face_bbox(ctx)[0]),
        _V3(lambda ctx: face_bbox(ctx)[1]),
        F("int15", lambda ctx: 0),
    ], class_id=11)

    layouts["coedge"] = L("coedge", [
        _P(), _I(-1), _I(-1), _P(),
        _P(lambda ctx: coedge_next_prev(ctx)[0]),
        _P(lambda ctx: coedge_next_prev(ctx)[1]),
        _P(coedge_partner),
        _P(lambda ctx: ctx.m.ce[ctx.key]["edge"]),
        _flg(lambda ctx: ctx.m.ce[ctx.key]["sense"]),
        _P(lambda ctx: ("loop", ctx.key[1], ctx.key[2])),
        _P(),
    ], class_id=16)

    layouts["edge"] = L("edge", [
        _P(lambda ctx: ("attrib", "ename", ctx.key[1], ctx.key[2])),
        _I(-1), _I(-1), _P(),
        _P(lambda ctx: ("vertex", ctx.key[1], ctx.m.ei[ctx.key]["v1"])),
        _D(lambda ctx: 0.0),
        _P(lambda ctx: ("vertex", ctx.key[1], ctx.m.ei[ctx.key]["v2"])),
        _D(edge_len),
        _P(lambda ctx: (ctx.m.coe.get(ctx.key) or [None])[0]),
        _P(lambda ctx: ("straight", ctx.key[1], ctx.key[2])),
        _FB(), _S("unknown"), _FA(),
        _V3(lambda ctx: edge_bbox(ctx)[0]),
        _V3(lambda ctx: edge_bbox(ctx)[1]),
    ], class_id=17)

    layouts["vertex"] = L("vertex", [
        _P(), _I(-1), _I(-1), _P(), _P(vertex_inc),
        _P(lambda ctx: ("point", ctx.key[1], ctx.key[2])),
    ], class_id=18)

    layouts["point"] = L("point", [
        _P(), _I(-1), _I(-1), _P(),
        _V3(lambda ctx: ctx.m.item(ctx.key[1])[1][ctx.key[2]]),
    ], class_id=21)

    layouts["plane"] = L("surface", [
        _P(), _I(-1), _I(-1), _P(),
        _V3(lambda ctx: ctx.m.fi[("face", ctx.key[1], ctx.key[2])]["f"]["center"]),
        _V3B(lambda ctx: ctx.m.fi[("face", ctx.key[1], ctx.key[2])]["f"]["normal"]),
        _V3B(lambda ctx: _ortho(ctx.m.fi[("face", ctx.key[1], ctx.key[2])]["f"]["normal"])),
        _FB(), _FB(), _FB(), _FB(), _FB(),
    ], class_id=13, chain=(("plane", 12),))

    layouts["straight"] = L("curve", [
        _P(), _I(-1), _I(-1), _P(),
        _V3(lambda ctx: ctx.m.ei[("edge", ctx.key[1], ctx.key[2])]["verts"][
            ctx.m.ei[("edge", ctx.key[1], ctx.key[2])]["v1"]]),
        _V3B(lambda ctx: _straight_dir(ctx)),
        _FA(), _D(lambda ctx: 0.0), _FA(), _D(edge_len),
    ], class_id=20, chain=(("straight", 19),))

    return layouts


def _straight_dir(ctx):
    d = ctx.m.ei[("edge", ctx.key[1], ctx.key[2])]
    p1, p2 = d["verts"][d["v1"]], d["verts"][d["v2"]]
    dx, dy, dz = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
    length = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
    return (dx / length, dy / length, dz / length)


# ----------------------------------------------------------------------
# public entry
# ----------------------------------------------------------------------
def build_sab(items, colors=None):
    """bytes(record stream body with header + end marker).  Mirrors the old
    _build_sab contract; caller supplies the header preamble."""
    wl = Worklist()
    makers = Makers(items, colors)
    # planar topology goes through the data-driven layout table; unknown kinds
    # (attrib, the cylindrical _c* builders) fall back to Makers.make.
    # Verified byte-identical to the hand-written Makers.make path for box.
    emitter = LayoutEmitter(makers, _planar_layouts())
    return wl.run([("body", bi) for bi in range(len(items))], emitter)

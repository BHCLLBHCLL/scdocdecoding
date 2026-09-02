# -*- coding: utf-8 -*-
"""Replace _build_sab in scdm/scdoc_write.py with the worklist (FIFO) emitter."""
import io
import re

PATH = "scdm/scdoc_write.py"
src = io.open(PATH, encoding="utf-8").read()

start = src.index("def _build_sab(items, colors=None):")
end = src.index("def _document_xml(")

new_fn = '''def _build_sab(items, colors=None):
    """Assemble the SAB stream with the reverse-engineered ACIS save algorithm.

    Official algorithm (from SpaACIS.dll api_save_entity_list + save_data):
      * a FIFO worklist (ENTITY_LIST) holds pending entities; the caller seeds
        it with the body(ies).
      * each entity's save_data writes its record immediately, and for every
        ENTITY pointer field calls save_entity_pointer(list, ent) which
        assigns the record index at FIRST reference (appending the entity to
        the worklist tail, FIFO) and writes that index into the stream.
      * iteration stops when the list is exhausted.

    Proven exactly against the official box.scdoc stream (141 records: a FIFO
    simulation seeded at the body reproduces the file order 0..140; LIFO does
    not).  This emitter therefore needs no per-model interleaving template:
    the interleave falls out of the pointer field order of each record.

    items = [('planar', verts, edges, faces) | ('cyl', info)] per body;
    colors = parallel list of per-body (r, g, b) in 0..1.

    Returns (bytes, face_counts, edge_counts).
    """
    B = len(items)
    planar = [(bi, it) for bi, it in enumerate(items) if it[0] == "planar"]
    cyls = [(bi, it) for bi, it in enumerate(items) if it[0] == "cyl"]
    col_of = {}
    for bi in range(B):
        col_of[bi] = colors[bi] if colors and bi < len(colors) else (0.745, 0.902, 0.961)

    # ------------------------------------------------------------------
    # geometry / topology model (keyed entities; keys are (kind, bi, ...))
    # ------------------------------------------------------------------
    face_info = {}      # ('face', bi, fi) -> dict(loop, verts, edges, n_faces, f, bi, fi)
    loop_coedges = {}   # ('loop', bi, fi) -> [coedge keys]
    coedge_of_edge = {}  # ('edge', bi, ei) -> [coedge keys]
    coedge_info = {}    # ('coedge', bi, fi, k) -> dict(loop_key, sense, vertex_a, vertex_b)
    edge_info = {}      # ('edge', bi, ei) -> dict(v1, v2, verts, bi, ei, F)
    vert_pending = {}   # ('vertex', bi, vi) -> ('edge', bi, ei) incident edge key

    for bi, it in planar:
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
                coedge_info[ck] = {"loop": ("loop", bi, fi), "sense": sense,
                                   "edge": ("edge", bi, eidx), "a": a, "b": b}
                coedge_of_edge.setdefault(("edge", bi, eidx), []).append(ck)
            loop_coedges[("loop", bi, fi)] = [
                ("coedge", bi, fi, k) for k in range(n)]
            face_info[("face", bi, fi)] = {
                "loop": loop, "verts": verts, "edges": edges, "f": f,
                "bi": bi, "fi": fi, "n_faces": F}
        for ei, (v1, v2) in enumerate(edges):
            edge_info[("edge", bi, ei)] = {"v1": v1, "v2": v2,
                                           "verts": verts, "bi": bi, "ei": ei,
                                           "F": F}
            vert_pending.setdefault(("vertex", bi, v1), ("edge", bi, ei))
            vert_pending.setdefault(("vertex", bi, v2), ("edge", bi, ei))

    # ------------------------------------------------------------------
    # the worklist emitter (API mirror of api_save_entity_list)
    # ------------------------------------------------------------------
    class _Worklist:
        def __init__(self):
            self._idx = {}          # key -> record index (0-based)
            self._q = []            # pending entities, FIFO
            self._qpos = 0
            self.recs = []          # serialized records

        def ref(self, key):
            """save_entity_pointer: assign index at first reference, else return it."""
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
            for s in seeds:
                self.ref(s)
            while self._qpos < len(self._q):
                key = self._q[self._qpos]
                self._qpos += 1
                rec = makers.make(key, self)
                self.recs.append(rec.bytes(seen))

    makers = _SabMakers(planar, cyls, col_of, face_info, loop_coedges,
                        coedge_of_edge, coedge_info, edge_info, vert_pending)
    wl = _Worklist()
    wl.run([("body", bi) for bi in range(B)], makers)

    out = bytearray()
    out += MAGIC
    blob = b"\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00"
    out += _ri(len(blob)) + blob
    out += _s("SpaceClaim")
    out += _s("ACIS 29.0 NT")
    out += _s("Mon Aug 24 00:13:12 2026")
    out += _td(1000.0) + _td(1e-8) + _td(1e-10)
    out += bytes([T_FLAG_A])
    out += _s("FQ8FFTTT5P7PJFMUMMYS2_J8B48CXKNEWAP4QAQV2CS3PP65QBQCNVPEFCMUSP6XAAPKK47XTA84Q")
    for rec in wl.recs:
        out += rec
    out += bytes([T_RECORD, len(END_NAME)]) + END_NAME.encode("latin-1")
    face_counts = [len(it[3]) if it[0] == "planar" else 3 for it in items]
    edge_counts = [len(it[2]) if it[0] == "planar" else 2 for it in items]
    return bytes(out), face_counts, edge_counts


class _SabMakers:
    """Record builders keyed by entity; each uses wl.ref() to wire pointers."""

    def __init__(self, planar, cyls, col_of, face_info, loop_coedges,
                 coedge_of_edge, coedge_info, edge_info, vert_pending):
        self.planar = planar
        self.cyls = cyls
        self.col = col_of
        self.fi = face_info
        self.lc = loop_coedges
        self.ce = coedge_info
        self.coe = coedge_of_edge
        self.ei = edge_info
        self.vp = vert_pending

    def make(self, key, wl):
        k = key[0]
        if k == "body":
            return self._body(key, wl)
        if k == "lump":
            return self._lump(key, wl)
        if k == "shell":
            return self._shell(key, wl)
        if k == "face":
            return self._face(key, wl)
        if k == "loop":
            return self._loop(key, wl)
        if k == "coedge":
            return self._coedge(key, wl)
        if k == "edge":
            return self._edge(key, wl)
        if k == "vertex":
            return self._vertex(key, wl)
        if k == "point":
            return self._point(key, wl)
        if k == "plane":
            return self._plane(key, wl)
        if k == "cone":
            return self._cone(key, wl)
        if k == "straight":
            return self._straight(key, wl)
        if k == "ellipse":
            return self._ellipse(key, wl)
        if k == "attrib":
            return self._attrib(key, wl)
        if k == "rgb":
            return self._rgb(key, wl)
        raise ValueError("unknown entity " + k)

    # ---- planar ----------------------------------------------------
    def _body(self, key, wl):
        bi = key[1]
        it = self._item(bi)
        smin, smax = _bbox(it[1]) if it[0] == "planar" else it[1]["bbox"]
        return (_Rec("body", 1)
                .add(wl.ref(("attrib", "bname", bi)), _ti(0), _ti(-1), _p(-1),
                     _ti(0), wl.ref(("lump", bi)), _p(-1), _p(-1),
                     bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))

    def _lump(self, key, wl):
        bi = key[1]
        it = self._item(bi)
        smin, smax = _bbox(it[1]) if it[0] == "planar" else it[1]["bbox"]
        return (_Rec("lump", 7)
                .add(wl.ref(("attrib", "bpn", bi)), _ti(-1), _ti(-1), _p(-1),
                     _p(-1), wl.ref(("shell", bi)), wl.ref(("body", bi)),
                     bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))

    def _shell(self, key, wl):
        bi = key[1]
        it = self._item(bi)
        smin, smax = _bbox(it[1]) if it[0] == "planar" else it[1]["bbox"]
        first = ("face", bi, 0)
        return (_Rec("shell", 9)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1), _p(-1),
                     wl.ref(first), _p(-1), wl.ref(("lump", bi)),
                     bytes([T_FLAG_A]), _v3(*smin), _v3(*smax)))

    def _face(self, key, wl):
        bi, fi = key[1], key[2]
        if self._item(bi)[0] == "cyl":
            return self._cyl_face(key, wl)
        d = self.fi[key]
        verts, f, n_faces = d["verts"], d["f"], d["n_faces"]
        fmin, fmax = _bbox(verts, d["loop"])
        next_key = ("face", bi, fi + 1) if fi + 1 < n_faces else None
        f1 = T_FLAG_A if fi % 2 == 0 else T_FLAG_B   # official parity flag
        return (_Rec("face", 10)
                .add(wl.ref(("attrib", "fname", bi, fi)), _ti(fi + 1),
                     _ti(-1), _p(-1),
                     wl.ref(next_key), wl.ref(("loop", bi, fi)),
                     wl.ref(("shell", bi)), _p(-1),
                     wl.ref(("plane", bi, fi)),
                     bytes([f1, T_FLAG_B, T_FLAG_A]), _v3(*fmin), _v3(*fmax),
                     bytes([T_FLAG_A]), _td(0.0), _td(0.01), _td(0.0),
                     _td(0.01)))

    def _loop(self, key, wl):
        bi, fi = key[1], key[2]
        if self._item(bi)[0] == "cyl":
            return self._cyl_loop(key, wl)
        d = self.fi[key]
        lmin, lmax = _bbox(d["verts"], d["loop"])
        coeds = self.lc[key]
        return (_Rec("loop", 11)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                     wl.ref(coeds[0]), wl.ref(("face", bi, fi)),
                     bytes([T_FLAG_A]), _v3(*lmin), _v3(*lmax),
                     bytes([T_INT15]) + _ri(0)))

    def _coedge(self, key, wl):
        bi, fi, k = key[1], key[2], key[3]
        if self._item(bi)[0] == "cyl":
            return self._cyl_coedge(key, wl)
        info = self.ce[key]
        coeds = self.lc[("loop", bi, fi)]
        n = len(coeds)
        nxt = coeds[(k + 1) % n]
        prv = coeds[(k - 1) % n]
        partners = self.coe.get(info["edge"], [])
        partner = partners[1] if len(partners) == 2 else partners[0]
        return (_Rec("coedge", 16)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                     wl.ref(nxt), wl.ref(prv), wl.ref(partner),
                     wl.ref(info["edge"]), bytes([info["sense"]]),
                     wl.ref(("loop", bi, fi)), _p(-1)))

    def _edge(self, key, wl):
        bi, ei = key[1], key[2]
        if self._item(bi)[0] == "cyl":
            return self._cyl_edge(key, wl)
        d = self.ei[key]
        v1, v2, verts = d["v1"], d["v2"], d["verts"]
        p1, p2 = verts[v1], verts[v2]
        length = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2
                  + (p2[2] - p1[2]) ** 2) ** 0.5
        emin, emax = _bbox(verts, [v1, v2])
        coeds = self.coe.get(key, [])
        first_co = coeds[0] if coeds else None
        return (_Rec("edge", 17)
                .add(wl.ref(("attrib", "ename", bi, ei)),
                     _ti(d["F"] + ei + 1), _ti(-1), _p(-1),
                     wl.ref(("vertex", bi, v1)), _td(0.0),
                     wl.ref(("vertex", bi, v2)), _td(length),
                     wl.ref(first_co), wl.ref(("straight", bi, ei)),
                     bytes([T_FLAG_B]), _s("unknown"),
                     bytes([T_FLAG_A]), _v3(*emin), _v3(*emax)))

    def _vertex(self, key, wl):
        bi, vi = key[1], key[2]
        dit = self._item(bi)
        if dit[0] == "cyl":
            return self._cyl_vertex(key, wl)
        inc = self.vp.get(key)
        return (_Rec("vertex", 18)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                     wl.ref(inc), wl.ref(("point", bi, vi))))

    def _point(self, key, wl):
        bi, vi = key[1], key[2]
        x, y, z = self._item(bi)[1][vi]
        return (_Rec("point", 21)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(x, y, z)))

    def _plane(self, key, wl):
        bi, fi = key[1], key[2]
        f = self.fi[key]["f"]
        return (_Rec("surface", 13, chain=[("plane", 12)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*f["center"]),
                     _v3b(*f["normal"]), _v3b(*_ortho(f["normal"])),
                     bytes([T_FLAG_B] * 5)))

    def _straight(self, key, wl):
        bi, ei = key[1], key[2]
        d = self.ei[key]
        p1 = d["verts"][d["v1"]]
        p2 = d["verts"][d["v2"]]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        length = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
        return (_Rec("curve", 20, chain=[("straight", 19)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*p1),
                     _v3b(dx / length, dy / length, dz / length),
                     bytes([T_FLAG_A]), _td(0.0), bytes([T_FLAG_A]),
                     _td(length)))

    def _attrib(self, key, wl):
        kind = key[1]
        if kind == "bname":
            idx = wl.ref(("body", key[2]))
            value = "0:%d" % (23 + 60 * key[2],)
            nxt = ("attrib", "bpn", key[2])
            prv = None
        elif kind == "bpn":
            idx = wl.ref(("body", key[2]))
            value = "SC:0"
            nxt, prv = None, ("attrib", "bname", key[2])
        elif kind == "fname":
            bi, fi = key[2], key[3]
            idx = wl.ref(("face", bi, fi))
            value = "0:%d" % (27 + 3 * fi + 60 * bi)
            nxt = ("attrib", "frgb", bi, fi)
            prv = None
        elif kind == "frgb":
            bi, fi = key[2], key[3]
            idx = wl.ref(("face", bi, fi))
            nxt = None
            prv = ("attrib", "fname", bi, fi)
            col = self.col[bi]
            return (_Rec("attrib", 5, chain=[("rgb_color", 14), ("st", 15)])
                    .add(_p(-1), _ti(-1), _p(-1), wl.ref(prv), wl.ref(idx),
                         _ti(14675654), _td(col[0]), _td(col[1]),
                         _td(col[2])))
        elif kind == "ename":
            bi, ei = key[2], key[3]
            idx = wl.ref(("edge", bi, ei))
            value = "0:%d" % (45 + 3 * ei + 60 * bi)
            nxt = prv = None
        else:
            raise ValueError("attrib key " + repr(key))
        return _attrib_chain(idx, value, wl, nxt, prv)

    def _rgb(self, key, wl):
        # handled by _attrib('frgb') directly
        raise ValueError("unexpected rgb key")

    # ---- cylindrical (sample layout from the official cylinder) ----
    def _item(self, bi):
        for bj, it in self.planar:
            if bj == bi:
                return it
        for bj, it in self.cyls:
            if bj == bi:
                return it
        raise ValueError("body " + str(bi))

    def _cyl_info(self, bi):
        return self.cyls[[b for b, _ in self.cyls].index(bi)][1]

    def _cyl_face(self, key, wl):
        bi, fi = key[1], key[2]
        info = self._cyl_info(bi)
        R, h, org, axis, mu = (info["R"], info["h"], info["origin"],
                               info["axis"], info["major_unit"])
        cap_a, cap_b, lo, hi = info["cap_a"], info["cap_b"], info["bbox"]
        u = (0.0, h / R, -math.pi, math.pi)
        f1, f2, f3 = (T_FLAG_B, T_FLAG_B, T_FLAG_A)
        if fi == 1:
            f1 = T_FLAG_A
        uv = (-R, R, -R, R)
        fmin, fmax = lo, hi
        surf = ("cone", bi)
        if fi == 1:
            fmin, fmax = circ_bbox_of(cap_b, R, axis)
            surf = ("plane", bi, 0)
        elif fi == 2:
            fmin, fmax = circ_bbox_of(cap_a, R, axis)
            surf = ("plane", bi, 1)
        next_key = ("face", bi, fi + 1) if fi < 2 else None
        return (_Rec("face", 10)
                .add(wl.ref(("attrib", "fname", bi, fi)), _ti(fi + 1),
                     _ti(-1), _p(-1), wl.ref(next_key),
                     wl.ref(("loop", bi, fi)), wl.ref(("shell", bi)), _p(-1),
                     wl.ref(surf),
                     bytes([f1, f2, f3]), _v3(*fmin), _v3(*fmax),
                     bytes([T_FLAG_A]), _td(uv[0]), _td(uv[1]),
                     _td(uv[2]), _td(uv[3])))

    def _cyl_loop(self, key, wl):
        bi, fi = key[1], key[2]
        info = self._cyl_info(bi)
        R, axis = info["R"], info["axis"]
        cap_a, cap_b, lo, hi = info["cap_a"], info["cap_b"], info["bbox"]
        co_i = 0 if fi == 0 else (1 if fi == 1 else 2)
        coeds = [("coedge", bi, c) for c in
                 (0, 1, 2, 3) if fi == 0] if fi == 0 else [("coedge", bi, co_i + 3)]
        hmm = coeds
        if fi == 0:
            hmm = [("coedge", bi, 0), ("coedge", bi, 1),
                   ("coedge", bi, 2), ("coedge", bi, 3)]
        else:
            hmm = [("coedge", bi, 4 if fi == 1 else 5)]
        lmin, lmax = (lo, hi) if fi == 0 else (
            circ_bbox_of(cap_b, R, axis) if fi == 1 else circ_bbox_of(cap_a, R, axis))
        return (_Rec("loop", 11)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _p(-1),
                     wl.ref(hmm[0]), wl.ref(("face", bi, fi)),
                     bytes([T_FLAG_A]), _v3(*lmin), _v3(*lmax),
                     bytes([T_INT15]) + _ri(0)))

    def _cyl_coedge(self, key, wl):
        bi, ci = key[1], key[2]
        info = self._cyl_info(bi)
        name = info["axis"]
        R = info["R"]
        specs = [
            (1, 3, 1, T_FLAG_A), (2, 0, 2, T_FLAG_A), (3, 1, 0, T_FLAG_B),
            (0, 2, 2, T_FLAG_B), (4, 4, 1, T_FLAG_B), (5, 5, 0, T_FLAG_A)]
        nxt_i, prv_i, edg_i, sense = specs[ci]
        loop_ptr = ("loop", bi, 0) if ci < 4 else (("loop", bi, 1) if ci == 4 else ("loop", bi, 2))
        partn = (3, 2, 1, 0, 0, 0)[ci]
        return (_Rec("coedge", 16)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1),
                     wl.ref(("coedge", bi, nxt_i)),
                     wl.ref(("coedge", bi, prv_i)),
                     wl.ref(("coedge", bi, partn)),
                     wl.ref(("edge", bi, edg_i)), bytes([sense]),
                     wl.ref(loop_ptr), _p(-1)))

    def _cyl_edge(self, key, wl):
        bi, ei = key[1], key[2]
        info = self._cyl_info(bi)
        R, h, mu = info["R"], info["h"], info["major_unit"]
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        vbot = (cap_a[0] + mu[0] * R, cap_a[1] + mu[1] * R,
                cap_a[2] + mu[2] * R)
        vtop = (cap_b[0] + mu[0] * R, cap_b[1] + mu[1] * R,
                cap_b[2] + mu[2] * R)
        co_c = 2 if ei == 0 else (0 if ei == 1 else 2)
        if ei == 0:
            v, v2, curve = ("vertex", bi, 0), ("vertex", bi, 0), ("ellipse", bi, 1)
            length = 2.0 * math.pi
            bmin = circ_bbox_of(cap_a, R, info["axis"])[0]
            bmax = circ_bbox_of(cap_a, R, info["axis"])[1]
            attrib_i = wl.ref(("attrib", "ename", bi, ei))
            return (_Rec("edge", 17)
                    .add(wl.ref(("attrib", "ename", bi, ei)), _ti(4), _ti(-1),
                         _p(-1), wl.ref(v), _td(0.0), wl.ref(v), _td(length),
                         wl.ref(("coedge", bi, co_c)), wl.ref(curve),
                         bytes([T_FLAG_B]), _s("unknown"),
                         bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))
        if ei == 1:
            bmin, bmax = circ_bbox_of(cap_b, R, info["axis"])
            return (_Rec("edge", 17)
                    .add(wl.ref(("attrib", "ename", bi, ei)), _ti(5), _ti(-1),
                         _p(-1), wl.ref(("vertex", bi, 1)), _td(0.0),
                         wl.ref(("vertex", bi, 1)), _td(2.0 * math.pi),
                         wl.ref(("coedge", bi, 0)), wl.ref(("ellipse", bi, 0)),
                         bytes([T_FLAG_B]), _s("unknown"),
                         bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))
        bmin = (min(vbot[0], vtop[0]), min(vbot[1], vtop[1]), min(vbot[2], vtop[2]))
        bmax = (max(vbot[0], vtop[0]), max(vbot[1], vtop[1]), max(vbot[2], vtop[2]))
        v = "z"
        return (_Rec("edge", 17)
                .add(wl.ref(("attrib", "ename", bi, ei)), _ti(6), _ti(-1),
                     _p(-1), wl.ref(("vertex", bi, 0)), _td(0.0),
                     wl.ref(("vertex", bi, 1)), _td(h),
                     wl.ref(("coedge", bi, 2)), wl.ref(("straight", bi, 0)),
                     bytes([T_FLAG_B]), _s("unknown"),
                     bytes([T_FLAG_A]), _v3(*bmin), _v3(*bmax)))

    def _cyl_vertex(self, key, wl):
        bi, vi = key[1], key[2]
        info = self._cyl_info(bi)
        R, mu = info["R"], info["major_unit"]
        cap_a, cap_b = info["cap_a"], info["cap_b"]
        pos = (cap_a[0] + mu[0] * R, cap_a[1] + mu[1] * R,
               cap_a[2] + mu[2] * R) if vi == 0 else (
            cap_b[0] + mu[0] * R, cap_b[1] + mu[1] * R, cap_b[2] + mu[2] * R)
        edge_key = ("edge", bi, 0) if vi == 0 else ("edge", bi, 1)
        return (_Rec("vertex", 18)
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), wl.ref(edge_key),
                     wl.ref(("point", bi, vi))))
        # note: point via _point for cyl uses cyl geometry below

    def _point(self, key, wl):
        # cyl points handled separately (position depends on body kind)
        raise ValueError("use _cyl_point via _point registry")

    def _cone(self, key, wl):
        bi = key[1]
        info = self._cyl_info(bi)
        R, axis, mu, org = info["R"], info["axis"], info["major_unit"], info["origin"]
        return (_Rec("surface", 13, chain=[("cone", 14)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*org),
                     _v3b(-axis[0], -axis[1], -axis[2]),
                     _v3b(mu[0] * R, mu[1] * R, mu[2] * R),
                     _td(1.0), bytes([T_FLAG_B, T_FLAG_B]),
                     _td(-0.0), _td(1.0), _td(R),
                     bytes([T_FLAG_A, T_FLAG_B, T_FLAG_B, T_FLAG_B, T_FLAG_B])))

    def _ellipse(self, key, wl):
        bi, k = key[1], key[2]
        info = self._cyl_info(bi)
        R, mu, axis = info["R"], info["major_unit"], info["axis"]
        center = info["cap_b"] if k == 0 else info["cap_a"]
        return (_Rec("curve", 21, chain=[("ellipse", 20)])
                .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*center),
                     _v3b(*axis), _v3b(mu[0] * R, mu[1] * R, mu[2] * R),
                     _td(1.0), bytes([T_FLAG_B, T_FLAG_B])))

    def _straight(self, key, wl):
        bi = key[1]
        if self._item(bi)[0] == "cyl":
            info = self._cyl_info(bi)
            h = info["h"]
            mu, cap_a, cap_b = info["major_unit"], info["cap_a"], info["cap_b"]
            R = info["R"]
            ax = (0.0, 0.0, 0.001)
            p1 = (cap_a[0] + mu[0] * R, cap_a[1] + mu[1] * R,
                  cap_a[2] + mu[2] * R)
            return (_Rec("curve", 21, chain=[("straight", 22)])
                    .add(_p(-1), _ti(-1), _ti(-1), _p(-1), _v3(*p1),
                         _v3b(*ax), bytes([T_FLAG_A]), _td(0.0),
                         bytes([T_FLAG_A]), _td(h)))
        return self._straight_planar(key, wl)


def circ_bbox_of(center, R, axis):
    import math as _m
    ex = R * _m.sqrt(max(0.0, 1.0 - axis[0] * axis[0]))
    ey = R * _m.sqrt(max(0.0, 1.0 - axis[1] * axis[1]))
    ez = R * _m.sqrt(max(0.0, 1.0 - axis[2] * axis[2]))
    return ((center[0] - ex, center[1] - ey, center[2] - ez),
            (center[0] + ex, center[1] + ey, center[2] + ez))


'''
io.open(PATH, "w", encoding="utf-8").write(src[:start] + new_fn + src[end:])
print("patched: replaced _build_sab (%d..%d)" % (start, end))

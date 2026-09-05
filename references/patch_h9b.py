# -*- coding: utf-8 -*-
"""Wire write_scdoc_multi into the save path + facets fallback per part."""
import io

P = "scdm_gui.py"
s = io.open(P, encoding="utf-8").read()
old = '''                elif low.endswith(".scdoc"):
                    from scdm.scdoc_write import write_scdoc
                    write_scdoc(path, ses.kdoc, name=ses.name)'''
new = '''                elif low.endswith(".scdoc"):
                    from scdm.scdoc_write import write_scdoc
                    if ses.kdoc.components:
                        from scdm.scdoc_write import write_scdoc_multi
                        write_scdoc_multi(path, ses.kdoc, name=ses.name)
                    else:
                        write_scdoc(path, ses.kdoc, name=ses.name)'''
assert old in s
s = s.replace(old, new, 1)
io.open(P, "w", encoding="utf-8").write(s)
print("save path wired")

P2 = "scdm/scdoc_write.py"
s2 = io.open(P2, encoding="utf-8").read()
# multi writer: facets fallback for non-planar groups (mesh body on read)
old2 = '''        for gi, (_gname, items, colors) in enumerate(groups):
            items2 = [it[:4] for it in items]
            out.writestr("SpaceClaim/Geometry/part%dbodies.sab" % (gi + 1),
                         build_sab_for(items2, colors))
    return len(groups)'''
new2 = '''        non_planar = any(it[0] in ("cyl", "sphere", "torus")
                         for _g, items, _c in groups for it in items)
        if non_planar:
            try:
                tessellations = []
                for body in kdoc.bodies:
                    sols = K.explore(body.shape, "solid") or [body.shape]
                    for sol in sols:
                        try:
                            from scdm.kernel import tessellate_faces
                            tessellations.append(tessellate_faces(
                                sol, deflection=max(1e-5, 0.05 / 1000.0)))
                        except Exception:
                            tessellations.append([])
                items_all = [it[:4] for _g, items, _c in groups
                             for it in items]
                out.writestr("SpaceClaim/Graphics/facets.bin",
                             _facets_bytes(items_all, tessellations))
            except Exception:
                pass
        for gi, (_gname, items, colors) in enumerate(groups):
            items2 = [it[:4] for it in items]
            out.writestr("SpaceClaim/Geometry/part%dbodies.sab" % (gi + 1),
                         build_sab_for(items2, colors))
    return len(groups)'''
assert old2 in s2
s2 = s2.replace(old2, new2, 1)
io.open(P2, "w", encoding="utf-8").write(s2)
print("facets fallback added")

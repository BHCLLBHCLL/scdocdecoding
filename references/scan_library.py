# -*- coding: utf-8 -*-
"""Scan the official Library scdoc instances through our parser and report
how much geometry each yields (bodies/faces/edges/coedges and any parse
failures), so we can drive parser-improvement work.

Usage: python scan_library.py   (paths hardcoded to the SpaceClaim install)
"""
import glob
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scdoc_parser import sab as sab_mod
from scdoc_parser import topology
from scdoc_parser import opc

SR = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\SrModels"
DF = r"C:\Program Files\ANSYS Inc\v195\scdm\Library\DrawingFormats"


def scan_one(path):
    result = {"path": path, "status": "ok", "geometry": [], "kind_counts": {},
              "note": ""}
    try:
        pkg = opc.parse_package(path)
        geom = pkg.find_geometry()
        if not geom:
            result["status"] = "no-geometry"
            return result
        # all SAB parts
        total = {}
        models = []
        for gp in geom:
            try:
                sf = sab_mod.tokenize(pkg.read(gp.name))
                model = topology.SabModel(sf)
                counts = {}
                for k in ("body", "lump", "shell", "face", "loop", "coedge",
                          "edge", "vertex", "plane", "cone", "straight",
                          "ellipse", "point"):
                    counts[k] = len(model.of_kind(k))
                models.append(counts)
                for k, v in counts.items():
                    total[k] = total.get(k, 0) + v
            except Exception as e:
                result["status"] = "parse-error"
                result["note"] = f"{gp.name}: {type(e).__name__}: {e}"
                return result
        result["geometry"] = models
        result["kind_counts"] = total
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "fatal"
        result["note"] = repr(e)
    return result


def main():
    print("=== SrModels (has geometry) ===")
    for base, label in ((SR, "SrModels"), (DF, "DrawingFormats")):
        for f in sorted(glob.glob(os.path.join(base, "*.scdoc"))):
            r = scan_one(f)
            name = os.path.basename(f)
            if r["status"] == "ok" and r["geometry"]:
                tot = r["kind_counts"]
                print(f"[{label}] {name}: {len(r['geometry'])} SAB; "
                      f"bodies={tot.get('body',0)} faces={tot.get('face',0)} "
                      f"edges={tot.get('edge',0)} coedges={tot.get('coedge',0)} "
                      f"planes={tot.get('plane',0)} cones={tot.get('cone',0)} "
                      f"verts={tot.get('vertex',0)}")
            elif r["status"] == "ok":
                print(f"[{label}] {name}: no geometry parts")
            else:
                print(f"[{label}] {name}: {r['status']} {r.get('note')}")


if __name__ == "__main__":
    main()

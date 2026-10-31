#!/usr/bin/env python
"""Final integrated check on the EXPORTED files (not the in-memory model) + package zip.
Checks: STEP re-import validity, full pairwise rigid interference on the assembly (excluding flexible parts), print STLs watertight,
BOM-to-CAD agreement (every printed/machined/COTS part in v3_info has a BOM line; bearing/seal sizes agree), depth from the STEP."""
import csv, itertools, json, os, sys, zipfile, math
import cadquery as cq, trimesh
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "cad", "out"); info = json.load(open(os.path.join(OUT, "v3_info.json")))
report = []
for var in ("min76", "robust"):
    names = [p["name"] for p in info["configs"][var]["parts"]]
    a = cq.importers.importStep(os.path.join(OUT, f"{var}_assembly.step")); sol = a.solids().vals()
    ok = all(s.isValid() for s in sol)
    xs = [s.BoundingBox() for s in sol]; depth = max(b.xmax for b in xs) - min(b.xmin for b in xs)
    report.append(f"{var}_assembly.step: {len(sol)} solids (parts listed {len(names)}), all valid {ok}, depth from STEP {depth:.2f} mm (layout {info['configs'][var]['layout']['axial_depth_mm']:.2f})")
    flexible = lambda n: n.startswith("oring") or n in ("lip_seal", "plug_oring")
    named = list(zip(names, sol))
    clashes = []
    for (na, sa), (nb, sb) in itertools.combinations(named, 2):
        if flexible(na) or flexible(nb): continue
        ba, bb = sa.BoundingBox(), sb.BoundingBox()
        if ba.xmax < bb.xmin - 0.5 or bb.xmax < ba.xmin - 0.5: continue
        try: v = sa.intersect(sb).Volume()
        except Exception: v = -1
        if v > 0.5 or v < 0: clashes.append((na, nb, round(v, 2)))
    report.append(f"   full pairwise rigid check ({len(named)} solids): {'no clash' if not clashes else clashes}")
stls = sorted(f for f in os.listdir(OUT) if f.endswith("_PRINT.stl"))
nw, volmis = [], []
for f in stls:
    mm = trimesh.load(os.path.join(OUT, f), force="mesh")
    if not mm.is_watertight: nw.append(f)
    var, part = f.split("_", 1)[0], f.rsplit("_PRINT.stl", 1)[0].split("_", 1)[1]
    entry = next((p for p in info["configs"][var]["parts"] if p["name"] == part), None)
    if entry:
        dv = (mm.volume / entry["volume_mm3"] - 1) * 100
        if abs(dv) > 1.5: volmis.append((f, round(dv, 2)))
    if mm.bounds[0][2] < -1e-3 or mm.bounds[0][2] > 1e-3: volmis.append((f, "not on z=0"))
report.append(f"print STLs: {len(stls)}; non-watertight: {nw if nw else 'none'}; STL-vs-STEP volume beyond 1.5 % or not on the bed: {volmis if volmis else 'none'}")
bom = list(csv.DictReader(open(os.path.join(ROOT, "docs", "BOM_v3.csv"))))
bomtxt = " ".join((r["part"] + " " + r["specification"] + " " + r["drawing / file"]).lower() for r in bom)
missing = []
for p in info["configs"]["min76"]["parts"]:
    n = p["name"]; base = n.split("_")[0]
    key = {"tube": "pressure tube", "front": "front cap", "rear": "rear cap", "spindle": "spindle", "bearing": "6702", "lip": "lip seal", "speedi": "99059", "circlip": "din 471", "drive": "drive disc",
           "motor": "gl60", "boss": "strut boss", "carrier": "carrier segment", "blade": "blades", "pin": "spring pin", "dome": "dome", "strut": "struts", "duct": "duct", "oring": "as568-147",
           "shim": "shim", "split": "split thrust ring", "potting": "potting plug", "plug": "as568-010", "vent": "vent", "screw": "din 7984"}.get(base, base)
    if key not in bomtxt: missing.append((n, key))
report.append(f"BOM-to-CAD: {'every CAD part has a BOM line' if not missing else 'missing ' + str(missing)}; bearing '{info['variants']['min76']['brg']}' in BOM: {info['variants']['min76']['brg'] in bomtxt}; seal '{info['variants']['min76']['seal']}' in BOM: {info['variants']['min76']['seal'].replace('x', ' x ') in bomtxt or info['variants']['min76']['seal'] in bomtxt}")
txt = "\n".join(report); print(txt)
open(os.path.join(ROOT, "docs", "FINAL_CHECK.txt"), "w").write(txt + "\n")
if "--zip" in sys.argv:
    z = zipfile.ZipFile(os.path.join(ROOT, "turbine_redesign_v3_package.zip"), "w", zipfile.ZIP_DEFLATED)
    for d, _, fs in os.walk(ROOT):
        for f in fs:
            fp = os.path.join(d, f); rel = os.path.relpath(fp, ROOT)
            if "__pycache__" in rel or rel.endswith(".zip") or rel.endswith(".pyc"): continue
            z.write(fp, os.path.join("turbine_redesign_v3", rel))
    z.close(); print("zip written")

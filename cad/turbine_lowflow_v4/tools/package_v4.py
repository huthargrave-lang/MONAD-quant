#!/usr/bin/env python3
import os, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
z = zipfile.ZipFile(os.path.join(ROOT, "turbine_lowflow_v4_package.zip"), "w", zipfile.ZIP_DEFLATED)
for d, _, fs in os.walk(ROOT):
    for f in fs:
        fp = os.path.join(d, f); rel = os.path.relpath(fp, ROOT)
        if "__pycache__" in rel or rel.endswith(".zip") or rel.endswith(".pyc") or rel.endswith("REPORT_v4.html"): continue
        z.write(fp, os.path.join("turbine_lowflow_v4", rel))
z.close(); print("zip written", os.path.getsize(os.path.join(ROOT, "turbine_lowflow_v4_package.zip")) // 1024, "kB")

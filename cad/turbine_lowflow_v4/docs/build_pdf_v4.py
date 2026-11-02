#!/usr/bin/env python3
"""REPORT_v4.md -> REPORT_v4.html (figures inlined) -> REPORT_v4.pdf via the pre-installed Chromium (playwright)."""
import base64, os, re, sys, markdown
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, "..")
md = open(os.path.join(D, "REPORT_v4.md")).read()
figs = {"## 2. Baseline": ["fig4_power_vs_v.png"], "## 3. Optimisation": ["fig_polars.png"], "## 4. Comparison": ["fig2_cp_tsr.png"], "## 5. Selected": ["fig5_6_chord_twist.png"],
        "## 6. Generator": ["fig1_hydraulic_power.png", "fig3_torque_rpm.png", "fig9_operating_point.png", "fig7_generator_losses.png"], "## 7. Recommended": ["fig10a_section.png", "fig10b_dimensioned.png", "fig10c_exploded.png"], "## 8. Plots": ["fig8_sensitivity.png"]}
def b64(f):
    with open(os.path.join(ROOT, "out", f), "rb") as fh: return "data:image/png;base64," + base64.b64encode(fh.read()).decode()
for head, fl in figs.items():
    i = md.index(head); j = md.index("\n", i)
    block = "".join(f'\n\n<figure><img src="{b64(f)}" alt="{f}"><figcaption>{f}</figcaption></figure>' for f in fl)
    # place figures at the END of the section (before the next '## ')
    k = md.find("\n## ", j + 1); k = len(md) if k < 0 else k
    md = md[:k] + block + md[k:]
body = markdown.markdown(md, extensions=["tables", "fenced_code"])
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Low-flow turbine v4 report</title>
<style>body{{font:10.5pt/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#141414;margin:0 auto;max-width:1100px;padding:24px}}
h1{{font-size:20pt}} h2{{font-size:14pt;margin-top:26px;border-top:1px solid #ddd;padding-top:8px}} table{{border-collapse:collapse;font-size:8.2pt;margin:8px 0;width:100%}}
th,td{{border:1px solid #ccc;padding:3px 5px;vertical-align:top}} th{{background:#f0efe9}} code{{font-size:0.9em;background:#f3f2ee;padding:0 3px}} pre{{font-size:8pt;background:#f3f2ee;padding:8px;white-space:pre-wrap}}
figure{{margin:12px 0;page-break-inside:avoid}} img{{width:100%}} figcaption{{font-size:8pt;color:#666}} @page{{size:A4 landscape;margin:12mm}}</style></head><body>{body}</body></html>"""
open(os.path.join(D, "REPORT_v4.html"), "w").write(html); print("html", len(html) // 1024, "kB")
import subprocess
r = subprocess.run(["node", os.path.join(D, "html2pdf.js"), os.path.join(D, "REPORT_v4.html"), os.path.join(D, "REPORT_v4.pdf")], capture_output=True, text=True, timeout=300)
print(r.stdout.strip() or r.stderr.strip()[-300:])
if os.path.exists(os.path.join(D, "REPORT_v4.pdf")): print("pdf", os.path.getsize(os.path.join(D, "REPORT_v4.pdf")) // 1024, "kB")

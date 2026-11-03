#!/usr/bin/env python3
"""BLADE_OPTIMIZATION_v4.md -> pdf with numbered figures inlined (Chromium via html2pdf.js)."""
import base64, os, subprocess, markdown
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, "..")
md = open(os.path.join(D, "BLADE_OPTIMIZATION_v4.md")).read()
def b64(f):
    with open(os.path.join(ROOT, "out", f), "rb") as fh: return "data:image/png;base64," + base64.b64encode(fh.read()).decode()
figs = {"## 4.": [("fig_polars.png", "Figure 1. Surrogate polars of the candidate sections (lift curve and drag polar at Re 6e4, best L/D against Reynolds number). Dotted: low surrogate confidence, excluded from the search.")],
        "## 5.": [("fig2_cp_tsr.png", "Figure 2. Power coefficient against tip-speed ratio at 0.5, 0.7 and 1.0 m/s: selected blade, original rev-2 blade and v3.1 drum blade."),
                  ("fig5_6_chord_twist.png", "Figure 3. Chord and twist distributions of the selected blade and the previous designs.")],
        "## 8.": [("fig4_power_vs_v.png", "Figure 4. Net electrical output against flow speed. Crosses mark speeds gated out by the self-start or sustain conditions.")],
        "## 10.": [("fig8_sensitivity.png", "Figure 5. One-at-a-time sensitivity of the net output at 0.5, 0.7 and 1.0 m/s.")]}
for head, fl in figs.items():
    i = md.index(head); k = md.find("\n## ", i + 1); k = len(md) if k < 0 else k
    md = md[:k] + "".join(f'\n\n<figure><img src="{b64(f)}" alt="{f}"><figcaption>{cap}</figcaption></figure>' for f, cap in fl) + md[k:]
body = markdown.markdown(md, extensions=["tables", "fenced_code"])
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Blade Geometry Optimization for 0.5-1.0 m/s Streams</title>
<style>
@page{{size:A4;margin:16mm 15mm}}
body{{font:10pt/1.5 "Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1a1a1a;max-width:190mm;margin:0 auto}}
h1{{font-size:19pt;font-weight:600;margin:0 0 4px;letter-spacing:-0.01em}}
p.sub{{font-size:9.5pt;color:#555;margin:0 0 18px;padding-bottom:10px;border-bottom:2px solid #2b4a6b}}
h2{{font-size:13pt;font-weight:600;color:#2b4a6b;margin:22px 0 6px;padding-bottom:3px;border-bottom:1px solid #c9d3dd;page-break-after:avoid}}
p{{margin:6px 0}} ul{{margin:4px 0 8px 0;padding-left:18px}} li{{margin:2px 0}}
table{{border-collapse:collapse;font-size:8.6pt;margin:8px 0 10px;width:100%}} tr{{page-break-inside:avoid}} thead{{display:table-header-group}}
th,td{{border:1px solid #d5d5d5;padding:3px 6px;vertical-align:top;text-align:left}} th{{background:#eef2f6;font-weight:600}}
tr:nth-child(even) td{{background:#fafafa}}
code{{font-size:0.9em;background:#f1f1f1;padding:0 3px;border-radius:2px}}
figure{{margin:10px 0 14px;page-break-inside:avoid}} img{{width:100%;border:1px solid #e4e4e4}} figcaption{{font-size:8.5pt;color:#555;margin-top:4px}}
strong{{font-weight:600}}
</style></head><body>{body}</body></html>"""
open(os.path.join(D, "BLADE_OPTIMIZATION_v4.html"), "w").write(html)
r = subprocess.run(["node", os.path.join(D, "html2pdf.js"), os.path.join(D, "BLADE_OPTIMIZATION_v4.html"), os.path.join(D, "BLADE_OPTIMIZATION_v4.pdf")], capture_output=True, text=True, timeout=300)
print(r.stdout.strip() or r.stderr.strip()[-300:]); os.remove(os.path.join(D, "BLADE_OPTIMIZATION_v4.html"))
print("pdf", os.path.getsize(os.path.join(D, "BLADE_OPTIMIZATION_v4.pdf")) // 1024, "kB")

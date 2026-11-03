#!/usr/bin/env python3
"""BLADE_OPTIMIZATION_v4.md -> pdf with the optimisation figures inlined (Chromium via html2pdf.js)."""
import base64, os, subprocess, markdown
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, "..")
md = open(os.path.join(D, "BLADE_OPTIMIZATION_v4.md")).read()
def b64(f):
    with open(os.path.join(ROOT, "out", f), "rb") as fh: return "data:image/png;base64," + base64.b64encode(fh.read()).decode()
figs = {"## 3.": [("fig_polars.png", "Figure 1. Surrogate polars (lift, drag, L/D) of the candidate sections across Reynolds number, with the Viterna post-stall extension.")],
        "## 4.": [("fig2_cp_tsr.png", "Figure 2. Cp against tip-speed ratio at 0.5 / 0.7 / 1.0 m/s: selected blade vs the original rev-2 blade and the v3.1 drum blade."),
                  ("fig5_6_chord_twist.png", "Figures 3-4. Chord and twist distributions of the selected blade against the previous designs.")],
        "## 6.": [("fig4_power_vs_v.png", "Figure 5. Net electrical power against flow speed; crosses mark points gated out by self-start or sustain.")],
        "## 8.": [("fig8_sensitivity.png", "Figure 6. One-at-a-time sensitivity of the net output at 0.5 / 0.7 / 1.0 m/s.")]}
for head, fl in figs.items():
    i = md.index(head); k = md.find("\n## ", i + 1); k = len(md) if k < 0 else k
    md = md[:k] + "".join(f'\n\n<figure><img src="{b64(f)}" alt="{f}"><figcaption>{cap}</figcaption></figure>' for f, cap in fl) + md[k:]
body = markdown.markdown(md, extensions=["tables", "fenced_code"])
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Blade optimisation for 0.5-1.0 m/s</title>
<style>body{{font:10.5pt/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#141414;margin:0 auto;max-width:1100px;padding:24px}}
h1{{font-size:20pt}} h2{{font-size:14pt;margin-top:26px;border-top:1px solid #ddd;padding-top:8px}} table{{border-collapse:collapse;font-size:8.2pt;margin:8px 0;width:100%}}
th,td{{border:1px solid #ccc;padding:3px 5px;vertical-align:top}} th{{background:#f0efe9}} code{{font-size:0.9em;background:#f3f2ee;padding:0 3px}}
figure{{margin:12px 0;page-break-inside:avoid}} img{{width:100%}} figcaption{{font-size:8.5pt;color:#555}} @page{{size:A4 landscape;margin:12mm}}</style></head><body>{body}</body></html>"""
open(os.path.join(D, "BLADE_OPTIMIZATION_v4.html"), "w").write(html)
r = subprocess.run(["node", os.path.join(D, "html2pdf.js"), os.path.join(D, "BLADE_OPTIMIZATION_v4.html"), os.path.join(D, "BLADE_OPTIMIZATION_v4.pdf")], capture_output=True, text=True, timeout=300)
print(r.stdout.strip() or r.stderr.strip()[-300:]); os.remove(os.path.join(D, "BLADE_OPTIMIZATION_v4.html"))
print("pdf", os.path.getsize(os.path.join(D, "BLADE_OPTIMIZATION_v4.pdf")) // 1024, "kB")

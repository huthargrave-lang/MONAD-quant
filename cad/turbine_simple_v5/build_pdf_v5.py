#!/usr/bin/env python3
"""REPORT_v5.md -> REPORT_v5.pdf (figures inlined) via the v4 package's html2pdf.js (pre-installed Chromium / playwright)."""
import base64, os, subprocess, markdown
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4"))
md = open(os.path.join(HERE, "REPORT_v5.md")).read()
def b64(f):
    with open(os.path.join(OUT, f), "rb") as fh: return "data:image/png;base64," + base64.b64encode(fh.read()).decode()
figs = {"## 1.": ["fig_v5_section.png", "fig_v5_exploded.png"], "## 3.": ["fig_v5_power.png"]}
for head, fl in figs.items():
    i = md.index(head); k = md.find("\n## ", i + 1); k = len(md) if k < 0 else k
    md = md[:k] + "".join(f'\n\n<figure><img src="{b64(f)}" alt="{f}"><figcaption>{f}</figcaption></figure>' for f in fl) + md[k:]
body = markdown.markdown(md, extensions=["tables", "fenced_code"])
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Simplified prototype turbine v5</title>
<style>body{{font:10.5pt/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#141414;margin:0 auto;max-width:1100px;padding:24px}}
h1{{font-size:20pt}} h2{{font-size:14pt;margin-top:26px;border-top:1px solid #ddd;padding-top:8px}} table{{border-collapse:collapse;font-size:8.6pt;margin:8px 0;width:100%}}
th,td{{border:1px solid #ccc;padding:3px 5px;vertical-align:top}} th{{background:#f0efe9}} code{{font-size:0.9em;background:#f3f2ee;padding:0 3px}}
figure{{margin:12px 0;page-break-inside:avoid}} img{{width:100%}} figcaption{{font-size:8pt;color:#666}} @page{{size:A4 landscape;margin:12mm}}</style></head><body>{body}</body></html>"""
open(os.path.join(HERE, "REPORT_v5.html"), "w").write(html)
r = subprocess.run(["node", os.path.join(V4, "docs", "html2pdf.js"), os.path.join(HERE, "REPORT_v5.html"), os.path.join(HERE, "REPORT_v5.pdf")], capture_output=True, text=True, timeout=300)
print(r.stdout.strip() or r.stderr.strip()[-300:]); os.remove(os.path.join(HERE, "REPORT_v5.html"))
print("pdf", os.path.getsize(os.path.join(HERE, "REPORT_v5.pdf")) // 1024, "kB")

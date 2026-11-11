#!/usr/bin/env python3
"""Re-centre the v5 rotor print mesh on its rotation axis for rendering (translation only; geometry unchanged).
usage: recenter_rotor.py <in: out/v5_rotor_PRINT.stl> <out: rotor.stl>"""
import sys, numpy as np, trimesh
m = trimesh.load(sys.argv[1]); v = m.vertices
tip = v[v[:, 2] < v[:, 2].min() + 0.3]                       # flat nose tip on the print bed sits on the rotation axis
c = np.r_[0.5 * (tip[:, 0].min() + tip[:, 0].max()), 0.5 * (tip[:, 1].min() + tip[:, 1].max())]
r = np.hypot(v[:, 0] - c[0], v[:, 1] - c[1]).max(); assert abs(2 * r - 203.2) < 0.2, f"unexpected rotor diameter {2 * r:.2f} mm"
v0 = m.volume; m.apply_translation([-c[0], -c[1], -0.5 * (v[:, 2].min() + v[:, 2].max())]); assert abs(m.volume - v0) < 1e-6
m.export(sys.argv[2]); print(f"rotor diameter {2 * r:.1f} mm, {len(m.faces)} faces, watertight {m.is_watertight}")

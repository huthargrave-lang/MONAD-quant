#!/usr/bin/env python
"""Dimensioned 2D drawings (half-sections) of the machined parts, generated from the same parameters as the CAD."""
import json, os, sys, math
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_v3 as m
VAR = sys.argv[1] if len(sys.argv) > 1 else "min76"
P = m.P; V = m.VARIANTS[VAR]; OUT = m.OUT
SURFACE, INK, INK2 = "#fcfcfb", "#0b0b0b", "#52514e"
def dim(ax, xa, ya, xb, yb, txt, off=(0, 3), rot=0):
    ax.annotate("", (xa, ya), (xb, yb), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.9))
    ax.text(0.5 * (xa + xb) + off[0], 0.5 * (ya + yb) + off[1], txt, ha="center", va="center", color=INK, fontsize=8, rotation=rot)
def profile(ax, pts, **kw):
    xs, ys = zip(*(pts + [pts[0]])); ax.plot(xs, ys, color=INK, lw=1.4, **kw)
    ax.fill(xs, ys, color="#dcd9cf", alpha=0.6)
figs = []
# ---------------- front cap (half section, axis at y=0)
t = V["flange_t"]; L = V["plug_len"]; rp = (P["tube_id"] - P["plug_clear"]) / 2; rf = P["tube_od"] / 2
g_r = rp - P["oring_groove_d"]; gw = P["oring_groove_w"]; g1 = 2.0; g2 = 2.0 + V["oring_pitch"]
brg_r = V["brg_od"] / 2; bw = V["brg_w"]
fig, ax = plt.subplots(figsize=(12, 6), facecolor=SURFACE); ax.set_facecolor(SURFACE)
pts = [(0, 0), (0, rf), (t, rf), (t, rp), (t + g1, rp), (t + g1, g_r), (t + g1 + gw, g_r), (t + g1 + gw, rp), (t + g2, rp), (t + g2, g_r), (t + g2 + gw, g_r), (t + g2 + gw, rp),
       (t + L, rp), (t + L, brg_r), (t + L - bw - 0.2, brg_r), (t + L - bw - 0.2, 10.0), (t + L - bw - 2.0, 10.0), (t + L - bw - 2.0, 0)]
profile(ax, pts)
ax.plot([-5, t + L + 5], [0, 0], "-.", color=INK2, lw=0.8)
dim(ax, 0, rf + 4, t, rf + 4, f"{t}"); dim(ax, t, rp + 4, t + L, rp + 4, f"plug {L}"); dim(ax, t + g1, g_r - 3, t + g1 + gw, g_r - 3, f"{gw}"); dim(ax, t + g1 + gw / 2, g_r - 8, t + g2 + gw / 2, g_r - 8, f"pitch {V['oring_pitch']}")
dim(ax, -4, 0, -4, rf, f"Ø{P['tube_od']} flange", off=(-2, 0), rot=90); dim(ax, t + L + 3, 0, t + L + 3, rp, f"Ø{2*rp:.2f} plug (to measured bore -0.15)", off=(3, 0), rot=90)
dim(ax, t + L - bw - 0.2 - 3, 0, t + L - bw - 0.2 - 3, brg_r, f"Ø{V['brg_od']} H7 x {bw + 0.2} (blind)", off=(-3, 0), rot=90)
dim(ax, t + g1 + gw + 1, g_r, t + g1 + gw + 1, rp, f"{P['oring_groove_d']}", off=(2, 0), rot=90)
ax.text(0, -6, f"FRONT CAP, Delrin (POM-C). Flange face: 3 notches 6.3 x 3.3 x {t} at the rim (120 deg, for the carrier lugs); 3x M3 blind tapped 5 deep on Ø{P['tube_od']-18:.0f} (dome).\n"
        f"Inner face: 4x M3 blind tapped 6 deep on PCD {P['disc_pcd_out']} (drive disc). Circlip recess Ø20 x 1.9 behind the bearing pocket. Groove corners R0.2, groove surfaces Ra 1.6, plug OD Ra 0.8, 15 deg lead chamfer 1.0.", color=INK2, fontsize=8, va="top")
ax.set_aspect("equal"); ax.set_xlim(-10, t + L + 14); ax.set_ylim(-16, rf + 10); ax.set_axis_off(); ax.set_title(f"Drawing 1: front cap ({VAR}) - half section, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_front_cap.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("front_cap")
# ---------------- rear cap
sw = V["seal_w"]; sr = V["seal_od"] / 2
fig, ax = plt.subplots(figsize=(12, 6), facecolor=SURFACE); ax.set_facecolor(SURFACE)
x_brg0 = L + t - sw - 1.5 - bw  # from the plug inner face at x=0 to the wet face at L+t
pts = [(0, 9.0), (0, brg_r), (x_brg0 + bw, brg_r), (x_brg0 + bw, 9.0), (L + t - sw, 9.0), (L + t - sw, sr), (L + t, sr), (L + t, rf), (L, rf), (L, rp),
       (L - 2.0, rp), (L - 2.0, g_r), (L - 2.0 - gw, g_r), (L - 2.0 - gw, rp), (L - 2.0 - V["oring_pitch"], rp), (L - 2.0 - V["oring_pitch"], g_r), (L - 2.0 - V["oring_pitch"] - gw, g_r), (L - 2.0 - V["oring_pitch"] - gw, rp), (0, rp)]
profile(ax, pts)
ax.plot([-5, L + t + 5], [0, 0], "-.", color=INK2, lw=0.8)
dim(ax, 0, rp + 4, L, rp + 4, f"plug {L}"); dim(ax, L, rf + 4, L + t, rf + 4, f"{t}"); dim(ax, L + t - sw, sr + 3, L + t, sr + 3, f"seal {sw}")
dim(ax, 0, brg_r + 7, x_brg0 + bw, brg_r + 7, f"bearing bore {x_brg0 + bw:.1f} deep from the inner face")
dim(ax, -4, 0, -4, brg_r, f"Ø{V['brg_od']} H7", off=(-3, 0), rot=90); dim(ax, L + t + 3, 0, L + t + 3, sr, f"Ø{V['seal_od']} H8 seal seat", off=(3, 0), rot=90); dim(ax, x_brg0 + bw + 2, 0, x_brg0 + bw + 2, 9.0, "Ø18 wall hole", off=(2, 0), rot=90)
ax.text(0, -6, f"REAR CAP, Delrin (POM-C). Plug with 2 O-ring grooves as the front cap; 3 lug notches in the flange rim; M6 tapped through at r={P['vent_r']} (vent, 316 screw + Dowty washer);\n"
        f"bearing bore open to the inside with the shoulder at the rear (thrust); 1.5 mm wall with Ø18 hole clears the spindle collar Ø17.6; lip-seal seat from the wet face, 0.3 x 15 deg chamfer, Ra 0.8.", color=INK2, fontsize=8, va="top")
ax.set_aspect("equal"); ax.set_xlim(-10, L + t + 14); ax.set_ylim(-16, rf + 10); ax.set_axis_off(); ax.set_title(f"Drawing 2: rear cap ({VAR}) - half section, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_rear_cap.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("rear_cap")
# ---------------- spindle
info = json.load(open(os.path.join(OUT, "v3_info.json")))["configs"][VAR]["layout"]
Ls = info["x_boss"][1] - (info["x_brg_front"] - 1.7); xf = info["x_motor"][1] - (info["x_brg_front"] - 1.7)
fig, ax = plt.subplots(figsize=(13, 5), facecolor=SURFACE); ax.set_facecolor(SURFACE)
rs = P["spindle_d"] / 2; rb = P["spindle_bore"] / 2; rfl = P["sp_flange_od"] / 2; tfl = P["sp_flange_t"]
pts = [(0, rb), (0, rs), (xf, rs), (xf, rfl), (xf + tfl, rfl), (xf + tfl, rs), (Ls, rs), (Ls, rb)]
profile(ax, pts); ax.plot([-5, Ls + 5], [0, 0], "-.", color=INK2, lw=0.8)
xg = 1.5 - 0.3; ax.plot([xg, xg, xg + P["circlip_w"], xg + P["circlip_w"]], [rs, P["circlip_d"] / 2, P["circlip_d"] / 2, rs], color=INK, lw=1.2)
xc = info["x_brg_rear"] + V["brg_w"] + 0.1 - (info["x_brg_front"] - 1.7); ax.plot([xc, xc, xc + 1.3, xc + 1.3], [rs, 8.8, 8.8, rs], color=INK, lw=1.2)
xs_ = info["x_seal"] - 1.0 - (info["x_brg_front"] - 1.7); ax.plot([xs_, xs_ + V["seal_w"] + 2], [rs + 0.28, rs + 0.28], color="#555", lw=2)
dim(ax, 0, rfl + 9, Ls, rfl + 9, f"overall {Ls:.1f}"); dim(ax, 0, -rs - 4, xf, -rs - 4, f"{xf:.1f} to the flange"); dim(ax, xf, rfl + 3, xf + tfl, rfl + 3, f"{tfl}")
dim(ax, -4, 0, -4, rs, "Ø15 h6", off=(-2, 0), rot=90); dim(ax, Ls + 4, 0, Ls + 4, rb, f"Ø{P['spindle_bore']} bore", off=(3, 0), rot=90); dim(ax, xf + tfl + 3, 0, xf + tfl + 3, rfl, f"Ø{P['sp_flange_od']} flange", off=(3, 0), rot=90)
ax.text(xg, rs + 2.5, "DIN 471-15 groove 14.3 x 1.1", fontsize=7.5, color=INK2); ax.text(xc + 3, rs + 2.5, "collar Ø17.6 x 1.3 (thrust)", fontsize=7.5, color=INK2); ax.text(xs_ - 2, -rs - 2.5, "Speedi-Sleeve 99059 track", fontsize=7.5, color=INK2, va="top")
ax.text(0, -rs - 9, f"SPINDLE, 6061-T6, hard-anodised (type III, 40-50 um) after machining; journals 15 h6 before coating, re-measure after. Flange: 4 holes on the GL60 stator PCD (TO MEASURE: PCD {P['motor_pcd']} shown) + radial lead slot 4.5 wide.\n"
        f"Side holes Ø4.5: lead entry {xf + tfl + 3.5:.1f} from the nose (inside the drum) and lead exit {Ls - 4.5:.1f} (inside the boss, potted). Cross-pin hole Ø3.1 at {Ls - V['boss_t']/2:.1f}. Deburr all holes; bore chamfers 0.5 for the leads.", color=INK2, fontsize=8, va="top")
ax.set_aspect("equal"); ax.set_xlim(-10, Ls + 12); ax.set_ylim(-rs - 20, rfl + 14); ax.set_axis_off(); ax.set_title(f"Drawing 3: spindle ({VAR}) - half section, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_spindle.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("spindle")
# ---------------- boss and strut bar (plan views)
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 6), facecolor=SURFACE); ax.set_facecolor(SURFACE); ax2.set_facecolor(SURFACE)
rbo = P["boss_od"] / 2; th = [i * math.pi / 180 for i in range(361)]
ax.plot([rbo * math.cos(a) for a in th], [rbo * math.sin(a) for a in th], color=INK, lw=1.4); ax.plot([7.5 * math.cos(a) for a in th], [7.5 * math.sin(a) for a in th], color=INK, lw=1.2)
for k in range(3):
    a = math.radians(90 + 120 * k); r0, r1 = rbo - 6, rbo + 1
    for s_ in (-1, 1):
        ax.plot([r0 * math.cos(a) + s_ * 2.2 * math.sin(a), r1 * math.cos(a) + s_ * 2.2 * math.sin(a)], [r0 * math.sin(a) - s_ * 2.2 * math.cos(a), r1 * math.sin(a) - s_ * 2.2 * math.cos(a)], color=INK, lw=1)
ax.plot([0, 0], [-rbo, rbo], ":", color=INK2); ax.plot([2.75, 2.75, -2.75, -2.75], [7.5, rbo, rbo, 7.5], color=INK, lw=0.8)
ax.text(0, -rbo - 8, f"STRUT BOSS, 6061-T6 plate {P['boss_od']} dia x {V['boss_t']} thick (laser/water-jet + drill): bore Ø15 H7; cross-pin Ø3.1 through;\n3 strut pockets 4.4 x {V['boss_t']+2:.0f} x 7 deep at 120 deg with Ø3.1 pin holes; cable channel 5.5 x 5.5 on the rear face from the bore to pocket 1. Anodise.",
        ha="center", va="top", color=INK2, fontsize=8)
ax.set_aspect("equal"); ax.set_xlim(-rbo - 10, rbo + 10); ax.set_ylim(-rbo - 24, rbo + 8); ax.set_axis_off(); ax.set_title("Drawing 4: strut boss - plan, mm", loc="left", fontweight="bold")
# strut bar development (flat pattern) and side view
jog = V["strut_jog"]; w = P["strut_w"]; tb = V["boss_t"] - 0.4; r_in = rbo - 5.8; r0j, r1j = P["r_jog0"], P["r_jog1"]; rfoot = P["duct_od"] / 2
ax2.plot([r_in, r0j, r0j, r1j, r1j, rfoot + 4, rfoot + 4, r1j, r1j, r0j, r0j, r_in, r_in], [-tb / 2, -tb / 2, -tb / 2 - jog + 0, -w / 2 - jog, -w / 2 - jog, -w / 2 - jog, w / 2 - jog, w / 2 - jog, w / 2 - jog, tb / 2, tb / 2, tb / 2, -tb / 2], color=INK, lw=1.4)
ax2.plot([rfoot, rfoot + 4, rfoot + 4 + P["foot_len"]], [-w / 2 - jog - 1, -w / 2 - jog - 1, -w / 2 - jog - 1], color=INK2, lw=0.8)
dim(ax2, r_in, 8, r0j, 8, f"tab {r0j - r_in:.1f} x {tb:.1f} wide"); dim(ax2, r1j, -jog - w / 2 - 6, rfoot, -jog - w / 2 - 6, f"outer leg {rfoot - r1j:.1f} x {w} wide"); dim(ax2, r0j - 3, 0, r0j - 3, -jog, f"jog {jog}", off=(-4, 0), rot=90)
ax2.text(r_in, 20, f"STRUT (3x), 6061-T6 flat bar {w} x {P['strut_t']} mm: cut, drill Ø3 (root pin) and 2x Ø4.3 (foot), bend the jog ({jog} mm, 2 x 45 deg or 2 x 90 deg) and the 90 deg foot ({P['foot_len']} long) with R >= 2t.\nOptional printed NACA fairing clamshell over the outer leg.", color=INK2, fontsize=8, va="top")
ax2.set_aspect("equal"); ax2.set_xlim(r_in - 10, rfoot + 30); ax2.set_ylim(-jog - w - 14, 26); ax2.set_axis_off(); ax2.set_title("Drawing 5: strut bar - side view (X vertical), mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_boss_strut.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("boss_strut")
print("drawings:", figs)

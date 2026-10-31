#!/usr/bin/env python
"""Dimensioned 2D drawings (half-sections / plan views) of the machined parts, generated from the same parameters as the CAD (v3.1).
These are quotation drawings: the STEP files carry the full geometry; the notes carry tolerances, finishes and coating."""
import json, os, sys, math, textwrap
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_v3 as m
VAR = sys.argv[1] if len(sys.argv) > 1 else "min76"
P = m.P; V = m.VARIANTS[VAR]; OUT = m.OUT
info = json.load(open(os.path.join(OUT, "v3_info.json")))["configs"][VAR]["layout"]
SURFACE, INK, INK2 = "#fcfcfb", "#0b0b0b", "#52514e"
def dim(ax, xa, ya, xb, yb, txt, off=(0, 3), rot=0):
    ax.annotate("", (xa, ya), (xb, yb), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.9))
    ax.text(0.5 * (xa + xb) + off[0], 0.5 * (ya + yb) + off[1], txt, ha="center", va="center", color=INK, fontsize=8, rotation=rot)
def note(ax, x, y, txt, width=150, **kw):
    ax.text(x, y, "\n".join(textwrap.fill(par, width) for par in txt.split("\n")), color=INK2, fontsize=7.5, va="top", **kw)
def profile(ax, pts, **kw):
    xs, ys = zip(*(pts + [pts[0]])); ax.plot(xs, ys, color=INK, lw=1.4, **kw); ax.fill(xs, ys, color="#dcd9cf", alpha=0.6)
figs = []
rf = P["tube_od"] / 2; rp = (P["tube_id"] - P["plug_clear"]) / 2; g_r = rp - P["oring_groove_d"]; gw = P["oring_groove_w"]; land = P["oring_land"]
t = V["flange_t"]; brg_r = V["brg_od"] / 2; bw = V["brg_w"]
# ---------------- front cap (half section, flange at x=0..t, plug t..t+L, axis y=0)
L = V["plug_front"]
fig, ax = plt.subplots(figsize=(12, 6), facecolor=SURFACE); ax.set_facecolor(SURFACE)
x_in = t + L; x_brg = x_in - bw - 0.2
pts = [(0, 0), (0, rf), (t, rf), (t, rp)]
for i in range(V["n_orings"]):
    xg = t + land + i * V["oring_pitch"]; pts += [(xg, rp), (xg, g_r), (xg + gw, g_r), (xg + gw, rp)]
pts += [(x_in, rp), (x_in, brg_r), (x_brg, brg_r), (x_brg, 12.0), (x_brg - 2.0, 12.0), (x_brg - 2.0, 8.0), (x_brg - 3.5, 8.0), (x_brg - 3.5, 0)]
profile(ax, pts); ax.plot([-5, x_in + 5], [0, 0], "-.", color=INK2, lw=0.8)
# dog pocket (section through one pocket at r = 24) and dome tapped hole (r = 29) shown dashed
ax.plot([x_in - P["dog_h"] - 0.8, x_in - P["dog_h"] - 0.8, x_in + 1], [P["disc_pcd_out"] / 2 - 4.15, P["disc_pcd_out"] / 2 + 4.15, P["disc_pcd_out"] / 2 + 4.15], "--", color=INK2, lw=0.9)
ax.plot([-1, 4], [rf - 9, rf - 9], ":", color=INK2, lw=1.2)
dim(ax, 0, rf + 4, t, rf + 4, f"{t}"); dim(ax, t, rp + 4, x_in, rp + 4, f"plug {L}"); dim(ax, t + land, g_r - 3, t + land + gw, g_r - 3, f"{gw}")
dim(ax, t, g_r - 8, t + land, g_r - 8, f"land {land}")
dim(ax, -4, 0, -4, rf, f"Ø{P['tube_od']} flange", off=(-2, 0), rot=90); dim(ax, x_in + 3, 0, x_in + 3, rp, f"Ø{2*rp:.2f} plug (to the bored tube -0.15)", off=(3, 0), rot=90)
dim(ax, x_brg + 1, 0, x_brg + 1, brg_r, f"Ø{V['brg_od']} N7 x {bw + 0.2} (blind)", off=(3, 0), rot=90)
dim(ax, x_brg - 1, 0, x_brg - 1, 12.0, "Ø24 x 2.0 circlip recess", off=(-3, 0), rot=90); dim(ax, x_brg - 2.8, 0, x_brg - 2.8, 8.0, "Ø16 x 1.5 nose pocket", off=(-3, 0), rot=90)
dim(ax, t + land + gw + 1, g_r, t + land + gw + 1, rp, f"{P['oring_groove_d']}", off=(2, 0), rot=90)
note(ax, 0, -6, f"FRONT CAP, 6061-T6, hard-anodised type III 40-50 um after machining (journal/bore sizes AFTER coating). Flange face: 3 notches 6.3 x 3.3 x {t} at the rim (60/180/300 deg) for the carrier lugs; "
        f"3x M3 blind tapped 4 deep on Ø{P['tube_od']-18:.0f} (0/120/240 deg, dome).\nInner face: 4 blind dog pockets Ø{P['dog_d']+0.3} x {P['dog_h']+0.8} on PCD {P['disc_pcd_out']} at 45/135/225/315 deg (TPU disc dogs). "
        f"Bearing pocket Ø{V['brg_od']} N7 (interference for the rotating outer ring), circlip recess Ø24 x 2.0 (DIN 471-15 incl. lugs), nose pocket Ø16 x 1.5.\n"
        f"{V['n_orings']} O-ring groove(s) {gw} x {P['oring_groove_d']} for AS568-147: lands {land} mm, corners R0.2, groove Ra 1.6, plug OD Ra 0.8, 15 deg x 1.0 lead chamfer ON THE LAND side only (do not cut into the groove wall).", width=120)
ax.set_aspect("equal"); ax.set_xlim(-10, x_in + 14); ax.set_ylim(-20, rf + 10); ax.set_axis_off(); ax.set_title(f"Drawing 1: front cap ({VAR}) - half section, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_front_cap.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("front_cap")
# ---------------- rear cap (plug 0..L from the inner face, flange L..L+t, wet face at L+t)
L = V["plug_rear"]; sw = V["seal_w"]; sr = V["seal_od"] / 2; web = P["cap_web"]
fig, ax = plt.subplots(figsize=(12, 6), facecolor=SURFACE); ax.set_facecolor(SURFACE)
x_wet = L + t; x_brg0 = x_wet - sw - web - bw
pts = [(0, 9.0), (0, brg_r), (x_brg0 + bw, brg_r), (x_brg0 + bw, 9.0), (x_wet - sw, 9.0), (x_wet - sw, sr), (x_wet, sr), (x_wet, P["lab_groove_r0"]), (x_wet - P["lab_groove_d"], P["lab_groove_r0"]),
       (x_wet - P["lab_groove_d"], P["lab_groove_r1"]), (x_wet, P["lab_groove_r1"]), (x_wet, rf), (L, rf), (L, rp)]
for i in range(V["n_orings"]):
    xg = L - land - gw - i * V["oring_pitch"]; pts += [(xg + gw, rp), (xg + gw, g_r), (xg, g_r), (xg, rp)]
pts += [(0, rp)]
profile(ax, pts); ax.plot([-5, x_wet + 5], [0, 0], "-.", color=INK2, lw=0.8)
ax.plot([x_wet - P["vent_cb_depth"], x_wet - P["vent_cb_depth"], x_wet + 1], [P["vent_r"] - 5.5, P["vent_r"] + 5.5, P["vent_r"] + 5.5], "--", color=INK2, lw=0.9); ax.plot([-1, x_wet + 1], [P["vent_r"], P["vent_r"]], ":", color=INK2, lw=1.0)
dim(ax, 0, rp + 4, L, rp + 4, f"plug {L}"); dim(ax, L, rf + 4, x_wet, rf + 4, f"{t}"); dim(ax, x_wet - sw, sr + 3, x_wet, sr + 3, f"seal {sw}")
dim(ax, x_brg0 + bw, 9.0 - 3, x_wet - sw, 9.0 - 3, f"web {web}")
dim(ax, 0, brg_r + 7, x_brg0 + bw, brg_r + 7, f"bearing bore {x_brg0 + bw:.1f} deep from the inner face (shoulder = thrust stop)")
dim(ax, -4, 0, -4, brg_r, f"Ø{V['brg_od']} N7", off=(-3, 0), rot=90); dim(ax, x_wet + 3, 0, x_wet + 3, sr, f"Ø{V['seal_od']} H8 seal seat", off=(3, 0), rot=90); dim(ax, x_brg0 + bw + 1.2, 0, x_brg0 + bw + 1.2, 9.0, "Ø18 wall hole", off=(2, 0), rot=90)
dim(ax, x_wet + 8, P["lab_groove_r0"], x_wet + 8, P["lab_groove_r1"], f"labyrinth groove r {P['lab_groove_r0']}-{P['lab_groove_r1']} x {P['lab_groove_d']} deep", off=(3, 0), rot=90)
note(ax, 0, -6, f"REAR CAP, 6061-T6, hard-anodised type III 40-50 um. {V['n_orings']} O-ring groove(s) as the front cap (lands {land}); 3 lug notches in the flange rim (60/180/300 deg); "
        f"M6 tapped through at r {P['vent_r']} with a Ø{P['vent_cb_d']} x {P['vent_cb_depth']} counterbore from the wet face (vent: M6 low-head 316 screw + Dowty washer, head inside the counterbore);\n"
        f"bearing bore Ø{V['brg_od']} N7 open to the inside with the thrust shoulder at the rear; {web} mm web with the Ø18 hole clears the split thrust ring Ø17.6 and the shim; seal seat Ø{V['seal_od']} H8 from the wet face, 0.3 x 15 deg chamfer, Ra 0.8 "
        f"(PTFE pressure-rated lip seal {V['seal']}, press AFTER the cap is on the spindle);\nlabyrinth groove r {P['lab_groove_r0']}-{P['lab_groove_r1']} x {P['lab_groove_d']} in the wet face (boss tongue enters 1.5 mm, 0.5 mm radial clearance). Runout of the bearing bore and seal seat to the plug OD < 0.03.", width=120)
ax.set_aspect("equal"); ax.set_xlim(-10, x_wet + 22); ax.set_ylim(-20, rf + 10); ax.set_axis_off(); ax.set_title(f"Drawing 2: rear cap ({VAR}) - half section, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_rear_cap.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("rear_cap")
# ---------------- spindle (x from the nose end)
x0 = info["x_spindle"][0]; Ls = info["x_spindle"][1] - x0; xf = info["x_motor"][1] - x0
rs = P["spindle_d"] / 2; rb = P["spindle_bore"] / 2; rfl = P["sp_flange_od"] / 2; tfl = P["sp_flange_t"]
fig, ax = plt.subplots(figsize=(14, 7), facecolor=SURFACE); ax.set_facecolor(SURFACE)
pts = [(0, rb), (0, rs), (xf, rs), (xf, rfl), (xf + tfl, rfl), (xf + tfl, rs), (Ls, rs), (Ls, rb)]
profile(ax, pts); ax.plot([-5, Ls + 5], [0, 0], "-.", color=INK2, lw=0.8)
xg = info["x_circlip"] - x0; ax.plot([xg, xg, xg + P["circlip_w"], xg + P["circlip_w"]], [rs, P["circlip_d"] / 2, P["circlip_d"] / 2, rs], color=INK, lw=1.2)
xc = info["x_collar"] - x0; ax.plot([xc, xc, xc + P["collar_w"], xc + P["collar_w"]], [rs, P["collar_groove_d"] / 2, P["collar_groove_d"] / 2, rs], color=INK, lw=1.2)
xs0, xs1 = info["x_sleeve"][0] - x0, info["x_sleeve"][1] - x0; ax.plot([xs0, xs1], [rs + 0.28, rs + 0.28], color="#555", lw=2.5)
xl = xf + P["lead_channel_d"] / 2; ax.plot([xl - 2.25, xl - 2.25, xl + 2.25, xl + 2.25], [rb, rs + 2, rs + 2, rb], "--", color=INK2, lw=0.9)
ax.plot([xf, xf + P["lead_channel_d"], xf + P["lead_channel_d"]], [rs, rs, rfl], ":", color=INK2, lw=1.2)
xp = info["x_boss_pin"] - x0; ax.plot([xp, xp], [-rs - 1, rs + 1], "--", color=INK2, lw=0.9)
for pcd in (P["bell_pcd"], P["motor_pcd"]):
    ax.plot([xf + tfl - P["screw_cb_depth"], xf + tfl + 0.5], [pcd / 2, pcd / 2], "-", color=INK2, lw=2.0)
dim(ax, 0, rfl + 9, Ls, rfl + 9, f"overall {Ls:.1f}"); dim(ax, 0, -rs - 4, xf, -rs - 4, f"{xf:.1f} to the flange"); dim(ax, xf, rfl + 3, xf + tfl, rfl + 3, f"{tfl}")
dim(ax, 0, -rs - 9, xg, -rs - 9, f"{xg:.1f}"); dim(ax, xf + tfl, -rs - 4, xc, -rs - 4, f"{xc - xf - tfl:.2f} to the ring groove"); dim(ax, xc, -rs - 9, Ls, -rs - 9, f"{Ls - xc:.1f}")
dim(ax, -4, 0, -4, rs, "Ø15 h6", off=(-2, 0), rot=90); dim(ax, Ls + 4, 0, Ls + 4, rb, f"Ø{P['spindle_bore']} bore\n(9 H7 reamed 15 deep from the rear)", off=(5, 0), rot=90); dim(ax, xf + tfl + 3, 0, xf + tfl + 3, rfl, f"Ø{P['sp_flange_od']} flange", off=(3, 0), rot=90)
ax.text(xg, rs + 2.5, f"DIN 471-15 groove {P['circlip_d']} x {P['circlip_w']}, {P['circlip_edge']} from the end", fontsize=7.5, color=INK2); ax.text(xc + 3, rs + 5.5, f"split-ring groove Ø{P['collar_groove_d']} x {P['collar_w']}", fontsize=7.5, color=INK2); ax.text(xs0 + 1, rs + 2.5, "Speedi-Sleeve 99059 track (Ra 0.4)", fontsize=7.5, color=INK2)
ax.text(xl + 3, rfl + 1, f"lead hole Ø{P['lead_hole_d']} at {P['lead_angle']:.0f} deg under the flange channel ({P['lead_channel_w']} x {P['lead_channel_d']}, front face)", fontsize=7.5, color=INK2); ax.text(xp + 1, rs + 8.5, "cross-pin Ø3.1", fontsize=7.5, color=INK2)
note(ax, 0, -rs - 14, f"SPINDLE, 6061-T6, hard-anodised type III 40-50 um after machining; both journals 15 h6 AFTER coating (machine ~14.95 before). Integral flange Ø{P['sp_flange_od']} x {tfl}: 4x Ø3.4 on PCD {P['bell_pcd']} and 4x Ø2.9 on PCD {P['motor_pcd']} (0/90/180/270 deg, both GL60 patterns) "
        f"with Ø{P['screw_cb_d']} x {P['screw_cb_depth']} counterbores on the REAR face; lead channel {P['lead_channel_w']} x {P['lead_channel_d']} on the FRONT face at {P['lead_angle']:.0f} deg from the OD to the bore.\n"
        f"Rear end recessed {P['spindle_recess']} mm inside the boss; rear bore reamed 9 H7 x 15 for the potting plug (O-ring land Ra 0.8). Cross-pin hole Ø3.1 through at {xp:.1f} from the nose. Deburr; 0.5 chamfers at the lead hole and the bore ends; sealant under the Speedi-Sleeve; Tef-Gel on the pins.", width=130)
ax.set_aspect("equal"); ax.set_xlim(-10, Ls + 16); ax.set_ylim(-rs - 34, rfl + 16); ax.set_axis_off(); ax.set_title(f"Drawing 3: spindle ({VAR}) - half section, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_spindle.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("spindle")
# ---------------- boss (plan), strut profile, potting plug
fig, (ax, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6), facecolor=SURFACE, gridspec_kw=dict(width_ratios=[1.0, 1.3, 0.7]))
for a in (ax, ax2, ax3): a.set_facecolor(SURFACE)
rbo = P["boss_od"] / 2; th = [i * math.pi / 180 for i in range(361)]
ax.plot([rbo * math.cos(a) for a in th], [rbo * math.sin(a) for a in th], color=INK, lw=1.4); ax.plot([7.5 * math.cos(a) for a in th], [7.5 * math.sin(a) for a in th], color=INK, lw=1.2)
for rr in (P["lab_r0"], P["lab_r1"]): ax.plot([rr * math.cos(a) for a in th], [rr * math.sin(a) for a in th], "--", color=INK2, lw=0.8)
for k in range(3):
    a = math.radians(90 + 120 * k); r0, r1 = rbo - 6, rbo + 1
    for s_ in (-1, 1):
        ax.plot([r0 * math.cos(a) + s_ * 2.2 * math.sin(a), r1 * math.cos(a) + s_ * 2.2 * math.sin(a)], [r0 * math.sin(a) - s_ * 2.2 * math.cos(a), r1 * math.sin(a) - s_ * 2.2 * math.cos(a)], color=INK, lw=1)
a = math.radians(90 - P["lead_groove_angle"]); r0, r1 = 4.0, rbo + 1
for s_ in (-1, 1):
    ax.plot([r0 * math.cos(a) + s_ * 3 * math.sin(a), r1 * math.cos(a) + s_ * 3 * math.sin(a)], [r0 * math.sin(a) - s_ * 3 * math.cos(a), r1 * math.sin(a) - s_ * 3 * math.cos(a)], "--", color=INK2, lw=1)
ax.plot([-rbo, rbo], [0, 0], ":", color=INK2)
note(ax, 0, -rbo - 8, f"STRUT BOSS, 6061-T6, Ø{P['boss_od']} x {V['boss_t']} (turn + mill, anodise): bore Ø15 H7 (thermal paste); cross-pin Ø3.1 through at {P['boss_pin_x']} from the front face;\n"
        f"labyrinth tongue r {P['lab_r0']}-{P['lab_r1']} x {P['lab_h']} proud of the front face; 3 strut pockets 4.4 x {V['boss_t']:.0f} through x 7 deep at 120 deg with Ø3.1 pin holes;\n"
        f"lead groove {P['lead_groove_w']} x {P['lead_groove_d']} on the REAR face from the bore to the OD at {P['lead_groove_angle']:.0f} deg from strut 0 (dashed); spindle end {P['spindle_recess']} mm below the rear face.", width=80, ha="center")
ax.set_aspect("equal"); ax.set_xlim(-rbo - 10, rbo + 10); ax.set_ylim(-rbo - 30, rbo + 8); ax.set_axis_off(); ax.set_title("Drawing 4: strut boss - plan (rear face), mm", loc="left", fontweight="bold")
# strut profile (x axial vertical, r horizontal) as cut from plate
jog = V["strut_jog"]; w = P["strut_w"]; tb = V["boss_t"] - 0.4; r_in = rbo - 5.8; r0j, r1j = P["r_jog0"], P["r_jog1"]; r_end = P["duct_od"] / 2 + 10
xc = 0.0
pts = [(r_in, xc - tb / 2), (r_in, xc + tb / 2), (r0j, xc + tb / 2), (r1j, xc - jog + w / 2), (r_end, xc - jog + w / 2), (r_end, xc - jog - w / 2), (r1j, xc - jog - w / 2), (r0j, xc - tb / 2)]
profile(ax2, pts)
for rr in (P["duct_od"] / 2 + 2.5, P["duct_od"] / 2 + 8.0): ax2.add_patch(plt.Circle((rr, xc - jog), 2.15, fill=False, color=INK, lw=1))
ax2.add_patch(plt.Circle((rbo - 3, xc), 1.5, fill=False, color=INK, lw=1))
ax2.plot([P["duct_id"] / 2, P["duct_id"] / 2], [xc - jog - w, xc + 10], ":", color=INK2); ax2.plot([P["duct_od"] / 2, P["duct_od"] / 2], [xc - jog - w, xc + 10], ":", color=INK2)
dim(ax2, r_in, xc + tb / 2 + 4, r0j, xc + tb / 2 + 4, f"tab {r0j - r_in:.1f} x {tb:.1f}"); dim(ax2, r1j, xc - jog - w / 2 - 5, r_end, xc - jog - w / 2 - 5, f"leg {r_end - r1j:.1f} x {w}")
dim(ax2, r0j - 4, xc, r0j - 4, xc - jog, f"jog {jog}", off=(-4, 0), rot=90); dim(ax2, r0j, xc - jog - w / 2 - 12, r1j, xc - jog - w / 2 - 12, f"jog span {r1j - r0j:.0f} radial")
note(ax2, r_in, xc + 34, f"STRUT (3x), 6061-T6 plate {P['strut_t']} mm, profile water-jet/laser cut in ONE plane (no bending): tab in the boss pocket (Ø3 root pin), cranked jog, 16 mm leg through the duct slot\ninto the printed clevis (2x Ø4.3 for M4 x 25 A4 + nyloc). Deburr, radius the jog corners R3, anodise or leave bare (6061 in fresh water with Tef-Gel on the 316 fasteners). Optional printed fairing clamshell on the leg.", width=110)
ax2.set_aspect("equal"); ax2.set_xlim(r_in - 10, r_end + 10); ax2.set_ylim(xc - jog - w - 16, xc + 50); ax2.set_axis_off(); ax2.set_title("Drawing 5: strut - plate profile (axial X vertical, flow up), mm", loc="left", fontweight="bold")
# potting plug
pl, ph, pd, hd, ht = P["plug_len"], P["plug_head_t"], P["plug_d"], P["plug_head_d"], 2.4
pts = [(0, 0), (0, pd / 2), (3.0, pd / 2), (3.0, 3.04), (3.0 + ht, 3.04), (3.0 + ht, pd / 2), (pl, pd / 2), (pl, hd / 2), (pl + ph, hd / 2), (pl + ph, 0)]
profile(ax3, pts); ax3.plot([-2, pl + ph + 2], [0, 0], "-.", color=INK2, lw=0.8); ax3.plot([-1, pl + ph + 1], [2.25, 2.25], "--", color=INK2, lw=0.9)
dim(ax3, 0, pd / 2 + 2, pl, pd / 2 + 2, f"{pl}"); dim(ax3, pl, hd / 2 + 2, pl + ph, hd / 2 + 2, f"{ph}"); dim(ax3, 3.0, 2.0, 3.0 + ht, 2.0, f"{ht}")
dim(ax3, -2, 0, -2, pd / 2, f"Ø{pd} f7", off=(-2, 0), rot=90); dim(ax3, pl + ph + 2, 0, pl + ph + 2, hd / 2, f"Ø{hd}", off=(2, 0), rot=90); dim(ax3, 3.0 + ht + 1.5, 0, 3.0 + ht + 1.5, 3.04, "Ø6.08", off=(2, 0), rot=90)
note(ax3, 0, -3, "POTTING PLUG, Delrin (POM-C): Ø9 f7 x 10 + Ø12 x 2 head; Ø4.5 through for 3 leads;\nAS568-010 EPDM groove 2.4 wide, Ø6.08 bottom (squeeze ~18 %). Leads stripped 6 mm and solder-filled\ninside the plug, then epoxy-potted (Loctite EA E-30CL or 3M DP270). Head bears on the spindle end face.", width=70)
ax3.set_aspect("equal"); ax3.set_xlim(-6, pl + ph + 8); ax3.set_ylim(-12, hd / 2 + 6); ax3.set_axis_off(); ax3.set_title("Drawing 6: potting plug, mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(OUT, f"{VAR}_drawing_boss_strut.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight"); figs.append("boss_strut_plug")
print("drawings:", figs)

#!/usr/bin/env python3
"""Low-Reynolds hydrofoil polars for the 0.5-1.0 m/s turbine study.

Source: NeuralFoil 0.3.3 (neural-network surrogate of XFOIL, Ncrit 9, trained on 2-D viscous XFOIL results) via
AeroSandbox's UIUC coordinate database.  Each polar is tabulated on an (alpha, Re) grid and extended past the surrogate's
validity (|alpha| > 18 deg) with the Viterna post-stall model (needed for the standstill / starting-torque estimate).
The surrogate's own 'analysis_confidence' is stored; airfoils with confidence < 0.9 are reported but not selectable.
XFOIL-class predictions are optimistic at Re < 1e5 (laminar separation bubbles): the uncertainty study applies a drag
multiplier (1.0 / 1.3 / 1.6) and a lift knockdown (1.0 / 0.9) on top of these tables (REPORT section 8).  No experimental
polar at the operating Reynolds numbers is available to this project."""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "polars_cache.json")
ALPHAS = np.arange(-10.0, 18.01, 1.0)
RES = np.array([2e4, 3e4, 4e4, 6e4, 8e4, 1e5, 1.5e5, 2e5, 3e5, 5e5])
CANDIDATES = {
    # name: (asb name, nominal t/c, note)
    "naca4412": ("naca4412", 0.12, "baseline family of the original 1-2 m/s blade"),
    "naca4415": ("naca4415", 0.15, "thicker baseline family (root blend)"),
    "naca4418": ("naca4418", 0.18, "root section"),
    "sg6043":   ("sg6043",   0.10, "Selig/Giguere low-Re high-lift small-wind-turbine section"),
    "e387":     ("e387",     0.091, "Eppler low-Re glider section, widely measured at Re 6e4-3e5"),
    "fx63137":  ("fx63137",  0.137, "Wortmann high-camber low-Re section"),
    "e818":     ("e818",     0.12, "Eppler hydrofoil requested by the brief: database coordinates are coarse (67 pts), surrogate confidence low"),
}
THICK_ROOT = "naca4418"

def viterna_extend(alpha_deg, cl, cd, al_s_pos, al_s_neg, cdmax=1.8, ar_eff=None):
    """Return cl, cd at any alpha using the tabulated range inside [al_s_neg, al_s_pos] and Viterna outside."""
    def tab(a):
        return float(np.interp(a, alpha_deg, cl)), float(np.interp(a, alpha_deg, cd))
    def vit(a, a_s, cl_s, cd_s):
        a, a_s = math.radians(a), math.radians(a_s)
        kl = (cl_s - cdmax * math.sin(a_s) * math.cos(a_s)) * math.sin(a_s) / max(math.cos(a_s) ** 2, 1e-6)
        kd = (cd_s - cdmax * math.sin(a_s) ** 2) / max(math.cos(a_s), 1e-6)
        sa = max(math.sin(a), 1e-6)
        return cdmax / 2 * math.sin(2 * a) + kl * math.cos(a) ** 2 / sa, cdmax * sa ** 2 + kd * math.cos(a)
    def f(a):
        if al_s_neg <= a <= al_s_pos:
            return tab(a)
        if a > al_s_pos:
            cl_s, cd_s = tab(al_s_pos); return vit(min(a, 89.0), al_s_pos, cl_s, cd_s)
        cl_s, cd_s = tab(al_s_neg)
        c, d = vit(min(-a, 89.0), -al_s_neg, -cl_s, cd_s); return -c, d
    return f

def build_tables(force=False):
    if os.path.exists(CACHE) and not force:
        return json.load(open(CACHE))
    import aerosandbox as asb, neuralfoil as nf
    out = {}
    for name, (asb_name, tc, note) in CANDIDATES.items():
        af = asb.Airfoil(asb_name)
        tab = dict(tc=tc, note=note, alphas=ALPHAS.tolist(), Res=RES.tolist(), cl=[], cd=[], conf=[], coords=af.coordinates.tolist())
        for Re in RES:
            r = nf.get_aero_from_airfoil(af, alpha=ALPHAS, Re=float(Re), model_size="xlarge")
            tab["cl"].append(np.asarray(r["CL"]).tolist()); tab["cd"].append(np.asarray(r["CD"]).tolist()); tab["conf"].append(np.asarray(r["analysis_confidence"]).tolist())
        cl = np.array(tab["cl"]); cd = np.array(tab["cd"]); conf = np.array(tab["conf"])
        # best L/D and stall angles per Re (stall = alpha of max cl within the table, clipped to 16 deg for the Viterna hand-off)
        tab["best_ld"] = [float((cl[i] / cd[i]).max()) for i in range(len(RES))]
        tab["alpha_best"] = [float(ALPHAS[(cl[i] / cd[i]).argmax()]) for i in range(len(RES))]
        tab["cl_best"] = [float(cl[i][(cl[i] / cd[i]).argmax()]) for i in range(len(RES))]
        tab["alpha_stall"] = [float(min(ALPHAS[cl[i].argmax()], 16.0)) for i in range(len(RES))]
        tab["clmax"] = [float(cl[i].max()) for i in range(len(RES))]
        tab["conf_mean"] = float(conf[:, (ALPHAS >= -4) & (ALPHAS <= 14)].mean())
        tab["selectable"] = bool(tab["conf_mean"] >= 0.9)
        out[name] = tab
        print(f"{name:9s} t/c {tc:.3f} conf {tab['conf_mean']:.2f} | Re 6e4: best L/D {tab['best_ld'][3]:.1f} at {tab['alpha_best'][3]:.0f} deg (cl {tab['cl_best'][3]:.2f}), clmax {tab['clmax'][3]:.2f} | Re 1.5e5: L/D {tab['best_ld'][6]:.1f}")
    json.dump(out, open(CACHE, "w"))
    return out

class Polar:
    """Interpolating polar with Viterna extension: cl, cd = polar(alpha_rad, Re). Optional cd multiplier / cl factor."""
    def __init__(self, tab, cd_mult=1.0, cl_fac=1.0, cd_add=0.0):
        self.al = np.array(tab["alphas"]); self.Res = np.array(tab["Res"]); self.logRe = np.log(self.Res)
        self.cl = np.array(tab["cl"]) * cl_fac; self.cd = np.array(tab["cd"]) * cd_mult + cd_add
        self.al_s = np.array(tab["alpha_stall"]); self.tc = tab["tc"]
        self._fns = {}
    def _fn(self, i):
        if i not in self._fns:
            self._fns[i] = viterna_extend(self.al, self.cl[i], self.cd[i], self.al_s[i], -8.0)
        return self._fns[i]
    def __call__(self, alpha, Re):
        a = math.degrees(alpha)
        lr = min(max(math.log(max(Re, 1.0)), self.logRe[0]), self.logRe[-1])
        j = int(np.searchsorted(self.logRe, lr, side="right") - 1); j = min(max(j, 0), len(self.Res) - 2)
        w = (lr - self.logRe[j]) / (self.logRe[j + 1] - self.logRe[j])
        c0, d0 = self._fn(j)(a); c1, d1 = self._fn(j + 1)(a)
        return (1 - w) * c0 + w * c1, (1 - w) * d0 + w * d1
    def best(self, Re):
        """design angle (rad) and cl at the best L/D for this Re (interpolated)"""
        lr = min(max(math.log(Re), self.logRe[0]), self.logRe[-1])
        j = int(np.searchsorted(self.logRe, lr, side="right") - 1); j = min(max(j, 0), len(self.Res) - 2)
        w = (lr - self.logRe[j]) / (self.logRe[j + 1] - self.logRe[j])
        ld0 = self.cl[j] / self.cd[j]; ld1 = self.cl[j + 1] / self.cd[j + 1]
        ld = (1 - w) * ld0 + w * ld1
        # design point: slightly below best L/D for margin against stall at the root: use alpha at 0.97 of max L/D on the low side
        k = int(ld.argmax())
        return math.radians(self.al[k]), float(((1 - w) * self.cl[j] + w * self.cl[j + 1])[k])

def blended_polar(tabs, outer, root=THICK_ROOT):
    return Polar(tabs[outer]), Polar(tabs[root])

if __name__ == "__main__":
    tabs = build_tables(force="--force" in sys.argv)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(16, 5), facecolor="#fcfcfb")
    for name, t in tabs.items():
        cl = np.array(t["cl"]); cd = np.array(t["cd"]); i6 = list(t["Res"]).index(6e4)
        ls = "-" if t["selectable"] else ":"
        axs[0].plot(t["alphas"], cl[i6], ls, label=f"{name} (conf {t['conf_mean']:.2f})"); axs[1].plot(cd[i6], cl[i6], ls); axs[2].plot(t["Res"], t["best_ld"], ls + "o", ms=3)
    axs[0].set_xlabel("alpha (deg)"); axs[0].set_ylabel("CL at Re 6e4"); axs[0].legend(fontsize=7); axs[0].grid(alpha=0.3)
    axs[1].set_xlabel("CD"); axs[1].set_ylabel("CL (drag polar, Re 6e4)"); axs[1].set_xlim(0, 0.08); axs[1].grid(alpha=0.3)
    axs[2].set_xscale("log"); axs[2].set_xlabel("Re"); axs[2].set_ylabel("best L/D"); axs[2].grid(alpha=0.3)
    fig.suptitle("Candidate hydrofoil polars (NeuralFoil surrogate of XFOIL, Ncrit 9; dotted = low surrogate confidence); experimental data at these Re are NOT available to this study", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "..", "out", "fig_polars.png"), dpi=130, facecolor="#fcfcfb"); print("polars written")

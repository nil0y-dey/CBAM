"""
Paper figures (PDF) and LaTeX table bodies from Data/ and ../results_extra.

Run from paper/code: python3 make_figures_tables.py [path/to/repo]
"""
import math
import os
import sys

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt               # noqa: E402
from matplotlib.lines import Line2D           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
RES = os.path.join(REPO, "Data", "results")
TREES = os.path.join(REPO, "Data", "trees")
PARS = os.path.join(REPO, "Data", "parameters")
EXTRA = os.path.join(HERE, "..", "results_extra")
FIG = os.path.join(HERE, "..", "figures")
TAB = os.path.join(HERE, "..", "tables")
os.makedirs(FIG, exist_ok=True)
os.makedirs(TAB, exist_ok=True)

from cbam_verify import m0                     # noqa: E402

YEARS = list(range(2026, 2035))
TREE_IDS = ["T1", "T2", "T3", "T4"]
SHORT = {"T1": "T1 China steel", "T2": "T2 India steel", "T3": "T3 Türkiye steel", "T4": "T4 China aluminium"}

# style
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
ORD4 = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
TREE_COLOR = dict(zip(TREE_IDS, [C1, C2, C3, C4]))
TREE_MARK = dict(zip(TREE_IDS, ["o", "s", "^", "D"]))
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 7.5, "axes.labelsize": 7.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "grid.linestyle": "-",
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.5,
    "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
    "legend.frameon": False, "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
MS = 4.0          # pt
RING = dict(markeredgecolor="white", markeredgewidth=0.8)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)


# data
m0b = pd.read_csv(os.path.join(RES, "m0_base.csv"))
m0p = pd.read_csv(os.path.join(RES, "m0_plans.csv"))
m1b = pd.read_csv(os.path.join(RES, "m1_base.csv"))
m1s = pd.read_csv(os.path.join(RES, "m1_sweeps.csv"))
m2g = pd.read_csv(os.path.join(RES, "m2_grid.csv"))
nodes = pd.read_csv(os.path.join(TREES, "nodes.csv"))
pol = pd.read_csv(os.path.join(PARS, "policy_parameters.csv"))
prices = pd.read_csv(os.path.join(PARS, "price_scenarios.csv"))
pm0 = pd.read_csv(os.path.join(EXTRA, "protocol_m0.csv"))            # make_extra_results.py
pm1 = pd.read_csv(os.path.join(EXTRA, "protocol_m1.csv"))
curves = pd.read_csv(os.path.join(EXTRA, "m1_start_curves.csv"))
t2first = pd.read_csv(os.path.join(EXTRA, "t2_yearly_first.csv"))
t2decl = pd.read_csv(os.path.join(EXTRA, "t2_yearly_declared.csv"))
regime = pd.read_csv(os.path.join(EXTRA, "regime_map.csv"))          # regime_map.py
rpoints = pd.read_csv(os.path.join(EXTRA, "regime_points.csv"))
brk = pd.read_csv(os.path.join(EXTRA, "breakeven.csv"))              # m2_deferred_and_breakeven.py
m2d = pd.read_csv(os.path.join(EXTRA, "m2_deferred.csv"))
srun = pd.read_csv(os.path.join(EXTRA, "scal_runtime.csv"))          # scalability.py
ssmall = pd.read_csv(os.path.join(EXTRA, "scal_m2_small.csv"))
slarge = pd.read_csv(os.path.join(EXTRA, "scal_m2_large.csv"))
sprot = pd.read_csv(os.path.join(EXTRA, "scal_protocol.csv"))

# Figure: M0 value by year
fig, axes = plt.subplots(1, 4, figsize=(6.6, 2.05))
for ax, tid in zip(axes, TREE_IDS):
    b = m0b[m0b.tree == tid].sort_values("year")
    p = pm0[pm0.tree == tid].sort_values("year")
    ax.plot(p.year, p.full_info_bound / 1e6, color=MUTED, lw=1.0, ls=(0, (4, 2)), zorder=1)
    ax.plot(p.year, p.value_deferred / 1e6, color=C3, marker="^", ms=MS, zorder=3, **RING)
    ax.plot(b.year, b.value_static / 1e6, color=C2, marker="s", ms=MS * 0.9, zorder=2, **RING)
    ax.plot(b.year, b.value_m0 / 1e6, color=C1, marker="o", ms=MS, zorder=4, **RING)
    ax.set_title(SHORT[tid], loc="left", pad=3)
    ax.set_xticks([2026, 2028, 2030, 2032, 2034])
    ax.set_xticklabels(["2026", "", "2030", "", "2034"])
    ax.set_ylim(bottom=0)
    ax.margins(x=0.04)
axes[0].set_ylabel("Net saving (€ million per year)")
handles = [Line2D([], [], color=C1, marker="o", ms=MS, **RING, label="Commitment (M0)"),
           Line2D([], [], color=C2, marker="s", ms=MS * 0.9, **RING, label="Commitment, no withholding"),
           Line2D([], [], color=C3, marker="^", ms=MS, **RING, label="Deferred declaration"),
           Line2D([], [], color=MUTED, lw=1.0, ls=(0, (4, 2)), label="Full-information bound")]
fig.legend(handles=handles, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.16), handlelength=2.2,
           columnspacing=2.0)
fig.tight_layout(w_pad=0.6)
save(fig, "fig_m0_by_year.pdf")

# Figure: withhold option (Prop. 3), share of M0
from cbam_verify.cases import build_all              # noqa: E402
from cbam_verify.params import load_policy           # noqa: E402

os.chdir(REPO)
policy = load_policy("futures")
trees = build_all()
terms = m0.node_terms(trees["T2"], policy, m0.Setting(year=2030))
dri = terms["DRI"]
k_dri = float(m0p[(m0p.tree == "T2") & (m0p.year == 2030) & (m0p.node == "DRI")].use_if_theta_below.iloc[0])
kstar = dri.mean + dri.cost / (dri.rho * dri.B)


def omega(k, cv):
    va = max(0.0, -dri.cost + dri.rho * dri.B * m0.put(k, dri.mean, cv))
    vs = max(0.0, -dri.cost + dri.rho * dri.B * (k - dri.mean))
    return va - vs


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.35), gridspec_kw={"width_ratios": [1.05, 1]})
ks = np.linspace(2.0, 7.5, 400)
for cv, col in zip([0.10, 0.25, 0.40], [ORD4[0], ORD4[2], ORD4[3]]):
    ax1.plot(ks, [omega(k, cv) / 1e6 for k in ks], color=col, label=f"CV = {cv:.2f}")
ax1.axvline(kstar, color=MUTED, lw=0.7, zorder=0)
ax1.text(kstar - 0.06, 0.95, r"$k^{\ast}$", ha="right", va="center", color=INK2, fontsize=8)
ax1.plot([k_dri], [omega(k_dri, 0.25) / 1e6], marker="o", ms=MS + 1, color=ORD4[2], **RING, zorder=5)
ax1.annotate("DRI plant (T2, 2030)", xy=(k_dri, omega(k_dri, 0.25) / 1e6),
             xytext=(2.05, 2.35), color=INK2, fontsize=6.8, ha="left",
             arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6, shrinkA=2, shrinkB=3))
ax1.set_xlabel(r"Use threshold $k$ (t CO$_2$e per t of DRI)")
ax1.set_ylabel("Value of withholding (€ million)")
ax1.set_title("(a) Value of the withhold option at one node", loc="left", pad=3)
ax1.set_ylim(bottom=0)
ax1.legend(loc="upper right", handlelength=1.6)
for tid in TREE_IDS:
    b = m0b[m0b.tree == tid].sort_values("year")
    share = np.where(b.value_m0 > 0, 100 * b.withhold_option_value / b.value_m0.where(b.value_m0 > 0), np.nan)
    ax2.plot(b.year, share, color=TREE_COLOR[tid], marker=TREE_MARK[tid], ms=MS * (0.85 if tid == "T4" else 1),
             **RING, label=SHORT[tid])
ax2.set_xlabel("Compliance year")
ax2.set_ylabel("Share of the M0 value (%)")
ax2.set_title("(b) Value of withholding as a share of the M0 value", loc="left", pad=3)
ax2.set_ylim(0, 105)
ax2.set_xticks([2026, 2028, 2030, 2032, 2034])
ax2.legend(loc="center left", bbox_to_anchor=(0.0, 0.62), handlelength=1.6)
fig.tight_layout(w_pad=1.2)
save(fig, "fig_withhold.pdf")

# Figure: M1 start-year value
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.35))
for tid in TREE_IDS:
    v = curves[curves.tree == tid].sort_values("start_year").pv_m1.to_numpy(float)
    ax1.plot(YEARS, 100 * v / v.max(), color=TREE_COLOR[tid], marker=TREE_MARK[tid],
             ms=MS * (0.85 if tid == "T4" else 1), **RING, label=SHORT[tid])
ax1.set_ylim(0, 108)
ax1.set_xticks([2026, 2028, 2030, 2032, 2034])
ax1.set_xlabel("Start year of verification at the root")
ax1.set_ylabel("Present value, % of the best start year")
ax1.set_title("(a) M1: value of each start year", loc="left", pad=3)
ax1.legend(loc="lower left", handlelength=1.6)
c2 = curves[curves.tree == "T2"].sort_values("start_year")
s_curve = c2.pv_no_withholding.to_numpy(float) / 1e6
w_curve = c2.pv_m1.to_numpy(float) / 1e6
flex = c2.pv_yearly_choice.to_numpy(float) / 1e6
for curve, col, mk, lab in ((s_curve, C2, "s", "Commitment, no withholding"),
                            (w_curve, C1, "o", "Commitment (M1)"),
                            (flex, C3, "^", "Deferred (yearly choice)")):
    ax2.plot(YEARS, curve, color=col, marker=mk, ms=MS, **RING, label=lab)
    j = int(np.argmax(curve))
    ax2.plot([YEARS[j]], [curve[j]], marker=mk, ms=MS + 2.5, color=col, markeredgecolor=INK, markeredgewidth=0.7,
             zorder=6)
ax2.axhline(0, color=AXIS, lw=0.6)
ax2.set_xticks([2026, 2028, 2030, 2032, 2034])
ax2.set_xlabel("Earliest start year of verification")
ax2.set_ylabel("Present value (€ million, 2026)")
ax2.set_title("(b) T2 India steel under three rules", loc="left", pad=3)
ax2.set_ylim(-5.5, 12.8)
ax2.legend(loc="lower right", handlelength=1.6)
fig.tight_layout(w_pad=1.2)
save(fig, "fig_m1_start.pdf")

# Figure: M2 capacity and deadline
fig, axes = plt.subplots(2, 4, figsize=(6.6, 3.75), sharex=True)
WS = [13, 26, 39]
for col, tid in enumerate(TREE_IDS):
    yr = 2030 if tid == "T2" else 2026
    g = m2g[(m2g.tree == tid) & (m2g.year == yr) & (m2g.duration_scale == 1.0)]
    m0v = float(g.value_m0_no_limits.iloc[0])
    ax = axes[0, col]
    for K, c in zip([1, 2, 3, 4], ORD4):
        gg = g[g.slots == K].sort_values("window_weeks")
        ax.plot(gg.window_weeks, 100 * gg.value_optimal / m0v, color=c, marker="o", ms=MS * 0.9, **RING,
                label=f"K = {K}")
    ax.axhline(100, color=MUTED, lw=0.7, zorder=0)
    ax.set_title(f"{SHORT[tid]} ({yr})", loc="left", pad=3)
    ax.set_ylim(0, 115)
    ax = axes[1, col]
    gg = g[g.slots == 2].sort_values("window_weeks")
    ax.plot(gg.window_weeks, 100 * gg.value_sequential / m0v, color=C2, marker="s", ms=MS * 0.9, **RING,
            label="Sequential rule")
    ax.plot(gg.window_weeks, 100 * gg.value_speculative / m0v, color=C3, marker="^", ms=MS, **RING,
            label="Parallel rule")
    ax.plot(gg.window_weeks, 100 * gg.value_optimal / m0v, color=C1, marker="o", ms=MS * 0.8, lw=1.0, **RING,
            label="Optimal", zorder=5)
    ax.axhline(100, color=MUTED, lw=0.7, zorder=0)
    ax.set_ylim(0, 115)
    ax.set_xticks(WS)
    ax.set_xlabel("Window W (weeks)")
axes[0, 0].set_ylabel("Optimal value, % of M0")
axes[1, 0].set_ylabel("Value with K = 2, % of M0")
axes[0, 3].legend(loc="lower right", handlelength=1.4, title="Slots", title_fontsize=7)
axes[1, 3].legend(loc="lower right", handlelength=1.4)
fig.tight_layout(h_pad=0.8, w_pad=0.5)
save(fig, "fig_m2.pdf")

# Figure: regime map
from matplotlib.colors import BoundaryNorm, ListedColormap     # noqa: E402

A_ = np.sort(regime.a.unique())
B_ = np.sort(regime.b.unique())


def grid(col):
    return regime.pivot(index="b", columns="a", values=col).loc[B_, A_].to_numpy(float)


vd, vc, vs, vm = grid("v_deferred"), grid("v_commit"), grid("v_static"), grid("v_myopic")
with np.errstate(divide="ignore", invalid="ignore"):
    shares = [100 * (1 - vm / vd), 100 * (vc - vs) / vd, 100 * (vd - vc) / vd]
none = vd <= 1e-9
for s in shares:
    s[none] = np.nan
bounds = [0, 1, 5, 10, 25, 50, 100.001]
ramp = ["#f3f7fd", "#c6dbf5", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
cmap = ListedColormap(ramp)
cmap.set_bad("#ffffff")
norm = BoundaryNorm(bounds, cmap.N)
ea = np.concatenate([[A_[0] - 0.0625], (A_[:-1] + A_[1:]) / 2, [A_[-1] + 0.0625]])
eb = np.concatenate([[B_[0] - 0.0625], (B_[:-1] + B_[1:]) / 2, [B_[-1] + 0.0625]])
titles = ["(a) Loss of the myopic rule", "(b) Value of withholding", "(c) Value of deferred declaration"]
fig, axes = plt.subplots(1, 3, figsize=(6.6, 2.55), sharey=True)
for ax, s, title in zip(axes, shares, titles):
    pc = ax.pcolormesh(ea, eb, s, cmap=cmap, norm=norm, shading="flat", rasterized=True)
    ax.contour(A_, B_, np.where(none, 1.0, 0.0), levels=[0.5], colors=[MUTED], linewidths=0.6)
    ax.axhline(0, color=INK2, lw=0.6, ls=(0, (3, 2)))
    ax.axvline(0, color=INK2, lw=0.6, ls=(0, (3, 2)))
    for tid in ("T1", "T2", "T3"):
        p = rpoints[rpoints.tree == tid].set_index("year")
        ax.plot(p.a, p.b, color=INK, lw=0.6, zorder=4)
        ax.plot([p.a[2026]], [p.b[2026]], marker=TREE_MARK[tid], ms=MS + 0.5, color="white", markeredgecolor=INK,
                markeredgewidth=0.8, zorder=5, ls="none")
        ax.plot([p.a[2030]], [p.b[2030]], marker=TREE_MARK[tid], ms=MS + 0.5, color=INK, markeredgecolor="white",
                markeredgewidth=0.8, zorder=5, ls="none")
    ax.set_title(title, loc="left", pad=3)
    ax.set_xlim(ea[0], ea[-1])
    ax.set_ylim(eb[0], eb[-1])
    ax.grid(False)
    ax.set_xticks([-2, 0, 2, 4, 6])
    ax.set_xlabel("Supplier's margin $a$ (SDs)")
axes[0].set_ylabel("Root's unlocking cost $b$ (supplier SDs)")
lab = {"T1": (0.12, 0.10), "T2": (0.15, 0.10), "T3": (0.12, -0.28)}
for tid, (dx, dy) in lab.items():
    p = rpoints[(rpoints.tree == tid) & (rpoints.year == 2026)].iloc[0]
    axes[1].text(p.a + dx, p.b + dy, tid, fontsize=6.5, color=INK, zorder=6)
axes[0].text(-1.85, 2.75, "no value", fontsize=6.3, color=INK2, va="center")
cb = fig.colorbar(pc, ax=axes, orientation="vertical", fraction=0.025, pad=0.015, ticks=bounds[:-1] + [100])
cb.ax.set_yticklabels(["0", "1", "5", "10", "25", "50", "100"])
cb.ax.tick_params(labelsize=6.5, length=2)
cb.set_label("% of the value under deferred declaration", fontsize=6.8, color=INK2)
cb.outline.set_linewidth(0.4)
save(fig, "fig_regime.pdf")

# Tables


def m(x, d=2):
    """EUR -> EUR million."""
    if pd.isna(x):
        return "--"
    v = x / 1e6
    if abs(v) < 0.005:
        return "0.00" if d == 2 else "0"
    return f"{v:,.{d}f}".replace("-", "$-$")


def pct(x, d=1):
    return "--" if pd.isna(x) else f"{x:.{d}f}".replace("-", "$-$")


def write_tab(name, text):
    with open(os.path.join(TAB, name), "w") as f:
        f.write(text)


# policy paths
cf = pol[pol.parameter == "cbam_factor"].set_index("period").value.astype(float)
mk = {2026: 0.10, 2027: 0.20}
lines = []
for y in YEARS:
    pr = prices[prices.year == y].set_index("scenario").price_eur_per_t
    lines.append(f"{y} & {cf[str(y)]:.3f} & {int(100 * mk.get(y, 0.30))}\\% & "
                 f"{'1.00' if y <= 2030 else '1.00$^{a}$'} & {pr['flat']:.2f} & {pr['futures']:.2f} & {pr['high']:.2f} \\\\")
write_tab("tab_policy.tex", "\n".join(lines) + "\n")

# calibrated trees
NAMES = {("T1", "R"): "Re-roller: cold rolling, coating", ("T1", "M1"): "BF-BOF mill A (60\\% of coil)",
         ("T1", "M2"): "BF-BOF mill B (40\\% of coil)",
         ("T2", "R"): "Induction furnace and caster", ("T2", "DRI"): "Coal-based DRI plant",
         ("T2", "PEL"): "Pellet plant", ("T2", "PIG"): "Merchant blast furnace",
         ("T3", "R"): "Re-roller: cold rolling, coating", ("T3", "EAF"): "Scrap-EAF mill (50\\% of coil)",
         ("T3", "BF"): "BF-BOF mill (50\\% of coil)",
         ("T4", "R"): "Fabricator: extrusion", ("T4", "PRI"): "Primary smelter (70\\% of metal)",
         ("T4", "SEC"): "Secondary remelter (30\\% of metal)"}
SHOW_ID = {("T1", "M1"): "A", ("T1", "M2"): "B"}   # not to be confused with models M1, M2
lines = []
prev = None
for _, n in nodes.iterrows():
    if prev is not None and n.tree != prev:
        lines.append("\\addlinespace")
    prev = n.tree
    dr = n.default_route if isinstance(n.default_route, str) else "--"
    lines.append(f"{n.tree} & {SHOW_ID.get((n.tree, n.node), n.node)} & {NAMES[(n.tree, n.node)]} & {n.output_cn8} & {n.a:.3f} & {n.w:.3f} & "
                 f"{n.D_base:.3f} ({dr}) & {n.BMd_2026:.3f} & {n.BMa_2026:.3f} & {n.theta_mean:.2f} & "
                 f"{n.theta_cv:.2f} & {int(n.cost_eur / 1000)} \\\\")
write_tab("tab_trees.tex", "\n".join(lines) + "\n")

# M0 results (2026, 2030)
lines = []
for tid in TREE_IDS:
    for y in (2026, 2030):
        b = m0b[(m0b.tree == tid) & (m0b.year == y)].iloc[0]
        p = pm0[(pm0.tree == tid) & (pm0.year == y)].iloc[0]
        ws = 100 * b.withhold_option_value / b.value_m0 if b.value_m0 > 0 else float("nan")
        nv = b.nodes_verified
        allnodes = set(nodes[nodes.tree == tid].node)
        nv = "all" if isinstance(nv, str) and set(nv.split()) == allnodes else ("none" if nv == "none" else nv)
        lines.append(f"{tid if y == 2026 else ''} & {y} & {b.certs_per_t_defaults:.2f} & {b.certs_per_t_m0:.2f} & "
                     f"{m(b.value_m0)} & {m(b.value_static)} & {m(b.value_myopic)} & {m(b.value_verify_all)} & "
                     f"{m(p.value_deferred)} & {m(p.full_info_bound)} & {pct(ws)} & {nv} \\\\")
    if tid != "T4":
        lines.append("\\addlinespace")
write_tab("tab_m0.tex", "\n".join(lines) + "\n")

# protocols, T2 by year
def shares_of(s):
    return {k: float(v) for k, v in (x.split(":") for x in s.split())}


lines = []
for y in YEARS:
    p = pm0[(pm0.tree == "T2") & (pm0.year == y)].iloc[0]
    gap_c = 100 * (p.full_info_bound - p.value_commitment) / p.full_info_bound
    gap_d = 100 * (p.full_info_bound - p.value_deferred) / p.full_info_bound
    sh = shares_of(p.p_verified_deferred)
    lines.append(f"{y} & {m(p.value_static)} & {m(p.value_commitment)} & {m(p.value_deferred)} & "
                 f"{m(p.full_info_bound)} & {pct(gap_c)} & {pct(gap_d)} & {100 * sh['R']:.0f} \\\\")
write_tab("tab_protocol.tex", "\n".join(lines) + "\n")
others = pm0[pm0.tree != "T2"].copy()
others["gain"] = 100 * (others.value_deferred - others.value_commitment) / others.value_commitment
others["gap_c"] = 100 * (others.full_info_bound - others.value_commitment) / others.full_info_bound
print(f"T1,T3,T4: max deferral gain {others.gain.max():.3f}%  max gap of commitment to full info {others.gap_c.max():.3f}%")
t2p = pm0[pm0.tree == "T2"].copy()
t2p["sim_gap"] = (t2p.value_deferred_sim - t2p.value_deferred_dp) / t2p.deferred_sim_se
print("T2 deferred: simulated policy minus DP value, in standard errors:", t2p.sim_gap.round(2).tolist())

# M1 results
def starts(s):
    parts = dict(x.split(":") for x in s.split())
    ys = set(parts.values())
    return f"{ys.pop()} (all)" if len(ys) == 1 else ", ".join(f"{k} {v}" for k, v in parts.items())


lines = []
for tid in TREE_IDS:
    b = m1b[m1b.tree == tid].iloc[0]
    p = pm1[pm1.tree == tid].iloc[0]
    lines.append(f"{tid} & {m(b.pv_m1)} & {starts(b.start_years_m1)} & {m(b.pv_now_or_never)} & "
                 f"{m(b.pv_no_withholding)} & {m(b.pv_start_all_2026)} & {m(b.value_of_waiting)} & "
                 f"{m(b.value_of_withholding)} & {m(p.pv_yearly_choice)} ({int(p.first_verification_year_yearly_choice)}) \\\\")
write_tab("tab_m1.tex", "\n".join(lines) + "\n")

# M2 summary
lines = []
for tid in TREE_IDS:
    yr = 2030 if tid == "T2" else 2026
    g = m2g[(m2g.tree == tid) & (m2g.year == yr)]

    def cell(K, W, s=1.0, col="pct_of_m0"):
        return g[(g.slots == K) & (g.window_weeks == W) & (g.duration_scale == s)][col].iloc[0]
    lines.append(f"{tid} ({yr}) & {pct(cell(1, 39))} & {pct(cell(2, 39))} & {pct(cell(4, 39))} & {pct(cell(2, 26))} & "
                 f"{pct(cell(2, 13))} & {pct(cell(4, 13))} & {pct(cell(2, 13, col='gap_sequential_pct'))} & "
                 f"{pct(cell(2, 13, col='gap_speculative_pct'))} & {pct(cell(2, 39, col='scarcity_cost_eur_per_t'), 2)} & "
                 f"{pct(cell(2, 13, col='scarcity_cost_eur_per_t'), 2)} \\\\")
write_tab("tab_m2.tex", "\n".join(lines) + "\n")
lines = []
for tid in TREE_IDS:
    yr = 2030 if tid == "T2" else 2026
    g = m2g[(m2g.tree == tid) & (m2g.year == yr) & (m2g.slots == 2) & (m2g.window_weeks == 39)].set_index("duration_scale")
    ws = g.wasted_spend.loc[1.0] / 1000
    lines.append(f"{tid} ({yr}) & " + " & ".join(pct(g.pct_of_m0.loc[s]) for s in (0.5, 1.0, 1.5, 2.0))
                 + f" & {ws:.0f} & {g.expected_spend.loc[1.0] / 1000:.0f} \\\\")
write_tab("tab_m2_durations.tex", "\n".join(lines) + "\n")

# M1 sensitivity
LAB = {"discount_rate": "Discount rate", "setup_cost_ratio": "Set-up cost / annual cost",
       "price_scenario": "Price path", "supplier_cv": "Supplier CV", "volume_t": "Volume (kt per year)",
       "success_probability": "Success probability $\\rho$"}
order = ["discount_rate", "setup_cost_ratio", "price_scenario", "supplier_cv", "success_probability", "volume_t"]
lines = []
for fac in order:
    sub = m1s[m1s.factor == fac]
    if fac == "volume_t":
        for lv_steel, lv_al in zip([5000, 10000, 25000, 50000, 100000, 250000], [1000, 2000, 5000, 10000, 25000, 50000]):
            row = [f"{int(lv_steel / 1000)} ({lv_al / 1000:g})"]
            for tid in TREE_IDS:
                lv = lv_al if tid == "T4" else lv_steel
                r = sub[(sub.tree == tid) & (sub.level.astype(float) == lv)].iloc[0]
                row.append(m(r.pv_m1))
                if tid == "T2":
                    row.append(r.start_years.split()[0].split(":")[1])
            lines.append((LAB[fac] if lv_steel == 5000 else "") + " & " + " & ".join(row) + " \\\\")
    else:
        levels = list(dict.fromkeys(sub.level))
        FMT = {"discount_rate": "{:.2f}", "setup_cost_ratio": "{:.1f}", "supplier_cv": "{:.2f}",
               "success_probability": "{:.1f}"}
        for k, lv in enumerate(levels):
            row = [FMT[fac].format(float(lv)) if fac in FMT else str(lv)]
            for tid in TREE_IDS:
                r = sub[(sub.tree == tid) & (sub.level == lv)].iloc[0]
                row.append(m(r.pv_m1))
                if tid == "T2":
                    row.append(r.start_years.split()[0].split(":")[1])
            lines.append((LAB[fac] if k == 0 else "") + " & " + " & ".join(row) + " \\\\")
    lines.append("\\addlinespace")
write_tab("tab_m1_sensitivity.tex", "\n".join(lines[:-1]) + "\n")

# T2, yearly choice
COLS = ["R", "DRI", "PIG", "PEL"]
dec = t2decl.set_index(t2decl.year.astype(str))
lines = []
for _, r in t2first.iterrows():
    y = str(r.year)
    left = " & ".join(f"{100 * r[c]:.0f}" for c in COLS)
    right = " & ".join(f"{100 * dec.loc[y, c]:.0f}" for c in COLS) if y in dec.index else " & ".join(["--"] * 4)
    lines.append(f"{'Never' if y == 'never' else y} & {left} & {right} \\\\")
write_tab("tab_t2_yearly.tex", "\n".join(lines) + "\n")

# break-evens
lines = []
for _, r in brk.iterrows():
    if r.value_m0 <= 0:
        lines.append(f"{r.tree} & {r.year} & 0.00 & none & -- & -- & -- \\\\")
        continue
    nv = set(r.verified.split())
    allnodes = set(nodes[nodes.tree == r.tree].node)
    lines.append(f"{r.tree if r.year == 2026 else ''} & {r.year} & {m(r.value_m0)} & {'all' if nv == allnodes else r.verified} & "
                 f"{r.cost_multiplier_plan_changes:.1f} & {r.cost_multiplier_value_zero:.1f} & "
                 f"{r.min_volume_t_value_positive:,.0f} \\\\")
write_tab("tab_breakeven.tex", "\n".join(lines) + "\n")

# M2, deferred
lines = []
for tid in TREE_IDS:
    g = m2d[m2d.tree == tid]
    yr = int(g.year.iloc[0])

    def cell(K, W):
        return g[(g.slots == K) & (g.window_weeks == W)].pct_of_deferred.iloc[0]
    lines.append(f"{tid} ({yr}) & {m(g.deferred_value_no_limits.iloc[0])} & " +
                 " & ".join(pct(cell(K, W)) for K, W in ((1, 39), (2, 39), (4, 39), (2, 26), (2, 13), (4, 13))) + " \\\\")
write_tab("tab_m2_deferred.tex", "\n".join(lines) + "\n")

# scalability, small trees
q = ssmall[ssmall.value_optimal > 0].copy()
q["spec"] = 100 * (q.value_optimal - q.value_speculative) / q.value_optimal
q["seq"] = 100 * (q.value_optimal - q.value_sequential) / q.value_optimal
lines = []
for W in (13, 26, 39, None):
    s = q if W is None else q[q.window == W]
    lab = "All" if W is None else str(W)
    lines.append(f"{lab} & {len(s)} & " + " & ".join(f"{f(s[c]):.1f}" for c in ("spec", "seq")
                                                    for f in (np.median, lambda x: np.quantile(x, 0.9), np.mean)) + " \\\\")
write_tab("tab_scal.tex", "\n".join(lines) + "\n")
L = slarge.copy()
L["spec"] = 100 * L.value_speculative / L.value_m0
L["seq"] = 100 * L.value_sequential / L.value_m0
print("large random trees, % of M0 (mean over replications):")
print(L.groupby(["nodes", "slots", "window"])[["spec", "seq"]].mean().round(1).to_string())
P = sprot[sprot.value_commitment > 0].copy()
P["gain"] = 100 * (P.deferred_lower_bound - P.value_commitment) / P.value_commitment
P["gap_fi"] = 100 * (P.full_info_bound - P.value_commitment) / P.full_info_bound
print("random trees, deferral gain over commitment and gap of commitment to full info (%):")
print(P.groupby("nodes")[["gain", "gap_fi"]].describe(percentiles=[0.5, 0.9]).round(2).to_string())
print("run times (ms):")
print(srun.to_string(index=False))
print("figures:", sorted(os.listdir(FIG)))
print("tables:", sorted(os.listdir(TAB)))

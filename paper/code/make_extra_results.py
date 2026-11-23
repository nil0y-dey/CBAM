"""
Extra results for the paper -> ../results_extra:
protocol_m0.csv, protocol_m1.csv, m1_start_curves.csv, t2_yearly_first.csv,
t2_yearly_declared.csv, withhold_distance.csv.
Deferred DP: 40 bins (one year), 32 bins (yearly choice).

Run from paper/code: python3 make_extra_results.py [path/to/repo]
"""
import csv
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, HERE)
os.chdir(REPO)

from cbam_verify import m0, m1                     # noqa: E402
from cbam_verify.cases import build_all            # noqa: E402
from cbam_verify.params import load_policy, YEARS  # noqa: E402
import deferred as D                               # noqa: E402

OUT = os.path.join(HERE, "..", "results_extra")
os.makedirs(OUT, exist_ok=True)
POLICY = load_policy("futures")
TREES = build_all()
M_YEAR, M_YEARS = 40, 32


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# 1. one year
rows = []
for tid, tree in TREES.items():
    for y in YEARS:
        terms = m0.node_terms(tree, POLICY, m0.Setting(year=y))
        tr = D.Tree.from_terms(terms)
        v_c = m0.adaptive_plan(terms).value
        v_s = m0.static_plan(terms).value
        v_dp, sol = D.solve_year(tr, M_YEAR)
        v_sim, se_sim, p_ver, first = D.simulate_year(tr, sol, n_draws=40_000, rng=np.random.default_rng(1000 + y))
        v_fi, se_fi = D.full_info_value(tr, n_draws=400_000, rng=np.random.default_rng(2000 + y))
        v_d = max(v_dp, v_c)          # V_D >= V_C
        first_node = "none" if first[0] > 0.5 else tr.ids[int(np.argmax(first[1:]))]
        rows.append([tid, y, round(v_s), round(v_c), round(v_dp), round(v_d), round(v_sim), round(se_sim),
                     round(v_fi), round(se_fi), first_node,
                     " ".join(f"{i}:{p:.3f}" for i, p in zip(tr.ids, p_ver))])
write("protocol_m0.csv",
      ["tree", "year", "value_static", "value_commitment", "value_deferred_dp", "value_deferred",
       "value_deferred_sim", "deferred_sim_se", "full_info_bound", "full_info_se", "first_verified_deferred",
       "p_verified_deferred"], rows)

# 2. several years
d = 1.0 / 1.08


def year_arrays(tree):
    st = m1.M1Setting()
    yt = m1.yearly_terms(tree, POLICY, st)
    tr = D.Tree.from_terms(yt[YEARS[0]])
    beta = np.array([[yt[y][i].B for i in tr.ids] for y in YEARS])
    eta = np.array([[yt[y][i].K for i in tr.ids] for y in YEARS])
    cost = np.array([[yt[y][i].cost for i in tr.ids] for y in YEARS])
    return tr, beta, eta, cost, cost[0] * st.setup_ratio


rows, curve_rows = [], []
for tid, tree in TREES.items():
    p_w = m1.solve(tree, POLICY, m1.M1Setting())
    p_s = m1.solve(tree, POLICY, m1.M1Setting(withhold=False))
    root = [i for i, n in tree.nodes.items() if not n.parent][0]
    tr, beta, eta, cost, setup = year_arrays(tree)
    v_yc, sol = D.solve_years(tr, beta, eta, cost, setup, d, M=M_YEARS)
    v_sim, se, first_year, declared = D.simulate_years(tr, sol, beta, eta, cost, setup, d, n_draws=20_000,
                                                       rng=np.random.default_rng(77))
    # first year anything is verified
    any_first = np.where((first_year >= 0).any(axis=1), np.where(first_year >= 0, first_year, 99).min(axis=1), -1)
    start_mode = YEARS[int(np.bincount(any_first[any_first >= 0]).argmax())] if (any_first >= 0).any() else None
    rows.append([tid, round(p_s.value), p_s.start[root], round(p_w.value), p_w.start[root], round(v_yc), round(v_sim),
                 round(se), start_mode])
    # value if start >= s
    for k, s in enumerate(YEARS):
        v_s_curve = d ** (s - YEARS[0]) * p_s.W[root][s]
        v_w_curve = d ** (s - YEARS[0]) * p_w.W[root][s]
        v_yc_s, _ = D.solve_years(tr, beta, eta, cost, setup, d, M=M_YEARS, earliest=k)
        curve_rows.append([tid, s, round(v_s_curve), round(v_w_curve), round(v_yc_s)])
    if tid == "T2":
        fr = []
        for t, y in enumerate(YEARS):
            fr.append([y] + [round(float((first_year[:, j] == t).mean()), 3) for j in range(tr.n)])
        fr.append(["never"] + [round(float((first_year[:, j] < 0).mean()), 3) for j in range(tr.n)])
        write("t2_yearly_first.csv", ["year"] + tr.ids, fr)
        write("t2_yearly_declared.csv", ["year"] + tr.ids,
              [[y] + [round(float(declared[t, j]), 3) for j in range(tr.n)] for t, y in enumerate(YEARS)])
write("protocol_m1.csv",
      ["tree", "pv_no_withholding", "start_no_withholding", "pv_m1", "start_m1", "pv_yearly_choice",
       "pv_yearly_choice_sim", "yearly_choice_sim_se", "first_verification_year_yearly_choice"], rows)
write("m1_start_curves.csv", ["tree", "start_year", "pv_no_withholding", "pv_m1", "pv_yearly_choice"], curve_rows)

# 3. distance of use thresholds from k* (Prop. 3)
rows = []
for tid, tree in TREES.items():
    for y in YEARS:
        terms = m0.node_terms(tree, POLICY, m0.Setting(year=y))
        plan = m0.adaptive_plan(terms)
        for i, t in terms.items():
            k = plan.threshold[i]
            kstar = t.mean + t.cost / (t.rho * t.B)
            sd = t.mean * t.cv
            rows.append([tid, y, i, plan.attempt[i], round(k, 4), round(kstar, 4), round(sd, 4),
                         round((k - kstar) / sd, 2) if sd > 0 else ""])
write("withhold_distance.csv",
      ["tree", "year", "node", "verified", "threshold_k", "static_breakeven_kstar", "sd_theta", "z"], rows)
print("written to", os.path.abspath(OUT))

"""
Regime map: root + one supplier. Units: supplier beta = mean = 1, CV 0.25, sigma = 0.25.
  a: supplier margin, eta_s = mu_s + a * sigma
  b: root's own gain = -b * beta_s * sigma (theta_r known)
  c = kappa * beta_s * sigma for both nodes, rho = 0.9
Values: myopic, static, M0, deferred (DP, 40 bins), full info.
Calibrated trees placed by merging suppliers:
  a = E[supplier gain] / SD, b = -(root's own gain) / SD.
"""
import csv
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deferred as D                                    # noqa: E402

V_CV, RHO, KAPPA, M = 0.25, 0.9, 0.02, 40
SIG = V_CV


def chain(a, b, kappa=KAPPA):
    beta = [1.0, 1.0]
    eta = [1.0 - b * SIG, 1.0 + a * SIG]               # theta_r = 1 known
    c = kappa * SIG
    return D.Tree(["root", "supplier"], [-1, 0], beta, eta, [1.0, 1.0], [0.0, V_CV], [c, c], [RHO, RHO])


def values(a, b, kappa=KAPPA):
    tr = chain(a, b, kappa)
    c = tr.cost
    g_r = tr.beta[0] * (tr.eta[0] - 1.0)
    mean_gain_s = tr.beta[1] * (tr.eta[1] - 1.0)
    # myopic: each node on its own gain, use all
    sup_my = max(0.0, -c[1] + RHO * mean_gain_s)
    v_my = -c[0] + RHO * (g_r + sup_my) if -c[0] + RHO * g_r > 0 else 0.0
    v_my = max(0.0, v_my)
    # static commitment
    vs_s = max(0.0, -c[1] + RHO * mean_gain_s)
    v_static = max(0.0, -c[0] + RHO * (g_r + vs_s))
    v_c = D.commitment_value(tr)
    v_d, _ = D.solve_year(tr, M)
    v_d = max(v_d, v_c)                                 # V_D >= V_C
    return v_my, v_static, v_c, v_d


def tree_points(repo):
    sys.path.insert(0, os.path.join(repo, "src"))
    cwd = os.getcwd()
    os.chdir(repo)
    from cbam_verify import m0
    from cbam_verify.cases import build_all
    from cbam_verify.params import load_policy
    pol, trees = load_policy("futures"), build_all()
    out = []
    for tid, tree in trees.items():
        for y in (2026, 2030):
            terms = m0.node_terms(tree, pol, m0.Setting(year=y))
            r = m0._root(terms)
            sup = [t for i, t in terms.items() if i != r]
            mean = sum(t.B * (t.K - t.mean) for t in sup)
            sd = math.sqrt(sum((t.B * t.mean * t.cv) ** 2 for t in sup))
            root_gain = terms[r].B * (terms[r].K - terms[r].mean)
            out.append((tid, y, mean / sd, -root_gain / sd))
    os.chdir(cwd)
    return out


def main(repo, out_dir):
    A = np.round(np.linspace(-2.0, 7.0, 73), 4)
    Bv = np.round(np.linspace(-1.0, 3.0, 33), 4)
    rows = []
    for b in Bv:
        for a in A:
            v_my, v_s, v_c, v_d = values(a, b)
            rows.append([a, b, v_my, v_s, v_c, v_d])
    with open(os.path.join(out_dir, "regime_map.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["a", "b", "v_myopic", "v_static", "v_commit", "v_deferred"])
        w.writerows(rows)
    with open(os.path.join(out_dir, "regime_points.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tree", "year", "a", "b"])
        for p in tree_points(repo):
            w.writerow([p[0], p[1], round(p[2], 3), round(p[3], 3)])


if __name__ == "__main__":
    repo = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", ".."))
    out = os.path.join(HERE, "..", "results_extra")
    os.makedirs(out, exist_ok=True)
    main(repo, out)
    print("written", os.path.abspath(out))

"""
1. M2 under deferred declaration: fixed priority order, start as slots free up, skip nodes
   behind a failure, declare the best rooted set finished by week W. Best order over all
   permutations = lower bound.
2. Break-evens (2026, 2030): cost multiplier at which the M0 plan changes and at which it
   stops paying; smallest volume at which verification pays.
"""
import csv
import itertools
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, HERE)
os.chdir(REPO)
from cbam_verify import m0                                    # noqa: E402
from cbam_verify.cases import build_all                      # noqa: E402
from cbam_verify.params import load_policy, load_assumptions  # noqa: E402
import deferred as D                                          # noqa: E402

OUT = os.path.join(HERE, "..", "results_extra")
POL, TREES, ASM = load_policy("futures"), build_all(), load_assumptions()


def mean_weeks(tree, ids):
    return np.array([ASM[f"verification_weeks_{tree.nodes[i].size}"]["central"] for i in ids], float)


def simulate_fixed_order(tr, order, K, W, mweeks, draws):
    """Mean net saving of a fixed-priority rule."""
    th, ok, dur = draws
    n, N = tr.n, th.shape[0]
    anc = [tr.ancestors(j) for j in range(n)]
    total = np.zeros(N)
    for d in range(N):
        finish = {}                 # node -> finish week
        running = []                # (finish_week, node)
        started = set()
        t = 0
        free = K
        queue = list(order)
        dead = set()
        succ = set()
        cost = 0.0
        while t < W:
            # finished by week t
            for fw, j in sorted(running):
                if fw <= t:
                    running.remove((fw, j))
                    free += 1
                    if ok[d, j]:
                        succ.add(j)
                    else:
                        dead.add(j)
            for j in list(queue):
                if free == 0:
                    break
                if any(a in dead for a in anc[j]):
                    queue.remove(j)
                    continue
                queue.remove(j)
                started.add(j)
                cost += tr.cost[j]
                running.append((t + dur[d, j], j))
                free -= 1
            if not running and not queue:
                break
            t = min([fw for fw, _ in running] + [W]) if running else W
        for fw, j in running:          # finishing at W still counts
            if fw <= W and ok[d, j]:
                succ.add(j)
        best = np.zeros(n)
        for i in reversed(range(n)):
            if i in succ:
                best[i] = max(0.0, tr.beta[i] * (tr.eta[i] - th[d, i]) + sum(best[c] for c in tr.children[i]))
        total[d] = best[0] - cost
    return float(total.mean())


def draws_for(tr, mweeks, n_draws, rng):
    n = tr.n
    th = np.empty((n_draws, n))
    for i in range(n):
        s = math.sqrt(math.log(1 + tr.cv[i] ** 2)) if tr.cv[i] > 0 else 0.0
        th[:, i] = np.exp(rng.normal(math.log(tr.mean[i]) - s * s / 2, s, n_draws)) if s > 0 else tr.mean[i]
    ok = rng.random((n_draws, n)) < tr.rho
    dur = rng.geometric(1.0 / mweeks, size=(n_draws, n))
    return th, ok, dur


def m2_deferred(n_draws=6000):
    rows = []
    rng = np.random.default_rng(31)
    settings = [(1, 39), (2, 39), (4, 39), (2, 26), (2, 13), (4, 13)]
    for tid, tree in TREES.items():
        year = 2030 if tid == "T2" else 2026
        terms = m0.node_terms(tree, POL, m0.Setting(year=year))
        tr = D.Tree.from_terms(terms)
        mw = mean_weeks(tree, tr.ids)
        v_d, _ = D.solve_year(tr, 40)
        v_d = max(v_d, D.commitment_value(tr))
        dr = draws_for(tr, mw, n_draws, rng)
        for K, W in settings:
            best_v, best_o = -math.inf, None
            for order in itertools.permutations(range(tr.n)):
                v = simulate_fixed_order(tr, order, K, W, mw, dr)
                if v > best_v:
                    best_v, best_o = v, order
            rows.append([tid, year, K, W, round(v_d), round(best_v), round(100 * best_v / v_d, 1),
                         " ".join(tr.ids[k] for k in best_o)])
            print(rows[-1], flush=True)
    with open(os.path.join(OUT, "m2_deferred.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tree", "year", "slots", "window_weeks", "deferred_value_no_limits", "best_fixed_order_value",
                    "pct_of_deferred", "best_order"])
        w.writerows(rows)


def breakeven():
    rows = []
    for tid, tree in TREES.items():
        for year in (2026, 2030):
            def plan(scale=1.0, Q=None):
                terms = m0.node_terms(tree, POL, m0.Setting(year=year, cost_scale=scale, Q=Q))
                p = m0.adaptive_plan(terms)
                return p.value, frozenset(i for i, a in p.attempt.items() if a)
            v1, s1 = plan()
            # cost multipliers: plan changes / value hits zero
            def first_change():
                lo, hi = 1.0, 2.0
                while plan(hi)[1] == s1 and hi < 1e4:
                    lo, hi = hi, hi * 2
                for _ in range(40):
                    mid = math.sqrt(lo * hi)
                    if plan(mid)[1] == s1:
                        lo = mid
                    else:
                        hi = mid
                return hi
            def zero_value():
                lo, hi = 1.0, 2.0
                while plan(hi)[0] > 0 and hi < 1e5:
                    lo, hi = hi, hi * 2
                for _ in range(40):
                    mid = math.sqrt(lo * hi)
                    if plan(mid)[0] > 0:
                        lo = mid
                    else:
                        hi = mid
                return hi
            def min_volume():
                lo, hi = 1.0, tree.Q
                if plan(Q=hi)[0] <= 0:
                    return float("nan")
                for _ in range(60):
                    mid = math.sqrt(lo * hi)
                    if plan(Q=mid)[0] > 0:
                        hi = mid
                    else:
                        lo = mid
                return hi
            if v1 > 0:
                rows.append([tid, year, round(v1), " ".join(sorted(s1)), round(first_change(), 2),
                             round(zero_value(), 1), round(min_volume())])
            else:
                rows.append([tid, year, 0, "none", "", "", ""])
            print(rows[-1], flush=True)
    with open(os.path.join(OUT, "breakeven.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tree", "year", "value_m0", "verified", "cost_multiplier_plan_changes",
                    "cost_multiplier_value_zero", "min_volume_t_value_positive"])
        w.writerows(rows)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    breakeven()
    m2_deferred()

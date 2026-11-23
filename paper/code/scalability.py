"""
Random-tree tests.

Trees: node 0 = exporter; others pick a customer among nodes of depth <= 3. a ~ U(0.3, 1.5);
beta = 5e6 * w; supplier mu ~ U(0.05, 3.0), CV ~ U(0.15, 0.35), eta = mu + z mu CV,
z ~ N(1, 1.5); root eta - mu ~ N(0, 0.4), CV 0.10. Size classes p = .3/.4/.3:
EUR 10k/30k/100k, 6/8/12 weeks. rho = 0.9. M1: eta drifts by N(0, 0.3) over 2026-34,
futures prices.

Out (../results_extra): scal_runtime.csv, scal_m2_small.csv (4-6 nodes, exact),
scal_m2_large.csv (20, 50 nodes, simulated), scal_protocol.csv (5-30 nodes).
'speculative' = parallel rule in the paper.
"""
import csv
import itertools
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, HERE)
from cbam_verify import m0, m2                    # noqa: E402
import deferred as D                              # noqa: E402

OUT = os.path.join(HERE, "..", "results_extra")
YEARS = list(range(2026, 2035))
PRICE = [77.65, 90.5, 93.5, 96.5, 99.5, 99.5, 99.5, 99.5, 99.5]
SIZES = [(10_000, 6.0), (30_000, 8.0), (100_000, 12.0)]


def random_tree(n, rng):
    parent, depth = [None], [0]
    for k in range(1, n):
        cand = [i for i in range(k) if depth[i] <= 3]
        p = int(rng.choice(cand))
        parent.append(p)
        depth.append(depth[p] + 1)
    a = np.ones(n)
    a[1:] = rng.uniform(0.3, 1.5, n - 1)
    w = np.ones(n)
    for k in range(1, n):
        w[k] = w[parent[k]] * a[k]
    mu = np.empty(n); cv = np.empty(n); eta = np.empty(n)
    mu[0] = rng.uniform(0.02, 0.3); cv[0] = 0.10; eta[0] = mu[0] + rng.normal(0, 0.4)
    mu[1:] = rng.uniform(0.05, 3.0, n - 1)
    cv[1:] = rng.uniform(0.15, 0.35, n - 1)
    eta[1:] = mu[1:] + rng.normal(1.0, 1.5, n - 1) * mu[1:] * cv[1:]
    cls = rng.choice(3, size=n, p=[0.3, 0.4, 0.3])
    cost = np.array([SIZES[c][0] for c in cls], float)
    weeks = np.array([SIZES[c][1] for c in cls], float)
    ids = [f"n{k}" for k in range(n)]
    terms = {}
    for k in range(n):
        ch = [ids[j] for j in range(n) if parent[j] == k]
        terms[ids[k]] = m0.Terms(ids[k], ids[parent[k]] if parent[k] is not None else "", ch, 5e6 * w[k], eta[k],
                                 mu[k], cv[k], cost[k], 0.9, w[k])
    return terms, dict(zip(ids, weeks)), rng.normal(0, 0.3, n)


# M1 on arbitrary yearly terms (same recursion as cbam_verify.m1.solve)
def m1_solve_terms(yt, setup_ratio=1.0, delta=1 / 1.08):
    base = yt[YEARS[0]]
    root = m0._root(base)
    order = m0._post_order(base, root)
    W = {}
    for i in order:
        W[i] = {}
        for s in YEARS:
            later = [t for t in YEARS if t >= s]
            Bbar = sum(delta ** (t - s) * yt[t][i].B for t in later)
            A = sum(delta ** (t - s) * yt[t][i].B * yt[t][i].K for t in later)
            A -= sum(delta ** (t - s) * yt[t][i].cost for t in later if t > s)
            A += sum(max([0.0] + [delta ** (s2 - s) * W[j][s2] for s2 in YEARS if s2 >= s]) for j in base[i].children)
            W[i][s] = -yt[s][i].cost * (1 + setup_ratio) + yt[s][i].rho * Bbar * m0.put(A / Bbar, yt[s][i].mean, yt[s][i].cv)
    return max([0.0] + [delta ** (s - YEARS[0]) * W[root][s] for s in YEARS])


def yearly(terms, drift):
    yt = {}
    for k, y in enumerate(YEARS):
        yt[y] = {}
        for j, (i, t) in enumerate(terms.items()):
            yt[y][i] = m0.Terms(t.id, t.parent, t.children, t.B * PRICE[k] / 100.0,
                                t.K + drift[j] * (y - 2026) / 8, t.mean, t.cv, t.cost, t.rho, t.w)
    return yt


def timeit(f, reps=3):
    best = math.inf
    for _ in range(reps):
        t0 = time.perf_counter()
        f()
        best = min(best, time.perf_counter() - t0)
    return best


def runtime(rng):
    rows = []
    for n in (10, 50, 100, 500, 1000):
        terms, _, drift = random_tree(n, rng)
        t_m0 = timeit(lambda: m0.adaptive_plan(terms))
        yt = yearly(terms, drift)
        t_m1 = timeit(lambda: m1_solve_terms(yt), reps=1) if n <= 500 else float("nan")
        rows.append(["M0", n, round(1000 * t_m0, 2)])
        if not math.isnan(t_m1):
            rows.append(["M1", n, round(1000 * t_m1, 2)])
    for n in (3, 4, 5, 6, 7, 8):
        terms, weeks, _ = random_tree(n, rng)
        tr = D.Tree.from_terms(terms)
        if n <= 6:
            M = 20 if n <= 5 else 10
            rows.append([f"Deferred DP ({M} bins)", n, round(1000 * timeit(lambda: D.solve_year(tr, M), reps=1), 1)])
        prob = m2.Problem(terms, None, m2.M2Setting(slots=2, weeks=26, durations=weeks), None)
        rows.append(["M2 exact (K=2, W=26)", n, round(1000 * timeit(lambda: m2.Solver(prob).value(), reps=1), 1)])
        print(rows[-1], flush=True)
    return rows


def m2_small(rng, n_inst=120):
    rows = []
    for k in range(n_inst):
        n = [4, 5, 6][k % 3]
        K = int(rng.choice([1, 2, 3]))
        W = int(rng.choice([13, 26, 39]))
        terms, weeks, _ = random_tree(n, rng)
        v_m0 = m0.adaptive_plan(terms).value
        if v_m0 <= 0:
            continue
        prob = m2.Problem(terms, None, m2.M2Setting(slots=K, weeks=W, durations=weeks), None)
        v_opt = m2.Solver(prob).value()
        v_seq = m2.Solver(prob, m2.sequential_policy(prob)).value()
        v_spec = m2.Solver(prob, m2.speculative_policy(prob)).value()
        rows.append([k, n, K, W, round(v_m0), round(v_opt), round(v_seq), round(v_spec)])
    return rows


def simulate_index(terms, weeks, K, W, speculative, n_draws, rng):
    """Index rule with M0 thresholds, commitment. Mean net saving."""
    plan = m0.adaptive_plan(terms)
    ids = list(terms)
    idx = {i: k for k, i in enumerate(ids)}
    n = len(ids)
    par = [idx[terms[i].parent] if terms[i].parent else -1 for i in ids]
    keep = [plan.attempt[i] for i in ids]
    prio = sorted([k for k in range(n) if keep[k]], key=lambda k: -plan.node_value[ids[k]] / weeks[ids[k]])
    thr = [plan.threshold[i] for i in ids]
    B = np.array([terms[i].B for i in ids]); Kt = np.array([terms[i].K for i in ids])
    c = np.array([terms[i].cost for i in ids]); rho = np.array([terms[i].rho for i in ids])
    q = np.array([1.0 / weeks[i] for i in ids])
    mu = np.array([terms[i].mean for i in ids]); cv = np.array([terms[i].cv for i in ids])
    s = np.sqrt(np.log(1 + cv ** 2))
    tot = np.zeros(n_draws)
    for d in range(n_draws):
        th = np.exp(rng.normal(np.log(mu) - s * s / 2, s))
        st = np.zeros(n, int)          # 0 idle 1 running 2 waiting 3 in use 4 dead
        val = 0.0

        def kill(k):
            stack = [k]
            while stack:
                j = stack.pop()
                st[j] = 4
                stack.extend(x for x in range(n) if par[x] == j)

        for t in range(W + 1):
            changed = True
            while changed:                       # open results
                changed = False
                for k in range(n):
                    if st[k] == 2 and (par[k] < 0 or st[par[k]] == 3):
                        if th[k] < thr[k]:
                            st[k] = 3
                            val += B[k] * (Kt[k] - th[k])
                        else:
                            kill(k)
                        changed = True
            if t == W:
                break
            free = K - int((st == 1).sum())
            for k in prio:
                if free == 0:
                    break
                if st[k] != 0:
                    continue
                if par[k] >= 0 and st[par[k]] == 4:
                    continue
                if not speculative and not (par[k] < 0 or st[par[k]] == 3):
                    continue
                st[k] = 1
                val -= c[k]
                free -= 1
            run = np.where(st == 1)[0]
            done = run[rng.random(len(run)) < q[run]]
            for k in done:
                if rng.random() < rho[k]:
                    st[k] = 2
                else:
                    kill(k)
        tot[d] = val
    return float(tot.mean()), float(tot.std(ddof=1) / math.sqrt(n_draws))


def m2_large(rng):
    rows = []
    for n in (20, 50):
        for rep in range(5):
            terms, weeks, _ = random_tree(n, rng)
            v_m0 = m0.adaptive_plan(terms).value
            if v_m0 <= 0:
                continue
            for K, W in ((2, 39), (4, 39), (2, 13), (4, 13), (8, 13)):
                t0 = time.perf_counter()
                v_spec, se = simulate_index(terms, weeks, K, W, True, 1500, rng)
                t_spec = time.perf_counter() - t0
                v_seq, _ = simulate_index(terms, weeks, K, W, False, 1500, rng)
                rows.append([n, rep, K, W, round(v_m0), round(v_seq), round(v_spec), round(se),
                             round(1000 * t_spec / 1500, 3)])
        print("large", n, flush=True)
    return rows


def protocol_random(rng, n_inst=60):
    rows = []
    for k in range(n_inst):
        n = [5, 10, 20, 30][k % 4]
        terms, _, _ = random_tree(n, rng)
        tr = D.Tree.from_terms(terms)
        plan = m0.adaptive_plan(terms)
        v_c = plan.value
        N = 20000
        th = np.empty((N, n))
        for i in range(n):
            s = math.sqrt(math.log(1 + tr.cv[i] ** 2))
            th[:, i] = np.exp(rng.normal(math.log(tr.mean[i]) - s * s / 2, s, N))
        ok = rng.random((N, n)) < tr.rho
        gain = tr.beta * (tr.eta - th)
        # M0 plan, declare at the end
        reach = np.zeros((N, n), bool); verok = np.zeros((N, n), bool); cost = np.zeros(N)
        thr = np.array([plan.threshold[i] for i in tr.ids]); att = np.array([plan.attempt[i] for i in tr.ids])
        used = np.zeros((N, n), bool)
        for i in range(n):
            r = np.ones(N, bool) if tr.parent[i] < 0 else used[:, tr.parent[i]]
            if att[i]:
                cost += tr.cost[i] * r
                verok[:, i] = r & ok[:, i]
                used[:, i] = verok[:, i] & (th[:, i] < thr[i])
        best = np.zeros((N, n))
        for i in reversed(range(n)):
            inner = gain[:, i] + sum(best[:, j] for j in tr.children[i])
            best[:, i] = np.where(verok[:, i], np.maximum(0.0, inner), 0.0)
        v_d1 = float((best[:, 0] - cost).mean())
        best = np.zeros((N, n))
        for i in reversed(range(n)):
            inner = gain[:, i] + sum(best[:, j] for j in tr.children[i])
            best[:, i] = np.where(ok[:, i], np.maximum(0.0, inner), 0.0)
        v_d2 = float(best[:, 0].mean() - tr.cost.sum())
        best = np.zeros((N, n))
        for i in reversed(range(n)):
            inner = gain[:, i] - tr.cost[i] + sum(best[:, j] for j in tr.children[i])
            best[:, i] = np.where(ok[:, i], np.maximum(0.0, inner), 0.0)
        v_fi = float(best[:, 0].mean())
        rows.append([k, n, round(v_c), round(max(v_c, v_d1, v_d2)), round(v_fi)])
    return rows


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(20261124)

    def w(name, header, rows):
        with open(os.path.join(OUT, name), "w", newline="") as f:
            x = csv.writer(f); x.writerow(header); x.writerows(rows)
    w("scal_runtime.csv", ["model", "nodes", "milliseconds"], runtime(rng))
    w("scal_protocol.csv", ["instance", "nodes", "value_commitment", "deferred_lower_bound", "full_info_bound"],
      protocol_random(rng))
    w("scal_m2_small.csv", ["instance", "nodes", "slots", "window", "value_m0", "value_optimal", "value_sequential",
                            "value_speculative"], m2_small(rng))
    w("scal_m2_large.csv", ["nodes", "rep", "slots", "window", "value_m0", "value_sequential", "value_speculative",
                            "speculative_se", "ms_per_simulated_year"], m2_large(rng))
    print("done")

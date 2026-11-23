"""
Deferred declaration: verify in any order, declare once the year's results are in.

solve_year: one year, one verification at a time (no deadline). Declare the best rooted
set of verified nodes (max-weight rooted subtree, weights beta_i (eta_i - theta_i)).
solve_years: yearly choice. First verification costs c0_j + c_j, failure permanent,
theta_j constant. Each year declare the best rooted set of known nodes, paying c_i for
declared nodes not yet paid that year. PV at the first year.

Exact DP on a discretised prior: M equal-probability bins, value = bin conditional mean.
State = status per node, one numpy array per status pattern. simulate_* runs the policy
on continuous draws (lower bound).
"""
import itertools
import math
from statistics import NormalDist

import numpy as np

_N = NormalDist()
U, F, K, KP = 0, 1, 2, 3          # unknown, failed, known, known + paid this year


# discretisation
def bins(mean, cv, M):
    """Equal-probability bins of a lognormal: edges (M+1) and conditional means (M)."""
    if cv <= 0:
        return np.array([0.0] + [math.inf] * M), np.full(M, mean)
    s = math.sqrt(math.log(1 + cv * cv))
    nu = math.log(mean) - s * s / 2
    edges = [0.0] + [math.exp(nu + s * _N.inv_cdf(k / M)) for k in range(1, M)] + [math.inf]
    vals = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        a = 0.0 if lo == 0 else _N.cdf((math.log(lo) - nu - s * s) / s)
        b = 1.0 if hi == math.inf else _N.cdf((math.log(hi) - nu - s * s) / s)
        vals.append(M * mean * (b - a))
    return np.array(edges), np.array(vals)


def to_bin(theta, edges):
    return np.clip(np.searchsorted(edges, theta, side="right") - 1, 0, len(edges) - 2)


# tree helpers
class Tree:
    """Arrays for a tree, from M0 terms or raw lists."""

    def __init__(self, ids, parent, beta, eta, mean, cv, cost, rho, setup=None):
        self.ids = list(ids)
        self.n = len(self.ids)
        self.parent = list(parent)                       # -1 for root; parents first
        self.children = [[j for j in range(self.n) if self.parent[j] == i] for i in range(self.n)]
        self.beta = np.asarray(beta, float)              # (n,) or (Y, n)
        self.eta = np.asarray(eta, float)
        self.mean = np.asarray(mean, float)
        self.cv = np.asarray(cv, float)
        self.cost = np.asarray(cost, float)
        self.rho = np.asarray(rho, float)
        self.setup = None if setup is None else np.asarray(setup, float)

    @staticmethod
    def from_terms(terms):
        ids = list(terms)
        # parents before children
        order, stack = [], [next(i for i in ids if not terms[i].parent)]
        while stack:
            i = stack.pop(0)
            order.append(i)
            stack.extend(terms[i].children)
        idx = {i: k for k, i in enumerate(order)}
        t = [terms[i] for i in order]
        return Tree(order, [idx[x.parent] if x.parent else -1 for x in t], [x.B for x in t], [x.K for x in t],
                    [x.mean for x in t], [x.cv for x in t], [x.cost for x in t], [x.rho for x in t])

    def ancestors(self, j):
        out, p = [], self.parent[j]
        while p >= 0:
            out.append(p)
            p = self.parent[p]
        return out


def _axis_shape(n_axes, axis, M):
    shp = [1] * n_axes
    shp[axis] = M
    return tuple(shp)


def best_subtree(tree, pattern, weights, M, usable=(K, KP)):
    """Max-weight rooted subtree on the grid of known nodes' bins. weights[i]: (M,), net of cost."""
    known = [i for i in range(tree.n) if pattern[i] in usable]
    pos = {i: a for a, i in enumerate(known)}
    na = len(known)
    best = [None] * tree.n
    for i in reversed(range(tree.n)):                 # children first
        if pattern[i] not in usable:
            best[i] = 0.0
            continue
        w = weights[i].reshape(_axis_shape(na, pos[i], M)) if na else weights[i]
        tot = w
        for j in tree.children[i]:
            tot = tot + best[j]
        best[i] = np.maximum(0.0, tot)
    out = best[0]
    if np.isscalar(out) or np.ndim(out) == 0:
        out = np.zeros((M,) * na) + out
    else:
        out = np.broadcast_to(out, (M,) * na).copy()
    return out


def _known_axes(pattern, usable=(K, KP)):
    return [i for i, s in enumerate(pattern) if s in usable]


def _mean_new_axis(arr, pattern_after, j, usable=(K, KP)):
    """Average over node j's axis."""
    axis = _known_axes(pattern_after, usable).index(j)
    return arr.mean(axis=axis)


# one year
def solve_year(tree, M=20):
    """Exact one-year deferred value and policy (discretised prior)."""
    n = tree.n
    vals = [bins(tree.mean[i], tree.cv[i], M) for i in range(n)]
    weights = [tree.beta[i] * (tree.eta[i] - vals[i][1]) for i in range(n)]
    patterns = sorted(itertools.product((U, F, K), repeat=n), key=lambda p: sum(s == U for s in p))
    V, P = {}, {}
    for pat in patterns:
        term = best_subtree(tree, pat, weights, M, usable=(K,))
        best, act = term, np.full(term.shape, -1, dtype=np.int8)
        for j in range(n):
            if pat[j] != U or any(pat[a] == F for a in tree.ancestors(j)):
                continue
            pf = list(pat); pf[j] = F
            pk = list(pat); pk[j] = K
            cont = -tree.cost[j] + (1 - tree.rho[j]) * V[tuple(pf)] \
                + tree.rho[j] * _mean_new_axis(V[tuple(pk)], pk, j, usable=(K,))
            better = cont > best + 1e-9
            best = np.where(better, cont, best)
            act = np.where(better, j, act).astype(np.int8)
        V[pat], P[pat] = best, act
    start = tuple([U] * n)
    return float(V[start]), {"V": V, "P": P, "edges": [v[0] for v in vals], "M": M}


def simulate_year(tree, sol, n_draws=200_000, rng=None):
    """Policy on continuous draws (lower bound); P(verified), P(declared), first node verified."""
    rng = rng or np.random.default_rng(0)
    n, P, edges = tree.n, sol["P"], sol["edges"]
    th = np.empty((n_draws, n))
    for i in range(n):
        if tree.cv[i] > 0:
            s = math.sqrt(math.log(1 + tree.cv[i] ** 2))
            th[:, i] = np.exp(rng.normal(math.log(tree.mean[i]) - s * s / 2, s, n_draws))
        else:
            th[:, i] = tree.mean[i]
    ok = rng.random((n_draws, n)) < tree.rho
    total = np.zeros(n_draws)
    verified = np.zeros((n_draws, n), bool)
    first = np.full(n_draws, -1)
    bidx = np.stack([to_bin(th[:, i], edges[i]) for i in range(n)], axis=1)
    for d in range(n_draws):
        pat = [U] * n
        while True:
            known = [i for i in range(n) if pat[i] == K]
            a = int(P[tuple(pat)][tuple(bidx[d, known])]) if known else int(P[tuple(pat)])
            if a < 0:
                break
            if first[d] < 0:
                first[d] = a
            total[d] -= tree.cost[a]
            verified[d, a] = True
            pat[a] = K if ok[d, a] else F
        # declare with continuous values
        best = np.zeros(n)
        for i in reversed(range(n)):
            if pat[i] == K:
                best[i] = max(0.0, tree.beta[i] * (tree.eta[i] - th[d, i]) + sum(best[j] for j in tree.children[i]))
        total[d] += best[0]
    declared = None
    return float(total.mean()), float(total.std(ddof=1) / math.sqrt(n_draws)), verified.mean(axis=0), \
        np.bincount(first + 1, minlength=n + 1) / n_draws


def commitment_value(tree):
    """M0 value, closed form, for comparison."""
    n = tree.n
    V = np.zeros(n)
    for i in reversed(range(n)):
        k = tree.eta[i] + sum(V[j] for j in tree.children[i]) / tree.beta[i]
        V[i] = max(0.0, -tree.cost[i] + tree.rho[i] * tree.beta[i] * _put(k, tree.mean[i], tree.cv[i]))
    return float(V[0])


def _put(k, mean, cv):
    if k <= 0:
        return 0.0
    if cv <= 0:
        return max(0.0, k - mean)
    s = math.sqrt(math.log(1 + cv * cv))
    nu = math.log(mean) - s * s / 2
    d = (math.log(k) - nu) / s
    return k * _N.cdf(d) - mean * _N.cdf(d - s)


def full_info_value(tree, n_draws=400_000, rng=None):
    rng = rng or np.random.default_rng(1)
    n = tree.n
    th = np.empty((n_draws, n))
    for i in range(n):
        s = math.sqrt(math.log(1 + tree.cv[i] ** 2)) if tree.cv[i] > 0 else 0.0
        th[:, i] = np.exp(rng.normal(math.log(tree.mean[i]) - s * s / 2, s, n_draws)) if s > 0 else tree.mean[i]
    ok = rng.random((n_draws, n)) < tree.rho
    best = [None] * n
    for i in reversed(range(n)):
        inner = tree.beta[i] * (tree.eta[i] - th[:, i]) - tree.cost[i] + sum(best[j] for j in tree.children[i])
        best[i] = np.where(ok[:, i], np.maximum(0.0, inner), 0.0)
    return float(best[0].mean()), float(best[0].std(ddof=1) / math.sqrt(n_draws))


# several years
def solve_years(tree, beta_t, eta_t, cost_t, setup, delta, M=12, earliest=0):
    """Exact yearly-choice value. Arrays (Y, n); first verification from index `earliest`."""
    n, Y = tree.n, beta_t.shape[0]
    vals = [bins(tree.mean[i], tree.cv[i], M) for i in range(n)]
    S_next = None                                    # value at start of year t+1
    policies = [None] * Y
    for t in reversed(range(Y)):
        w_paid = [beta_t[t, i] * (eta_t[t, i] - vals[i][1]) for i in range(n)]
        w_unpaid = [w_paid[i] - cost_t[t, i] for i in range(n)]
        pats = sorted(itertools.product((U, F, K, KP), repeat=n), key=lambda p: sum(s == U for s in p))
        Wv, Pol = {}, {}
        for pat in pats:
            # declare: weights depend on paid status
            wts = [w_paid[i] if pat[i] == KP else w_unpaid[i] for i in range(n)]
            decl = best_subtree(tree, pat, wts, M, usable=(K, KP))
            if S_next is not None:
                nxt = tuple(K if s in (K, KP) else s for s in pat)
                cont_next = S_next[nxt]
                term = decl + delta * cont_next
            else:
                term = decl
            best, act = term, np.full(term.shape, -1, dtype=np.int8)
            for j in range(n):
                if t < earliest or pat[j] != U or any(pat[a] == F for a in tree.ancestors(j)):
                    continue
                pf = list(pat); pf[j] = F
                pk = list(pat); pk[j] = KP
                cont = -(setup[j] + cost_t[t, j]) + (1 - tree.rho[j]) * Wv[tuple(pf)] \
                    + tree.rho[j] * _mean_new_axis(Wv[tuple(pk)], pk, j, usable=(K, KP))
                better = cont > best + 1e-9
                best = np.where(better, cont, best)
                act = np.where(better, j, act).astype(np.int8)
            Wv[pat], Pol[pat] = best, act
        S_next = {pat: Wv[pat] for pat in itertools.product((U, F, K), repeat=n)}
        policies[t] = Pol
    return float(S_next[tuple([U] * n)]), {"policies": policies, "edges": [v[0] for v in vals], "M": M}


def simulate_years(tree, sol, beta_t, eta_t, cost_t, setup, delta, n_draws=20_000, rng=None):
    """Yearly-choice policy on continuous draws: PV, SE, first year verified, P(declared)."""
    rng = rng or np.random.default_rng(2)
    n, Y = tree.n, beta_t.shape[0]
    edges, pols = sol["edges"], sol["policies"]
    th = np.empty((n_draws, n))
    for i in range(n):
        s = math.sqrt(math.log(1 + tree.cv[i] ** 2)) if tree.cv[i] > 0 else 0.0
        th[:, i] = np.exp(rng.normal(math.log(tree.mean[i]) - s * s / 2, s, n_draws)) if s > 0 else tree.mean[i]
    ok = rng.random((n_draws, n)) < tree.rho
    bidx = np.stack([to_bin(th[:, i], edges[i]) for i in range(n)], axis=1)
    pv = np.zeros(n_draws)
    first_year = np.full((n_draws, n), -1)
    declared = np.zeros((Y, n))
    for d in range(n_draws):
        status = [U] * n
        for t in range(Y):
            disc = delta ** t
            pat = [K if s == K else s for s in status]
            while True:
                known = [i for i in range(n) if pat[i] in (K, KP)]
                arr = pols[t][tuple(pat)]
                a = int(arr[tuple(bidx[d, known])]) if known else int(arr)
                if a < 0:
                    break
                pv[d] -= disc * (setup[a] + cost_t[t, a])
                first_year[d, a] = t
                pat[a] = KP if ok[d, a] else F
            # declare, continuous values
            best = np.zeros(n)
            use = np.zeros(n, bool)
            for i in reversed(range(n)):
                if pat[i] in (K, KP):
                    w = beta_t[t, i] * (eta_t[t, i] - th[d, i]) - (cost_t[t, i] if pat[i] == K else 0.0)
                    best[i] = max(0.0, w + sum(best[j] for j in tree.children[i]))
            # declared set, top-down
            stack = [0] if best[0] > 0 else []
            while stack:
                i = stack.pop()
                use[i] = True
                stack.extend(j for j in tree.children[i] if best[j] > 0 and pat[j] in (K, KP))
            declared[t] += use
            pv[d] += disc * best[0]
            status = [K if s in (K, KP) else s for s in pat]
    return float(pv.mean()), float(pv.std(ddof=1) / math.sqrt(n_draws)), first_year, declared / n_draws

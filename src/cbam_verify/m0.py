"""
M0: one compliance year, commitment (paper Prop. 1).

Using node i's data saves B_i (K_i - theta_i); B = beta, K = eta in the paper.
  V_i = max(0, -c_i + rho_i B_i E[(k_i - theta_i)^+]),  k_i = K_i + sum_j V_j / B_i
Verify i if V_i > 0; use the result if theta_i < k_i. Lognormal theta -> closed form.

Baselines: static (no withholding), myopic, verify all, nothing. perfect_info_value is an
upper bound. Values in EUR/yr vs all defaults; zero floor ignored (checked in simulate).
"""
import math
from dataclasses import dataclass, field
from statistics import NormalDist

import numpy as np

_N = NormalDist()
INF = float("inf")


# lognormal
def ln_params(mean, cv):
    s2 = math.log(1 + cv * cv)
    return math.log(mean) - s2 / 2, math.sqrt(s2)


def prob_below(t, mean, cv):
    """P(theta < t)."""
    if t == INF:
        return 1.0
    if t <= 0:
        return 0.0
    if cv == 0:
        return 1.0 if mean < t else 0.0
    m, s = ln_params(mean, cv)
    return _N.cdf((math.log(t) - m) / s)


def partial_mean_below(t, mean, cv):
    """E[theta 1{theta < t}]."""
    if t == INF:
        return mean
    if t <= 0:
        return 0.0
    if cv == 0:
        return mean if mean < t else 0.0
    m, s = ln_params(mean, cv)
    return mean * _N.cdf((math.log(t) - m - s * s) / s)


def put(k, mean, cv):
    """E[(k - theta)^+], lognormal theta."""
    if k <= 0:
        return 0.0
    return k * prob_below(k, mean, cv) - partial_mean_below(k, mean, cv)


# settings and per-node terms
@dataclass
class Setting:
    year: int = 2026
    scenario: str = "futures"
    Q: float = None           # t/yr; None = tree value
    lam: float = None         # None = tree value
    price: float = None       # None = scenario price
    rho: float = None         # None = node values
    cv_supplier: float = None
    cv_own: float = None
    cost_scale: float = 1.0


@dataclass
class Terms:
    id: str
    parent: str
    children: list
    B: float      # EUR per unit theta (beta)
    K: float      # break-even (eta)
    mean: float
    cv: float
    cost: float
    rho: float
    w: float


def node_terms(tree, cbam_policy, setting):
    y = setting.year
    price = setting.price if setting.price is not None else cbam_policy.price(y, setting.scenario)
    Q = setting.Q if setting.Q is not None else tree.Q
    lam = setting.lam if setting.lam is not None else tree.lam
    terms = {}
    for i, n in tree.nodes.items():
        cv = n.theta_cv
        if n.own and setting.cv_own is not None:
            cv = setting.cv_own
        if not n.own and setting.cv_supplier is not None:
            cv = setting.cv_supplier
        K = tree.gain(i, 0.0, y, cbam_policy) / n.w
        terms[i] = Terms(i, n.parent, list(n.children), lam * Q * price * n.w, K, n.theta_mean, cv,
                         n.cost * setting.cost_scale, setting.rho if setting.rho is not None else n.rho, n.w)
    return terms


# plans
@dataclass
class Plan:
    name: str
    attempt: dict                 # id -> verify?
    threshold: dict               # id -> use if theta below
    value: float = 0.0            # EUR/yr
    node_value: dict = field(default_factory=dict)

    def attempted(self):
        return [i for i, a in self.attempt.items() if a]


def _post_order(terms, root):
    order, stack = [], [root]
    while stack:
        i = stack.pop()
        order.append(i)
        stack.extend(terms[i].children)
    return list(reversed(order))


def _root(terms):
    return next(i for i, t in terms.items() if not t.parent)


def _prune(att, terms):
    """Switch off nodes whose parent is not verified."""
    stack = [_root(terms)]
    reachable = set()
    while stack:
        i = stack.pop()
        reachable.add(i)
        if att[i]:
            stack.extend(terms[i].children)
    return {i: (att[i] and i in reachable) for i in att}


def adaptive_plan(terms):
    V, att, thr = {}, {}, {}
    for i in _post_order(terms, _root(terms)):
        t = terms[i]
        k = t.K + sum(V[j] for j in t.children) / t.B
        cont = -t.cost + t.rho * t.B * put(k, t.mean, t.cv)
        V[i], att[i], thr[i] = max(0.0, cont), cont > 0, k
    r = _root(terms)
    return Plan("adaptive (M0)", _prune(att, terms), thr, V[r], V)


def static_plan(terms):
    V, att, thr = {}, {}, {}
    for i in _post_order(terms, _root(terms)):
        t = terms[i]
        cont = -t.cost + t.rho * (t.B * (t.K - t.mean) + sum(V[j] for j in t.children))
        V[i], att[i], thr[i] = max(0.0, cont), cont > 0, INF
    r = _root(terms)
    return Plan("static commitment", _prune(att, terms), thr, V[r], V)


def _fixed_plan(name, terms, attempt):
    plan = Plan(name, attempt, {i: INF for i in terms})
    plan.value, plan.node_value = evaluate(plan, terms)
    return plan


def myopic_plan(terms):
    att, stack = {i: False for i in terms}, [_root(terms)]
    while stack:
        i = stack.pop()
        t = terms[i]
        if -t.cost + t.rho * t.B * (t.K - t.mean) > 0:
            att[i] = True
            stack.extend(t.children)
    return _fixed_plan("myopic", terms, att)


def verify_all_plan(terms):
    return _fixed_plan("verify all", terms, {i: True for i in terms})


def nothing_plan(terms):
    return _fixed_plan("verify nothing", terms, {i: False for i in terms})


def evaluate(plan, terms):
    """Exact value of a plan given attempt flags and use thresholds."""
    val = {}
    for i in _post_order(terms, _root(terms)):
        t = terms[i]
        if not plan.attempt[i]:
            val[i] = 0.0
            continue
        thr = plan.threshold[i]
        p = prob_below(thr, t.mean, t.cv)
        pm = partial_mean_below(thr, t.mean, t.cv)
        val[i] = -t.cost + t.rho * (t.B * (t.K * p - pm) + p * sum(val[j] for j in t.children))
    return val[_root(terms)], val


# simulation
def sample(terms, n, rng):
    """id -> (theta draws, success draws)."""
    out = {}
    for i, t in terms.items():
        if t.cv > 0:
            m, s = ln_params(t.mean, t.cv)
            th = np.exp(rng.normal(m, s, n))
        else:
            th = np.full(n, t.mean)
        out[i] = (th, rng.random(n) < t.rho)
    return out


def simulate(plan, terms, draws, tree=None, cbam_policy=None, year=None, setting=None):
    """Per-draw net saving. With tree and policy given, also with the zero floor."""
    n = len(next(iter(draws.values()))[0])
    r = _root(terms)
    total = np.zeros(n)
    used = {i: np.zeros(n, bool) for i in terms}
    reach = {r: np.ones(n, bool)}
    order = list(reversed(_post_order(terms, r)))          # parents first
    for i in order:
        t = terms[i]
        here = reach[i]
        if plan.attempt[i]:
            th, ok = draws[i]
            total -= t.cost * here
            use = here & ok & (th < plan.threshold[i])
            used[i] = use
            total += np.where(use, t.B * (t.K - th), 0.0)
        for j in t.children:
            reach[j] = used[i]
    floored = None
    if tree is not None:
        Q = setting.Q if setting.Q is not None else tree.Q
        lam = setting.lam if setting.lam is not None else tree.lam
        price = setting.price if setting.price is not None else cbam_policy.price(year, setting.scenario)
        e0 = tree.E([], {}, year, cbam_policy, floor=False)
        cost = total - sum(np.where(used[i], terms[i].B * (terms[i].K - draws[i][0]), 0.0) for i in terms)
        floored = np.empty(n)
        for s in range(n):
            S = [i for i in terms if used[i][s]]
            e = tree.E(S, {i: draws[i][0][s] for i in S}, year, cbam_policy, floor=False)
            floored[s] = lam * Q * price * (max(0.0, e0) - max(0.0, e)) + cost[s]
    return total, floored


def perfect_info_value(terms, draws):
    """Mean value with theta known in advance (success still random). Upper bound."""
    r = _root(terms)
    best = {}
    for i in _post_order(terms, r):
        t = terms[i]
        th = draws[i][0]
        inner = np.maximum(0.0, t.B * (t.K - th) + sum(best[j] for j in t.children))
        best[i] = np.maximum(0.0, -t.cost + t.rho * inner)
    return float(best[r].mean()), float(best[r].std(ddof=1) / math.sqrt(len(best[r])))


ALL_PLANS = [adaptive_plan, static_plan, myopic_plan, verify_all_plan, nothing_plan]


def plan_stats(plan, terms):
    """Reach and use probabilities per node, expected spend."""
    r = _root(terms)
    reach, use = {r: 1.0}, {}
    spend = 0.0
    for i in reversed(_post_order(terms, r)):     # parents first
        t = terms[i]
        if plan.attempt[i]:
            spend += reach[i] * t.cost
            use[i] = reach[i] * t.rho * prob_below(plan.threshold[i], t.mean, t.cv)
        else:
            use[i] = 0.0
        for j in t.children:
            reach[j] = use[i]
    return {"reach": reach, "use": use, "spend": spend}

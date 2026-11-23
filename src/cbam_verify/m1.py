"""
M1: start year per installation, 2026-2034, commitment (paper Prop. 4).

s_i no earlier than the parent's. In s_i pay c0_i + c_i; failure is permanent. On success
decide once: use every year to 2034, or withhold for good.
  W_i(s)    = -c0_i - c_i + rho_i E[(Abar_i(s) - Bbar_i(s) theta_i)^+]
  Bbar_i(s) = sum_{t>=s} d^(t-s) B_i(t)
  Abar_i(s) = sum_{t>=s} d^(t-s) B_i(t) K_i(t) - sum_{t>s} d^(t-s) c_i + sum_j C_j(s)
  C_j(s)    = max(0, max_{s'>=s} d^(s'-s) W_j(s'))
W and C are U and Gamma in the paper. PV in 2026 EUR vs defaults throughout, no floor.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from . import m0
from .params import YEARS


@dataclass
class M1Setting:
    scenario: str = "futures"
    Q: float = None
    lam: float = None
    rho: float = None
    cv_supplier: float = None
    cv_own: float = None
    cost_scale: float = 1.0
    discount_rate: float = 0.08
    setup_ratio: float = 1.0       # c0 = setup_ratio * c
    starts: tuple = None           # None = any year
    withhold: bool = True


@dataclass
class M1Plan:
    name: str
    start: dict                    # id -> start year or None
    threshold: dict                # id -> use if theta below
    value: float                   # PV, 2026 EUR
    W: dict = field(default_factory=dict)   # id -> {start year: W_i(s)}


def yearly_terms(tree, cbam_policy, st, years=YEARS):
    out = {}
    for y in years:
        s0 = m0.Setting(year=y, scenario=st.scenario, Q=st.Q, lam=st.lam, rho=st.rho,
                        cv_supplier=st.cv_supplier, cv_own=st.cv_own, cost_scale=st.cost_scale)
        out[y] = m0.node_terms(tree, cbam_policy, s0)
    return out


def _structure(terms_by_year):
    any_year = next(iter(terms_by_year.values()))
    root = m0._root(any_year)
    return any_year, root, m0._post_order(any_year, root)


def _own_terms(i, s, yt, years, d):
    """Bbar, the node's own part of Abar, and the first-year cost, for start year s."""
    later = [t for t in years if t >= s]
    Bbar = sum(d ** (t - s) * yt[t][i].B for t in later)
    Aown = sum(d ** (t - s) * yt[t][i].B * yt[t][i].K for t in later)
    Aown -= sum(d ** (t - s) * yt[t][i].cost for t in later if t > s)
    return Bbar, Aown


def solve(tree, cbam_policy, st=None, years=YEARS):
    st = st or M1Setting()
    yt = yearly_terms(tree, cbam_policy, st, years)
    base, root, order = _structure(yt)
    d = 1.0 / (1.0 + st.discount_rate)
    allowed = [y for y in years if st.starts is None or y in st.starts]
    W, best_child = {}, {}
    for i in order:
        t0 = base[i]
        W[i] = {}
        for s in allowed:
            Bbar, Aown = _own_terms(i, s, yt, years, d)
            C = 0.0
            for j in t0.children:
                C += max([0.0] + [d ** (s2 - s) * W[j][s2] for s2 in allowed if s2 >= s])
            Abar = Aown + C
            c_first = yt[s][i].cost * (1 + st.setup_ratio)
            rho, mean, cv = yt[s][i].rho, yt[s][i].mean, yt[s][i].cv
            if st.withhold:
                W[i][s] = -c_first + rho * Bbar * m0.put(Abar / Bbar, mean, cv)
            else:
                W[i][s] = -c_first + rho * (Abar - Bbar * mean)
    # plan, top-down
    start, thr = {i: None for i in order}, {i: m0.INF for i in order}
    first = years[0]
    cand = [(d ** (s - first) * W[root][s], s) for s in allowed]
    value, s_root = max(cand) if cand else (0.0, None)
    if value <= 0:
        return M1Plan("M1" if st.withhold else "M1 static", start, thr, 0.0, W)

    def place(i, s):
        start[i] = s
        Bbar, Aown = _own_terms(i, s, yt, years, d)
        C = 0.0
        for j in base[i].children:
            opts = [(d ** (s2 - s) * W[j][s2], s2) for s2 in allowed if s2 >= s]
            v, s2 = max(opts) if opts else (0.0, None)
            if v > 0:
                C += v
                place(j, s2)
        thr[i] = (Aown + C) / Bbar if st.withhold else m0.INF

    place(root, s_root)
    return M1Plan("M1" if st.withhold else "M1 static", start, thr, value, W)


def evaluate(plan, tree, cbam_policy, st=None, years=YEARS):
    """Exact PV (2026 EUR) for given start years and thresholds."""
    st = st or M1Setting()
    yt = yearly_terms(tree, cbam_policy, st, years)
    base, root, order = _structure(yt)
    d = 1.0 / (1.0 + st.discount_rate)
    val = {}
    for i in order:
        s = plan.start[i]
        if s is None:
            val[i] = 0.0
            continue
        for j in base[i].children:
            if plan.start[j] is not None and plan.start[j] < s:
                raise ValueError("a supplier cannot start before its customer")
        Bbar, Aown = _own_terms(i, s, yt, years, d)
        C = sum(d ** (plan.start[j] - s) * val[j] for j in base[i].children if plan.start[j] is not None)
        t = yt[s][i]
        p = m0.prob_below(plan.threshold[i], t.mean, t.cv)
        pm = m0.partial_mean_below(plan.threshold[i], t.mean, t.cv)
        val[i] = -t.cost * (1 + st.setup_ratio) + t.rho * (Aown * p - Bbar * pm + p * C)
    s = plan.start[root]
    return 0.0 if s is None else d ** (s - years[0]) * val[root]


def simulate(plan, tree, cbam_policy, st=None, years=YEARS, n=20000, rng=None):
    """PV per draw (theta and success) for the plan."""
    st = st or M1Setting()
    rng = rng or np.random.default_rng(0)
    yt = yearly_terms(tree, cbam_policy, st, years)
    base, root, order = _structure(yt)
    d = 1.0 / (1.0 + st.discount_rate)
    draws = m0.sample(base, n, rng)
    total = np.zeros(n)
    in_use = {}
    for i in reversed(order):                       # parents first
        s = plan.start[i]
        parent = base[i].parent
        reach = np.ones(n, bool) if not parent else in_use[parent]
        if s is None:
            in_use[i] = np.zeros(n, bool)
            continue
        th, ok = draws[i]
        disc0 = d ** (s - years[0])
        total -= reach * disc0 * yt[s][i].cost * (1 + st.setup_ratio)
        use = reach & ok & (th < plan.threshold[i])
        in_use[i] = use
        Bbar, Aown = _own_terms(i, s, yt, years, d)
        total += np.where(use, disc0 * (Aown - Bbar * th), 0.0)
    return total


def start_all_plan(tree, cbam_policy, st=None, years=YEARS):
    """Every node from the first year, every result used."""
    ids = list(tree.nodes)
    return M1Plan("start all in 2026", {i: years[0] for i in ids}, {i: m0.INF for i in ids}, 0.0)

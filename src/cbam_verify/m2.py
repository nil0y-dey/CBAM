"""
M2: verifier slots K and deadline W (weeks), one year, commitment.

Durations geometric (q_i = 1 / mean weeks); cost paid at start; success w.p. rho_i.
A supplier may start before its customer's result is in. Its result is opened once the
customer is in use. Anything not in use by week W is worth nothing.
Status: 0 idle, 1 running, 2 done/waiting, 3 in use, 4 dead. Exact memoised DP over
(statuses, week); fixed start rules are evaluated with the same recursion.
"""
import itertools
import math
import sys
from dataclasses import dataclass

import numpy as np

from . import m0

IDLE, RUNNING, WAITING, IN_USE, DEAD = 0, 1, 2, 3, 4
sys.setrecursionlimit(100000)


@dataclass
class M2Setting:
    slots: int = 2
    weeks: int = 39
    duration_scale: float = 1.0
    durations: dict = None        # id -> mean weeks; None = by size


class Problem:
    def __init__(self, terms, tree, st, assumptions):
        self.ids = list(terms)                    # parents first
        self.idx = {i: k for k, i in enumerate(self.ids)}
        self.terms = [terms[i] for i in self.ids]
        self.parent = [self.idx[t.parent] if t.parent else -1 for t in self.terms]
        self.children = [[self.idx[c] for c in t.children] for t in self.terms]
        self.n = len(self.ids)
        self.K, self.W = st.slots, st.weeks
        mean = {}
        for i in self.ids:
            if st.durations and i in st.durations:
                mean[i] = st.durations[i]
            else:
                mean[i] = assumptions[f"verification_weeks_{tree.nodes[i].size}"]["central"]
        self.mean_weeks = [mean[i] * st.duration_scale for i in self.ids]
        self.q = [min(1.0, 1.0 / w) for w in self.mean_weeks]

    def kill(self, s, k):
        """Node k and everything below it -> dead."""
        s = list(s)
        stack = [k]
        while stack:
            j = stack.pop()
            s[j] = DEAD
            stack.extend(self.children[j])
        return tuple(s)

    def startable(self, s):
        return [k for k in range(self.n)
                if s[k] == IDLE and (self.parent[k] < 0 or s[self.parent[k]] != DEAD)]

    def openable(self, s):
        for k in range(self.n):
            if s[k] == WAITING and (self.parent[k] < 0 or s[self.parent[k]] == IN_USE):
                return k
        return None


class Solver:
    """policy=None: optimal. Else policy(prob, state, week) -> nodes to start, in order."""

    def __init__(self, prob, policy=None):
        self.p, self.policy = prob, policy
        self._V, self._settle, self._step = {}, {}, {}

    def value(self):
        return self.settle(tuple([IDLE] * self.p.n), 0)

    def settle(self, s, t):
        key = (s, t)
        if key in self._settle:
            return self._settle[key]
        p = self.p
        k = p.openable(s)
        if k is None:
            v = self.V(s, t)
        else:
            su = list(s); su[k] = IN_USE
            vu = self.settle(tuple(su), t)
            vd = self.settle(p.kill(s, k), t)
            tk = p.terms[k]
            v = vd + tk.B * m0.put(tk.K + (vu - vd) / tk.B, tk.mean, tk.cv)
        self._settle[key] = v
        return v

    def options(self, s, t):
        p = self.p
        free = p.K - sum(1 for x in s if x == RUNNING)
        cand = p.startable(s)
        if self.policy is None:
            out = [()]
            for r in range(1, min(free, len(cand)) + 1):
                out.extend(itertools.combinations(cand, r))
            return out
        chosen = [k for k in self.policy(p, s, t) if k in cand]
        return [tuple(chosen[:max(0, free)])]

    def after_start(self, s, S):
        s1 = list(s)
        for k in S:
            s1[k] = RUNNING
        return tuple(s1), sum(self.p.terms[k].cost for k in S)

    def V(self, s, t):
        key = (s, t)
        if key in self._V:
            return self._V[key]
        if t >= self.p.W:
            v = 0.0
        else:
            v = -math.inf
            for S in self.options(s, t):
                s1, cost = self.after_start(s, S)
                v = max(v, -cost + self.step(s1, t))
        self._V[key] = v
        return v

    def decision(self, s, t):
        best, arg = -math.inf, ()
        for S in self.options(s, t):
            s1, cost = self.after_start(s, S)
            v = -cost + self.step(s1, t)
            if v > best + 1e-9:
                best, arg = v, S
        return arg

    def step(self, s, t):
        """Expectation over one week of the running verifications."""
        key = (s, t)
        if key in self._step:
            return self._step[key]
        p = self.p
        run = [k for k in range(p.n) if s[k] == RUNNING]
        if not run:
            v = self.settle(s, t + 1)
        else:
            v = 0.0
            for combo in itertools.product((0, 1, 2), repeat=len(run)):  # not done, success, failure
                prob = 1.0
                s1 = list(s)
                dead = []
                for k, o in zip(run, combo):
                    q, rho = p.q[k], p.terms[k].rho
                    if o == 0:
                        prob *= 1 - q
                    elif o == 1:
                        prob *= q * rho
                        s1[k] = WAITING
                    else:
                        prob *= q * (1 - rho)
                        dead.append(k)
                if prob == 0.0:
                    continue
                s1 = tuple(s1)
                for k in dead:
                    s1 = p.kill(s1, k)
                v += prob * self.settle(s1, t + 1)
        self._step[key] = v
        return v

    def threshold(self, s, t, k):
        """Use k's result if theta_k is below this (k openable in state s)."""
        su = list(s); su[k] = IN_USE
        vu, vd = self.settle(tuple(su), t), self.settle(self.p.kill(s, k), t)
        tk = self.p.terms[k]
        return tk.K + (vu - vd) / tk.B


# start rules
def _m0_index(prob):
    terms = {i: t for i, t in zip(prob.ids, prob.terms)}
    plan = m0.adaptive_plan(terms)
    keep = [plan.attempt[i] for i in prob.ids]
    idx = [plan.node_value[i] / w if keep[k] else -1.0 for k, (i, w) in enumerate(zip(prob.ids, prob.mean_weeks))]
    return keep, idx


def sequential_policy(prob):
    """Sequential rule: start a node once its customer is in use. M0 nodes, by M0 value per week."""
    keep, idx = _m0_index(prob)

    def pol(p, s, t):
        ok = [k for k in p.startable(s) if keep[k] and (p.parent[k] < 0 or s[p.parent[k]] == IN_USE)]
        return sorted(ok, key=lambda k: -idx[k])
    return pol


def speculative_policy(prob):
    """Parallel rule in the paper: start M0 nodes as soon as a slot is free."""
    keep, idx = _m0_index(prob)

    def pol(p, s, t):
        ok = [k for k in p.startable(s) if keep[k]]
        return sorted(ok, key=lambda k: -idx[k])
    return pol


# simulation
def simulate(solver, n=20000, rng=None):
    """Simulated savings of the solver's policy; share of runs each node ends in use."""
    p = solver.p
    rng = rng or np.random.default_rng(0)
    out = np.zeros(n)
    used = np.zeros(p.n)
    for r in range(n):
        s, total = tuple([IDLE] * p.n), 0.0
        thetas = {}
        for t in range(p.W + 1):
            # open results whose customer is in use
            while True:
                k = p.openable(s)
                if k is None:
                    break
                tk = p.terms[k]
                if k not in thetas:
                    m, sg = m0.ln_params(tk.mean, tk.cv) if tk.cv > 0 else (math.log(tk.mean), 0.0)
                    thetas[k] = math.exp(rng.normal(m, sg)) if sg > 0 else tk.mean
                if thetas[k] < solver.threshold(s, t, k):
                    total += tk.B * (tk.K - thetas[k])
                    s = tuple(IN_USE if j == k else x for j, x in enumerate(s))
                else:
                    s = p.kill(s, k)
            if t >= p.W:
                break
            S = solver.decision(s, t)
            s, cost = solver.after_start(s, S)
            total -= cost
            s1 = list(s)
            dead = []
            for k in range(p.n):
                if s[k] == RUNNING and rng.random() < p.q[k]:
                    if rng.random() < p.terms[k].rho:
                        s1[k] = WAITING
                    else:
                        dead.append(k)
            s = tuple(s1)
            for k in dead:
                s = p.kill(s, k)
        out[r] = total
        used += np.array([1.0 if x == IN_USE else 0.0 for x in s])
    return out, dict(zip(p.ids, used / n))


def usage(solver):
    """Exact P(node in use at deadline) and expected spend."""
    p = solver.p
    dist = {tuple([IDLE] * p.n): 1.0}
    spend = 0.0
    final = np.zeros(p.n)
    for t in range(p.W + 1):
        # open results whose customer is in use
        settled = {}
        stack = list(dist.items())
        while stack:
            s, pr = stack.pop()
            k = p.openable(s)
            if k is None:
                settled[s] = settled.get(s, 0.0) + pr
                continue
            tk = p.terms[k]
            pu = m0.prob_below(solver.threshold(s, t, k), tk.mean, tk.cv)
            su = tuple(IN_USE if j == k else x for j, x in enumerate(s))
            if pu > 0:
                stack.append((su, pr * pu))
            if pu < 1:
                stack.append((p.kill(s, k), pr * (1 - pu)))
        if t >= p.W:
            for s, pr in settled.items():
                final += pr * np.array([1.0 if x == IN_USE else 0.0 for x in s])
            break
        nxt = {}
        for s, pr in settled.items():
            S = solver.decision(s, t)
            s1, cost = solver.after_start(s, S)
            spend += pr * cost
            run = [k for k in range(p.n) if s1[k] == RUNNING]
            for combo in itertools.product((0, 1, 2), repeat=len(run)):
                q = 1.0
                s2 = list(s1)
                dead = []
                for k, o in zip(run, combo):
                    if o == 0:
                        q *= 1 - p.q[k]
                    elif o == 1:
                        q *= p.q[k] * p.terms[k].rho
                        s2[k] = WAITING
                    else:
                        q *= p.q[k] * (1 - p.terms[k].rho)
                        dead.append(k)
                if q == 0.0:
                    continue
                s2 = tuple(s2)
                for k in dead:
                    s2 = p.kill(s2, k)
                nxt[s2] = nxt.get(s2, 0.0) + pr * q
        dist = nxt
    in_use = dict(zip(p.ids, final))
    useful = sum(in_use[i] * t.cost for i, t in zip(p.ids, p.terms))
    return {"in_use": in_use, "spend": spend, "wasted_spend": spend - useful}

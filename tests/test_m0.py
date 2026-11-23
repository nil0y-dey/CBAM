"""M0 tests. python tests/test_m0.py, or pytest tests/"""
import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify import m0  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.params import load_policy  # noqa: E402

POLICY = load_policy("futures")
TREES = build_all()


def test_put_matches_simulation():
    rng = np.random.default_rng(0)
    for mean, cv, k in [(2.0, 0.25, 2.3), (0.2, 0.4, 0.1), (4.3, 0.1, 4.0), (1.0, 0.25, 0.5)]:
        m, s = m0.ln_params(mean, cv)
        th = np.exp(rng.normal(m, s, 1_000_000))
        mc = np.maximum(k - th, 0).mean()
        assert abs(m0.put(k, mean, cv) - mc) < 4 * np.maximum(k - th, 0).std() / 1000 + 1e-6
        assert abs(np.exp(rng.normal(m, s, 1_000_000)).mean() - mean) / mean < 0.002


def test_dp_value_equals_exact_evaluation_and_simulation():
    rng = np.random.default_rng(1)
    for tid, tree in TREES.items():
        for year in (2026, 2030):
            terms = m0.node_terms(tree, POLICY, m0.Setting(year=year))
            plan = m0.adaptive_plan(terms)
            exact, _ = m0.evaluate(plan, terms)
            assert abs(exact - plan.value) < 1e-6 * max(1.0, abs(plan.value)), (tid, year)
            sims, _ = m0.simulate(plan, terms, m0.sample(terms, 200_000, rng))
            se = sims.std(ddof=1) / math.sqrt(len(sims))
            assert abs(sims.mean() - plan.value) < 4 * se + 1.0, (tid, year, sims.mean(), plan.value, se)


def test_ordering_of_plans():
    rng = np.random.default_rng(2)
    for tid, tree in TREES.items():
        for year in (2026, 2028, 2030, 2034):
            terms = m0.node_terms(tree, POLICY, m0.Setting(year=year))
            a = m0.adaptive_plan(terms).value
            for f in (m0.static_plan, m0.myopic_plan, m0.verify_all_plan, m0.nothing_plan):
                assert f(terms).value <= a + 1e-6, (tid, year, f.__name__)
            pi, se = m0.perfect_info_value(terms, m0.sample(terms, 100_000, rng))
            assert a <= pi + 4 * se + 1e-6, (tid, year, a, pi)


def test_no_spread_means_no_withhold_value():
    for tid, tree in TREES.items():
        terms = m0.node_terms(tree, POLICY, m0.Setting(year=2030, cv_supplier=0.0, cv_own=0.0))
        assert abs(m0.adaptive_plan(terms).value - m0.static_plan(terms).value) < 1e-6, tid


def _random_terms(rng, n_nodes):
    parents = [""] + [str(rng.integers(0, i)) for i in range(1, n_nodes)]
    terms = {}
    for i in range(n_nodes):
        mean = float(rng.uniform(0.2, 3.0))
        terms[str(i)] = m0.Terms(str(i), parents[i], [], float(rng.uniform(1e5, 5e6)),
                                 float(mean + rng.normal(0, 0.6 * mean)), mean, float(rng.uniform(0.05, 0.5)),
                                 float(rng.uniform(5e3, 2e5)), float(rng.uniform(0.6, 1.0)), 1.0)
    for i, t in terms.items():
        if t.parent:
            terms[t.parent].children.append(i)
    return terms


def test_dp_beats_brute_force_over_threshold_plans():
    """Random small trees: no grid plan beats the DP; the best one comes close."""
    rng = np.random.default_rng(3)
    for _ in range(40):
        terms = _random_terms(rng, int(rng.integers(2, 4)))
        dp = m0.adaptive_plan(terms).value
        ids = list(terms)
        grids = {}
        for i in ids:
            t = terms[i]
            m, s = m0.ln_params(t.mean, t.cv)
            grids[i] = [math.exp(m + s * z) for z in np.linspace(-2.5, 2.5, 11)] + [m0.INF]
        best = 0.0
        for att in itertools.product([False, True], repeat=len(ids)):
            attempt = dict(zip(ids, att))
            for thr in itertools.product(*(grids[i] if attempt[i] else [m0.INF] for i in ids)):
                v, _ = m0.evaluate(m0.Plan("grid", attempt, dict(zip(ids, thr))), terms)
                best = max(best, v)
        assert best <= dp + 1e-6 * max(1.0, dp), (best, dp)


def test_dp_plan_is_locally_optimal():
    """Moving a threshold or switching a node never raises the exact value."""
    rng = np.random.default_rng(4)
    cases = [_random_terms(rng, int(rng.integers(2, 6))) for _ in range(30)]
    cases += [m0.node_terms(t, POLICY, m0.Setting(year=y)) for t in TREES.values() for y in (2026, 2030)]
    for terms in cases:
        plan = m0.adaptive_plan(terms)
        base, _ = m0.evaluate(plan, terms)
        for i in terms:
            for f in (0.9, 0.99, 1.01, 1.1):
                thr = dict(plan.threshold)
                thr[i] = thr[i] * f
                v, _ = m0.evaluate(m0.Plan("perturbed", plan.attempt, thr), terms)
                assert v <= base + 1e-6 * max(1.0, abs(base)), (i, f, v, base)
            att = dict(plan.attempt)
            att[i] = not att[i]
            v, _ = m0.evaluate(m0.Plan("flipped", att, plan.threshold), terms)
            assert v <= base + 1e-6 * max(1.0, abs(base)), (i, "flip", v, base)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"passed: {name}")

"""M2 tests. python tests/test_m2.py, or pytest tests/"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify import m0, m2  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.params import load_assumptions, load_policy  # noqa: E402

POLICY, A = load_policy("futures"), load_assumptions()
TREES = build_all()


def problem(tree, year=2030, **kw):
    terms = m0.node_terms(tree, POLICY, m0.Setting(year=year))
    return terms, m2.Problem(terms, tree, m2.M2Setting(**kw), A)


def test_sequential_policy_with_ample_time_recovers_m0():
    """Fast verifications, many slots, long window: sequential rule = M0."""
    for tid, tree in TREES.items():
        terms, prob = problem(tree, slots=len(tree.nodes), weeks=150, duration_scale=0.15)
        v = m2.Solver(prob, m2.sequential_policy(prob)).value()
        v0 = m0.adaptive_plan(terms).value
        assert abs(v - v0) <= 0.002 * max(1.0, v0), (tid, v, v0)


def test_optimal_is_at_least_m0_with_ample_time_and_beats_heuristics():
    for tid, tree in TREES.items():
        for year in (2026, 2030):
            terms, prob = problem(tree, year, slots=4, weeks=150, duration_scale=0.15)
            assert m2.Solver(prob).value() >= m0.adaptive_plan(terms).value - 1e-6 * max(1, m0.adaptive_plan(terms).value)
            for K in (1, 2):
                _, prob = problem(tree, year, slots=K, weeks=39)
                v = m2.Solver(prob).value()
                for pol in (m2.sequential_policy, m2.speculative_policy):
                    assert m2.Solver(prob, pol(prob)).value() <= v + 1e-6 * max(1.0, v), (tid, year, K)


def test_value_grows_with_slots_and_window():
    for tid, tree in TREES.items():
        vals = [m2.Solver(problem(tree, slots=K, weeks=W)[1]).value() for K in (1, 2, 3) for W in (13, 26, 39)]
        grid = np.array(vals).reshape(3, 3)
        assert np.all(np.diff(grid, axis=0) >= -1e-6), tid
        assert np.all(np.diff(grid, axis=1) >= -1e-6), tid


def test_simulation_matches_value_and_usage():
    rng = np.random.default_rng(7)
    for tid in ("T1", "T2"):
        _, prob = problem(TREES[tid], slots=1, weeks=26)
        sol = m2.Solver(prob)
        v = sol.value()
        sims, used = m2.simulate(sol, n=4000, rng=rng)
        se = sims.std(ddof=1) / math.sqrt(len(sims))
        assert abs(sims.mean() - v) < 4 * se + 1.0, (tid, sims.mean(), v, se)
        exact = m2.usage(sol)["in_use"]
        for i in exact:
            assert abs(exact[i] - used[i]) < 4 * math.sqrt(exact[i] * (1 - exact[i]) / 4000) + 0.01, (tid, i)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"passed: {name}")

"""M1 tests. python tests/test_m1.py, or pytest tests/"""
import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify import m0, m1  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.params import load_policy  # noqa: E402

POLICY = load_policy("futures")
TREES = build_all()


def test_one_year_without_setup_cost_equals_m0():
    for tid, tree in TREES.items():
        for year in (2026, 2030):
            v1 = m1.solve(tree, POLICY, m1.M1Setting(setup_ratio=0.0), years=[year]).value
            v0 = m0.adaptive_plan(m0.node_terms(tree, POLICY, m0.Setting(year=year))).value
            assert abs(v1 - v0) < 1e-6 * max(1.0, v0), (tid, year, v1, v0)


def test_value_equals_exact_evaluation_and_simulation():
    rng = np.random.default_rng(5)
    for tid, tree in TREES.items():
        plan = m1.solve(tree, POLICY)
        assert abs(m1.evaluate(plan, tree, POLICY) - plan.value) < 1e-6 * max(1.0, plan.value), tid
        sims = m1.simulate(plan, tree, POLICY, n=100_000, rng=rng)
        se = sims.std(ddof=1) / math.sqrt(len(sims))
        assert abs(sims.mean() - plan.value) < 4 * se + 1.0, (tid, sims.mean(), plan.value, se)


def test_ordering_of_plans():
    for tid, tree in TREES.items():
        v = m1.solve(tree, POLICY).value
        assert m1.solve(tree, POLICY, m1.M1Setting(starts=(2026,))).value <= v + 1e-6, tid
        assert m1.solve(tree, POLICY, m1.M1Setting(withhold=False)).value <= v + 1e-6, tid
        assert m1.evaluate(m1.start_all_plan(tree, POLICY), tree, POLICY) <= v + 1e-6, tid


def test_start_years_beat_brute_force():
    """No start-year assignment beats the DP (case trees, short horizon)."""
    years = [2026, 2027, 2028, 2029, 2030]
    for tid, tree in TREES.items():
        st = m1.M1Setting()
        dp = m1.solve(tree, POLICY, st, years=years)
        ids = list(tree.nodes)
        best = 0.0
        for combo in itertools.product([None] + years, repeat=len(ids)):
            start = dict(zip(ids, combo))
            okay = all(start[i] is None or (not tree.nodes[i].parent and True) or
                       (start[tree.nodes[i].parent] is not None and start[tree.nodes[i].parent] <= start[i])
                       for i in ids)
            if not okay:
                continue
            # restrict the DP to these start years
            plan = _plan_for_starts(tree, st, years, start)
            best = max(best, m1.evaluate(plan, tree, POLICY, st, years))
        assert best <= dp.value + 1e-6 * max(1.0, dp.value), (tid, best, dp.value)
        assert best >= dp.value - 1e-6 * max(1.0, dp.value), (tid, best, dp.value)


def _plan_for_starts(tree, st, years, start):
    """Optimal thresholds for fixed start years."""
    yt = m1.yearly_terms(tree, POLICY, st, years)
    base, root, order = m1._structure(yt)
    d = 1.0 / (1.0 + st.discount_rate)
    thr, val = {}, {}
    for i in order:
        s = start[i]
        if s is None:
            thr[i], val[i] = m0.INF, 0.0
            continue
        Bbar, Aown = m1._own_terms(i, s, yt, years, d)
        C = sum(d ** (start[j] - s) * val[j] for j in base[i].children if start[j] is not None)
        thr[i] = (Aown + C) / Bbar
        t = yt[s][i]
        val[i] = -t.cost * (1 + st.setup_ratio) + t.rho * Bbar * m0.put(thr[i], t.mean, t.cv)
    return m1.M1Plan("fixed starts", start, thr, 0.0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"passed: {name}")

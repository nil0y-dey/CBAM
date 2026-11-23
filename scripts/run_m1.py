#!/usr/bin/env python3
"""
M1 for the four trees -> Data/results/m1_base.csv, m1_plans.csv, m1_sweeps.csv.
Baselines: 2026 or never, no withholding, start all in 2026.

Usage: python scripts/run_m1.py
"""
import argparse, csv, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify import m1  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.params import ROOT, YEARS, load_assumptions, load_policy  # noqa: E402


def starts_text(plan, order):
    return " ".join(f"{i}:{plan.start[i]}" for i in order if plan.start[i] is not None) or "none"


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=str(ROOT / "Data" / "results"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    A = load_assumptions()
    central = m1.M1Setting(discount_rate=A["discount_rate"]["central"], setup_ratio=A["setup_cost_ratio"]["central"])
    policies = {s: load_policy(s) for s in ("flat", "futures", "high")}
    policy = policies["futures"]
    trees = build_all()

    def variant(**kw):
        d = dict(central.__dict__)
        d.update(kw)
        return m1.M1Setting(**d)

    base, plans = [], []
    for tid, tree in trees.items():
        order = list(tree.nodes)
        plan = m1.solve(tree, policy, central)
        now = m1.solve(tree, policy, variant(starts=(YEARS[0],)))
        static = m1.solve(tree, policy, variant(withhold=False))
        allp = m1.evaluate(m1.start_all_plan(tree, policy), tree, policy, central)
        sims = m1.simulate(plan, tree, policy, central, n=a.draws, rng=rng)
        base.append({
            "tree": tid, "pv_m1": round(plan.value), "pv_now_or_never": round(now.value),
            "pv_no_withholding": round(static.value), "pv_start_all_2026": round(allp),
            "value_of_waiting": round(plan.value - now.value),
            "value_of_withholding": round(plan.value - static.value),
            "start_years_m1": starts_text(plan, order), "start_years_now_or_never": starts_text(now, order),
            "sim_pv_m1": round(float(sims.mean())), "sim_se": round(float(sims.std(ddof=1) / np.sqrt(len(sims))))})
        for i in order:
            n = tree.nodes[i]
            row = {"tree": tid, "node": i, "depth": n.depth, "start_year": plan.start[i] or "never",
                   "use_if_theta_below": round(plan.threshold[i], 4) if plan.start[i] else "",
                   "theta_mean": n.theta_mean}
            for y in YEARS:
                row[f"W_{y}"] = round(plan.W[i][y])
            plans.append(row)
    write(os.path.join(a.out, "m1_base.csv"), base)
    write(os.path.join(a.out, "m1_plans.csv"), plans)

    sweeps = []
    def record(tid, tree, factor, level, st, pol):
        p = m1.solve(tree, pol, st)
        now = m1.solve(tree, pol, m1.M1Setting(**{**st.__dict__, "starts": (YEARS[0],)}))
        sweeps.append({"tree": tid, "factor": factor, "level": level, "pv_m1": round(p.value),
                       "pv_now_or_never": round(now.value), "value_of_waiting": round(p.value - now.value),
                       "start_years": starts_text(p, list(tree.nodes))})
    for tid, tree in trees.items():
        al = tree.sector == "aluminium"
        for r in (0.0, 0.04, 0.08, 0.15):
            record(tid, tree, "discount_rate", r, variant(discount_rate=r), policy)
        for k in (0.5, 1.0, 2.0, 4.0):
            record(tid, tree, "setup_cost_ratio", k, variant(setup_ratio=k), policy)
        for sc in ("flat", "futures", "high"):
            record(tid, tree, "price_scenario", sc, variant(scenario=sc), policies[sc])
        for cv in (0.10, 0.15, 0.25, 0.40):
            record(tid, tree, "supplier_cv", cv, variant(cv_supplier=cv), policy)
        for q in ((1e3, 2e3, 5e3, 1e4, 2.5e4, 5e4) if al else (5e3, 1e4, 2.5e4, 5e4, 1e5, 2.5e5)):
            record(tid, tree, "volume_t", q, variant(Q=q), policy)
        for rho in (0.6, 0.9, 1.0):
            record(tid, tree, "success_probability", rho, variant(rho=rho), policy)
    write(os.path.join(a.out, "m1_sweeps.csv"), sweeps)

    print(f"M1 solved for {len(trees)} trees; {len(sweeps)} sweep runs "
          f"(discount rate {central.discount_rate:.0%}, set-up cost {central.setup_ratio:g} x annual cost)")
    for r in base:
        print(f"  {r['tree']}: PV EUR {r['pv_m1']:>12,} | 2026-or-never {r['pv_now_or_never']:>12,} | "
              f"no withholding {r['pv_no_withholding']:>12,} | start all 2026 {r['pv_start_all_2026']:>12,} | {r['start_years_m1']}")


if __name__ == "__main__":
    main()

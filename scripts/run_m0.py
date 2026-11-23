#!/usr/bin/env python3
"""
M0 for the four trees -> Data/results/m0_base.csv, m0_plans.csv, m0_sweeps.csv.

Usage: python scripts/run_m0.py [--draws 20000] [--seed 2026]
"""
import argparse, csv, os, sys, time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify import m0  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.params import ROOT, YEARS, load_policy  # noqa: E402

BASELINES = [m0.static_plan, m0.myopic_plan, m0.verify_all_plan]


def solve(tree, policy, setting):
    terms = m0.node_terms(tree, policy, setting)
    t0 = time.perf_counter()
    plan = m0.adaptive_plan(terms)
    runtime = time.perf_counter() - t0
    return terms, plan, runtime


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20000, help="draws for the zero-floor check")
    ap.add_argument("--pi-draws", type=int, default=400000, help="draws for the perfect-information bound")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=str(ROOT / "Data" / "results"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    policies = {s: load_policy(s) for s in ("flat", "futures", "high")}
    policy = policies["futures"]
    trees = build_all()

    base, plans, runtimes = [], [], []
    for tid, tree in trees.items():
        for y in YEARS:
            setting = m0.Setting(year=y)
            terms, plan, runtime = solve(tree, policy, setting)
            st = m0.plan_stats(plan, terms)
            vals = {f.__name__.replace("_plan", ""): f(terms).value for f in BASELINES}
            pi, pi_se = m0.perfect_info_value(terms, m0.sample(terms, a.pi_draws, rng))
            draws = m0.sample(terms, a.draws, rng)
            sim, sim_floor = m0.simulate(plan, terms, draws, tree, policy, y, setting)
            price, Q, lam = policy.price(y), tree.Q, tree.lam
            e0 = tree.E([], {}, y, policy, floor=False)
            saving_certs = (plan.value + st["spend"]) / (lam * Q * price)
            r = tree.root.id
            base.append({
                "tree": tid, "year": y, "price": price, "Q_t": Q,
                "certs_per_t_defaults": round(e0, 4),
                "certs_per_t_m0": round(e0 - saving_certs, 4),
                "value_m0": round(plan.value), "value_static": round(vals["static"]),
                "value_myopic": round(vals["myopic"]), "value_verify_all": round(vals["verify_all"]),
                "value_perfect_info": round(pi), "perfect_info_se": round(pi_se),
                "withhold_option_value": round(plan.value - vals["static"]),
                # within 3 SE of the simulated bound -> 0
                "gap_to_perfect_info_pct": (round(100 * (pi - plan.value) / pi, 1)
                                            if pi > 0 and pi - plan.value > 3 * pi_se else 0.0),
                "verification_spend": round(st["spend"]),
                "p_root_on_actual_values": round(st["use"][r], 3),
                "nodes_verified": " ".join(plan.attempted()) or "none",
                "sim_value_m0": round(float(sim.mean())), "sim_se": round(float(sim.std(ddof=1) / np.sqrt(len(sim)))),
                "sim_value_m0_with_floor": round(float(sim_floor.mean()))})
            runtimes.append(runtime)
            for i, t in terms.items():
                n = tree.nodes[i]
                plans.append({
                    "tree": tid, "year": y, "node": i, "depth": n.depth, "verify": plan.attempt[i],
                    "use_if_theta_below": round(plan.threshold[i], 4) if plan.attempt[i] else "",
                    "theta_mean": t.mean, "theta_cv": t.cv,
                    "p_reached": round(st["reach"][i], 3), "p_used": round(st["use"][i], 3),
                    "own_expected_gain_eur": round(t.rho * t.B * (t.K - t.mean) - t.cost),
                    "option_value_eur": round(plan.node_value[i])})
    write(os.path.join(a.out, "m0_base.csv"), base)
    write(os.path.join(a.out, "m0_plans.csv"), plans)

    sweeps = []
    def record(tid, tree, factor, level, setting, pol):
        terms, plan, _ = solve(tree, pol, setting)
        st = m0.plan_stats(plan, terms)
        sweeps.append({"tree": tid, "factor": factor, "level": level, "year": setting.year,
                       "value_m0": round(plan.value), "value_static": round(m0.static_plan(terms).value),
                       "value_myopic": round(m0.myopic_plan(terms).value),
                       "value_verify_all": round(m0.verify_all_plan(terms).value),
                       "withhold_option_value": round(plan.value - m0.static_plan(terms).value),
                       "verification_spend": round(st["spend"]),
                       "p_root_on_actual_values": round(st["use"][tree.root.id], 3),
                       "nodes_verified": " ".join(plan.attempted()) or "none"})
    for tid, tree in trees.items():
        al = tree.sector == "aluminium"
        for y in (2026, 2028, 2030):
            for cv in (0.10, 0.15, 0.25, 0.40):
                record(tid, tree, "supplier_cv", cv, m0.Setting(year=y, cv_supplier=cv), policy)
            for q in ((1e3, 2e3, 5e3, 1e4, 2.5e4, 5e4) if al else (5e3, 1e4, 2.5e4, 5e4, 1e5, 2.5e5)):
                record(tid, tree, "volume_t", q, m0.Setting(year=y, Q=q), policy)
            for sc in ("flat", "futures", "high"):
                record(tid, tree, "price_scenario", sc, m0.Setting(year=y, scenario=sc), policies[sc])
            for c in (0.5, 1.0, 2.0):
                record(tid, tree, "cost_scale", c, m0.Setting(year=y, cost_scale=c), policy)
            for rho in (0.6, 0.9, 1.0):
                record(tid, tree, "success_probability", rho, m0.Setting(year=y, rho=rho), policy)
            for lam in (0.25, 0.5, 1.0):
                record(tid, tree, "pass_through", lam, m0.Setting(year=y, lam=lam), policy)
    write(os.path.join(a.out, "m0_sweeps.csv"), sweeps)

    print(f"M0 solved for {len(trees)} trees x {len(YEARS)} years; {len(sweeps)} sweep runs; "
          f"slowest single solve {1000 * max(runtimes):.2f} ms")
    for r in base:
        if r["year"] in (2026, 2028, 2030):
            print(f"  {r['tree']} {r['year']}: M0 EUR {r['value_m0']:>11,} | static {r['value_static']:>11,} | "
                  f"myopic {r['value_myopic']:>11,} | all {r['value_verify_all']:>11,} | perfect {r['value_perfect_info']:>11,} "
                  f"| verify: {r['nodes_verified']}")


if __name__ == "__main__":
    main()

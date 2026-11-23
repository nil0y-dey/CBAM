#!/usr/bin/env python3
"""
M2 grid (slots x window x duration scale) for the four trees
-> Data/results/m2_grid.csv, m2_usage.csv. 'speculative' = parallel rule in the paper.

Usage: python scripts/run_m2.py
"""
import argparse, csv, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify import m0, m2  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.params import ROOT, load_assumptions, load_policy  # noqa: E402

SLOTS = (1, 2, 3, 4)
WINDOWS = (13, 26, 39)
SCALES = (0.5, 1.0, 1.5, 2.0)
YEARS = (2026, 2030)


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "Data" / "results"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    policy, A, trees = load_policy("futures"), load_assumptions(), build_all()
    grid, usage_rows = [], []
    for tid, tree in trees.items():
        for y in YEARS:
            terms = m0.node_terms(tree, policy, m0.Setting(year=y))
            v0 = m0.adaptive_plan(terms).value
            for K in SLOTS:
                for W in WINDOWS:
                    for sc in SCALES:
                        prob = m2.Problem(terms, tree, m2.M2Setting(slots=K, weeks=W, duration_scale=sc), A)
                        opt = m2.Solver(prob)
                        v = opt.value()
                        vs = m2.Solver(prob, m2.sequential_policy(prob)).value()
                        vp = m2.Solver(prob, m2.speculative_policy(prob)).value()
                        u = m2.usage(opt)
                        grid.append({
                            "tree": tid, "year": y, "slots": K, "window_weeks": W, "duration_scale": sc,
                            "value_optimal": round(v), "value_sequential": round(vs), "value_speculative": round(vp),
                            "value_m0_no_limits": round(v0),
                            "scarcity_cost_eur_per_t": round((v0 - v) / tree.Q, 3),
                            "pct_of_m0": round(100 * v / v0, 1) if v0 > 0 else "",
                            "gap_sequential_pct": round(100 * (v - vs) / v, 1) if v > 0 else "",
                            "gap_speculative_pct": round(100 * (v - vp) / v, 1) if v > 0 else "",
                            "expected_spend": round(u["spend"]), "wasted_spend": round(u["wasted_spend"])})
                        for i, pu in u["in_use"].items():
                            usage_rows.append({"tree": tid, "year": y, "slots": K, "window_weeks": W,
                                               "duration_scale": sc, "node": i, "depth": tree.nodes[i].depth,
                                               "p_in_use": round(pu, 4)})
    write(os.path.join(a.out, "m2_grid.csv"), grid)
    write(os.path.join(a.out, "m2_usage.csv"), usage_rows)
    print(f"M2 solved for {len(grid)} settings")
    for r in grid:
        if r["window_weeks"] == 39 and r["duration_scale"] == 1.0 and r["slots"] in (1, 2):
            print(f"  {r['tree']} {r['year']} K={r['slots']}: optimal EUR {r['value_optimal']:>10,} "
                  f"(M0 {r['value_m0_no_limits']:>10,}) | sequential gap {r['gap_sequential_pct']}% | "
                  f"speculative gap {r['gap_speculative_pct']}% | wasted EUR {r['wasted_spend']:,}")


if __name__ == "__main__":
    main()

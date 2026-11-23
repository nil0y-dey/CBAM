#!/usr/bin/env python3
"""
Build the case trees -> Data/trees/ (T*.json, nodes.csv, node_gains.csv, tree_totals.csv).

Usage: python scripts/build_trees.py [--scenario futures]
"""
import argparse, csv, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify.params import ROOT, YEARS, load_policy  # noqa: E402
from cbam_verify.cases import build_all  # noqa: E402
from cbam_verify.trees import check_tree  # noqa: E402

REPORT_YEARS = list(YEARS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="futures", help="price scenario in price_scenarios.csv")
    ap.add_argument("--out", default=str(ROOT / "Data" / "trees"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    policy = load_policy(a.scenario)
    trees = build_all(YEARS)

    node_rows, gain_rows, total_rows = [], [], []
    for tid, t in trees.items():
        err = check_tree(t, policy, YEARS)
        if err > 1e-9:
            raise RuntimeError(f"{tid}: E(S) and g_i disagree by {err}")
        t.save_json(os.path.join(a.out, f"{tid}.json"))
        thetas = {i: n.theta_mean for i, n in t.nodes.items()}
        for n in t.nodes.values():
            node_rows.append({
                "tree": tid, "node": n.id, "name": n.name, "parent": n.parent, "depth": n.depth,
                "output_cn8": n.output_cn8, "origin": n.origin, "route": n.route, "a": round(n.a, 4),
                "w": round(n.w, 4), "D_base": n.D_base, "default_route": n.default_route,
                "BMd_2026": round(n.BMd[2026], 4), "BMa_2026": round(n.BMa[2026], 4),
                "theta_mean": n.theta_mean, "theta_cv": n.theta_cv, "cost_eur": n.cost,
                "cost_low": n.cost_low, "cost_high": n.cost_high, "rho": n.rho, "size": n.size,
                "own": n.own, "prior_source": n.prior_source})
            for y in REPORT_YEARS:
                g = t.gain(n.id, n.theta_mean, y, policy)
                gain_rows.append({
                    "tree": tid, "node": n.id, "year": y, "scenario": a.scenario,
                    "D_tilde": round(t.D_tilde(n.id, y, policy), 4),
                    "theta_tilde_at_mean": round(t.theta_tilde(n.id, n.theta_mean, y, policy), 4),
                    "gain_t_per_t_export": round(g, 4),
                    "saving_eur_per_year": round(t.lam * t.Q * policy.price(y) * g),
                    "cost_eur": n.cost})
        for y in REPORT_YEARS:
            none = t.E([], thetas, y, policy)
            full = t.E(list(t.nodes), thetas, y, policy)
            total_rows.append({"tree": tid, "year": y, "scenario": a.scenario, "Q_t": t.Q,
                               "price": policy.price(y), "certs_per_t_no_verification": round(none, 4),
                               "certs_per_t_all_verified_at_mean": round(full, 4),
                               "saving_eur_per_year_all_verified": round(t.lam * t.Q * policy.price(y) * (none - full)),
                               "cost_eur_all_verified": sum(n.cost for n in t.nodes.values())})

    for name, rows in (("nodes.csv", node_rows), ("node_gains.csv", gain_rows), ("tree_totals.csv", total_rows)):
        with open(os.path.join(a.out, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"built {len(trees)} trees ({sum(len(t.nodes) for t in trees.values())} nodes); "
          f"scenario '{a.scenario}'; consistency check passed")
    for r in total_rows:
        if r["year"] in (2026, 2030):
            print(f"  {r['tree']} {r['year']}: certificates/t {r['certs_per_t_no_verification']:.3f} -> "
                  f"{r['certs_per_t_all_verified_at_mean']:.3f}; saving EUR {r['saving_eur_per_year_all_verified']:,} "
                  f"vs cost EUR {r['cost_eur_all_verified']:,}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
EAF and induction-furnace charge mix by country (GEM steel units).
Capacity-weighted over operating units with fully reported charge ('% known total' = 1).
Output in percent.

Usage: python scripts/gem_charge_mix.py --gem-units <GEM steel unit xlsx> --out Data/processed
"""
import argparse, csv, os
import openpyxl

SHEETS = {"Electric arc furnaces": "EAF", "Induction furnaces": "IF"}
SHARES = {"% scrap": "scrap", "% DRI": "DRI", "% HBI": "HBI",
          "% sponge iron (unknown if DRI or HBI)": "sponge_iron",
          "% basic/merchant pig iron": "merchant_pig_iron", "% granulated pig iron": "granulated_pig_iron",
          "% pig iron (unknown if basic/merchant or granulated)": "pig_iron_unspecified",
          "% other iron": "other_iron"}
OPERATING = {"operating", "operating pre-retirement"}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gem-units", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--countries", nargs="+", default=["China", "India", "Türkiye", "Vietnam"])
    a = ap.parse_args()
    wb = openpyxl.load_workbook(a.gem_units, read_only=True, data_only=True)
    out = []
    for sheet, ftype in SHEETS.items():
        rows = list(wb[sheet].iter_rows(values_only=True))
        H = {h: i for i, h in enumerate(rows[0]) if h}
        for c in a.countries:
            ops = [r for r in rows[1:] if r[H["Country/area"]] == c and r[H["Unit status"]] in OPERATING]
            known = [r for r in ops if (num(r[H["% known total"]]) or 0) >= 0.99]
            cap_all = sum(num(r[H["Current capacity (ttpa)"]]) or 0 for r in ops)
            cap_known = sum(num(r[H["Current capacity (ttpa)"]]) or 0 for r in known)
            row = {"country": c, "furnace": ftype, "operating_units": len(ops),
                   "operating_capacity_kt": round(cap_all), "units_with_charge_reported": len(known),
                   "capacity_with_charge_reported_kt": round(cap_known)}
            for col, name in SHARES.items():
                if cap_known > 0:
                    s = sum((num(r[H[col]]) or 0) * (num(r[H["Current capacity (ttpa)"]]) or 0) for r in known)
                    row[f"pct_{name}"] = round(100 * s / cap_known, 1)
                else:
                    row[f"pct_{name}"] = ""
            out.append(row)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "gem_charge_mix.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for r in out:
        if r["units_with_charge_reported"]:
            print(f"{r['country']:8s} {r['furnace']:3s} units {r['units_with_charge_reported']:>3}/{r['operating_units']:<3} "
                  f"scrap {r['pct_scrap']:>5}%  DRI {r['pct_DRI']:>5}%  merchant pig iron {r['pct_merchant_pig_iron']:>5}%")


if __name__ == "__main__":
    main()

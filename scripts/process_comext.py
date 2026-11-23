#!/usr/bin/env python3
"""
Comext DS-045409 (EU27 imports) -> comext_eu_imports.csv, comext_by_category.csv.
CN8 codes in chapters 72, 73, 76 and 2601 12 00. 100 kg -> tonnes.

Usage: python scripts/process_comext.py --inputs "Data/raw/comtext/*.csv" --out Data/processed
"""
import argparse, collections, csv, glob, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from cbam_verify.categories import goods_category, sector  # noqa: E402


def keep(cn):
    return len(cn) == 8 and (cn[:2] in ("72", "73", "76") or cn == "26011200")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted({f for pattern in a.inputs for f in glob.glob(pattern)})
    if not files:
        sys.exit("no input files found")
    os.makedirs(a.out, exist_ok=True)

    data = collections.defaultdict(lambda: {"tonnes": 0.0, "value_eur": 0.0})
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["flow"] != "1" or not keep(r["product"]):
                    continue
                key = (r["TIME_PERIOD"], r["partner"], r["product"])
                v = float(r["OBS_VALUE"]) if r["OBS_VALUE"] not in ("", None) else 0.0
                if r["indicators"] == "QUANTITY_IN_100KG":
                    data[key]["tonnes"] += v / 10.0
                elif r["indicators"] == "VALUE_IN_EUROS":
                    data[key]["value_eur"] += v

    rows = []
    for (year, partner, cn), d in sorted(data.items()):
        rows.append({"year": year, "origin_iso2": partner, "cn8": cn, "sector": sector(cn),
                     "goods_category": goods_category(cn), "tonnes": round(d["tonnes"], 1),
                     "value_eur": round(d["value_eur"]),
                     "eur_per_t": round(d["value_eur"] / d["tonnes"], 1) if d["tonnes"] > 0 else ""})
    with open(os.path.join(a.out, "comext_eu_imports.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for r in rows:
        k = (r["year"], r["origin_iso2"], r["sector"], r["goods_category"])
        agg[k][0] += r["tonnes"]
        agg[k][1] += r["value_eur"]
        agg[k][2] += 1
    with open(os.path.join(a.out, "comext_by_category.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "origin_iso2", "sector", "goods_category", "tonnes", "value_eur", "n_cn8_codes"])
        for k, (t, v, n) in sorted(agg.items()):
            w.writerow([*k, round(t, 1), round(v), n])

    years = sorted({r["year"] for r in rows})
    print(f"files: {len(files)}; years: {years}; CN8 rows kept: {len(rows)}")
    for y in years:
        tot = collections.defaultdict(float)
        for r in rows:
            if r["year"] == y:
                tot[(r["origin_iso2"], r["sector"])] += r["tonnes"]
        print(f"  {y}: " + ", ".join(f"{o} {s} {t/1e3:,.0f} kt" for (o, s), t in sorted(tot.items())))


if __name__ == "__main__":
    main()

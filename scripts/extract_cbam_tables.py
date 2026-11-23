#!/usr/bin/env python3
"""
CBAM default values and benchmarks (iron & steel, aluminium) -> tidy CSVs.

In:  --defaults   DV correcting act_final update_06.08.xlsx (IR 2025/2621 as corrected)
     --benchmarks CBAM Benchmarks_20260206.xlsx (IR 2025/2620 annex)
Out: defaults_long.csv, benchmarks_long.csv, defaults_with_benchmarks.csv,
     extraction_report.txt

Values are the Commission's information files, without mark-ups.
Column A: actual values; Column B: default values (IR 2025/2620, Annex point 5).
Routes: C BF/BOF, D DRI/EAF, E scrap/EAF; K primary, L secondary aluminium.

Usage:
  python scripts/extract_cbam_tables.py \
      --defaults "Data/raw/cbam_tables/DV correcting act_final update_06.08.xlsx" \
      --benchmarks "Data/raw/cbam_tables/CBAM Benchmarks_20260206.xlsx" --out Data/processed
"""

import argparse
import csv
import os
import re
import sys

import openpyxl

SECTORS_KEPT = {"iron and steel", "aluminium"}
DEFAULT_COUNTRIES = ["China", "India", "Türkiye", "Viet Nam"]
SPECIAL_SHEETS = {
    "Annex IV": "UNKNOWN ORIGIN (Annex IV)",
    "_Other Countries and Territorie": "OTHER COUNTRIES AND TERRITORIES",
}


# helpers
def nonempty_rows(ws):
    for r in ws.iter_rows(values_only=True):
        if any(c is not None and str(c).strip() != "" for c in r):
            yield r


def cell(r, i):
    return r[i] if i < len(r) else None


def is_section_header(r):
    """Row with only a text label in the first cell, e.g. 'Iron and steel'."""
    first = cell(r, 0)
    rest = [c for c in r[1:] if c is not None and str(c).strip() != ""]
    return isinstance(first, str) and not re.search(r"\d", first) and not rest


def to_number(v):
    """'3,187' -> (3.187, ''); '-' / 'N/A' / '' -> (None, flag)."""
    if v is None:
        return None, "missing"
    if isinstance(v, (int, float)):
        return float(v), ""
    s = str(v).strip()
    if s in ("", "-", "–"):
        return None, "missing"
    if s.upper() == "N/A":
        return None, "not_applicable"
    if s.lower().startswith("see below"):
        return None, "see_below"
    s2 = s.replace(" ", "").replace(",", ".")
    try:
        return float(s2), ""
    except ValueError:
        return None, "unparsed"


def norm_sector(v):
    """'Iron & Steel' and 'Iron and steel' -> 'iron and steel'."""
    return clean_text(v).lower().replace("&", "and")


def digits(code):
    return re.sub(r"\D", "", str(code or ""))


def clean_text(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


# default values
def read_defaults(path, countries, report):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    version = ""
    if "Version History" in wb.sheetnames:
        vrows = list(nonempty_rows(wb["Version History"]))
        if vrows:
            last = vrows[-1]
            version = f"v{cell(last, 0)} ({str(cell(last, 1))[:10]})"

    wanted = [(c, c) for c in countries]
    wanted += [(s, label) for s, label in SPECIAL_SHEETS.items()]
    out = []
    for sheet, label in wanted:
        if sheet not in wb.sheetnames:
            report.append(f"[defaults] sheet not found: {sheet!r}")
            continue
        ws = wb[sheet]
        annex_iv = sheet == "Annex IV"
        sector = None
        header_seen = False
        for r in nonempty_rows(ws):
            first = cell(r, 0)
            if not header_seen:
                if isinstance(first, str) and "CN Code" in first:
                    header_seen = True
                continue
            if is_section_header(r):
                sector = norm_sector(first)
                continue
            if sector not in SECTORS_KEPT:
                continue
            code = clean_text(first)
            desc = clean_text(cell(r, 1))
            if annex_iv:
                total, f_total = to_number(cell(r, 2))
                direct, f_direct = None, "not_given"
                indirect, f_indirect = None, "not_given"
                route = clean_text(cell(r, 3))
            else:
                direct, f_direct = to_number(cell(r, 2))
                indirect, f_indirect = to_number(cell(r, 3))
                total, f_total = to_number(cell(r, 4))
                route = clean_text(cell(r, 5))
            if "unparsed" in (f_direct, f_indirect, f_total):
                report.append(f"[defaults] unparsed value in {sheet} {code}: {r[:6]}")
            out.append({
                "origin": label,
                "sector": sector,
                "cn_code": code,
                "cn_digits": digits(code),
                "description": desc,
                "default_direct_tco2e_per_t": direct,
                "default_indirect_tco2e_per_t": indirect,
                "default_total_tco2e_per_t": total,
                "value_flag": f_total,
                "route_indicator": route,
                "is_aggregate_row": f_total == "see_below",
                "source_sheet": sheet,
                "source_version": version,
            })
    return out, version


# benchmarks
def read_benchmarks(path, report):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    version = ""
    vs = [s for s in wb.sheetnames if s.lower().startswith("version")]
    if vs:
        vrows = list(nonempty_rows(wb[vs[0]]))
        if vrows:
            last = vrows[-1]
            version = f"v{cell(last, 0)} ({str(cell(last, 1))[:10]})"
    ws = wb["Benchmarks"]
    out = []
    sector = None
    cur_code, cur_desc = None, None
    header_seen = False
    for r in nonempty_rows(ws):
        first = cell(r, 0)
        if not header_seen:
            if isinstance(first, str) and first.strip().upper().startswith("CN CODE"):
                header_seen = True
            continue
        if is_section_header(r):
            sector = norm_sector(first)
            continue
        if first not in (None, ""):
            cur_code, cur_desc = digits(first), clean_text(cell(r, 1))
        if sector not in SECTORS_KEPT:
            continue
        for col, vi, ri in (("A", 2, 3), ("B", 4, 5)):
            val, flag = to_number(cell(r, vi))
            route = clean_text(cell(r, ri))
            if val is None and flag == "missing" and not route:
                continue
            if flag == "unparsed":
                report.append(f"[benchmarks] unparsed value {cur_code} col {col}: {r[:6]}")
            rt_letter, period = split_indicator(route)
            out.append({
                "sector": sector,
                "cn8": cur_code,
                "description": cur_desc,
                "column": col,
                "route_indicator": route,
                "route": rt_letter,
                "period": period,
                "benchmark_tco2e_per_t": val,
                "source_version": version,
            })
    return out, version


# IR 2025/2620 Annex 5.3 legend:
#   (1) production years 2026-27   (2) production years 2028-30
#   (C)/(D)/(E) carbon steel via BF/BOF, DRI/EAF, scrap/EAF
#   (F)/(G)/(H) low-alloy steel via BF/BOF, DRI/EAF, scrap/EAF
#   (J) high-alloy steel (EAF)     (K) primary aluminium   (L) secondary aluminium
PERIODS = {"1": "2026-27", "2": "2028-30"}

# Goods categories, IR 2025/2547 Annex I Table 1.
# Longest prefix wins. 7205 mapped to products.
CATEGORY_PREFIXES = [
    ("260112", "sintered ore"),
    ("7201", "pig iron"),
    ("72021", "FeMn"), ("72024", "FeCr"), ("72026", "FeNi"),
    ("7203", "DRI"),
    ("7206", "crude steel"), ("7207", "crude steel"),
    ("7218", "crude steel"), ("7224", "crude steel"),
    ("72", "iron or steel products"), ("73", "iron or steel products"),
    ("7601", "unwrought aluminium"),
    ("76", "aluminium products"),
]


def goods_category(cn):
    best = ""
    cat = ""
    for prefix, name in CATEGORY_PREFIXES:
        if cn.startswith(prefix) and len(prefix) > len(best):
            best, cat = prefix, name
    return cat


def split_indicator(ind):
    """'(F)(1)' -> ('F', '2026-27'); '(C)' -> ('C', 'all'); '(2)' -> ('', '2028-30')."""
    parts = re.findall(r"\(([A-Z0-9]+)\)", ind or "")
    route = next((p for p in parts if p.isalpha()), "")
    period = next((PERIODS[p] for p in parts if p in PERIODS), "all")
    return route, period


# join: CN8 benchmark code -> longest default code that is a prefix
def build_join(defaults, benchmarks, report):
    by_origin = {}
    for d in defaults:
        if d["is_aggregate_row"]:
            continue
        by_origin.setdefault(d["origin"], []).append(d)

    bm = {}
    for b in benchmarks:
        bm.setdefault(b["cn8"], []).append(b)

    out, unmatched = [], {}
    for cn8, brows in sorted(bm.items()):
        desc = brows[0]["description"]
        sector = brows[0]["sector"]
        for origin, drows in by_origin.items():
            # default code is a prefix of CN8, or CN8 of a TARIC code
            cands = [d for d in drows
                     if cn8.startswith(d["cn_digits"]) or d["cn_digits"].startswith(cn8)]
            if not cands:
                unmatched.setdefault(origin, []).append(cn8)
                continue
            # longest match
            d = max(cands, key=lambda x: len(x["cn_digits"]))
            route = d["route_indicator"]
            colB = [b for b in brows if b["column"] == "B"]
            colA = [b for b in brows if b["column"] == "A"]

            default_letters = re.findall(r"\(([A-Z])\)", route or "")

            def pick(rows, period):
                """-> (value, route, status); status exact/plain/ambiguous/none."""
                rows = [b for b in rows if b["period"] in (period, "all")]
                if not rows:
                    return None, "", "none"
                if default_letters:
                    hit = [b for b in rows if b["route"] in default_letters]
                    if len(hit) == 1:
                        return hit[0]["benchmark_tco2e_per_t"], hit[0]["route"], "exact"
                    if len(hit) > 1:
                        return None, "", "ambiguous"
                plain = [b for b in rows if not b["route"]]
                if len(rows) == 1 and plain:
                    return plain[0]["benchmark_tco2e_per_t"], "", "plain"
                return None, "", "ambiguous"

            row = {
                "origin": origin,
                "sector": sector,
                "cn8": cn8,
                "cn8_description": desc,
                "goods_category": goods_category(cn8),
                "matched_default_code": d["cn_code"],
                "default_total_tco2e_per_t": d["default_total_tco2e_per_t"],
                "default_value_flag": d["value_flag"],
                "default_route_indicator": route,
            }
            for period in ("2026-27", "2028-30"):
                tag = period.replace("-", "_")
                vB, rB, sB = pick(colB, period)
                vA, rA, sA = pick(colA, period)
                row[f"bm_colB_{tag}"] = vB
                row[f"bm_colB_{tag}_match"] = sB
                row[f"bm_colA_{tag}"] = vA
                row[f"bm_colA_{tag}_match"] = sA
            row["bm_colB_candidates"] = "; ".join(
                f"{b['route_indicator'] or '-'}={b['benchmark_tco2e_per_t']}" for b in colB)
            row["bm_colA_candidates"] = "; ".join(
                f"{b['route_indicator'] or '-'}={b['benchmark_tco2e_per_t']}" for b in colA)
            out.append(row)
    for origin, codes in unmatched.items():
        report.append(f"[join] {origin}: {len(codes)} CN8 codes with no default row, "
                      f"e.g. {codes[:8]}")
    return out


def _count(rows, key):
    c = {}
    for r in rows:
        c[r[key]] = c.get(r[key], 0) + 1
    return c


def write_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--defaults", required=True)
    ap.add_argument("--benchmarks", required=True)
    ap.add_argument("--out", default="Data/processed")
    ap.add_argument("--countries", default=",".join(DEFAULT_COUNTRIES),
                    help="comma-separated sheet names, as spelled in the Excel file")
    args = ap.parse_args()

    countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    os.makedirs(args.out, exist_ok=True)
    report = []

    defaults, dver = read_defaults(args.defaults, countries, report)
    benchmarks, bver = read_benchmarks(args.benchmarks, report)
    joined = build_join(defaults, benchmarks, report)

    write_csv(defaults, os.path.join(args.out, "defaults_long.csv"))
    write_csv(benchmarks, os.path.join(args.out, "benchmarks_long.csv"))
    write_csv(joined, os.path.join(args.out, "defaults_with_benchmarks.csv"))

    lines = [
        f"defaults file:   {args.defaults}  [{dver}]",
        f"benchmarks file: {args.benchmarks}  [{bver}]",
        f"origins: {countries} + {list(SPECIAL_SHEETS.values())}",
        f"defaults_long rows: {len(defaults)} "
        f"(aggregate 'see below' rows: {sum(d['is_aggregate_row'] for d in defaults)})",
        f"benchmarks_long rows: {len(benchmarks)} "
        f"({len({b['cn8'] for b in benchmarks})} CN8 codes)",
        f"defaults_with_benchmarks rows: {len(joined)}",
        "  Column B match 2026-27: " + ", ".join(
            f"{k}={v}" for k, v in sorted(_count(joined, 'bm_colB_2026_27_match').items())),
        "  Column B match 2028-30: " + ", ".join(
            f"{k}={v}" for k, v in sorted(_count(joined, 'bm_colB_2028_30_match').items())),
        "  Column A match 2026-27: " + ", ".join(
            f"{k}={v}" for k, v in sorted(_count(joined, 'bm_colA_2026_27_match').items())),
        "  ('ambiguous' = the default allows two routes, e.g. carbon or low-alloy steel;",
        "   the candidates column lists every value)",
        "",
        "rows per origin and sector (defaults, excluding aggregate rows):",
    ]
    counts = {}
    for d in defaults:
        if not d["is_aggregate_row"]:
            k = (d["origin"], d["sector"])
            counts[k] = counts.get(k, 0) + 1
    lines += [f"  {o:35s} {s:15s} {n}" for (o, s), n in sorted(counts.items())]
    missing = {}
    for d in defaults:
        if d["value_flag"] == "missing":
            missing[d["origin"]] = missing.get(d["origin"], 0) + 1
    lines += ["", "codes with no default value ('-') per origin:"]
    lines += [f"  {o:35s} {n}" for o, n in sorted(missing.items())]
    lines += ["", "notes:"] + (report or ["  none"])
    with open(os.path.join(args.out, "extraction_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

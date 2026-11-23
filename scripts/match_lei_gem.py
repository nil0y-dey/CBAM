#!/usr/bin/env python3
"""
Match Lei et al. (2023) plant CO2 to GEM steel plants; within-country intensity spread.

Lei rows are owner shares, summed by Site ID. Sites are matched to GEM plants in the same
country by company and location name (rapidfuzz). Linked sites/plants form groups
(connected components). Per group: 2019 emissions, capacity, production, route class.
Intensity = emissions / production, else / capacity (biased low below full utilisation).
Spread by country x route: weighted median, P10, P90, robust CV (P90-P10)/(2*1.2816*med).

Usage:
  python scripts/match_lei_gem.py --lei ... --gem ... --out Data/processed/lei_gem
"""
import argparse, collections, csv, math, os, re, statistics
import openpyxl
from rapidfuzz import fuzz

ISO_TO_GEM = {"CHN": "China", "IND": "India", "TUR": "Türkiye", "VNM": "Vietnam",
              "RUS": "Russia", "KOR": "South Korea", "JPN": "Japan", "UKR": "Ukraine",
              "IRN": "Iran", "TWN": "Taiwan", "BRA": "Brazil", "ZAF": "South Africa",
              "USA": "United States", "GBR": "United Kingdom", "EGY": "Egypt"}

STOP = {"group", "grp", "co", "ltd", "limited", "company", "corp", "corporation", "inc",
        "plc", "pvt", "private", "holding", "holdings", "the", "and", "of", "industries",
        "industry", "industrial", "jsc", "pjsc", "llc", "sa", "as", "ag", "gmbh", "works",
        "plant", "mill", "mills", "steel", "iron", "metallurgy", "metallurgical", "metal",
        "metals", "celik", "demir", "metalurji", "sanayi", "ticaret", "ve", "enerji",
        "international", "intl", "jsc", "tap", "doan", "cong", "ty", "thep", "jt", "stock",
        "shareholding", "share", "joint", "state", "owned", "ispat", "special", "integrated"}

# Groups whose Lei and GEM names share no tokens.
ALIASES = {
    "anshan": ["angang", "ansteel"],
    "maanshan": ["masteel", "ma steel", "magang"],
    "hebei": ["hbis", "hegang"],
    "baowu": ["baosteel", "china baowu", "wisco", "wuhan"],
    "shagang": ["shagang", "shasteel"],
    "shougang": ["shougang"],
    "benxi": ["bengang", "benxi"],
    "valin": ["hunan valin", "hualing"],
    "tata": ["tata"],
    "jsw": ["jsw", "jindal south west"],
    "sail": ["steel authority of india", "sail"],
    "oyak": ["erdemir", "isdemir", "oyak"],
    "kardemir": ["kardemir", "karabuk"],
    "hoa phat": ["hoa phat"],
    "formosa": ["formosa ha tinh", "formosa"],
}

OPERATING_LIKE = {"operating", "operating pre-retirement", "mothballed",
                  "mothballed pre-retirement", "retired", "idled"}


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\[[^\]]*\]", " ", s)            # drop "[100.0%]"
    s = s.replace("&", " ")
    s = re.sub(r"[^a-z0-9çğıöşüâêôơưăđ ]+", " ", s)
    toks = [t for t in s.split() if t not in STOP and len(t) > 1]
    return " ".join(toks)


def year_of(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v)
    m = re.search(r"(19|20)\d\d", str(v or ""))
    return int(m.group(0)) if m else None


def num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _tok_in(t, toks):
    return any(t == u or (len(t) >= 5 and fuzz.ratio(t, u) >= 90) for u in toks)


def company_score(company, fields, loc_words):
    """Lei company name vs a GEM field. Place-only names need a full owner match or alias."""
    c = norm(company)
    if not c:
        return 0
    ctoks = c.split()
    generic = all(t in loc_words for t in ctoks)
    best = 0
    names, owners = fields[:2], fields[2:]
    for f in (owners if generic else fields):
        f = norm(f)
        if not f:
            continue
        best = max(best, fuzz.token_sort_ratio(c, f))
        if not generic:
            ftoks = f.split()
            distinct = [t for t in ctoks if t not in loc_words]
            if distinct and all(_tok_in(t, ftoks) for t in ctoks):
                best = max(best, 95)
    raw = " ".join((f or "").lower() for f in fields)
    for key, alts in ALIASES.items():
        if key in c:
            if any(a in raw for a in alts):
                best = max(best, 90)
    return best


def location_hit(loc_parts, fields):
    hay = " | ".join((f or "").lower() for f in fields)
    for p in loc_parts:
        p = p.strip().lower()
        if len(p) < 3:
            continue
        if p in hay:
            return True
        for f in fields:
            if f and fuzz.partial_ratio(p, f.lower()) >= 88 and len(p) >= 5:
                return True
    return False


def load_lei(path, countries):
    """Sum owner shares by Site ID. v2 has OwnerName; v1: owner = last comma-separated part."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    has_owner = len(rows[0]) > 4 and str(rows[0][4]).strip().lower() == "ownername"
    sites = {}
    for r in rows[1:]:
        site, name, c, e = r[:4]
        if c not in countries or not isinstance(e, (int, float)):
            continue
        parts = [p.strip() for p in str(name).split(",") if p.strip()]
        if has_owner and r[4]:
            company = str(r[4]).strip()
            loc = [p for p in parts if p.lower() != company.lower() and not p.isdigit()]
        else:
            company = parts[-1] if len(parts) > 1 else parts[0]
            loc = parts[:-1] if len(parts) > 1 else []
        key = (c, site)
        s = sites.setdefault(key, {"iso3": c, "site": site, "location": ", ".join(loc),
                                   "loc_parts": loc, "companies": [], "emissions_mt": 0.0})
        for p in loc:
            if p not in s["loc_parts"]:
                s["loc_parts"].append(p)
        s["location"] = ", ".join(s["loc_parts"])
        s["companies"].append(company)
        s["emissions_mt"] += float(e)
    return list(sites.values())


def load_gem(path, gem_countries):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    pdx = list(wb["Plant data"].iter_rows(values_only=True))
    H = {h: i for i, h in enumerate(pdx[0])}
    plants = {}
    for r in pdx[1:]:
        if not r[0] or r[H["Country/area"]] not in gem_countries:
            continue
        plants[r[0]] = {
            "gem_id": r[0], "country": r[H["Country/area"]],
            "name": r[H["Plant name (English)"]] or "",
            "names": [r[H["Plant name (English)"]], r[H["Other plant names (English)"]]],
            "owners": [r[H["Owner"]], r[H["Parent (English)"]]],
            "loc": [r[H["Municipality"]], r[H["Subnational unit"]], r[H["Location address"]],
                    r[H["Plant name (English)"]]],
            "subnational": r[H["Subnational unit"]] or "",
            "retired": year_of(r[H["Retired date"]]),
            "equipment": r[H["Main production equipment"]] or "",
            "cap": collections.Counter(), "prod2019": None,
        }
    cap = list(wb["Plant capacities and status"].iter_rows(values_only=True))
    C = {h: i for i, h in enumerate(cap[0]) if h}
    cols = {"steel": "Nominal crude steel capacity (ttpa)", "bof": "Nominal BOF steel capacity (ttpa)",
            "eaf": "Nominal EAF steel capacity (ttpa)", "if": "Nominal IF steel capacity (ttpa)",
            "oth_steel": "Other/unspecified steel capacity (ttpa)", "iron": "Nominal iron capacity (ttpa)",
            "bf": "Nominal BF capacity (ttpa)", "dri": "Nominal DRI capacity (ttpa)"}
    for r in cap[1:]:
        p = plants.get(r[0])
        if not p:
            continue
        status = (r[C["Status"]] or "").strip()
        start = year_of(r[C["Start date"]])
        if status not in OPERATING_LIKE or (start and start > 2019):
            continue
        if status == "retired" and p["retired"] and p["retired"] < 2019:
            continue
        for k, col in cols.items():
            p["cap"][k] += num(r[C[col]])
    pr = list(wb["Plant production"].iter_rows(values_only=True))
    for r in pr[1:]:
        p = plants.get(r[0])
        if p and r[2] == "Crude steel production (ttpa)" and isinstance(r[3], (int, float)):
            p["prod2019"] = float(r[3])
    return plants


def route_class(cap):
    steel = cap["bof"] + cap["eaf"] + cap["if"] + cap["oth_steel"]
    if steel <= 0:
        return "iron only" if cap["iron"] > 0 else "unknown"
    bof = cap["bof"] / steel
    ef = (cap["eaf"] + cap["if"]) / steel
    if bof >= 0.8:
        return "BF-BOF"
    if ef >= 0.8:
        return "DRI-EAF/IF" if cap["dri"] > 0 else ("EAF/IF + BF iron" if cap["bf"] > 0 else "scrap-EAF/IF")
    return "mixed"


def wquant(vals, wts, q):
    pairs = sorted(zip(vals, wts))
    tot = sum(wts)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= q * tot:
            return v
    return pairs[-1][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lei", required=True)
    ap.add_argument("--gem", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--countries", nargs="+", default=["CHN", "IND", "TUR", "VNM"])
    ap.add_argument("--company-threshold", type=int, default=88)
    ap.add_argument("--max-candidates", type=int, default=4)
    ap.add_argument("--plausible", nargs=2, type=float, default=[0.05, 5.0],
                    help="t CO2 per t steel capacity outside this range is flagged")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    sites = load_lei(a.lei, set(a.countries))
    gem = load_gem(a.gem, {ISO_TO_GEM[c] for c in a.countries})
    by_country = collections.defaultdict(list)
    for p in gem.values():
        by_country[p["country"]].append(p)

    subnat_words = collections.defaultdict(set)
    for p in gem.values():
        subnat_words[p["country"]] |= set(norm(p["subnational"]).split())
        subnat_words[p["country"]] |= set(norm(str(p["loc"][0] or "")).split())

    # candidate edges
    edges = collections.defaultdict(set)
    tier = {}
    for s in sites:
        cands = by_country[ISO_TO_GEM[s["iso3"]]]
        loc_words = set(norm(" ".join(s["loc_parts"])).split()) | subnat_words[ISO_TO_GEM[s["iso3"]]]
        scored = []
        for p in cands:
            sc = max(company_score(co, p["names"] + p["owners"], loc_words) for co in s["companies"])
            if sc >= a.company_threshold:
                scored.append((p, sc, location_hit(s["loc_parts"], p["loc"])))
        with_loc = [x for x in scored if x[2]]
        if len(with_loc) > a.max_candidates:
            chosen, t = [], f"ambiguous (>{a.max_candidates} plants)"
        elif with_loc:
            chosen, t = with_loc, "company+location"
        elif len(scored) == 1:
            chosen, t = scored, "company only (unique)"
        else:
            chosen, t = [], ("ambiguous company, no location" if scored else "no candidate")
        sid = (s["iso3"], s["site"])
        tier[sid] = t
        for p, sc, _ in chosen:
            edges[sid].add(p["gem_id"])

    # connected components over sites and plants
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        parent[find(x)] = find(y)
    for sid, pids in edges.items():
        for pid in pids:
            union(("S",) + sid, ("P", pid))
    comps = collections.defaultdict(lambda: {"sites": [], "plants": set()})
    for s in sites:
        sid = (s["iso3"], s["site"])
        if edges.get(sid):
            comps[find(("S",) + sid)]["sites"].append(s)
            for pid in edges[sid]:
                comps[find(("S",) + sid)]["plants"].add(pid)

    groups = []
    for gi, (root, g) in enumerate(sorted(comps.items(), key=lambda kv: -sum(x["emissions_mt"] for x in kv[1]["sites"]))):
        plants = [gem[pid] for pid in sorted(g["plants"])]
        cap = collections.Counter()
        for p in plants:
            cap.update(p["cap"])
        E = sum(x["emissions_mt"] for x in g["sites"])
        prod = sum(p["prod2019"] for p in plants) if all(p["prod2019"] is not None for p in plants) else None
        steel_cap = cap["bof"] + cap["eaf"] + cap["if"] + cap["oth_steel"]
        groups.append({
            "group_id": f"G{gi+1:04d}",
            "iso3": g["sites"][0]["iso3"],
            "match_type": "one-to-one" if len(g["sites"]) == 1 and len(plants) == 1 else f"group ({len(g['sites'])} sites : {len(plants)} plants)",
            "lei_sites": "; ".join(str(x["site"]) for x in g["sites"]),
            "lei_names": " | ".join(f"{x['location']}, {'/'.join(x['companies'])}" for x in g["sites"]),
            "match_tiers": "; ".join(sorted({tier[(x['iso3'], x['site'])] for x in g["sites"]})),
            "gem_ids": "; ".join(p["gem_id"] for p in plants),
            "gem_names": " | ".join(p["name"] for p in plants),
            "route_class": route_class(cap),
            "emissions_mt_2019": round(E, 4),
            "gem_steel_cap_kt_2019": round(steel_cap, 1),
            "gem_bof_cap_kt": round(cap["bof"], 1), "gem_eaf_if_cap_kt": round(cap["eaf"] + cap["if"], 1),
            "gem_bf_cap_kt": round(cap["bf"], 1), "gem_dri_cap_kt": round(cap["dri"], 1),
            "gem_crude_prod_kt_2019": round(prod, 1) if prod is not None else "",
            "intensity_per_t_prod": round(E * 1000 / prod, 3) if prod else "",
            "intensity_per_t_cap": round(E * 1000 / steel_cap, 3) if steel_cap > 0 else "",
        })
        ic = groups[-1]["intensity_per_t_cap"]
        groups[-1]["usable"] = ("no: no GEM steel capacity" if ic == "" else
                                "no: implausible ratio (mismatch or scope gap)" if not (a.plausible[0] <= ic <= a.plausible[1]) else
                                "no: large group (>5 sites or plants)" if len(g["sites"]) > 5 or len(plants) > 5 else "yes")

    # site table
    with open(os.path.join(a.out, "lei_sites.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iso3", "lei_site", "location", "companies", "emissions_mt_2019", "match_tier", "gem_ids"])
        for s in sorted(sites, key=lambda x: (x["iso3"], -x["emissions_mt"])):
            sid = (s["iso3"], s["site"])
            w.writerow([s["iso3"], s["site"], s["location"], "/".join(s["companies"]),
                        round(s["emissions_mt"], 4), tier[sid], "; ".join(sorted(edges.get(sid, [])))])
    with open(os.path.join(a.out, "lei_gem_groups.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(groups[0].keys()))
        w.writeheader()
        w.writerows(groups)

    # spread summary
    rows = []
    for basis in ("intensity_per_t_prod", "intensity_per_t_cap"):
        buckets = collections.defaultdict(list)
        for g in groups:
            if g[basis] != "" and g["usable"] == "yes" and g["route_class"] not in ("unknown", "iron only"):
                buckets[(g["iso3"], g["route_class"])].append((g[basis], g["emissions_mt_2019"]))
                buckets[(g["iso3"], "all routes")].append((g[basis], g["emissions_mt_2019"]))
        for (c, r), xs in sorted(buckets.items()):
            v = [x[0] for x in xs]; wts = [x[1] for x in xs]
            med = wquant(v, wts, 0.5); p10 = wquant(v, wts, 0.1); p90 = wquant(v, wts, 0.9)
            rows.append({"basis": basis, "iso3": c, "route_class": r, "n_groups": len(xs),
                         "emissions_mt": round(sum(wts), 2), "w_median": med, "w_p10": p10, "w_p90": p90,
                         "unweighted_median": round(statistics.median(v), 3),
                         "robust_cv": round((p90 - p10) / (2 * 1.2816 * med), 3) if med > 0 and len(xs) >= 3 else ""})
    with open(os.path.join(a.out, "intensity_spread_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # report
    lines = []
    for c in a.countries:
        cs = [s for s in sites if s["iso3"] == c]
        tot = sum(s["emissions_mt"] for s in cs)
        matched = [s for s in cs if edges.get((c, s["site"]))]
        me = sum(s["emissions_mt"] for s in matched)
        tc = collections.Counter(tier[(c, s["site"])] for s in cs)
        gs = [g for g in groups if g["iso3"] == c]
        lines.append(f"{c}: Lei sites {len(cs)} ({tot:.1f} Mt CO2). Matched {len(matched)} sites = "
                     f"{100*me/tot if tot else 0:.1f}% of emissions, in {len(gs)} groups "
                     f"({sum(1 for g in gs if g['match_type']=='one-to-one')} one-to-one). "
                     f"Groups with 2019 production: {sum(1 for g in gs if g['intensity_per_t_prod']!='')}.")
        uc = collections.Counter(g["usable"] for g in gs)
        lines.append("    groups usable for spread: " + ", ".join(f"{k}={v}" for k, v in uc.most_common()))
        lines.append("    tiers: " + ", ".join(f"{k}={v}" for k, v in tc.most_common()))
    with open(os.path.join(a.out, "match_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

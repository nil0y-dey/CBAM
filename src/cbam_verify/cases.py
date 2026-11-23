"""
Structure of the four case trees. All numbers come from Data/.

T1  China, coated-sheet re-roller <- two BF-BOF mills
T2  India, induction-furnace billets <- coal DRI (<- pellets), merchant pig iron
T3  Türkiye, coated-sheet re-roller <- scrap-EAF mill, BF-BOF mill
T4  China, aluminium fabricator <- primary smelter, secondary remelter (illustrative)
"""
from .params import load_assumptions, load_priors, load_mass_coefficients, read_csv, PROCESSED, YEARS
from .tables import CBAMTables
from .trees import NodeSpec, build_tree

# CN codes of goods made on site (Column A)
SLAB = "72071210"       # slab
PIG_IRON = "72011011"
SINTER = "26011200"


def charge_shares(country, furnace):
    """Charge mix (fractions) from gem_charge_mix.csv."""
    r = next(x for x in read_csv(PROCESSED / "gem_charge_mix.csv")
             if x["country"] == country and x["furnace"] == furnace)
    f = lambda k: float(r[k] or 0) / 100.0
    return {"dri_type": f("pct_DRI") + f("pct_HBI") + f("pct_sponge_iron"),
            "pig_iron": f("pct_merchant_pig_iron") + f("pct_granulated_pig_iron") + f("pct_pig_iron_unspecified"),
            "scrap": f("pct_scrap"), "other": f("pct_other_iron")}


def comext_tonnes(origin_iso2, cn8, year="2025"):
    for r in read_csv(PROCESSED / "comext_eu_imports.csv"):
        if r["origin_iso2"] == origin_iso2 and r["cn8"] == cn8 and r["year"] == year:
            return float(r["tonnes"])
    return 0.0


def build_all(years=YEARS):
    tables, priors, A = CBAMTables(), load_priors(), load_assumptions()
    mc = load_mass_coefficients()
    pig_per_semis = mc[("pig iron", "semis (crude steel)")]                    # 0.94
    semis_per_hr = mc[("semis (crude steel)", "hot-rolled flat and long products")]  # 1.03
    hr_per_coated = mc[("hot-rolled coil", "coated coil (7210)")]              # 1.04
    sinter_per_pig = mc[("sinter", "pig iron")]                                # 1.09
    charge_per_semis = mc[("metallic charge (scrap + DRI + pig iron)", "semis (crude steel)")]  # 1.13
    pellets_per_dri = mc[("pellets", "DRI")]                                   # 1.40

    # made on site in a BF-BOF mill, per t HRC
    bfbof_internal = [(SLAB, "C", semis_per_hr),
                      (PIG_IRON, "", semis_per_hr * pig_per_semis),
                      (SINTER, "", semis_per_hr * pig_per_semis * sinter_per_pig)]
    eaf_internal = [(SLAB, "E", semis_per_hr)]

    trees = {}

    # T1
    share_a, share_b = 0.6, 0.4
    t1 = [
        NodeSpec("R", "Re-roller: cold rolling and galvanising", "", "72104900", "China", "", 1.0,
                 "cold_rolling_coating", "medium", own=True),
        NodeSpec("M1", "Integrated BF-BOF mill A (60% of coil)", "R", "72083900", "China", "C",
                 hr_per_coated * share_a, "integrated_bfbof_hrc", "large", internal=bfbof_internal),
        NodeSpec("M2", "Integrated BF-BOF mill B (40% of coil)", "R", "72083900", "China", "C",
                 hr_per_coated * share_b, "integrated_bfbof_hrc", "large", internal=bfbof_internal),
    ]
    trees["T1"] = build_tree(
        "T1", "China: galvanised coil from two integrated mills",
        "Verifying the re-roller alone adds about 0.1 certificates per tonne, but it unlocks two "
        "suppliers whose verification removes about 1.6 per tonne: China's default sits far above "
        "plant estimates (verify-to-unlock).",
        "iron and steel", "China", t1, tables, priors, A, years,
        comext_note=f"EU imports of 7210 49 00 from China, 2025: {comext_tonnes('CN', '72104900')/1e3:,.0f} kt")

    # T2
    mix = charge_shares("India", "IF")
    t2 = [
        NodeSpec("R", "Induction furnace and billet caster", "", "72071116", "India", "D", 1.0,
                 "induction_furnace_billet", "medium", own=True),
        NodeSpec("DRI", "Coal-based DRI plant", "R", "72031000", "India", "",
                 round(mix["dri_type"] * charge_per_semis, 4), "coal_dri", "medium",
                 note=f"DRI-type share of charge {mix['dri_type']:.3f} (GEM, induction furnaces, India)"),
        NodeSpec("PEL", "Pellet plant", "DRI", "26011200", "India", "", pellets_per_dri,
                 "pellet_plant", "medium"),
        NodeSpec("PIG", "Merchant blast furnace", "R", "72011011", "India", "",
                 round(mix["pig_iron"] * charge_per_semis, 4), "merchant_bf_pig_iron", "small",
                 internal=[(SINTER, "", sinter_per_pig)],
                 note=f"pig-iron share of charge {mix['pig_iron']:.3f} (GEM, induction furnaces, India)"),
    ]
    trees["T2"] = build_tree(
        "T2", "India: induction-furnace billets from coal DRI and merchant pig iron",
        "At prior means, verifying the whole chain raises certificates until 2028: the default path "
        "keeps the BF-BOF benchmark, while actual values get the much smaller DRI-route benchmarks. "
        "It saves only from 2029 as the CBAM factor falls (a timing case); before then only the "
        "spread and the option to withhold can make verification worth it.",
        "iron and steel", "India", t2, tables, priors, A, years,
        comext_note=f"EU imports of 7207 11 16 from India, 2025: {comext_tonnes('IN', '72071116')/1e3:,.0f} kt")

    # T3
    t3 = [
        NodeSpec("R", "Re-roller: cold rolling and galvanising", "", "72104900", "Türkiye", "", 1.0,
                 "cold_rolling_coating", "medium", own=True),
        NodeSpec("EAF", "Scrap-EAF flat mill (50% of coil)", "R", "72083900", "Türkiye", "E",
                 hr_per_coated * 0.5, "scrap_eaf_hrc", "large", internal=eaf_internal),
        NodeSpec("BF", "Integrated BF-BOF mill (50% of coil)", "R", "72083900", "Türkiye", "C",
                 hr_per_coated * 0.5, "integrated_bfbof_hrc", "large", internal=bfbof_internal),
    ]
    trees["T3"] = build_tree(
        "T3", "Türkiye: galvanised coil from a scrap-EAF mill and an integrated mill",
        "Türkiye's default is set on the BF-BOF route, so the scrap-EAF supplier gains about three "
        "times as much per tonne as the BF-BOF supplier, even after losing almost all of its "
        "benchmark deduction. In 2026, at prior means, the BF-BOF supplier repays its "
        "verification only above about 7 kt of exports a year.",
        "iron and steel", "Türkiye", t3, tables, priors, A, years,
        comext_note=f"EU imports of 7210 49 00 from Türkiye, 2025: {comext_tonnes('TR', '72104900')/1e3:,.0f} kt")

    # T4
    t4 = [
        NodeSpec("R", "Fabricator: extrusion and structures", "", "76109090", "China", "", 1.0,
                 "aluminium_fabrication", "medium", own=True),
        NodeSpec("PRI", "Primary smelter (70% of metal)", "R", "76011090", "China", "K", 0.7,
                 "primary_smelter", "large"),
        NodeSpec("SEC", "Secondary remelter (30% of metal)", "R", "76011090", "China", "L", 0.3,
                 "secondary_remelter", "small"),
    ]
    trees["T4"] = build_tree(
        "T4", "China: aluminium structures from primary and secondary metal (illustrative)",
        "Both suppliers face the same default. The recycled metal's benchmark is 0.091 against "
        "1.423 for primary metal, which offsets about 40% of its emission gain, yet it still gains "
        "more than twice as much per tonne of metal.",
        "aluminium", "China", t4, tables, priors, A, years,
        comext_note=f"EU imports of 7610 90 90 from China, 2025: {comext_tonnes('CN', '76109090')/1e3:,.0f} kt")
    return trees

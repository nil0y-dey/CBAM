"""Policy paths and model assumptions, read from Data/parameters/."""
import csv
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "Data" / "parameters"
PROCESSED = ROOT / "Data" / "processed"
YEARS = list(range(2026, 2035))


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    return float(v) if v not in ("", None) else None


@dataclass
class Policy:
    """CBAM paths + price scenario: m (mark-up), cf, cscf, price (EUR/t)."""
    cbam_factor: dict
    markup: dict
    cscf_by_year: dict
    prices: dict = field(default_factory=dict)
    scenario: str = "futures"

    def m(self, year):
        return self.markup[year]

    def cf(self, year):
        return self.cbam_factor[year]

    def cscf(self, year):
        # 1.0 for 2026-30 (Decision 2026/1862), assumed after
        return self.cscf_by_year.get(year, 1.0)

    def deduction(self, year):
        return self.cf(year) * self.cscf(year)

    def price(self, year, scenario=None):
        return self.prices[scenario or self.scenario][year]


def load_policy(scenario="futures", params_dir=PARAMS):
    rows = read_csv(params_dir / "policy_parameters.csv")
    cf, markup, cscf = {}, {}, {}
    for r in rows:
        p, period, v = r["parameter"], r["period"], _num(r["value"])
        if p == "cbam_factor":
            cf[int(period)] = v
        elif p == "default_markup":
            if period.endswith("+"):
                for y in YEARS:
                    if y >= int(period[:-1]):
                        markup[y] = v
            else:
                markup[int(period)] = v
        elif p == "cscf" and v is not None:
            a, b = (int(x) for x in period.split("-"))
            for y in range(a, b + 1):
                cscf[y] = v
    prices = {}
    for r in read_csv(params_dir / "price_scenarios.csv"):
        prices.setdefault(r["scenario"], {})[int(r["year"])] = float(r["price_eur_per_t"])
    missing = [y for y in YEARS if y not in cf or y not in markup]
    if missing:
        raise ValueError(f"policy paths missing years {missing}")
    return Policy(cf, markup, cscf, prices, scenario)


def load_assumptions(params_dir=PARAMS):
    """parameter -> {'low', 'central', 'high', 'unit', 'source'}"""
    out = {}
    for r in read_csv(params_dir / "model_assumptions.csv"):
        out[r["parameter"]] = {"low": _num(r["value_low"]), "central": _num(r["value_central"]),
                               "high": _num(r["value_high"]), "unit": r["unit"], "source": r["source"]}
    return out


def load_priors(params_dir=PARAMS):
    """(key, country) -> row of prior_means.csv"""
    return {(r["key"], r["country"]): r for r in read_csv(params_dir / "prior_means.csv")}


def load_mass_coefficients(params_dir=PARAMS):
    """(from_good, to_good) -> coefficient"""
    out = {}
    for r in read_csv(params_dir / "mass_coefficients.csv"):
        if r["coefficient"] and "-" not in r["coefficient"]:
            out[(r["from_good"], r["to_good"])] = float(r["coefficient"])
    return out

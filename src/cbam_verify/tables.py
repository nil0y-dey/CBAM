"""Look-ups into the processed CBAM tables (default values and benchmarks)."""
import re
from .params import PROCESSED, read_csv


def period_of(year):
    """Benchmark period for a year. 2031+ not published: use 2028-30."""
    return "2026-27" if year <= 2027 else "2028-30"


class CBAMTables:
    def __init__(self, processed_dir=PROCESSED):
        self.defaults = {(r["origin"], r["cn8"]): r
                         for r in read_csv(processed_dir / "defaults_with_benchmarks.csv")}
        self.bm = {}
        for r in read_csv(processed_dir / "benchmarks_long.csv"):
            key = (r["cn8"], r["column"], r["route"], r["period"])
            self.bm[key] = float(r["benchmark_tco2e_per_t"])

    def default(self, origin, cn8):
        """Base default value (before mark-up) and the route letter its benchmark uses."""
        r = self.defaults.get((origin, cn8))
        if r is None:
            raise KeyError(f"no default value for {cn8} from {origin}")
        if r["default_value_flag"] not in ("", "value"):
            raise ValueError(f"default for {cn8} from {origin} is '{r['default_value_flag']}'")
        letters = re.findall(r"\(([A-Z])\)", r["default_route_indicator"] or "")
        return float(r["default_total_tco2e_per_t"]), (letters[0] if letters else "")

    def benchmark(self, cn8, column, route, year):
        """Column 'A' or 'B' benchmark; route-specific if there is one, else generic."""
        period = period_of(year)
        for rt in ([route] if route else []) + [""]:
            for per in (period, "all"):
                v = self.bm.get((cn8, column, rt, per))
                if v is not None:
                    return v
        raise KeyError(f"no column {column} benchmark for {cn8} route '{route}' in {period}")

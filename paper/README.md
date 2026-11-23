# paper/ — additional analyses for "Verify or Default"

This folder holds the code and results for the analyses in the paper that go beyond
the core models in `src/cbam_verify` and `scripts/`: the two declaration protocols,
the regime map, verifier limits under deferred declaration, break-even costs and
volumes, and the scalability tests. The manuscript itself is not part of this
repository.

## Files

| File / folder | What it is |
|---|---|
| `code/deferred.py` | Solvers for deferred declaration: one year (`solve_year`) and several years with a yearly choice of declared data (`solve_years`), plus simulation and the full-information bound. A module used by the scripts below. |
| `code/make_extra_results.py` | Commitment, deferred declaration and full information for the four calibrated trees; yearly choice; start-year curves; verification order in T2 |
| `code/regime_map.py` | Regime map for a two-installation chain, and the position of each calibrated tree on it |
| `code/m2_deferred_and_breakeven.py` | Verifier slots and the deadline under deferred declaration; break-even costs and volumes |
| `code/scalability.py` | Random trees: run times, index rules against the exact M2 optimum, deferral against commitment |
| `code/make_figures_tables.py` | Builds the paper's figures and table bodies into `figures/` and `tables/` |
| `results_extra/` | CSV output of the four analysis scripts |

## Run

From `paper/code/`, after installing the repository's `requirements.txt`:

```
python3 make_extra_results.py          # about 35 s
python3 regime_map.py                  # about 1 s
python3 m2_deferred_and_breakeven.py   # about 10 s
python3 scalability.py                 # about 80 s
python3 make_figures_tables.py         # writes ../figures and ../tables
```

Inside the repository the scripts find `src/cbam_verify` and `Data/` on their own; to
use a checkout elsewhere, pass its path as the first argument. Random seeds are fixed,
so the CSV files are reproduced exactly, except the run times in `scal_runtime.csv`
and `scal_m2_large.csv`, which depend on the machine.

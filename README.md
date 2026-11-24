# Verify or Default: Optimal Emissions Verification in Multi-Tier Supply Chains under the EU CBAM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24486312.svg)](https://doi.org/10.5281/zenodo.24486312)

Data and code for the paper *"Verify or Default: Optimal Emissions Verification in
Multi-Tier Supply Chains under the EU Carbon Border Adjustment Mechanism"* by
Niloy Dey (Department of Industrial and Production Engineering, Shahjalal University
of Science and Technology, Bangladesh). The repository reproduces every number,
table and figure in the paper and its online supplement.

## Summary

Since 1 January 2026, EU importers of steel, aluminium and other CBAM goods pay for
the emissions embedded in those goods. Actual emissions count only after an accredited
verifier has checked them at the producing installation; otherwise country default
values apply, marked up by 10% in 2026, 20% in 2027 and 30% from 2028. A default at
any step of the supply chain covers, and so blocks, the actual values of everything
upstream of it.

The paper models an exporter's choice of which installations in its supply chain to
have verified, in what order, from which year and with how many verifiers. Each model
is studied under two declaration protocols: **commitment**, where the exporter decides
whether to use each result as it arrives, and **deferred declaration**, where it chooses
the declared data once all results are in.

| Model | Question | Method |
|---|---|---|
| M0 | Which installations to verify in one compliance year | Closed-form tree recursion (commitment); dynamic program (deferred declaration) |
| M1 | When to start verifying each installation, 2026–2034 | Recursion over start years (commitment); dynamic program over years (deferred declaration) |
| M2 | What limited verifier slots and the declaration deadline cost | Exact dynamic program over installation statuses; simple scheduling rules |

The models are calibrated to the 2026 EU default values and benchmarks for four supply
chains: coated steel from China (T1), billets from India (T2), coated steel from
Türkiye (T3) and aluminium structures from China (T4).

## Quick start

Requires Python 3.10 or later.

```bash
git clone https://github.com/nil0y-dey/CBAM.git
cd CBAM
pip install -r requirements.txt
```

Rebuild everything, from the raw data to the paper's tables and figures, in this order:

```bash
# 1. Data pipeline: raw files -> Data/processed/ and Data/trees/
python scripts/extract_cbam_tables.py \
  --defaults "Data/raw/cbam_tables/DV correcting act_final update_06.08.xlsx" \
  --benchmarks "Data/raw/cbam_tables/CBAM Benchmarks_20260206.xlsx" \
  --out Data/processed
python scripts/match_lei_gem.py \
  --lei Data/raw/lei2023/PlantEmission_v2.xlsx \
  --gem "Data/raw/gem/Plant-level data - Global Iron and Steel Tracker - September 2026 (V1).xlsx" \
  --out Data/processed/lei_gem
python scripts/process_comext.py --inputs "Data/raw/comtext/*.csv" --out Data/processed
python scripts/gem_charge_mix.py \
  --gem-units "Data/raw/gem/Steel unit data - Global Iron and Steel Tracker - September 2026 (V1).xlsx" \
  --out Data/processed
python scripts/build_trees.py --scenario futures

# 2. Core models -> Data/results/
python scripts/run_m0.py
python scripts/run_m1.py
python scripts/run_m2.py

# 3. Protocols, regime map, break-evens and scalability -> paper/results_extra/
cd paper/code
python make_extra_results.py
python regime_map.py
python m2_deferred_and_breakeven.py
python scalability.py

# 4. Tables and figures of the paper -> paper/tables/ and paper/figures/
python make_figures_tables.py
```

The five notebooks in `notebooks/` walk through the same steps with explanations and
charts. Random seeds are fixed, so all results are reproduced exactly, except the run
times reported in the scalability tests, which depend on the machine.

## Where each result comes from

| In the paper | Produced by | Output files |
|---|---|---|
| Calibrated chains (Figure 2, Table 3; Tables S1–S2) | `scripts/build_trees.py` | `Data/trees/`, `Data/parameters/` |
| One compliance year (Table 4, Figures 3–4) | `scripts/run_m0.py`, `paper/code/make_extra_results.py` | `Data/results/m0_*.csv`, `paper/results_extra/protocol_m0.csv`, `withhold_distance.csv` |
| Commitment versus deferred declaration (Table 5) | `paper/code/make_extra_results.py` | `paper/results_extra/protocol_m0.csv` |
| Regime map (Figure 5) | `paper/code/regime_map.py` | `paper/results_extra/regime_map.csv`, `regime_points.csv` |
| Start years (Table 6, Figure 6; Tables S4, S6) | `scripts/run_m1.py`, `paper/code/make_extra_results.py` | `Data/results/m1_*.csv`, `paper/results_extra/protocol_m1.csv`, `m1_start_curves.csv`, `t2_yearly_*.csv` |
| Verifier slots and the deadline (Table 7, Figure 7; Tables S5, S7) | `scripts/run_m2.py`, `paper/code/m2_deferred_and_breakeven.py` | `Data/results/m2_*.csv`, `paper/results_extra/m2_deferred.csv` |
| Break-even costs and volumes (Table S3) | `paper/code/m2_deferred_and_breakeven.py` | `paper/results_extra/breakeven.csv` |
| Tests on random chains (Section 6.7; Table S8) | `paper/code/scalability.py` | `paper/results_extra/scal_*.csv` |

`paper/code/make_figures_tables.py` turns these files into the paper's tables and
figures. Section, table and figure numbers refer to the paper and its online supplement.

## Repository layout

```
Data/
  raw/          third-party source files (see Data/SOURCES.md for sources and licences)
  parameters/   policy parameters and assumptions entered by hand, each with its source
  processed/    tables produced by the data scripts
  trees/        the four calibrated supply chains (JSON and CSV)
  results/      results of models M0, M1 and M2, with sensitivity runs
  SOURCES.md    where every data file comes from
scripts/
  extract_cbam_tables.py   default values and benchmarks -> tidy tables
  match_lei_gem.py         plant emissions (Lei et al. 2023) matched to Global Energy Monitor plants
  process_comext.py        Eurostat Comext EU imports -> tidy tables
  gem_charge_mix.py        scrap, DRI and pig-iron shares of arc and induction furnaces
  build_trees.py           builds the calibrated supply chains
  run_m0.py, run_m1.py, run_m2.py   solve the three models with baselines and sensitivity runs
src/cbam_verify/
  params.py, tables.py     policy paths, assumptions and table look-ups
  trees.py                 supply-chain structure, certificates owed, break-even intensities
  cases.py                 the four calibrated chains
  m0.py                    one compliance year under commitment, baselines, simulation
  m1.py                    start years 2026-2034 under commitment
  m2.py                    verifier slots, verification times and the deadline
paper/
  code/                    deferred declaration, regime map, break-evens, scalability, tables and figures
  results_extra/           outputs of the scripts in paper/code/
  README.md                details of the paper/ folder
tests/
  test_m0.py, test_m1.py, test_m2.py   checks against simulation, brute force and analytical bounds
notebooks/
  01_data_pipeline.ipynb ... 05_model_m2.ipynb
```

## Tests

```bash
python tests/test_m0.py
python tests/test_m1.py
python tests/test_m2.py
```

The tests check each model against Monte Carlo simulation, brute-force enumeration on
small trees and the bounds proved in the paper.

## Data

All input data are public. `Data/SOURCES.md` lists every file with its source, version,
licence and use: the EU default values and benchmarks (Implementing Regulations (EU)
2025/2620 and 2025/2621, as corrected), the JRC report on default emission intensities,
the Global Energy Monitor Global Iron and Steel Tracker, plant-level emissions from
Lei et al. (2023, *Nature*) and Eurostat Comext trade data.

## Citation

Please cite the paper and this archive:

> Dey, N. (2026). *CBAM: data and code for "Verify or Default"* [Software].
> Zenodo. https://doi.org/10.5281/zenodo.24486312

Machine-readable metadata are in `CITATION.cff`. Please also cite the original data
sources listed in `Data/SOURCES.md`.

## Licence

Code: MIT licence (see `LICENSE`). Data files in `Data/raw/` keep their original
licences (CC BY 4.0 or the European Commission's reuse policy).

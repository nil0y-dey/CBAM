# Data sources

Every file in `Data/raw/` comes from a third party and keeps its own licence.
All of them allow redistribution with credit. If you reuse a file, cite the
original source below, not only this repository.

## Raw files

| Folder / file | What it is | Source | Version / date | Licence | Used for |
|---|---|---|---|---|---|
| `raw/cbam_tables/DV correcting act_final update_06.08.xlsx` | Country-specific CBAM default values, one sheet per origin, plus Annex IV (unknown origin) and "Other countries and territories" | European Commission, IR (EU) 2025/2621 as corrected by IR (EU) 2026/1740 | update of 6 Aug 2026 | EU reuse policy (Decision 2011/833/EU, CC BY 4.0) | Default values D by origin and CN code |
| `raw/cbam_tables/CBAM Benchmarks_20260206.xlsx` | CBAM benchmarks, Column A (actual values) and Column B (default values), with production-route indicators | European Commission, IR (EU) 2025/2620 Annex | version history says 6 Feb 2025; file name says 2026 | EU reuse policy (CC BY 4.0) | Free-allocation benchmarks BMa, BMd |
| `raw/legal/eli_reg_impl_2025_2620_oj_EN_TXT.pdf` | IR (EU) 2025/2620: free allocation adjustment and benchmarks | EUR-Lex | OJ 22 Dec 2025 | EU reuse policy (CC BY 4.0) | Route legend, SEFA equations |
| `raw/legal/OJ_L_202502547_EN_TXT.pdf` | IR (EU) 2025/2547: methodology for embedded emissions | EUR-Lex | adopted 10 Dec 2025 | EU reuse policy (CC BY 4.0) | CN-code categories, precursor rule |
| `raw/jrc/JRC134682_01.pdf` | JRC report on default emission intensities by country and product | Joint Research Centre, European Commission | 2023 | CC BY 4.0 | Mass coefficients, route-specific crude steel intensities |
| `raw/gem/*.xlsx` (3 files) | Global Iron and Steel Tracker: plant, steel-unit and iron-unit data | Global Energy Monitor | September 2026 (V1) | CC BY 4.0 | Plant capacity, route, 2019 production |
| `raw/lei2023/PlantEmission.xlsx` | Plant-level CO2 emissions, 2019 (Mt) | Lei et al. (2023), *Nature* 622, 514–520; Zenodo 10.5281/zenodo.7895711 | v1 | CC BY 4.0 | Superseded by v2 (identical numbers) |
| `raw/lei2023/PlantEmission_v2.xlsx` | Same as v1 plus an `OwnerName` column | as above | v2 | CC BY 4.0 | Plant-level emissions matched to GEM |
| `raw/lei2023/Lei2023_SI.pdf` | Supplementary Information of Lei et al. (2023) | *Nature* article page | 2023 | publisher's terms (free to read) | Emission boundary: direct emissions from unit capacities, activity rates and default emission factors per process (Table S5, section 1.8) |
| `raw/comtext/estat_ds-045409_filtered_en_2024.csv`, `..._2025.csv` | EU27 imports from China, India, Türkiye and Viet Nam, all CN codes, tonnes and euros | Eurostat Comext, dataset DS-045409 (SDMX API) | data updated 13 Nov 2026 | Eurostat reuse policy (CC BY 4.0) | Export volumes for the case trees |

Recommended citations:

- Global Energy Monitor, Global Iron and Steel Tracker, September 2026 (V1) release.
- Lei, T., Wang, D., Yu, X., et al. (2023). Global iron and steel plant CO2 emissions and carbon-neutrality pathways. *Nature*, 622, 514–520. https://doi.org/10.1038/s41586-023-06486-7
- Joint Research Centre (2023). JRC134682.
- Commission Implementing Regulations (EU) 2025/2547, 2025/2620, 2025/2621 and 2026/1740.

## Parameter files (`Data/parameters/`)

These are typed in by hand from legal texts and published figures. Each row
names its source.

| File | Contents |
|---|---|
| `policy_parameters.csv` | CBAM factor 2026–2034, default mark-ups, quarterly certificate prices 2026, cross-sectoral correction factor (100% for 2026–2030, Decision 2026/1862) |
| `mass_coefficients.csv` | Tonnes of precursor per tonne of product (JRC134682, p. 14 and p. 78) |
| `route_reference_intensities.csv` | Crude steel direct and indirect intensity by route and country, read off JRC Figures 56–57 (±0.1) |
| `prior_means.csv` | Expected direct emissions of each installation type in the case trees, with the JRC table or figure each comes from |
| `price_scenarios.csv` | Certificate price paths 2026–2034: flat, futures-anchored, high |
| `model_assumptions.csv` | Verification costs and times, success probability, prior spreads, pass-through share, export volumes, discount rate, verifier slots and window, carbon price paid (zero), EUA price anchors, status of the 2027 benchmark update |

## Processed files (`Data/processed/`)

Produced by the scripts; rerun `notebooks/01_data_pipeline.ipynb` to rebuild them.

| File | Made by | Contents |
|---|---|---|
| `defaults_long.csv` | `scripts/extract_cbam_tables.py` | Default values by origin and CN code (iron and steel, aluminium) |
| `benchmarks_long.csv` | same | Benchmarks by CN code, column, route and period |
| `defaults_with_benchmarks.csv` | same | Defaults joined to Column A and B benchmarks for 2026–27 and 2028–30, with goods category |
| `extraction_report.txt` | same | Row counts and match quality |
| `lei_gem/lei_sites.csv` | `scripts/match_lei_gem.py` | Lei sites (owner shares summed) and their match status |
| `lei_gem/lei_gem_groups.csv` | same | Matched groups: emissions, GEM capacity and production, route class, intensity |
| `lei_gem/intensity_spread_summary.csv` | same | Within-country spread of intensity by route |
| `lei_gem/match_report.txt` | same | Match coverage by country |
| `comext_eu_imports.csv` | `scripts/process_comext.py` | EU imports by year, origin and CN8 code (chapters 72, 73, 76 and 2601 12 00), tonnes and euros |
| `comext_by_category.csv` | same | The same totalled by goods category |
| `gem_charge_mix.csv` | `scripts/gem_charge_mix.py` | Scrap, DRI and pig-iron shares of arc and induction furnaces by country |

## Calibrated trees (`Data/trees/`)

Made by `scripts/build_trees.py` from the files above; the structure of each tree is in `src/cbam_verify/cases.py`.

| File | Contents |
|---|---|
| `T1.json` … `T4.json` | Full calibrated tree: nodes, masses, defaults, benchmarks by year, priors, costs, volume |
| `nodes.csv` | One row per node with its static parameters |
| `node_gains.csv` | Gain per tonne and expected annual saving per node, 2026–2034 (futures prices) |
| `tree_totals.csv` | Certificates per tonne with no verification and with every node verified, by year |

## Model results (`Data/results/`)

Made by `scripts/run_m0.py`, `scripts/run_m1.py` and `scripts/run_m2.py` from the calibrated trees (central assumptions unless stated).

| File | Contents |
|---|---|
| `m0_base.csv` | Per tree and year: value of the M0 plan and of each baseline, perfect-information bound, value of the withhold option, verification spend, simulation check with the zero floor |
| `m0_plans.csv` | Per tree, year and node: verify or not, the emission level below which the result is used, chance of being reached and used |
| `m0_sweeps.csv` | One-at-a-time sensitivity to supplier spread, volume, price scenario, verification cost, success probability and pass-through |
| `m1_base.csv` | Per tree: present value (2026 euros) of the M1 plan and of the baselines, value of waiting and of withholding, start year of every node, simulation check (made by `scripts/run_m1.py`) |
| `m1_plans.csv` | Per tree and node: start year, emission level below which the result is used, value of starting in each year |
| `m1_sweeps.csv` | One-at-a-time sensitivity to discount rate, set-up cost, price scenario, supplier spread, volume and success probability |
| `m2_grid.csv` | Per tree, year (2026, 2030), number of slots, window and verification-time scale: value of the optimal policy and of the sequential and speculative (parallel) rules, M0 value, cost of the limits per tonne, expected and wasted spend (made by `scripts/run_m2.py`) |
| `m2_usage.csv` | Per tree, setting and node: probability that the node's data are in use at the deadline under the optimal policy |

## Not yet added

- Updated CBAM benchmarks applying from 1 January 2027 (not published as of 16 November 2026).
- 2026-Q4 certificate price (due early January 2027).

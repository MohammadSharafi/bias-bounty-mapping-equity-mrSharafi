# Bias Bounty: Mapping Equity Challenge — mrSharafi

Entry for the Zindi Bias Bounty Mapping Equity Challenge (Humane Intelligence, Radiant Earth). Zindi user **mrSharafi**;
associated leaderboard submissions `RzkTLsFj` (c3, fully reproducible from this repository) and `2gyMPZPa` (k84).

| Writeup | File |
|---|---|
| **Best Bias Discovery** — a third of fire stations are missing from Overture, most of all in wildfire country and Oklahoma's tribal areas | [docs/BEST_BIAS_DISCOVERY_mrSharafi.pdf](docs/BEST_BIAS_DISCOVERY_mrSharafi.pdf) ([Markdown](docs/BEST_BIAS_DISCOVERY.md)) |
| **Best Documentation** — predicting map coverage gaps without the answer key | [docs/BEST_DOCUMENTATION_mrSharafi.pdf](docs/BEST_DOCUMENTATION_mrSharafi.pdf) ([Markdown](docs/BEST_DOCUMENTATION.md)) |

## Setup

Python 3.10, packages in `requirements.txt` (`make env`), plus matplotlib and fontTools for the figures. Challenge data
(permitted layers only) goes in `data_public/` with the same layout as the organisers' bucket:

```
aws s3 sync --no-sign-request s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/reference/ data_public/reference/
aws s3 sync --no-sign-request s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/strata/ data_public/strata/
```

`./check_compliance.sh` verifies that `model/` reads no removed reference layer.

## Reproduce the Bias Discovery (about 3 minutes)

The fire-station, school and hospital lists come from the public USGS National Structures Dataset (public domain);
snapshots retrieved 2026-11-01 are committed in `data_public/external/`.

```
.venv/bin/python research/fetch_usgs_stations.py                       # optional re-fetch (the live service changes)
PYTHONPATH=. .venv/bin/python research/discovery_stations.py           # stations.csv / .json, tables
python3 research/discovery_robust.py                                   # robust.json
PYTHONPATH=. .venv/bin/python research/discovery_checks.py             # checks.json
.venv/bin/python research/discovery_meta_baseline.py                   # meta_baseline.json
python3 research/discovery_figures_v3.py                               # figures
python3 research/check_entry_numbers.py                                # must print NUMBERS OK
./research/build_entry_pdf.sh                                          # rebuild the writeup PDF
```

## Reproduce the clean final submission c3 (`RzkTLsFj`, about 5 seconds)

`submissions2/` holds our own scored uploads and `submissions2/ledger.csv` their public scores; `out2/` holds the
per-tract features built by `model/features*.py` from the permitted layers.

```
PYTHONPATH=. python3 research/clean_fit.py --out c1_clean_fit
PYTHONPATH=. python3 -c "from model import probe as pr; pr.calibrate_regions('c1_clean_fit', 'c2_clean_regions'); pr.calibrate('c2_clean_regions', 'c3_clean_regions_grp05', 0.5)"
PYTHONPATH=. python3 -m model.check_submission submissions2/c3_clean_regions_grp05.csv
```

The rebuilt `c1`, `c2` and `c3` are byte-identical to the uploaded files. `k84` also depends on scored files that other
teams published, so it is not reproduced here; the documentation says so.

## Licences

Code: MIT (see `LICENSE`). Challenge data and files derived from it: CC BY-SA 4.0. USGS National Structures Dataset:
public domain. Overture Maps data © OpenStreetMap contributors and the Overture Maps Foundation.

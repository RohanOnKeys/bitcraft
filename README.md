![BitCraft](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/splash.png)

# BitCraft

[![PyPI](https://img.shields.io/pypi/v/bitcraft)](https://pypi.org/project/bitcraft/)
[![Python](https://img.shields.io/pypi/pyversions/bitcraft)](https://pypi.org/project/bitcraft/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/RohanOnKeys/bitcraft/blob/main/LICENSE)

AI-powered monitoring and analysis of Bitcoin transaction traffic, in your terminal.

BitCraft correlates blockchain transactions (wallets, txids, amounts) with network metadata (IPs, ports, timing, GeoIP country and ASN), clusters wallets, scores every transaction with machine learning, and presents ranked, explainable investigative leads in a terminal dashboard. It runs fully offline on Linux, Windows and macOS.

Built for Smart India Hackathon 2026, problem statement SIH26146 (NTRO, Blockchain & Cybersecurity).

---

## Installation

BitCraft needs Python 3.10 or newer.

| Method | Command | What you get |
| --- | --- | --- |
| pipx (recommended) | `pipx install bitcraft` | The `bitcraft` command in its own isolated environment |
| pip | `pip install bitcraft` | The `bitcraft` command |
| From source | `git clone https://github.com/RohanOnKeys/bitcraft && cd bitcraft && pip install -e .` | The TUI plus the ML pipeline and API code |
| Docker (Linux) | `docker compose up --build` | Full stack: pipeline, PostgreSQL, Redis and the API |
| Air-gapped Linux | `python packages/offline_bundle.py` | A bundle with every wheel, image and dataset, installed with `bash install.sh` on a machine with no network |

The pip and pipx packages contain the terminal interface. It connects to a BitCraft API at `http://localhost:8000` and falls back to built-in demo data when none is running. The ML pipeline and API run from a source checkout or Docker (see [Running the full system](#running-the-full-system)).

A Chocolatey package (`choco install bitcraft`) is prepared in [`packages/chocolatey`](https://github.com/RohanOnKeys/bitcraft/tree/main/packages/chocolatey) and not yet published to the community repository.

---

## Quick start

```text
bitcraft demo          # opens BitCraft in a new, large terminal window with demo data
bitcraft               # same, using the API when it is running
bitcraft here          # run inside the current terminal
bitcraft status        # API health, data counts and pipeline status
bitcraft --help        # every command and option
```

Press **Enter** on the home screen, then use **d** dashboard, **t** threats, **g** graph explorer, **w** wallets, **Enter** on an alert for its detail, **Esc** to go back and **q** to quit. A terminal of 160 x 46 characters or larger shows every panel; Windows Terminal, a modern Linux terminal or iTerm2 look best.

![Boot: data source, pipeline and alert checks while BitCraft starts](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/boot.png)

---

## Features

- Bulk ingestion of transaction and network metadata from CSV, JSON, JSON Lines and XML, with per-row validation
- Offline GeoIP enrichment (country, ASN, organisation) from the open DB-IP Lite databases
- Entity graph linking IP addresses, wallet addresses and transactions
- Wallet clustering with the common-input-ownership heuristic, and Louvain transaction communities
- Machine learning detection: a supervised risk model, a metadata model and an Isolation Forest, fused into one score
- Ranked, explainable alerts for transactions and wallets, each with a confidence score, SHAP reasons and evidence tagged real or modeled
- Terminal dashboard with link analysis, threat overview, wallet investigation and alert detail
- Fully offline at runtime; Linux verified end to end with Docker

![Dashboard: KPIs, filters, ranked alerts and a live preview of the selected alert](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/dashboard.png)

---

## How it works

1. **Ingest** CSV, JSON or XML metadata and reject malformed rows with a reason.
2. **Enrich** every source and destination IP with GeoIP country and ASN, and flag Tor-exit and hosting networks.
3. **Build the graph**: addresses, transactions and IPs, plus the 203,769-node transaction graph and its communities.
4. **Cluster wallets**: addresses spent together in one transaction belong to the same owner.
5. **Score**: a gradient-boosted risk model, a metadata model on the correlated network and blockchain features, community illicit ratios and an Isolation Forest are fused into a composite score.
6. **Explain**: SHAP reasons and plain-language evidence for every alert, each item tagged real or modeled.
7. **Serve and show**: results load into SQLite or PostgreSQL behind a read-only FastAPI service that the TUI reads.

No ML code runs at request time; the pipeline writes its results once and the API only reads them.

![Graph explorer: live connectivity graph with timestep, severity, driver and community charts](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/graph.png)

---

## Dataset

The problem statement calls for a synthetic dataset modeled on real Bitcoin P2P and transaction fields. BitCraft generates it (`python -m ml.metadata_generator`) on top of a labeled, Elliptic-derived base dataset, with every minimum field:

| Field | Example |
| --- | --- |
| `timestamp` | `2025-01-01T00:00:51Z` |
| `src_ip`, `dst_ip` | `185.220.101.22`, `81.7.151.252` |
| `src_port`, `dst_port` | `9150`, `8333` |
| `txid` | 64 hex characters |
| `input_addresses[]`, `output_addresses[]` | Bitcoin addresses with valid checksums |
| `input_amounts[]`, `output_amounts[]` | BTC, one per address |
| `fee`, `script_type` | `0.00025`, `p2wpkh` |
| `geo_country`, `asn` | Added offline from DB-IP Lite: `DE`, `AS60729` |

Counts, amounts, fees, timestamps and labels come from the base dataset. Wallets, addresses, routable IPs and ports are synthesised, with laundering typologies planted (with noise) on illicit activity: address reuse, peeling chains, CoinJoin-style mixing, Tor and hosting egress, multi-country IP hopping and round payouts. The 50,000 records ship as CSV, JSON and XML, with GeoIP-enriched versions from `python -m ml.ingest FILE --enrich --out FILE`.

Every dataset (base tables, metadata and the DB-IP Lite GeoIP databases) is attached to each [GitHub release](https://github.com/RohanOnKeys/bitcraft/releases) and fetched with `python -m ml.dataset download`, no Kaggle account needed. To run with no download at all, `python -m ml.synthetic` generates a fully synthetic dataset in the same format.

![Wallets: address clusters with their IPs, ports, GeoIP country and ASN](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/wallets.png)

---

## Results

Held-out timesteps 35 to 49, never seen in training (16,670 labeled transactions, 6.5% illicit):

| Score | AUC | Avg precision | Precision@100 | Precision@500 |
| --- | ---: | ---: | ---: | ---: |
| Isolation Forest alone | 0.197 | 0.037 | 0.00 | 0.00 |
| Risk model alone | 0.940 | 0.803 | 1.00 | 1.00 |
| **Composite (shipped ranking)** | **0.899** | **0.812** | **1.00** | **0.994** |

On the metadata layer the model reaches AUC 0.969, wallet clustering purity is 0.999, and 98% of the top 100 wallet alerts are illicit owners. That layer is synthetic, so those numbers measure recovery of the planted typologies rather than real-world accuracy. The [model card](https://github.com/RohanOnKeys/bitcraft/blob/main/docs/model_card.md) explains the model choice and the leakage guards.

![Threats: posture, top-25 queue with drivers, riskiest communities and coverage gaps](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/threats.png)

---

## Running the full system

From a source checkout:

```text
pip install -r requirements.txt -r backend/requirements.txt
pip install -e .
python -m ml.dataset download          # every dataset, about 235 MB, SHA-256 verified
python -m ml.pipeline                  # about 5 minutes; writes ml/artifacts/
cd backend && python -m app.loader     # loads the results into backend/bitcraft.db
bitcraft                               # starts the API and opens the TUI
```

With no `DATABASE_URL`, the API uses a local SQLite file and Redis is optional. `docker compose up --build` runs the same pipeline on PostgreSQL and Redis and serves the API on port 8000; on a fresh clone it downloads the datasets first. Interactive API docs are at `http://localhost:8000/docs`.

API: `/alerts`, `/alerts/{tx_id}`, `/graph/{tx_id}?depth=`, `/communities`, `/communities/{id}`, `/entities`, `/entities/{id}`, `/entities/{id}/graph`, `/addresses/{address}`, `/ips/{ip}`, `/metadata/{tx_id}`, `/stats/summary`, `/threats/overview`, `/pipeline/status`, `/pipeline/metrics`.

---

## Explainable alerts

Every alert shows its composite score, the weighted drivers behind it, the correlated network and blockchain metadata (txid, source and peer IP:port, GeoIP country and ASN, Tor flag, inputs and outputs, wallet), evidence tagged real or modeled, and SHAP reasons. Missing network evidence is shown as `n/a`, never as low risk.

![Alert detail: composite score, drivers, network and blockchain metadata, evidence and SHAP reasons](https://raw.githubusercontent.com/RohanOnKeys/bitcraft/main/docs/images/detail.png)

---

## Documentation

| Document | Contents |
| --- | --- |
| [User manual](https://github.com/RohanOnKeys/bitcraft/blob/main/docs/user_manual.md) | Install, data, pipeline, API, TUI, offline deployment, troubleshooting |
| [Technical writeup](https://github.com/RohanOnKeys/bitcraft/blob/main/docs/technical_writeup.md) | Approach, model choice, explainability and results |
| [Model card](https://github.com/RohanOnKeys/bitcraft/blob/main/docs/model_card.md) | Models, evaluation protocol, metrics and limitations |
| [Dataset provenance](https://github.com/RohanOnKeys/bitcraft/blob/main/docs/dataset_provenance.md) | What is real, what is synthetic, GeoIP attribution |
| [Submission checklist](https://github.com/RohanOnKeys/bitcraft/blob/main/docs/submission.md) | Each requirement of SIH26146 and where it is met |

---

## Project structure

```text
bitcraft/     terminal interface and the `bitcraft` command (the pip package)
ml/           ingestion, GeoIP, entity graph, models, scoring, explainability, pipeline
backend/      FastAPI service and the artifact loader
packages/     PyPI and Chocolatey packaging, air-gapped bundle builder
docs/         manual, writeup, model card, provenance, screenshots
tests/        ML, backend and TUI tests
datasets/     local data (not in git; `python -m ml.dataset download`)
```

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Data and features | pandas, PyArrow, NetworkX, python-louvain |
| Machine learning | scikit-learn (HistGradientBoosting, Isolation Forest), SHAP |
| GeoIP | DB-IP Lite (MMDB) via maxminddb |
| API and storage | FastAPI, SQLAlchemy, SQLite or PostgreSQL, Redis |
| Terminal interface | Textual, Rich |
| Packaging | PyPI, Chocolatey, Docker Compose |

---

## License

- **Code & Application**: BitCraft is open source under the [Apache License 2.0](https://github.com/RohanOnKeys/bitcraft/blob/main/LICENSE).<br>
  Copyright 2026 The BitCraft Authors: Rohan Pattanayak, Jagadish Prasad Pattanaik, Shreya Mishra, Shreya Mohanty, Ashutosh Badapanda, and Rosalin Nayak. See [NOTICE](https://github.com/RohanOnKeys/bitcraft/blob/main/NOTICE).
- **Datasets & Schemas**: Dataset pipelines, schemas, and synthetic metadata layers are licensed under [Apache License 2.0](https://github.com/RohanOnKeys/bitcraft/blob/main/datasets/LICENSE).<br>
  Copyright 2026 Ashutosh Badapanda. See [datasets/NOTICE](https://github.com/RohanOnKeys/bitcraft/blob/main/datasets/NOTICE).
- **Third-Party Data**: IP geolocation by [DB-IP](https://db-ip.com) (CC BY 4.0). The Elliptic-derived dataset is distributed separately, as release archives, and subject to its upstream research license.


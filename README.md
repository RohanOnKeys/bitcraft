# BitCraft

AI Powered Monitoring & Analysis of Bitcoin Transaction Traffic Software

BitCraft is an offline Bitcoin intelligence platform that correlates blockchain transactions with network metadata to generate explainable investigative leads. It ingests bulk transaction datasets, builds an entity graph linking wallets, IPs, and transactions, applies AI and graph analysis to detect suspicious behavior, and presents prioritized alerts through a terminal-based investigation dashboard (TUI).

The project is designed for Linux and operates entirely offline on synthetic datasets modeled after real Bitcoin transaction and P2P network activity.

---

## Background

Bitcoin's pseudonymous peer to peer architecture enables legitimate financial activity, but it also allows ransomware payments, darknet market proceeds, extortion, and money laundering to move across the network with limited traditional financial oversight.

BitCraft addresses this challenge by combining blockchain layer data with network layer observations. Instead of analyzing transactions in isolation, it reconstructs relationships between wallets, IP addresses, and transaction timing to uncover suspicious patterns that would otherwise remain hidden.

---

## Features

- Bulk ingestion of CSV, JSON, and XML datasets
- Bitcoin transaction and metadata parsing
- Entity graph connecting wallets, IPs, ports, and transactions
- AI powered anomaly detection
- Wallet and transaction clustering
- Explainable alerts with confidence scores
- Terminal-based investigation dashboard (TUI) for link analysis
- Fully offline Linux compatible workflow

---

## Dataset

BitCraft works with synthetic datasets modeled on real Bitcoin transaction fields.

### Supported Fields

- `timestamp`
- `src_ip`
- `dst_ip`
- `src_port`
- `dst_port`
- `txid`
- `input_addresses[]`
- `output_addresses[]`
- `input_amounts[]`
- `output_amounts[]`
- `fee`
- `script_type`
- `geo_country`
- `asn`

GeoIP enrichment uses downloadable open source GeoIP databases.

---

## Objectives

- Ingest and parse bulk Bitcoin transaction metadata.
- Correlate network layer and blockchain layer data.
- Build relationships between wallets, IP addresses, and transactions.
- Detect suspicious behavior using AI and machine learning.
- Generate explainable alerts with confidence scores.
- Provide investigators with a clear view of suspicious entities through a terminal-based dashboard.

---

## AI and Graph Analysis

BitCraft combines graph analytics with machine learning rather than relying solely on rule based detection.

Planned capabilities include:

- Entity clustering
- Transaction anomaly detection
- Suspicious transaction chain identification
- Temporal behavior analysis
- Wallet relationship discovery
- Network correlation between blockchain activity and observed IP metadata

Every alert includes supporting evidence and a confidence score.

---

## Project Structure

```text
bitcraft/
├── datasets/
├── docs/
├── plans/
├── src/
├── tests/
└── README.md
```

---

## Getting Started

### Terminal UI (demo mode)

```text
pip install -r tui/requirements.txt
python -m tui.app --demo
```

Other data sources:

```text
python -m tui.app --api
python -m tui.app
```

`--demo` forces synthetic data. `--api` talks to FastAPI at
`http://localhost:8000` (override with `--api-url`). Default `auto`
probes `/health` and falls back to demo.

Keys: Enter (boot/detail), d dashboard, t threats, g graph, Esc home, q quit.

Demo mode always shows a `DEMO DATA` badge. It is not live pipeline output.

Minimum terminal size: 100 columns by 30 rows.

---

## Expected Output

BitCraft produces:

- Parsed and correlated transaction data
- Entity relationship graphs
- Ranked suspicious wallets and transactions
- Explainable AI generated alerts
- Terminal-based investigation dashboard (TUI)

---

## Tech Stack

Planned technologies include:

- Python
- NetworkX
- FastAPI
- PostgreSQL
- Redis
- GeoIP databases
- Machine learning libraries
- Textual (terminal UI framework)

---

## License

License information will be added when the project reaches a stable release.
# BitCraft User Manual

BitCraft ranks suspicious Bitcoin transactions and wallets and shows why
each one was flagged. It runs fully offline on Linux, Windows and macOS.

This manual covers installing BitCraft, preparing data, running the
pipeline, and using the terminal interface (TUI).

---

## 1. Install

You need Python 3.10 or newer.

| Method | Command | Gives you |
| --- | --- | --- |
| pip | `pip install bitcraft` | The `bitcraft` command (TUI only) |
| Chocolatey (Windows) | `choco install bitcraft` | The `bitcraft` command (TUI only) |
| From source | `git clone https://github.com/RohanOnKeys/bitcraft` then `pip install -e .` | TUI plus the ML pipeline and API |

To run the full system (pipeline, API and TUI) from source, also install
the pipeline and API dependencies:

```text
pip install -r requirements.txt -r backend/requirements.txt
```

Docker users can skip the Python setup: `docker compose up --build` runs
the pipeline, loads PostgreSQL and serves the API on port 8000.

---

## 2. Quick start

```text
bitcraft demo        # new window with built-in demo data, nothing else needed
```

With the full system set up (section 3):

```text
bitcraft             # new window; starts the local API if a database is loaded
```

Press **Enter** on the splash screen, wait for the boot checks, and you land
on the dashboard. Press **q** to quit.

---

## 3. Preparing data

All data lives in `datasets/`, which is never committed to git.

### 3.1 The base dataset

Download the Kaggle dataset `rosalinnayak/bitcoin-transaction-traffic`
and put its five CSV files directly in `datasets/`:

```text
datasets/elliptic_features.csv
datasets/transactions.csv
datasets/network.csv
datasets/mapping.csv
datasets/relationships.csv
```

### 3.2 GeoIP databases (one-time download)

BitCraft resolves every IP to a country and ASN with the free DB-IP Lite
databases. Download them once; after that everything works offline:

```text
python -m ml.geoip download            # -> datasets/geoip/*.mmdb
python -m ml.geoip lookup 8.8.8.8      # check: US, AS15169 Google LLC
```

MaxMind GeoLite2 `.mmdb` files also work: drop them into `datasets/geoip/`.

### 3.3 Transaction and network metadata

The pipeline also reads per-transaction metadata in the challenge format:

| Field | Example |
| --- | --- |
| `timestamp` | `2025-01-01T00:00:51Z` |
| `src_ip`, `dst_ip` | `185.220.101.22`, `81.7.151.252` |
| `src_port`, `dst_port` | `9150`, `8333` |
| `txid` | 64 hex characters |
| `input_addresses[]`, `output_addresses[]` | Bitcoin addresses |
| `input_amounts[]`, `output_amounts[]` | BTC, one per address |
| `fee` | BTC (optional: derived from inputs minus outputs) |
| `script_type` | `p2pkh`, `p2sh`, `p2wpkh`, `p2tr` (optional) |

Country and ASN are not part of the input: BitCraft adds them from the
GeoIP databases.

To generate this layer from the base dataset:

```text
python -m ml.metadata_generator        # -> datasets/metadata/
```

This writes the same 50,000 records as CSV, JSON and XML, plus
`txid_map.csv` (links each txid to the base dataset) and
`generator_truth.csv` (what was planted, used only for validation).

### 3.4 Bringing your own metadata

Any file in the shape above works: CSV (lists as JSON `["a","b"]` or
`a;b`), JSON (an array of objects), JSON Lines, or XML:

```xml
<transactions>
  <transaction>
    <txid>…</txid>
    <src_ip>…</src_ip>
    <input_addresses><address>…</address></input_addresses>
    <input_amounts><amount>0.5</amount></input_amounts>
    …
  </transaction>
</transactions>
```

Check a file before running the pipeline:

```text
python -m ml.ingest my_metadata.xml
```

The report lists rows read, kept and rejected, with a reason for each
rejection (invalid IP or port, address/amount count mismatch, negative
amount, fee inconsistent with inputs minus outputs, duplicate txid,
missing field). Point the pipeline at your files with `metadata.files` in
`ml/config.yaml`.

---

## 4. Running the pipeline

```text
python -m ml.pipeline                  # about 5 minutes on the full dataset
cd backend && python -m app.loader     # load results into the API database
```

The pipeline writes everything to `ml/artifacts/`. Progress and the final
status go to `ml/artifacts/pipeline_status.json` (and to Redis, if
configured). The slow graph stage is cached, so reruns are faster.

`ml/artifacts/metrics.json` holds the validation results: held-out
precision and AUC, injected-pattern recovery, wallet clustering purity and
GeoIP coverage. See `docs/technical_writeup.md` for what they mean.

Model settings live in `ml/config.yaml`: score-fusion weights, the label
window, model hyperparameters, and the number of wallet alerts.

---

## 5. Starting the API

```text
cd backend
python -m uvicorn app.main:app --port 8000
```

`bitcraft` (run from the source folder) starts this for you when a loaded
database exists, and stops it when you quit. Interactive API docs are at
<http://localhost:8000/docs>.

With no `DATABASE_URL`, the API uses `backend/bitcraft.db` (SQLite). Set
`DATABASE_URL` for PostgreSQL and `REDIS_URL` to enable caching; see
`backend/.env.example`.

---

## 6. Using the TUI

### 6.1 Launching

| Command | What it does |
| --- | --- |
| `bitcraft` | Opens a new, large terminal window |
| `bitcraft demo` | Same, with demo data |
| `bitcraft here` | Runs in the current terminal |
| `bitcraft status` | Shows API health, data counts and pipeline status |
| `bitcraft run --size 200x60` | Opens a window of a chosen size |
| `bitcraft run --api-url http://host:8000` | Uses another API |

BitCraft needs at least 100×30 characters; 160×46 or larger shows every
panel. Windows Terminal, a modern Linux terminal or iTerm2 look best.

The data source defaults to **auto**: the API if it answers, otherwise
demo data. `--demo` and `--api` force one or the other.

### 6.2 Keys

| Key | Action |
| --- | --- |
| `d` | Dashboard |
| `t` | Threats |
| `g` | Graph explorer (focused on the selected alert) |
| `w` | Wallets |
| `Enter` | Open the selected alert |
| `Esc` | Back / home |
| `↑ ↓` or `j k` | Move the selection |
| `r` | Refresh |
| `q` | Quit |
| `Ctrl+P` | Command palette |

Dashboard only: `f` focuses the filters, `x` resets them, `n` / `p` page
through alerts, `s` cycles the sort order.

Threats only: `1` to `4` show all / critical / high / medium alerts, `a` /
`c` / `n` filter by the main driver (anomaly, community, network), `w`
toggles "network evidence required".

### 6.3 Screens

**Dashboard.** KPI tiles across the top. On the left are filters (minimum
score, community id, severity list, network and synthetic coverage) and
the score histogram. The ranked alert table is in the middle. On the right
is a preview of the selected alert: composite score, weighted drivers, and
its transaction neighbourhood.

**Threats.** Overall posture and the severity bar. The top-25 queue with
each alert's main driver, the average driver breakdown, and the riskiest
communities. Along the bottom: evidence signals for the selected alert,
coverage gaps, and alerts per timestep.

**Graph explorer.** An animated connectivity view of the selected
transaction's neighbourhood: the focus pulses in the middle, linked
communities orbit it, and dots show flow along edges. Around it: graph
stats, score drivers, alerts per timestep, severity mix and riskiest
communities.

**Wallets.** Wallets (address clusters) ranked by risk. For the selected
wallet you see why it was flagged, a link graph (wallet → transactions →
addresses and source IPs) and its riskiest transactions with IP:port,
GeoIP country and ASN.

**Alert detail** (`Enter` on an alert). Composite score, weighted drivers,
the linked network and blockchain metadata (txid, source and peer IP:port,
GeoIP country/ASN, Tor flag, inputs/outputs, wallet), evidence, and SHAP
reasons.

### 6.4 Reading an alert

- **Composite score** (0 to 1) fuses four signals with the weights shown on
  screen: the risk model, the anomaly detector, community illicit ratio,
  and the network/metadata model.
- **Severity** is a display tier: critical ≥ 0.80, high ≥ 0.60,
  medium ≥ 0.40.
- **REAL** evidence comes from the Elliptic features, labels and observed
  transaction graph. **MODELED** evidence comes from the synthetic
  transaction, network and wallet layers.
- **SHAP** features are anonymized Elliptic feature numbers (e.g.
  `feature_52`), or engineered features by name. Read them as "what pushed
  this score up", not as a business rule.
- **No network evidence is not the same as low risk.** A transaction
  without network data scores 0 on that signal and is labelled `n/a`.

---

## 7. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `No module named 'tui'` | Run from the repository root, or install with `pip install -e .` |
| Header says demo data / `bitcraft status` says not reachable | Start the API (section 5) or check `--api-url` |
| Wallets page says "wallets unavailable" | Generate metadata (3.3), rerun the pipeline and the loader |
| Countries show `--` | Download the GeoIP databases (3.2) and rerun the pipeline |
| Panels missing or squashed | Enlarge the window to 160×46 or more |
| Odd characters instead of blocks | Use Windows Terminal or another UTF-8 terminal with a modern font |
| `ml.pipeline` stops on a shape error | Your CSVs differ from the documented dataset; use `--no-strict` for smaller test sets |

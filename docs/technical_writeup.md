# BitCraft Technical Writeup

## Problem Statement

Smart India Hackathon 2026, SIH26146, National Technical Research
Organisation (NTRO), Blockchain & Cybersecurity.

Build an offline system that ingests bulk Bitcoin transaction and network
metadata (CSV/JSON/XML), correlates network-layer observations (IP, port,
timing) with blockchain-layer data (wallets, txids, amounts), applies AI/ML
to detect anomalies and cluster entities, and produces prioritised,
explainable investigative leads with a dashboard.

## Approach

### Data

Two layers, linked through `mapping.csv` and `txid_map.csv`:

1. **Base dataset** (Kaggle `rosalinnayak/bitcoin-transaction-traffic`):
   203,769 Elliptic transactions with 165 anonymised features and labels
   (22.9% labeled; 4,545 illicit), 245,856 transaction edges, and synthetic
   transaction and P2P layers for 24.5% and 12.3% of transactions.
2. **Metadata layer** in the challenge format (`ml/metadata_generator.py`):
   one record per synthetic transaction with timestamp, src/dst IP and
   port, txid, input/output addresses and amounts, fee and script type,
   written as CSV, JSON and XML. Counts, values, fees, timestamps and labels
   are taken from the dataset; wallets, addresses, IPs and ports are
   synthesised, with known laundering typologies planted (with noise) on
   illicit-owner activity. Details: `docs/dataset_provenance.md`.

### Ingestion and correlation

- `ml/ingest.py` reads CSV, JSON, JSON Lines and XML into one table and
  validates every row (IP and port syntax, address/amount counts, negative
  amounts, fee = inputs minus outputs, duplicate txids). Rejected rows are
  reported with a reason, never dropped silently.
- `ml/geoip.py` adds source/destination country, ASN and organisation from
  the open DB-IP Lite databases, fully offline after a one-time download.
  A reference list flags Tor-exit and hosting ASNs.
- `ml/entity_graph.py` builds the entity graph: address -input-> tx
  -output-> address and ip -relayed-> tx. Wallets are formed with the
  common-input-ownership heuristic (union-find over co-spent inputs).
  Per-transaction features cover amount shape, fee rate, script type, Tor
  ports and ASNs, non-standard ports, cross-border relays, address reuse,
  peeling-chain length and IP fan-out; wallet aggregates cover size,
  distinct IPs and countries, countries per day and Tor share.
- `ml/graph_builder.py` builds the 203k-node transaction graph from
  `relationships.csv`: degree, PageRank, clustering coefficient and Louvain
  communities with illicit ratios.

### Models

| Signal | Model | Fusion weight |
| --- | --- | ---: |
| Risk model | HistGradientBoosting on 191 transaction features | 0.65 |
| Anomaly | Isolation Forest, 300 trees, unsupervised | 0.05 |
| Community | Louvain community illicit ratio | 0.20 |
| Network / metadata | HistGradientBoosting on the correlated metadata features | 0.10 |

`composite_score` fuses the four signals (weights in `ml/config.yaml`). The
top 2.2% (4,483 transactions) become ranked alerts. Wallets are ranked by
`0.6 * max + 0.4 * shrunk mean` of their transactions' metadata scores, so
sustained behaviour outranks a single risky transaction.

## Model choice

The plan called for an unsupervised Isolation Forest. On this dataset it
ranks illicit transactions *below* random (held-out AUC 0.20): illicit
activity in Elliptic is unusually uniform, and the genuine outliers are
licit. A gradient-boosted classifier trained on known labels generalises
far better, so it leads the fusion and the forest stays as a small,
label-free signal.

Leakage guards: only labels from timesteps 1 to 34 are used for training
and for community ratios; rows inside that window are scored out-of-fold
(grouped by timestep); timesteps 35 to 49 are a clean holdout.

## Explainability

- **SHAP** (TreeExplainer) on the risk model for the top 100 alerts and on
  the metadata model for the top 500 wallets. Elliptic features are
  anonymised, so SHAP stays at feature-index level (`feature_52`);
  engineered features keep their names (`entity_tor_share`).
- **Evidence strings and items** are the primary explanation: community
  size and illicit ratio, degree and PageRank percentiles, distinct IPs and
  countries, Tor and hosting egress, peeling-chain length, round payouts,
  address reuse and linked Elliptic alerts.
- **Provenance**: every evidence item is tagged `real` (Elliptic features,
  labels, observed graph) or `modeled` (synthetic transaction, network and
  wallet layers).
- **Coverage-aware**: missing network evidence scores 0 but is shown as
  `n/a`, never as low risk.

## Results

Held-out timesteps 35 to 49 (16,670 labeled transactions, 6.5% illicit):

| Score | AUC | Avg precision | Precision@100 | Precision@500 |
| --- | ---: | ---: | ---: | ---: |
| Isolation Forest alone | 0.197 | 0.037 | 0.00 | 0.00 |
| Risk model alone | 0.940 | 0.803 | 1.00 | 1.00 |
| **Composite (shipped ranking)** | **0.899** | **0.812** | **1.00** | **0.994** |

Metadata layer (planted typologies, so these measure *recovery*, not
real-world accuracy):

| Check | Result |
| --- | --- |
| Rows ingested / rejected | 50,000 / 0 |
| GeoIP country / ASN resolved | 100% / 88.8% |
| Metadata model, held-out AUC | 0.969 (unsupervised forest: 0.874) |
| Wallet clustering purity | 0.999 (38,051 entities for 7,317 owners) |
| Peeling-chain detection, recall / precision | 0.97 / 0.41 |
| Tor egress detection, recall | 1.00 |
| Wallet alerts that are illicit owners, top 100 / 500 | 0.98 / 0.96 |

Other checks: Louvain modularity 0.981 (298 communities); every result is
reproducible from the seeded pipeline (`python -m ml.pipeline`).

## Limitations

- The risk model needs labels; with none, only the weak unsupervised
  signals remain.
- The metadata layer is synthetic; its metrics show the detectors recover
  the planted typologies, not that they would on live traffic.
- Common-input clustering cannot link addresses that are never co-spent,
  and CoinJoin-style transactions can merge unrelated owners.
- Severity tiers are display thresholds, not calibrated probabilities.
- Illicit volume collapses after timestep 43 (the dark-market shutdown in
  the source data), so late timesteps have few positives.

## System

Offline pipeline (`ml/`) writes Parquet artifacts; `backend/app/loader.py`
loads them into SQLite or PostgreSQL; a read-only FastAPI service (Redis
cache optional) serves alerts, graphs, communities, wallets, addresses, IPs
and metadata; the Textual TUI (`bitcraft`) shows the dashboard, threats,
graph explorer, wallets and alert detail. Docker Compose runs the whole
stack on Linux. See `docs/user_manual.md`.

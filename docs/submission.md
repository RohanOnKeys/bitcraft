# BitCraft Submission Checklist (SIH26146)

How each part of the problem statement is met, and how to check it.

## Challenge objectives

| Requirement | Where | Check it |
| --- | --- | --- |
| Ingest and parse bulk metadata in CSV / JSON / XML | `ml/ingest.py` | `python -m ml.ingest datasets/metadata/bitcoin_metadata.xml` |
| Minimum fields: timestamp, src/dst IP and port, txid, input/output addresses and amounts, fee, script type | `ml/metadata_generator.py`, `datasets/metadata/` | Open `bitcoin_metadata.csv`; `docs/dataset_provenance.md` |
| geo_country / ASN from an open-source, downloadable GeoIP database | `ml/geoip.py` (DB-IP Lite, offline) | `python -m ml.geoip lookup 8.8.8.8`; enriched file below |
| Entity / transaction graph linking IPs, wallets and transactions | `ml/entity_graph.py`, `ml/graph_builder.py` | Wallets page link graph; `GET /entities/{id}/graph` |
| Working AI/ML detection model, not just rules | `ml/risk_model.py`, `ml/metadata_model.py`, `ml/anomaly_model.py` | `ml/artifacts/metrics.json`; `docs/model_card.md` |
| Cluster entities | Common-input wallet clustering, Louvain communities | Wallets page; `GET /entities`, `GET /communities` |
| Ranked, explainable alerts with a confidence score | `ml/ranker.py`, `ml/explainability.py` | Dashboard, alert detail (score, drivers, evidence, SHAP) |
| Dashboard or link-analysis visualisation | `bitcraft/` (Textual TUI) | `bitcraft`; screenshots in `docs/images/` |

## Expected solution

| Deliverable | Where |
| --- | --- |
| Complete offline solution for Linux | `docker compose up --build`; air-gapped bundle via `python packages/offline_bundle.py` |
| Working prototype repo: ingestion, correlation, AI/ML model | This repository |
| Short technical write-up: approach, model choice, explainability | `docs/technical_writeup.md` |
| Dashboard showing flagged entities and evidence for each flag | TUI: dashboard, threats, wallets, alert detail |

## Dataset

The brief asks for a synthetic dataset modelled on real Bitcoin P2P and
transaction fields. `python -m ml.metadata_generator` produces it (50,000
records, CSV / JSON / XML) on top of the labeled Elliptic-derived base
dataset. The GeoIP-enriched version, with `src_country`, `src_asn`,
`dst_country`, `dst_asn`, comes from:

```text
python -m ml.ingest datasets/metadata/bitcoin_metadata.csv --enrich --out datasets/metadata/bitcoin_metadata_enriched.csv
```

Both are published privately on Kaggle as
`rohanllm/bitcraft-bitcoin-metadata`.

## Headline results

Held-out timesteps 35 to 49 (16,670 labeled transactions, 6.5% illicit):
composite AUC 0.899, precision@100 1.00, precision@500 0.994. Metadata
model AUC 0.969; 98% of the top 100 wallet alerts are illicit owners
(planted typologies, see the writeup).

## Run it for the judges

```text
pip install bitcraft && bitcraft demo          # TUI with demo data, any OS
docker compose up --build                      # full stack on Linux: pipeline, PostgreSQL, API
bitcraft                                       # TUI against the API
```

## Offline guarantee

Nothing calls the network at runtime: the pipeline, models, GeoIP lookups,
API, database and TUI all work air-gapped. Downloads happen only at setup
(Python or Docker dependencies, the dataset, the GeoIP databases); for a
machine with no network at all, build the bundle on a connected machine
and run its `install.sh` on the target (see `docs/user_manual.md`,
section 8).

# Anomalies

## Inferred dataset column names, unconfirmed

`ml/data_loader.py` and `ml/graph_builder.py` assume column names for
`transactions.csv`, `network.csv`, `mapping.csv`, and `relationships.csv`
beyond the documented primary/foreign keys. The real files were never
opened, only listed in a shared Google Drive folder. Verify against
`datasets/metadata.json` and `datasets/README.md` once the dataset is
added, and fix the `*_COLUMN` constants if they differ.

## Most of the ML and backend pipeline is still stubbed

`ml/feature_pipeline.py`, `ml/anomaly_model.py`, `ml/ranker.py`,
`ml/explainability.py`, `ml/pipeline.py`, and backend API handlers /
services raise `NotImplementedError`. The TUI can run fully in demo
mode; API mode needs a live backend.

## Demo data is synthetic, not pipeline output

`DemoProvider` invents deterministic alerts for UI work. Every screen
shows a `DEMO DATA` badge. Do not treat demo scores as real Isolation
Forest or Louvain output.

## relationship_type values are unconfirmed

Demo and API providers treat unknown `data_source` /
`relationship_type` values as modeled (fail safe). Confirm real
vocabulary against `datasets/` when available.

## Severity thresholds are display-only

`helpers/severity.py` maps composite score to critical/high/medium/low
for the TUI only. These are not model outputs and are not tuned against
precision@k yet.

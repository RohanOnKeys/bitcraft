# Anomalies

## The repo has the real dataset and a notebook-generated model artifact

The local workspace does include the data files in [datasets](datasets):
- [datasets/elliptic_features.csv](datasets/elliptic_features.csv)
- [datasets/mapping.csv](datasets/mapping.csv)
- [datasets/network.csv](datasets/network.csv)
- [datasets/relationships.csv](datasets/relationships.csv)
- [datasets/transactions.csv](datasets/transactions.csv)

The notebook workflow also produced a saved anomaly-score artifact at
[ml/models/anomaly_scores.parquet](ml/models/anomaly_scores.parquet).
This means the earlier claim that the dataset was missing was based on a
stale assumption and was not true for the current workspace.

## ML pipeline is corrected in the repo test scope

The data-loader contract, feature-matrix assembly, and Isolation Forest
scoring were fixed and verified. The fresh validation run completed with
45 passing tests in the ML suite.

The main issues that were corrected were:
- `class_label` is coerced to float64 with NaN for unknown labels
- synthetic-layer joins no longer create `_x` / `_y` collision columns
- canonical master-table fields remain intact after join operations
- relationship IDs are kept string-compatible for mixed ID namespaces
- feature matrix generation stays free of NaN / Inf and excludes
  leakage columns such as `class_label`, timestamps, and mapping metadata

## Remaining work outside the ML layer

The rest of the repository is not fully complete yet. `ml/ranker.py`,
`ml/explainability.py`, `ml/pipeline.py`, and the backend API handlers /
services remain incomplete or unintegrated. The TUI runs correctly in demo
mode, but the live backend and full end-to-end pipeline still require
follow-up work.

## Demo data is synthetic, not pipeline output

`DemoProvider` invents deterministic alerts for UI work. Every screen shows
a `DEMO DATA` badge. Do not treat demo scores as real Isolation Forest or
Louvain output.

## relationship_type values are unconfirmed

Demo and API providers treat unknown `data_source` / `relationship_type`
values as modeled (fail safe). Confirm the real vocabulary against the
dataset when available.

## Severity thresholds are display-only

`helpers/severity.py` maps composite score to critical/high/medium/low for
the TUI only. These are not model outputs and are not tuned against
precision@k yet.

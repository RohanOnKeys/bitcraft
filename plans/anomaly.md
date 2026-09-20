# Anomalies

## Inferred dataset column names, unconfirmed

`ml/data_loader.py` and `ml/graph_builder.py` assume column names for
`transactions.csv`, `network.csv`, `mapping.csv`, and `relationships.csv`
beyond the documented primary/foreign keys. The real files were never
opened, only listed in a shared Google Drive folder. Verify against
`datasets/metadata.json` and `datasets/README.md` once the dataset is
added, and fix the `*_COLUMN` constants if they differ.

## Most of the pipeline is still stubbed

`ml/feature_pipeline.py`, `ml/anomaly_model.py`, `ml/ranker.py`,
`ml/explainability.py`, `ml/pipeline.py`, all backend API handlers and
services, and all `tui/` widgets raise `NotImplementedError` or render
placeholder text. Nothing has been installed, built, or run.

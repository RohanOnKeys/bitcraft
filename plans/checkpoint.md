# Checkpoint

Status as of this push. Update before every push per RULE-WORKFLOW-001.

## Done

- Repository cloned and scaffolded per `plans/plan.md`.
- `ml/` created: `data_loader.py`, `graph_builder.py`, `anomaly_model.py`,
  `feature_pipeline.py`, `ranker.py`, `explainability.py`, `pipeline.py`,
  `config.yaml` (Isolation Forest params and score fusion weights),
  `Dockerfile`, `models/`, `notebooks/`. All functions are stubs
  (`raise NotImplementedError`), no logic implemented yet.
- `backend/` created: FastAPI app skeleton (`app/main.py`), `core/`
  (settings, SQLAlchemy engine, Redis client), `models/` (the five
  ORM tables from plan section 10.2), `schemas/`, `api/` (the six
  endpoints from plan section 10.1 as stub routers), `services/`,
  Alembic migration scaffolding, `requirements.txt`, `Dockerfile`,
  `.env.example`.
- Root `requirements.txt` (ML dependencies), `docker-compose.yml`
  (postgres, redis, ml, backend), `.gitignore`.
- `docs/` skeletons drafted: `architecture.md`, `model_card.md`,
  `dataset_provenance.md`, `technical_writeup.md`.
- `tests/ml/` and `tests/backend/` created, empty pending real tests.
- Decided the frontend is a terminal interface (TUI), not the React/Vite
  web dashboard originally described in `plans/plan.md`. Updated
  `plans/plan.md` sections 5, 10, 11, 12, 13, 16, and 17, plus
  `README.md` and `docs/architecture.md`, to describe the TUI instead.
  No `tui/` directory yet. TUI framework not chosen (candidates:
  Textual, Rich).
- Implemented `ml/data_loader.py`: loads and shape/key-validates all five
  tables, joins the synthetic layer through `mapping.csv` and the network
  layer through `synthetic_transaction_id` with per-observation
  aggregation, sets `has_synthetic_layer`/`has_network_layer` explicitly,
  fills missing synthetic numeric fields with a sentinel plus a missing
  indicator (never zero-fills network aggregates), and optionally flags
  known Tor-exit/hosting-provider ASNs. Column names beyond the
  documented keys and plan section 6.1 fields are inferred, not
  confirmed against the real dataset, and flagged as such in the module
  docstring.
- Implemented `ml/graph_builder.py`: builds the transaction graph from
  `relationships.csv`, computes degree/pagerank/clustering_coefficient
  per node, runs Louvain community detection, computes
  `community_illicit_ratio` from the labeled subset only (null, not
  zero, for communities with no labeled members), and computes
  modularity. Added `resolve_to_elliptic_tx_id` to bridge the graph's
  mixed elliptic_tx_id / synthetic_transaction_id node namespace back
  onto elliptic_tx_id for the master table join, without merging the two
  ID types.

## Not Done

- No dependencies installed (`pip install`, no containers built).
- No actual dataset files present in `datasets/` (only `.gitkeep`); the
  dataset shape was confirmed by listing a shared Google Drive folder,
  not by importing any file.
- `ml/anomaly_model.py`, `feature_pipeline.py`, `ranker.py`,
  `explainability.py`, and `pipeline.py` are still stubs
  (`raise NotImplementedError`).
- No database migrations generated.
- TUI framework not chosen, `tui/` not scaffolded.
- Nothing in `ml/` has been run against real data yet.

## Next

- Implement `ml/feature_pipeline.py` (assemble the coverage-aware
  feature matrix) and `ml/anomaly_model.py` (Isolation Forest scoring).
- Choose the TUI framework and scaffold `tui/`.
- Generate the first Alembic migration from the ORM models.
- Once the dataset is actually added to `datasets/`, verify the inferred
  column names in `ml/data_loader.py` and `ml/graph_builder.py` against
  `datasets/metadata.json` and `datasets/README.md`.

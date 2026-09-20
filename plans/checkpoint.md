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

## Not Done

- No dependencies installed (`pip install`, no containers built).
- No actual dataset files present in `datasets/` (only `.gitkeep`).
- No pipeline logic implemented; every `ml/` function still raises
  `NotImplementedError`.
- No database migrations generated.
- TUI framework not chosen, `tui/` not scaffolded.

## Next

- Choose the TUI framework and scaffold `tui/`.
- Implement `ml/data_loader.py` once the dataset files are available.
- Generate the first Alembic migration from the ORM models.

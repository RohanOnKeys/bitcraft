# BitCraft Architecture

Status: draft.

## Pipeline Overview

See `plans/plan.md` section 5 for the staged pipeline and section 17 for
the end-to-end flow.

## Components

- `ml/` - offline ingestion, graph, anomaly detection, scoring, explainability
- `backend/` - FastAPI service reading pre-computed results from PostgreSQL and Redis

## Data Flow

TODO

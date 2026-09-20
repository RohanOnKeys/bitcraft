# BitCraft Architecture

Status: draft.

## Pipeline Overview

See `plans/plan.md` section 5 for the staged pipeline and section 17 for
the end-to-end flow.

## Components

- `ml/` - offline ingestion, graph, anomaly detection, scoring, explainability
- `backend/` - FastAPI service reading pre-computed results from PostgreSQL and Redis
- `tui/` - terminal interface reading pre-computed results only, framework to be decided

BitCraft ships as a terminal user interface rather than a web dashboard,
so the whole system runs inside the offline Linux container with no
browser and no client-side build step. See `plans/plan.md` section 11.

## Data Flow

TODO

# Checkpoint

Status as of this push. Update before every push per RULE-WORKFLOW-001.

## Done

- The local workspace contains the real dataset files in [datasets](datasets),
  and the notebook workflow has already generated the anomaly-score model
  artifact at [ml/models/anomaly_scores.parquet](ml/models/anomaly_scores.parquet).
- TUI foundations through threat detection are working in demo mode:
  swappable `DataProvider` (`demo` / `api` / `auto`), `store.py`,
  Textual modes (`dashboard`, `threats`, `graph`), splash and boot flow,
  populated dashboard, paging/sort/filter support, and threat queue
  presentation.
- Textual floor set to `textual>=5.0` and verified in the project
  environment.
- `tui/api_client.py` and the provider layer are implemented.
- The ML pipeline has been fixed and validated in the repo test scope:
  data-loader coercion, synthetic-layer merge behavior, feature-matrix
  assembly, and Isolation Forest scoring all pass the ML test suite.
- Verified status: 45 tests passed in the ML subset.

## Not Done

- The live backend and full end-to-end API integration remain incomplete.
- `ml/ranker.py`, `ml/explainability.py`, `ml/pipeline.py`, and backend
  handlers / service endpoints are still not fully implemented.
- Alert detail / graph explorer polish remains incomplete.
- Analyst tooling (help overlay, triage file, export, guided tour) remains
  incomplete.
- Real-world validation against the production dataset still needs to be
  wired into the deployment and API path once the end-to-end pipeline is
  connected.

## Current verification status

- Passed: 45 ML tests in the repo test subset
- Dataset present: yes, under [datasets](datasets)
- Model artifact present: yes, under [ml/models/anomaly_scores.parquet](ml/models/anomaly_scores.parquet)
- Status: ML pipeline is fixed and passes the repository ML checks
- Remaining status: backend and full system integration are still work in progress

## Next

- Finish the backend and ranking/explainability layer to match the
  validated ML pipeline.
- Wire the live API and the TUI to the real training artifact and dataset
  flow once the backend contract is ready.
- Complete the remaining graph-explorer and analyst tooling work.

# Checkpoint

Status as of this push. Update before every push per RULE-WORKFLOW-001.

## Done

- TUI foundations through threat detection (enhancement plan steps 1-4):
  swappable `DataProvider` (`demo` / `api` / `auto`), `store.py`,
  Textual modes (`dashboard`, `threats`, `graph`), splash markup fix,
  boot screen with real provider stages, populated dashboard (KPI,
  filters, alert table, preview, paging/sort), threat detection page
  with driver tags and coverage caveat, severity helper and score
  fusion weights mirrored from `ml/config.yaml`.
- Textual floor set to `textual>=5.0` (needs `App.MODES` / `switch_mode`);
  installed/dev version verified at 8.2.x.
- `tui/api_client.py` implemented as thin httpx transport.
- Tests under `tests/tui/` for providers, helpers, boot, navigation,
  dashboard filter, and threat queue.

## Not Done

- Alert detail / graph explorer polish (enhancement steps 5+): canvas
  renderer, radial layout, inspector, depth controls.
- Analyst tooling (help overlay, triage file, export, command palette,
  guided tour).
- Full docs wrap-up pass and API-provider pilot against a live backend.
- `ml/` feature pipeline, anomaly model, ranker, explainability still
  stubs; `datasets/` still empty; backend handlers still stubs.

## Next

- Graph explorer character-cell renderer and alert-detail sections.
- Wire live backend once `/alerts` filter/paging params exist.
- Analyst tooling and docs wrap-up.

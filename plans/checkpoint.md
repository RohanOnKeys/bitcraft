# Checkpoint

Status as of this push. Update before every push per RULE-WORKFLOW-001.

## Done

- ML pipeline end to end (`python -m ml.pipeline`, about 5 minutes):
  ingestion, transaction graph and Louvain communities (cached), Isolation
  Forest, supervised risk model, metadata layer, score fusion, ranking,
  SHAP and provenance-tagged evidence, validation metrics.
- Metadata layer in the challenge format: generator (CSV, JSON, XML),
  validating ingestion for all three plus JSON Lines, offline GeoIP from
  DB-IP Lite, IP / address / transaction entity graph, common-input wallet
  clustering, metadata model and ranked wallet alerts.
- Backend: loader into SQLite or PostgreSQL, every planned endpoint plus
  `/communities`, `/threats/overview`, `/entities`, `/addresses`, `/ips`,
  `/metadata`, `/pipeline/metrics`; optional Redis cache.
- TUI reads the live API: dashboard, threats, graph explorer, wallets and
  alert detail; frogs only on the splash and boot screens.
- `bitcraft` CLI opens a sized terminal window; the installable package is
  `bitcraft` (wheel verified in a clean environment); pip and Chocolatey
  packaging; air-gapped Linux bundle (`packages/offline_bundle.py`);
  Apache 2.0 license with NOTICE.
- Docs: user manual, technical writeup, model card, dataset provenance,
  submission checklist (`docs/submission.md`), screenshots in `docs/images/`.
- Generated metadata, plain and GeoIP-enriched, published privately on
  Kaggle as `rohanllm/bitcraft-bitcoin-metadata`.

## Current verification status

- Tests: 78 passed (`python -m pytest tests`).
- Linux: `docker compose up --build` verified end to end (pipeline in a
  Linux container, PostgreSQL load in 66 s, API serving the TUI); results
  identical to the Windows run.
- Held-out timesteps 35 to 49: composite AUC 0.899, precision@100 1.00,
  precision@500 0.994.
- Metadata model held-out AUC 0.969; wallet alerts illicit at top 100 /
  500: 0.98 / 0.96; clustering purity 0.999.
- Dataset and artifacts are local only (`datasets/`, `ml/artifacts/`,
  git-ignored).

## Not Done

- PyPI and Chocolatey uploads (packages build, pass `twine check` and
  install cleanly).
- Items in `plans/future.md`.

## Next

- Open the PR from `feat/live-model-backend-and-tui-polish`.
- Publish packages once accounts and tokens are set up.

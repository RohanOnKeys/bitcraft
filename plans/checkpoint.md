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
  submission checklist (`docs/submission.md`), screenshots in `docs/images/`,
  architecture with Mermaid diagrams (system, pipeline, fusion, data and
  database relationships, entity graph, request flow, TUI navigation,
  deployment); no draft or TODO sections left.
- Generated metadata, plain and GeoIP-enriched, on Kaggle as
  `rohanllm/bitcraft-bitcoin-metadata`.
- Datasets packaged: base tables, metadata and GeoIP attached to GitHub
  release `v0.1.3` as zip archives; `python -m ml.dataset download`
  fetches and SHA-256 verifies them (hashes pinned in
  `ml/references/dataset_manifest.json`); `python -m ml.synthetic`
  generates a fully synthetic dataset with no download.

- Released: `bitcraft` 0.1.3 on PyPI (<https://pypi.org/project/bitcraft/>)
  and GitHub release `v0.1.3` with the dataset archives; README is the PyPI
  description; author credits corrected (Jagadish Prasad Pattanaik,
  Ashutosh Badapanda); dataset sources credited in `datasets/NOTICE`.

## Current verification status

- Tests: 82 passed (`python -m pytest tests`).
- Linux: `docker compose up --build` verified end to end (pipeline in a
  Linux container, PostgreSQL load in 66 s, API serving the TUI); results
  identical to the Windows run.
- Held-out timesteps 35 to 49: composite AUC 0.899, precision@100 1.00,
  precision@500 0.994.
- Metadata model held-out AUC 0.969; wallet alerts illicit at top 100 /
  500: 0.98 / 0.96; clustering purity 0.999.
- Dataset and artifacts are not in git (`datasets/`, `ml/artifacts/`);
  the data comes from the release archives.

## Not Done

- Chocolatey upload (package prepared in `packages/chocolatey`, needs a
  Chocolatey account and community moderation).
- Items in `plans/future.md`.

## Next

- Publish the Chocolatey package.
- Items in `plans/future.md`.

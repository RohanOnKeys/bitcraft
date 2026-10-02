# Future

Deferred ideas. Do not build these until the current TUI baseline is
stable and the backend exposes the needed fields.

- Graph explorer character-cell canvas, radial layout, and analyst
  tooling (triage file, export, help overlay, guided tour).
- Severity thresholds are still fixed display tiers (0.80 / 0.60 / 0.40);
  load them from `ml/config.yaml` and calibrate the composite score.
- Change-address heuristic on top of common-input clustering to merge
  wallets the current heuristic misses.
- Rename the installed `tui` package to `bitcraft` before the first PyPI
  release (top-level `tui` can clash with other packages).
- Live Tor exit list (refreshed when online) alongside the offline ASN list.
- Overview graph endpoint for the whole community graph, not only ego
  subgraphs.
- Analyst tooling: triage file, export, help overlay, guided tour.


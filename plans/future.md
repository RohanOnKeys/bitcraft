# Future

Deferred ideas. Do not build these until the current TUI baseline is
stable and the backend exposes the needed fields.

- Severity thresholds are still fixed display tiers (0.80 / 0.60 / 0.40);
  load them from `ml/config.yaml` and calibrate the composite score.
- Change-address heuristic on top of common-input clustering to merge
  wallets the current heuristic misses.
- Live Tor exit list (refreshed when online) alongside the offline ASN list.
- Overview graph endpoint for the whole community graph, not only ego
  subgraphs.
- Analyst tooling: save triage marks to a file, export, help overlay,
  guided tour (marks currently last for the session).
- Serve the fusion weights from the API so the TUI does not mirror
  `ml/config.yaml` (a test guards the mirror today).


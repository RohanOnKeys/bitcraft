# Future

Deferred ideas. Do not build these until the current TUI baseline is
stable and the backend exposes the needed fields.

- Severity tier thresholds should be loaded from `ml/config.yaml` and
  tuned against precision@k once the ML pipeline lands.
- `AlertSummary` lacks `timestep`, `community_id`, and `severity` on the
  real backend schemas; the TUI treats them as optional extensions.
- `AlertDetail` lacks structured evidence (label, value, provenance);
  today only `evidence_text` is specified.
- No `GET /communities` list endpoint and no overview graph endpoint.
- `/alerts` needs the filter, sort, and paging params the TUI already
  sends.
- Typology labels (peeling chain, rapid multi-geography hop) once the
  pipeline can emit them from the injected-anomaly work in plan 9.2.
- Graph explorer character-cell canvas, radial layout, and analyst
  tooling (triage file, export, help overlay, guided tour).

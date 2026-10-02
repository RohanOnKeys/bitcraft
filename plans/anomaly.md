# Anomalies

## The repo has the real dataset (artifact claim superseded)

The local workspace does include the data files in [datasets](datasets):
- [datasets/elliptic_features.csv](datasets/elliptic_features.csv)
- [datasets/mapping.csv](datasets/mapping.csv)
- [datasets/network.csv](datasets/network.csv)
- [datasets/relationships.csv](datasets/relationships.csv)
- [datasets/transactions.csv](datasets/transactions.csv)

The earlier notebook artifact `ml/models/anomaly_scores.parquet` is no
longer in the workspace. `python -m ml.pipeline` now writes every model
output to `ml/artifacts/` (git-ignored).

## ML pipeline is corrected in the repo test scope

The data-loader contract, feature-matrix assembly, and Isolation Forest
scoring were fixed and verified. The fresh validation run completed with
45 passing tests in the ML suite.

The main issues that were corrected were:
- `class_label` is coerced to float64 with NaN for unknown labels
- synthetic-layer joins no longer create `_x` / `_y` collision columns
- canonical master-table fields remain intact after join operations
- relationship IDs are kept string-compatible for mixed ID namespaces
- feature matrix generation stays free of NaN / Inf and excludes
  leakage columns such as `class_label`, timestamps, and mapping metadata

## Remaining work outside the ML layer (resolved)

`ml/ranker.py`, `ml/explainability.py`, `ml/pipeline.py` and every backend
handler are implemented, and the TUI reads the live API. See
`plans/checkpoint.md`.

## Demo data is synthetic, not pipeline output

`DemoProvider` invents deterministic alerts for UI work. Every screen shows
a `DEMO DATA` badge. Do not treat demo scores as real Isolation Forest or
Louvain output.

## relationship_type values are unconfirmed

Demo and API providers treat unknown `data_source` / `relationship_type`
values as modeled (fail safe). Confirm the real vocabulary against the
dataset when available.

## Severity thresholds are display-only

`helpers/severity.py` maps composite score to critical/high/medium/low for
the TUI only. These are not model outputs and are not tuned against
precision@k yet.

## Isolation Forest ranks illicit transactions backwards

On the real Elliptic features the plan's Isolation Forest scores illicit
transactions as *less* anomalous than licit ones: held-out AUC 0.20 (0.10
on all labeled rows). Illicit activity is unusually uniform, while licit
activity holds the genuine outliers. A supervised risk model now leads the
fusion and the forest keeps a 0.05 weight; see `docs/model_card.md`.

## Kaggle network IPs are documentation addresses

`network.csv` uses the reserved TEST-NET ranges (192.0.2.0/24,
198.51.100.0/24, 203.0.113.0/24), which no GeoIP database resolves. The
metadata generator therefore draws routable IPs from each country's real
blocks in the DB-IP database, so GeoIP enrichment reproduces the dataset's
countries.

## The base dataset lacks the challenge's minimum fields

No ports, txid hashes, wallet addresses or per-address amounts exist in the
Kaggle tables. `ml/metadata_generator.py` synthesises them on top of the
real counts, values, fees, timestamps and labels. Metrics on that layer
measure recovery of planted typologies, not real-world accuracy.

## Common-input clustering under-merges

38,051 spending entities for 7,317 true owners: addresses that are never
spent together cannot be linked by the common-input heuristic. Purity stays
high (0.999); adding a change-address heuristic would merge more.

## Peel-chain detection over-fires

Recall 0.97, precision 0.41: ordinary licit payments with one small output
look like peeling steps. Chain length is the stronger signal and is what
the wallet evidence reports.


## Threats network toggle key is shadowed

The threats screen binds `w` to the network-evidence toggle, but the app
binds `w` to the wallets page with `priority=True`, which wins. The toggle
is unreachable from the keyboard; it needs a free key.

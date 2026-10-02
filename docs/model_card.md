# BitCraft Model Card

Status: v1, trained 2026-10-02 on the full dataset. Numbers below come from
`ml/artifacts/metrics.json` (regenerate with `python -m ml.pipeline`).

## What it does

Ranks all 203,769 Elliptic transactions by risk and keeps the top 2.2%
(4,483) as alerts. Each alert has a composite score, per-driver scores, SHAP
reasons and a provenance-tagged evidence string.

## Models

| Signal | Model | Weight | Uses labels? |
| --- | --- | ---: | --- |
| `model_score` | HistGradientBoosting classifier (`ml/risk_model.py`) | 0.65 | Yes: labels from timesteps 1-34 only |
| `anomaly_score` | Isolation Forest, 300 trees (`ml/anomaly_model.py`) | 0.05 | No |
| `community_risk` | Louvain community illicit ratio (`ml/graph_builder.py`) | 0.20 | Yes: labels from timesteps 1-34 only |
| `network_signal` | Percentile mix of P2P aggregates (`ml/ranker.py`) | 0.10 | No (synthetic layer, modeled) |

Weights live in `ml/config.yaml` (`score_fusion`).

## Why a supervised model leads

The original plan (plans/plan.md section 6.2) used only the unsupervised
Isolation Forest. On this dataset it ranks illicit transactions *below*
random: illicit activity in Elliptic is unusually uniform (tight look-alike
clusters), while licit activity holds the genuine outliers. Measured on the
held-out timesteps:

| Score | AUC | Avg precision | Precision@100 | Precision@500 |
| --- | ---: | ---: | ---: | ---: |
| Isolation Forest alone | 0.197 | 0.037 | 0.00 | 0.00 |
| Risk model alone | 0.940 | 0.803 | 1.00 | 1.00 |
| **Composite (shipped ranking)** | **0.879** | **0.775** | **0.98** | **0.994** |

The team chose (2026-10-02) to add the supervised risk model and keep the
Isolation Forest as a small, label-free secondary signal.

## Metadata model and wallet scoring

The challenge-format metadata layer (IPs, ports, GeoIP country and ASN,
addresses, amounts, fee, script type) feeds a second HistGradientBoosting
classifier (`ml/metadata_model.py`) under the same label window and
out-of-fold scoring. Where a transaction has metadata, its score replaces
the hand-built network signal in the fusion; elsewhere the old signal (or
0 with `n/a`) stays.

Wallets are common-input clusters scored by
`0.6 * max + 0.4 * shrunk mean` of their transactions' metadata scores;
the shrinkage pulls one-transaction wallets toward the base rate so
sustained behaviour ranks first. SHAP reasons come from each wallet's
riskiest transaction.

On held-out timesteps the metadata model reaches AUC 0.969 (unsupervised
forest on the same features: 0.874), and 98% of the top 100 wallet alerts
are illicit owners. The layer is synthetic with planted typologies, so
these numbers measure recovery of those typologies, not real-world
accuracy.

## Evaluation protocol and leakage guards

- Temporal split, the standard Elliptic protocol: labels from timesteps 1-34
  train the model and feed community ratios; labeled transactions in
  timesteps 35-49 (16,670 rows, 6.5% illicit) are the holdout above.
- Rows inside the training window are scored out-of-fold (GroupKFold by
  timestep), so no transaction is scored by a model that saw its own label.
- Community illicit ratios are computed from training-window labels only.
- The Louvain partition has modularity 0.981 (298 communities).

## Training data

Kaggle `rosalinnayak/bitcoin-transaction-traffic` (`bitcraft_consolidated_v1`):
203,769 Elliptic transactions (22.85% labeled: 4,545 illicit, 42,019 licit),
24.5% synthetic-layer coverage, 12.3% network-layer coverage,
245,856 relationships. See `docs/dataset_provenance.md`.

## Features

191 columns from `ml/feature_pipeline.py`: the 165 anonymized Elliptic
features, timestep, graph features (degree, pagerank, clustering
coefficient), synthetic-layer amounts and categories, network aggregates,
coverage flags and missing-value indicators. `community_id` is excluded from
the risk model because it is an arbitrary identifier.

## Explainability

SHAP TreeExplainer on the risk model for the top 100 alerts (log-odds;
positive pushes toward illicit). Elliptic features are anonymized, so SHAP
stays at feature-index level and the evidence string is the main
human-readable explanation. Every evidence field is tagged `real` (Elliptic
features, labels, observed graph) or `modeled` (synthetic layers).

## Known limitations

- Labels are needed. A brand-new data source without labels falls back to
  the weak unsupervised signals.
- Illicit volume collapses after timestep 43 (the dark-market shutdown in
  the source data), so late timesteps have very few positives.
- Severity tiers (critical >= 0.80, high >= 0.60) are display thresholds,
  not calibrated probabilities.
- Network and synthetic signals are modeled, not observed. No network
  evidence is not the same as low risk.
- See also `plans/plan.md` section 15.

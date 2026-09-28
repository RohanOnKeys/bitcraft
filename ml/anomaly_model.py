"""Isolation Forest anomaly scoring.

Scores every transaction in the master table with an unsupervised
Isolation Forest. class_label is never used as a training target;
contamination is set to the known illicit rate only as a scoring prior.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def train_isolation_forest(
    feature_matrix: pd.DataFrame, config: dict
) -> IsolationForest:
    """Fit an Isolation Forest on the coverage-aware feature matrix."""
    model_config = config.get("isolation_forest", config)
    model = IsolationForest(
        n_estimators=int(model_config.get("n_estimators", 300)),
        max_samples=model_config.get("max_samples", "auto"),
        contamination=float(model_config.get("contamination", 0.022)),
        random_state=model_config.get("random_state", 42),
    )
    model.fit(feature_matrix.to_numpy())
    return model


def score_anomalies(
    model: IsolationForest, feature_matrix: pd.DataFrame
) -> pd.Series:
    """Score all transactions and return anomaly_score per elliptic_tx_id."""
    X = feature_matrix.to_numpy()
    raw_scores = -model.decision_function(X)

    score_min = float(raw_scores.min())
    score_max = float(raw_scores.max())

    if np.isclose(score_max, score_min):
        normalized = np.zeros(len(raw_scores), dtype=float)
    else:
        normalized = (raw_scores - score_min) / (score_max - score_min)

    return pd.Series(
        normalized,
        index=feature_matrix.index,
        name="anomaly_score",
        dtype=float,
    )

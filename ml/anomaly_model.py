"""Isolation Forest anomaly scoring.

Scores every transaction in the master table with an unsupervised
Isolation Forest. class_label is never used as a training target;
contamination is set to the known illicit rate only as a scoring prior.
"""

import pandas as pd
from sklearn.ensemble import IsolationForest


def train_isolation_forest(
    feature_matrix: pd.DataFrame, config: dict
) -> IsolationForest:
    """Fit an Isolation Forest on the coverage-aware feature matrix."""
    raise NotImplementedError


def score_anomalies(
    model: IsolationForest, feature_matrix: pd.DataFrame
) -> pd.Series:
    """Score all transactions and return anomaly_score per elliptic_tx_id."""
    raise NotImplementedError

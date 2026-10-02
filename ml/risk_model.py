"""Supervised illicit-risk model (gradient boosting on the labeled subset).

Why supervised: on this dataset illicit activity is unusually *uniform*, so
the Isolation Forest's rarity score runs opposite to the labels (held-out
AUC ~0.17). A classifier trained on known labels from early timesteps ranks
later timesteps far better (held-out AUC ~0.94). The Isolation Forest stays
as a secondary, label-free signal. See docs/model_card.md.

Leakage guards:
  * only labels with timestep <= train_max_timestep are used for training;
  * rows inside the training window are scored out-of-fold (grouped by
    timestep), so no transaction is scored by a model that saw its label;
  * later timesteps are a clean holdout for precision@k.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold

ILLICIT_CLASS_LABEL = 1
# Arbitrary IDs, not magnitudes: never fed to the model.
EXCLUDED_FEATURES = ("community_id",)


def model_features(feature_matrix: pd.DataFrame) -> pd.DataFrame:
    """Columns the risk model may use."""
    return feature_matrix.drop(columns=[c for c in EXCLUDED_FEATURES if c in feature_matrix.columns])


def _new_model(cfg: dict) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=int(cfg.get("max_iter", 300)),
        learning_rate=float(cfg.get("learning_rate", 0.08)),
        max_leaf_nodes=int(cfg.get("max_leaf_nodes", 31)),
        l2_regularization=float(cfg.get("l2_regularization", 0.0)),
        random_state=int(cfg.get("random_state", 42)),
    )


def train_and_score(
    feature_matrix: pd.DataFrame,
    class_label: pd.Series,
    timestep: pd.Series,
    config: dict,
) -> tuple[HistGradientBoostingClassifier, pd.Series]:
    """Fit on the training window and return (model, risk_score per row).

    feature_matrix, class_label and timestep share the elliptic_tx_id index.
    risk_score is the illicit probability, out-of-fold inside the window.
    """
    cfg = config.get("risk_model", {})
    max_ts = int(cfg.get("train_max_timestep", 34))
    folds = int(cfg.get("cv_folds", 5))
    X = model_features(feature_matrix)
    labels = class_label.reindex(X.index)
    steps = timestep.reindex(X.index)
    train_mask = (labels.notna() & (steps <= max_ts)).to_numpy()
    y = (labels[train_mask] == ILLICIT_CLASS_LABEL).astype(int).to_numpy()
    X_np = X.to_numpy()

    model = _new_model(cfg).fit(X_np[train_mask], y)
    scores = model.predict_proba(X_np)[:, 1]

    # Out-of-fold for every row inside the training window (labeled or not),
    # grouped by timestep so a fold never sees its own period.
    window = (steps <= max_ts).to_numpy()
    window_idx = np.flatnonzero(window)
    groups = steps.to_numpy()[window_idx]
    train_in_window = train_mask[window_idx]
    for fit_part, score_part in GroupKFold(n_splits=folds).split(window_idx, groups=groups):
        fit_rows = window_idx[fit_part][train_in_window[fit_part]]
        if len(fit_rows) == 0:
            continue
        fold_y = (labels.to_numpy()[fit_rows] == ILLICIT_CLASS_LABEL).astype(int)
        if fold_y.min() == fold_y.max():
            continue
        fold_model = _new_model(cfg).fit(X_np[fit_rows], fold_y)
        rows = window_idx[score_part]
        scores[rows] = fold_model.predict_proba(X_np[rows])[:, 1]

    return model, pd.Series(scores, index=X.index, name="risk_score")

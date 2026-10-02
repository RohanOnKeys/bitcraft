"""Pipeline validation metrics (plan section 9).

precision@k is computed on the labeled 22.9% subset only. The headline
numbers come from holdout_report: labeled transactions after the label
window, which neither the risk model nor community ratios ever saw.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ILLICIT_CLASS_LABEL = 1
DEFAULT_KS = (50, 100, 500, 1000)


def precision_at_k(scored: pd.DataFrame, ks=DEFAULT_KS, score_column: str = "composite_score") -> dict:
    """precision@k over labeled transactions ranked by score_column.

    Returns {"k": precision} plus the labeled base rate, so a reader can see
    the lift over picking labeled transactions at random.
    """
    labeled = scored.loc[scored["class_label"].notna()].sort_values(
        score_column, ascending=False, kind="mergesort"
    )
    is_illicit = labeled["class_label"].astype(int) == ILLICIT_CLASS_LABEL
    result: dict[str, float] = {}
    for k in ks:
        top = is_illicit.head(k)
        if len(top):
            result[str(k)] = round(float(top.mean()), 4)
    result["base_rate"] = round(float(is_illicit.mean()), 4) if len(is_illicit) else 0.0
    result["labeled_count"] = int(len(labeled))
    return result


def holdout_report(scored: pd.DataFrame, score_columns, min_timestep: int, ks=(100, 500)) -> dict:
    """AUC / average precision / precision@k on labeled rows after the label window.

    These rows were never used to train the risk model or to compute
    community illicit ratios, so this is the honest generalisation number.
    """
    holdout = scored.loc[scored["class_label"].notna() & (scored["timestep"] >= min_timestep)]
    y = (holdout["class_label"].astype(int) == ILLICIT_CLASS_LABEL).to_numpy()
    report: dict[str, dict] = {
        "_window": {"min_timestep": min_timestep, "labeled": int(len(y)), "base_rate": round(float(y.mean()), 4) if len(y) else 0.0}
    }
    if len(y) == 0 or y.min() == y.max():
        return report
    for column in score_columns:
        s = holdout[column].fillna(0.0).to_numpy()
        order = np.argsort(-s, kind="mergesort")
        entry = {
            "auc": round(float(roc_auc_score(y, s)), 4),
            "average_precision": round(float(average_precision_score(y, s)), 4),
        }
        for k in ks:
            entry[f"p@{k}"] = round(float(y[order[:k]].mean()), 4)
        report[column] = entry
    return report

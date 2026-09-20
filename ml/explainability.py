"""SHAP explainability and provenance-tagged evidence generation.

Computes SHAP TreeExplainer values for the top-N ranked alerts only, and
builds the plain-English evidence string that serves as the primary
explanation, since Elliptic's 165 features are anonymized and have no
published semantic mapping.
"""

import pandas as pd


def compute_shap_values(
    model, feature_matrix: pd.DataFrame, top_n: int
) -> pd.DataFrame:
    """Compute SHAP TreeExplainer values for the top-N ranked alerts."""
    raise NotImplementedError


def build_evidence_string(row: pd.Series) -> str:
    """Build a provenance-tagged, human-readable evidence string for one alert.

    Every evidence field must indicate whether it is real or modeled.
    """
    raise NotImplementedError

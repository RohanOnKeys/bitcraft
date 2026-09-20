"""End-to-end offline ML pipeline entry point.

Runs ingestion, graph construction, feature engineering, anomaly
detection, score fusion, and explainability in sequence, then writes
results for the backend to load. No ML code runs at API request time.
"""

from pathlib import Path


def run_pipeline(datasets_dir: Path, config_path: Path) -> None:
    """Run the full BitCraft ML pipeline end to end."""
    raise NotImplementedError


if __name__ == "__main__":
    run_pipeline(Path("datasets"), Path("ml/config.yaml"))

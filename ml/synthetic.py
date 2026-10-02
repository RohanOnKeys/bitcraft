"""Fully synthetic BitCraft datasets: no download, no Kaggle account.

    python -m ml.synthetic                         # -> datasets/synthetic/
    python -m ml.synthetic --tx 20000 --out datasets/synthetic
    python -m ml.pipeline --datasets datasets/synthetic --no-strict

Writes the five base tables in the bitcraft_consolidated_v1 contract (same
files and columns as the published dataset) plus the challenge-format
metadata layer in CSV, JSON and XML. Illicit transactions get shifted
feature distributions and cluster in their own graph pockets, so the
models have real signal to find. Every row is generated, so the scores
show that the system runs end to end, not how it performs on real data.

IPs come from the DB-IP Lite databases when they are present (see
`python -m ml.geoip download`), otherwise from small stand-in pools.
The default output folder keeps the published data in datasets/ intact.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

N_FEATURES = 165
# Stand-in IP pools for when the GeoIP databases are not downloaded.
FALLBACK_POOLS = {
    "country": {cc: ["81.2.69.0/24"] for cc in ("US", "DE", "RU", "NL", "SG", "BR", "IN", "GB")},
    "asn": {"60729": ["185.220.101.0/24"], "24940": ["88.198.0.0/16"]},
}


def write_base(out_dir: Path, n_tx: int = 2000, seed: int = 42, metadata: bool = False, pools: dict | None = None) -> Path:
    """Write the five contract CSVs into out_dir and return it.

    metadata=True also writes the challenge-format metadata layer
    (out_dir/metadata, CSV only) with the generator, using pools for IPs
    (FALLBACK_POOLS when None).
    """
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    tx_ids = np.arange(230_000_000, 230_000_000 + n_tx, dtype=np.int64)
    timestep = rng.integers(1, 50, n_tx)
    label = rng.choice(["1", "2", "unknown"], size=n_tx, p=[0.03, 0.20, 0.77])
    illicit = label == "1"
    feats = rng.normal(0, 1, (n_tx, N_FEATURES))
    feats[illicit] += rng.normal(2.5, 0.8, (illicit.sum(), N_FEATURES))
    features = pd.DataFrame(feats, columns=[f"feature_{i}" for i in range(N_FEATURES)])
    features.insert(0, "class_label", label)
    features.insert(0, "timestep", timestep)
    features.insert(0, "elliptic_tx_id", tx_ids)
    features["data_source"] = "elliptic"
    features["split"] = "all"
    features.to_csv(out_dir / "elliptic_features.csv", index=False)

    n_syn = n_tx // 4
    syn_ids = [f"SYN_TX_{i:06d}" for i in range(n_syn)]
    linked = rng.choice(tx_ids, n_syn, replace=False)
    countries = ["US", "DE", "RU", "NL", "SG", "BR", "IN", "GB"]
    linked_label = dict(zip(tx_ids, label))
    linked_step = dict(zip(tx_ids, timestep))
    in_value = rng.exponential(1.0, n_syn).round(8)
    fee = rng.exponential(0.0005, n_syn).round(8)
    pd.DataFrame(
        {
            "synthetic_transaction_id": syn_ids,
            "timestep": [linked_step[t] for t in linked],
            "timestamp": (pd.Timestamp("2025-01-01", tz="UTC") + pd.to_timedelta(rng.integers(0, 10**7, n_syn), unit="s")).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "block_number": rng.integers(830_000, 900_000, n_syn),
            "input_count": rng.integers(1, 6, n_syn),
            "output_count": rng.integers(1, 8, n_syn),
            "input_value_btc": in_value,
            "output_value_btc": (in_value - fee).round(8),
            "fee_btc": fee,
            "source_country": rng.choice(countries, n_syn),
            "source_asn": rng.integers(1000, 1100, n_syn),
            "destination_country": rng.choice(countries, n_syn),
            "destination_asn": rng.integers(1000, 1100, n_syn),
            "class_label": [linked_label[t] for t in linked],
            "data_source": "synthetic",
            "generation_method": "synthetic_distribution_sampling",
        }
    ).to_csv(out_dir / "transactions.csv", index=False)

    pd.DataFrame(
        {
            "mapping_id": [f"MAP_{i:06d}" for i in range(n_syn)],
            "elliptic_tx_id": linked,
            "synthetic_transaction_id": syn_ids,
            "mapping_type": "statistical",
            "mapping_method": "timestep_matched",
            "data_source": "mapping",
        }
    ).to_csv(out_dir / "mapping.csv", index=False)

    observed = rng.choice(syn_ids, int(n_syn * 0.8), replace=False)
    rows = []
    obs = 0
    for syn in observed:
        for _ in range(rng.integers(1, 4)):
            rows.append(
                {
                    "observation_id": f"OBS_{obs:07d}",
                    "synthetic_transaction_id": syn,
                    "source_ip": f"10.{rng.integers(0, 255)}.{rng.integers(0, 255)}.{rng.integers(1, 255)}",
                    "destination_ip": f"172.16.{rng.integers(0, 255)}.{rng.integers(1, 255)}",
                    "source_country": rng.choice(countries),
                    "destination_country": rng.choice(countries),
                    "source_asn": int(rng.integers(1000, 1100)),
                    "destination_asn": int(rng.integers(1000, 1100)),
                    "connection_duration_sec": float(rng.exponential(30)),
                    "peer_count": int(rng.integers(1, 40)),
                    "timestamp": "2025-01-01T00:00:00Z",
                    "data_source": "synthetic",
                    "generation_method": "synthetic_rule_based",
                }
            )
            obs += 1
    pd.DataFrame(rows).to_csv(out_dir / "network.csv", index=False)

    edges = []
    illicit_ids = tx_ids[illicit]
    for _ in range(n_tx * 1):
        a, b = rng.choice(tx_ids, 2, replace=False)
        edges.append((str(a), str(b), "elliptic_edge", "elliptic"))
    for _ in range(len(illicit_ids) * 3):
        a, b = rng.choice(illicit_ids, 2, replace=False)
        edges.append((str(a), str(b), "elliptic_edge", "elliptic"))
    for _ in range(n_syn):
        a, b = rng.choice(syn_ids, 2, replace=False)
        edges.append((a, b, "same_timestep", "synthetic"))
    rel = pd.DataFrame(edges, columns=["source_tx_id", "target_tx_id", "relationship_type", "data_source"])
    rel.insert(0, "relationship_id", [f"REL_{i:07d}" for i in range(len(rel))])
    rel["timestep"] = rng.integers(1, 50, len(rel))
    rel.to_csv(out_dir / "relationships.csv", index=False)
    if metadata:
        from ml.metadata_generator import generate, write_all

        records, truth = generate(out_dir, pools=pools or FALLBACK_POOLS, seed=seed)
        write_all(records, truth, out_dir / "metadata", formats=("csv",))
    return out_dir


def main(argv: list[str] | None = None) -> None:
    from ml import geoip
    from ml.metadata_generator import KNOWN_RANGES, generate, write_all

    parser = argparse.ArgumentParser(description="Generate a fully synthetic BitCraft dataset")
    parser.add_argument("--out", type=Path, default=Path("datasets/synthetic"))
    parser.add_argument("--tx", type=int, default=20_000, help="number of base transactions")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--geoip", type=Path, default=geoip.DEFAULT_DIR)
    parser.add_argument("--formats", default="csv,json,xml", help="metadata formats")
    args = parser.parse_args(argv)

    write_base(args.out, args.tx, args.seed)
    print(f"wrote base tables to {args.out} ({args.tx:,} transactions)")
    if any((args.geoip / name).is_file() for name in geoip.COUNTRY_FILES):
        known = pd.read_csv(KNOWN_RANGES)
        asns = known.loc[known["category"].isin(["tor_exit", "hosting_provider"]), "asn"].astype(int)
        pools = geoip.build_ip_pools(args.geoip, asns=asns.tolist(), seed=args.seed)
    else:
        print("note: no GeoIP databases found, using stand-in IP pools")
        pools = FALLBACK_POOLS
    records, truth = generate(args.out, pools=pools, seed=args.seed)
    for path in write_all(records, truth, args.out / "metadata", tuple(args.formats.split(","))):
        print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

"""Synthetic Bitcoin transaction/network metadata in the challenge's format.

    python -m ml.metadata_generator            # -> datasets/metadata/

One record per synthetic transaction in transactions.csv, carrying the
minimum fields from the problem statement:

    timestamp, src_ip, dst_ip, src_port, dst_port, txid,
    input_addresses[], output_addresses[], input_amounts[], output_amounts[],
    fee, script_type

Country/ASN are *not* written: they come from the open GeoIP databases at
ingestion time (ml/geoip.py), as the brief asks.

Grounded in the dataset: timestamps, input/output counts, BTC values, fees
and labels come from transactions.csv; countries of the observed P2P
connections come from network.csv. Synthesised: wallets (owners with
address sets), addresses (valid checksums), routable IPs drawn from each
country's real address blocks, ports, txids, and per-address amounts.

Illicit-labelled transactions belong to illicit owners, who show known
typologies with noise: heavy address reuse, peeling chains, CoinJoin-style
mixing (which breaks common-input clustering on purpose), Tor/hosting
egress, multi-country IP hopping, non-standard ports and round payouts.
Licit owners show the same behaviours at low rates. What was injected where
is written to generator_truth.csv, used only to validate recovery.

Outputs (datasets/metadata/):
    bitcoin_metadata.csv / .json / .xml   the same records in three formats
    txid_map.csv                          txid <-> synthetic_transaction_id
    generator_truth.csv                   owner and injected patterns per txid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd

from ml import geoip
from ml.addresses import SCRIPT_TYPES, make_address

DEFAULT_OUT = Path("datasets/metadata")
KNOWN_RANGES = Path(__file__).resolve().parent / "reference" / "known_ranges.csv"

# Owner counts at full size; smaller inputs scale down so owners still
# transact repeatedly (about 5 licit / 15 illicit transactions per owner).
N_LICIT_OWNERS = 9000
N_ILLICIT_OWNERS = 120
# Share of unlabeled transactions secretly routed through illicit owners.
HIDDEN_ILLICIT_SHARE = 0.03

# Behaviour rates: (illicit owner, licit owner).
REUSE = (0.65, 0.25)
PEEL = (0.45, 0.02)
COINJOIN = (0.08, 0.004)
TOR_EGRESS = (0.55, 0.01)
HOSTING_EGRESS = (0.35, 0.08)
HOPPER = (0.5, 0.03)
ROUND_PAYOUT = (0.35, 0.05)
ODD_PORT = (0.2, 0.02)

SCRIPT_MIX = {
    True: ((0.45, 0.25, 0.25, 0.05)),   # illicit: legacy-heavy
    False: ((0.20, 0.15, 0.55, 0.10)),  # licit: segwit-heavy
}
P2P_PORT = 8333
ODD_PORTS = (8332, 18333, 9333, 443, 8080)
TOR_PORTS = (9050, 9150)

REQUIRED_FIELDS = (
    "timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
    "input_addresses", "output_addresses", "input_amounts", "output_amounts",
    "fee", "script_type",
)


@dataclass
class Owner:
    owner_id: int
    illicit: bool
    script_type: str
    home_country: str
    countries: list[str]
    hopper: bool
    tor: bool
    addresses: list[str] = field(default_factory=list)
    home_ips: list[str] = field(default_factory=list)
    last_change: str | None = None


class _IPSource:
    """Routable IPs per country / ASN, from GeoIP pools when available."""

    def __init__(self, pools: dict, rng: random.Random) -> None:
        self.country = pools.get("country", {})
        self.asn = pools.get("asn", {})
        self.rng = rng

    def in_country(self, code: str) -> str:
        cidrs = self.country.get(code) or self.country.get("US")
        if cidrs:
            return geoip.random_ip(cidrs, self.rng)
        # No GeoIP database: any public-looking IPv4 (country unknown later).
        while True:
            first = self.rng.randrange(11, 223)
            if first not in (127, 169, 172, 192, 198, 203):
                return f"{first}.{self.rng.randrange(256)}.{self.rng.randrange(256)}.{self.rng.randrange(1, 255)}"

    def in_asn(self, asns: list[int], fallback_country: str) -> str:
        available = [a for a in asns if self.asn.get(str(a))]
        if not available:
            return self.in_country(fallback_country)
        return geoip.random_ip(self.asn[str(self.rng.choice(available))], self.rng)


def _txid(synthetic_id: str) -> str:
    return hashlib.sha256(f"bitcraft:{synthetic_id}".encode()).hexdigest()


def _split(total: float, parts: int, rng: np.random.Generator) -> list[float]:
    if parts <= 1:
        return [round(total, 8)]
    shares = rng.dirichlet(np.ones(parts))
    values = [round(float(total * s), 8) for s in shares]
    values[-1] = round(total - sum(values[:-1]), 8)
    return values


def generate(
    datasets_dir: Path = Path("datasets"),
    geoip_dir: Path = geoip.DEFAULT_DIR,
    seed: int = 42,
    limit: int | None = None,
    pools: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (records, truth). records holds exactly the challenge fields."""
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    tx = pd.read_csv(datasets_dir / "transactions.csv")
    net = pd.read_csv(datasets_dir / "network.csv")
    if limit:
        tx = tx.head(limit)
    tx = tx.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    first_obs = net.drop_duplicates("synthetic_transaction_id").set_index("synthetic_transaction_id")

    known = pd.read_csv(KNOWN_RANGES)
    tor_asns = known.loc[known["category"] == "tor_exit", "asn"].astype(int).tolist()
    hosting_asns = known.loc[known["category"] == "hosting_provider", "asn"].astype(int).tolist()
    if pools is None:
        pools = geoip.build_ip_pools(geoip_dir, asns=tor_asns + hosting_asns, seed=seed)
    ips = _IPSource(pools, rng)

    countries = net["source_country"].value_counts(normalize=True)
    country_codes, country_weights = countries.index.tolist(), countries.to_numpy()

    def make_owner(owner_id: int, illicit: bool) -> Owner:
        i = 0 if illicit else 1
        home = str(nrng.choice(country_codes, p=country_weights))
        hopper = rng.random() < HOPPER[i]
        spread = rng.sample(country_codes, k=min(len(country_codes), rng.randint(4, 7))) if hopper else [home]
        owner = Owner(
            owner_id=owner_id,
            illicit=illicit,
            script_type=rng.choices(SCRIPT_TYPES, weights=SCRIPT_MIX[illicit])[0],
            home_country=home,
            countries=spread,
            hopper=hopper,
            tor=rng.random() < TOR_EGRESS[i],
        )
        owner.home_ips = [ips.in_country(home) for _ in range(rng.randint(1, 2))]
        return owner

    n_illicit_tx = int((tx["class_label"].astype(str) == "1").sum())
    n_licit_owners = max(20, min(N_LICIT_OWNERS, len(tx) // 5))
    n_illicit_owners = max(3, min(N_ILLICIT_OWNERS, n_illicit_tx // 15))
    licit = [make_owner(i, False) for i in range(n_licit_owners)]
    illicit = [make_owner(n_licit_owners + i, True) for i in range(n_illicit_owners)]
    # Zipf-like activity: a few busy owners, a long tail of occasional ones.
    licit_w = 1.0 / np.arange(1, n_licit_owners + 1) ** 0.9
    illicit_w = 1.0 / np.arange(1, n_illicit_owners + 1) ** 0.7
    licit_w /= licit_w.sum()
    illicit_w /= illicit_w.sum()

    def new_address(owner: Owner) -> str:
        address = make_address(owner.script_type, rng)
        owner.addresses.append(address)
        return address

    def address_of(owner: Owner, reuse: float) -> str:
        if owner.addresses and rng.random() < reuse:
            return rng.choice(owner.addresses)
        return new_address(owner)

    records, truth = [], []
    for row in tx.itertuples(index=False):
        label = str(row.class_label)
        hidden = label not in ("1", "2") and rng.random() < HIDDEN_ILLICIT_SHARE
        is_illicit = label == "1" or hidden
        owner = (
            illicit[int(nrng.choice(n_illicit_owners, p=illicit_w))]
            if is_illicit
            else licit[int(nrng.choice(n_licit_owners, p=licit_w))]
        )
        i = 0 if owner.illicit else 1
        fee = max(0.0, float(row.fee_btc))
        total_in = max(float(row.input_value_btc), fee + 1e-6)
        total_out = round(total_in - fee, 8)
        n_in, n_out = max(1, int(row.input_count)), max(1, int(row.output_count))

        peel = owner.last_change is not None and rng.random() < PEEL[i]
        coinjoin = False
        if peel:
            inputs = [owner.last_change]
            n_out = 2
        else:
            inputs = [address_of(owner, REUSE[i]) for _ in range(n_in)]
            if n_in >= 2 and rng.random() < COINJOIN[i]:
                coinjoin = True
                for k in range(0, n_in, 2):
                    other = licit[rng.randrange(n_licit_owners)]
                    inputs[k] = address_of(other, 0.5)
        in_amounts = _split(total_in, len(inputs), nrng)

        round_payout = rng.random() < ROUND_PAYOUT[i]
        if peel:
            payment = round(total_out * rng.uniform(0.05, 0.15), 8)
            pay_to = licit[rng.randrange(n_licit_owners)]
            change = new_address(owner)
            outputs = [address_of(pay_to, 0.3), change]
            out_amounts = [payment, round(total_out - payment, 8)]
            owner.last_change = change
        else:
            has_change = n_out >= 2 and rng.random() < 0.7
            payees = n_out - 1 if has_change else n_out
            outputs = [address_of(licit[rng.randrange(n_licit_owners)], 0.3) for _ in range(payees)]
            out_amounts = _split(total_out, n_out, nrng)
            if has_change:
                change = new_address(owner)
                outputs.append(change)
                owner.last_change = change
        if round_payout and len(out_amounts) > 1:
            rounded = [max(0.01, round(a, 2)) for a in out_amounts[:-1]]
            last = round(total_out - sum(rounded), 8)
            if last > 0:
                out_amounts = rounded + [last]

        src_country = rng.choice(owner.countries) if owner.hopper else owner.home_country
        egress = "home"
        if owner.tor and rng.random() < 0.6:
            src_ip, egress = ips.in_asn(tor_asns, src_country), "tor"
        elif rng.random() < HOSTING_EGRESS[i]:
            src_ip, egress = ips.in_asn(hosting_asns, src_country), "hosting"
        elif not owner.hopper and rng.random() < 0.7:
            src_ip = rng.choice(owner.home_ips)
        else:
            src_ip = ips.in_country(src_country)
        obs = first_obs.loc[row.synthetic_transaction_id] if row.synthetic_transaction_id in first_obs.index else None
        dst_country = str(obs["destination_country"]) if obs is not None else str(nrng.choice(country_codes, p=country_weights))
        dst_ip = ips.in_country(dst_country)
        src_port = rng.choice(TOR_PORTS) if egress == "tor" else rng.randrange(49152, 65536)
        dst_port = rng.choice(ODD_PORTS) if rng.random() < ODD_PORT[i] else P2P_PORT

        txid = _txid(row.synthetic_transaction_id)
        records.append(
            {
                "timestamp": row.timestamp,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": int(src_port),
                "dst_port": int(dst_port),
                "txid": txid,
                "input_addresses": inputs,
                "output_addresses": outputs,
                "input_amounts": in_amounts,
                "output_amounts": out_amounts,
                "fee": round(fee, 8),
                "script_type": owner.script_type,
            }
        )
        truth.append(
            {
                "txid": txid,
                "synthetic_transaction_id": row.synthetic_transaction_id,
                "owner_id": owner.owner_id,
                "owner_illicit": owner.illicit,
                "hidden_illicit": hidden,
                "peel_chain": peel,
                "coinjoin": coinjoin,
                "egress": egress,
                "ip_hopping": owner.hopper,
                "round_payout": round_payout,
            }
        )
    return pd.DataFrame(records), pd.DataFrame(truth)


# --- Writers ----------------------------------------------------------------


LIST_FIELDS = ("input_addresses", "output_addresses", "input_amounts", "output_amounts")


def write_csv(records: pd.DataFrame, path: Path) -> None:
    """Arrays become JSON lists inside the cell."""
    frame = records.copy()
    for column in LIST_FIELDS:
        frame[column] = frame[column].map(json.dumps)
    frame.to_csv(path, index=False)


def write_json(records: pd.DataFrame, path: Path) -> None:
    path.write_text(json.dumps(records.to_dict("records"), separators=(",", ":")), encoding="utf-8")


def write_xml(records: pd.DataFrame, path: Path) -> None:
    item_tag = {"input_addresses": "address", "output_addresses": "address",
                "input_amounts": "amount", "output_amounts": "amount"}
    with open(path, "w", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n<transactions>\n')
        for rec in records.to_dict("records"):
            out.write("  <transaction>\n")
            for key, value in rec.items():
                if key in item_tag:
                    tag = item_tag[key]
                    inner = "".join(f"<{tag}>{escape(str(v))}</{tag}>" for v in value)
                    out.write(f"    <{key}>{inner}</{key}>\n")
                else:
                    out.write(f"    <{key}>{escape(str(value))}</{key}>\n")
            out.write("  </transaction>\n")
        out.write("</transactions>\n")


def write_all(records: pd.DataFrame, truth: pd.DataFrame, out_dir: Path, formats=("csv", "json", "xml")) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    writers = {"csv": write_csv, "json": write_json, "xml": write_xml}
    for fmt in formats:
        path = out_dir / f"bitcoin_metadata.{fmt}"
        writers[fmt](records, path)
        written.append(path)
    truth[["txid", "synthetic_transaction_id"]].to_csv(out_dir / "txid_map.csv", index=False)
    truth.to_csv(out_dir / "generator_truth.csv", index=False)
    written += [out_dir / "txid_map.csv", out_dir / "generator_truth.csv"]
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate challenge-format Bitcoin metadata")
    parser.add_argument("--datasets", type=Path, default=Path("datasets"))
    parser.add_argument("--geoip", type=Path, default=geoip.DEFAULT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--formats", default="csv,json,xml")
    parser.add_argument("--limit", type=int, default=None, help="only the first N transactions")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    records, truth = generate(args.datasets, args.geoip, args.seed, args.limit)
    for path in write_all(records, truth, args.out, tuple(args.formats.split(","))):
        print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    print(f"{len(records):,} transactions, {truth['owner_id'].nunique():,} owners, "
          f"{int(truth['owner_illicit'].sum()):,} illicit-owner transactions")


if __name__ == "__main__":
    main()

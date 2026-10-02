"""Offline GeoIP enrichment from open, downloadable databases.

Uses DB-IP Lite (CC BY 4.0) country and ASN databases in MaxMind's MMDB
format. Download once, then everything runs offline:

    python -m ml.geoip download          # -> datasets/geoip/*.mmdb

GeoLite2-Country.mmdb / GeoLite2-ASN.mmdb from MaxMind work as drop-in
replacements (same format), if you have a licence key for those.

IP attribution by DB-IP (https://db-ip.com), licensed CC BY 4.0.
"""

from __future__ import annotations

import argparse
import gzip
import ipaddress
import json
import random
import shutil
import urllib.request
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

DEFAULT_DIR = Path("datasets/geoip")
COUNTRY_FILES = ("dbip-country-lite.mmdb", "GeoLite2-Country.mmdb")
ASN_FILES = ("dbip-asn-lite.mmdb", "GeoLite2-ASN.mmdb")
DBIP_URL = "https://download.db-ip.com/free/dbip-{kind}-lite-{month}.mmdb.gz"
POOLS_FILE = "ip_pools.json"
# Networks kept per country / ASN when sampling realistic public IPs.
POOL_SIZE = 400


def _first_existing(directory: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        if (directory / name).is_file():
            return directory / name
    return None


class GeoIP:
    """Country and ASN lookups for IPv4/IPv6 addresses (cached)."""

    def __init__(self, directory: Path = DEFAULT_DIR, country_reader=None, asn_reader=None) -> None:
        import maxminddb

        self.directory = Path(directory)
        if country_reader is None:
            path = _first_existing(self.directory, COUNTRY_FILES)
            country_reader = maxminddb.open_database(str(path)) if path else None
        if asn_reader is None:
            path = _first_existing(self.directory, ASN_FILES)
            asn_reader = maxminddb.open_database(str(path)) if path else None
        self._country = country_reader
        self._asn = asn_reader

    @property
    def available(self) -> bool:
        return self._country is not None or self._asn is not None

    @lru_cache(maxsize=500_000)
    def lookup(self, ip: str) -> tuple[str | None, int | None, str | None]:
        """(ISO country, ASN, ASN organisation) for one address; Nones if unknown."""
        country = asn = org = None
        try:
            if self._country is not None:
                rec = self._country.get(ip) or {}
                country = (rec.get("country") or rec.get("registered_country") or {}).get("iso_code")
            if self._asn is not None:
                rec = self._asn.get(ip) or {}
                asn = rec.get("autonomous_system_number")
                org = rec.get("autonomous_system_organization")
        except ValueError:  # not an IP address
            pass
        return country, asn, org

    def enrich(self, frame: pd.DataFrame, columns=("src_ip", "dst_ip")) -> pd.DataFrame:
        """Add <prefix>_country / _asn / _asn_org for each IP column."""
        out = frame.copy()
        for column in columns:
            prefix = column.removesuffix("_ip")
            unique = out[column].dropna().unique()
            table = {ip: self.lookup(str(ip)) for ip in unique}
            looked = out[column].map(table)
            out[f"{prefix}_country"] = looked.map(lambda t: t[0] if isinstance(t, tuple) else None)
            out[f"{prefix}_asn"] = looked.map(lambda t: t[1] if isinstance(t, tuple) else None).astype("Int64")
            out[f"{prefix}_asn_org"] = looked.map(lambda t: t[2] if isinstance(t, tuple) else None)
        out["geo_source"] = "geoip" if self.available else "unavailable"
        return out


# --- IP pools for the synthetic generator ------------------------------------


def build_ip_pools(directory: Path = DEFAULT_DIR, asns=(), seed: int = 42) -> dict:
    """Sample real IPv4 networks per country and per ASN from the databases.

    Walking a full database takes ~20-30 s, so the result is cached in
    directory/ip_pools.json. Returns {"country": {CC: [cidr...]},
    "asn": {ASN: [cidr...]}}.
    """
    cache = Path(directory) / POOLS_FILE
    wanted = sorted({int(a) for a in asns})
    if cache.exists():
        pools = json.loads(cache.read_text(encoding="utf-8"))
        if set(map(str, wanted)) <= set(pools.get("asn", {})):
            return pools
    import maxminddb

    rng = random.Random(seed)
    pools: dict[str, dict[str, list[str]]] = {"country": {}, "asn": {}}

    def reservoir(bucket: dict, key: str, value: str, seen: dict) -> None:
        seen[key] = seen.get(key, 0) + 1
        items = bucket.setdefault(key, [])
        if len(items) < POOL_SIZE:
            items.append(value)
        else:
            j = rng.randrange(seen[key])
            if j < POOL_SIZE:
                items[j] = value

    country_path = _first_existing(Path(directory), COUNTRY_FILES)
    if country_path:
        seen: dict[str, int] = {}
        with maxminddb.open_database(str(country_path)) as reader:
            for network, record in reader:
                if network.version != 4 or network.prefixlen > 28 or not network.is_global:
                    continue
                code = ((record or {}).get("country") or {}).get("iso_code")
                if code:
                    reservoir(pools["country"], code, str(network), seen)
    asn_path = _first_existing(Path(directory), ASN_FILES)
    if asn_path and wanted:
        seen = {}
        wanted_set = set(wanted)
        with maxminddb.open_database(str(asn_path)) as reader:
            for network, record in reader:
                if network.version != 4 or network.prefixlen > 28 or not network.is_global:
                    continue
                number = (record or {}).get("autonomous_system_number")
                if number in wanted_set:
                    reservoir(pools["asn"], str(number), str(network), seen)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pools), encoding="utf-8")
    return pools


def random_ip(cidrs: list[str], rng: random.Random) -> str:
    """A host address inside one of the given networks."""
    network = ipaddress.ip_network(rng.choice(cidrs))
    span = max(1, network.num_addresses - 2)
    return str(network.network_address + 1 + rng.randrange(span))


# --- Download ------------------------------------------------------------------


def download(directory: Path = DEFAULT_DIR, month: str | None = None) -> list[Path]:
    """Fetch the DB-IP Lite country and ASN databases (no account needed)."""
    directory.mkdir(parents=True, exist_ok=True)
    month = month or date.today().strftime("%Y-%m")
    written = []
    for kind in ("country", "asn"):
        url = DBIP_URL.format(kind=kind, month=month)
        target = directory / f"dbip-{kind}-lite.mmdb"
        print(f"downloading {url}")
        with urllib.request.urlopen(url, timeout=120) as response, open(target, "wb") as out:
            with gzip.GzipFile(fileobj=response) as unzipped:
                shutil.copyfileobj(unzipped, out)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BitCraft offline GeoIP databases")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="download DB-IP Lite country + ASN databases")
    dl.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    dl.add_argument("--month", help="YYYY-MM (default: current month)")
    look = sub.add_parser("lookup", help="look up IP addresses")
    look.add_argument("ips", nargs="+")
    look.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    if args.command == "download":
        for path in download(args.dir, args.month):
            print(f"saved {path}")
        return
    geo = GeoIP(args.dir)
    for ip in args.ips:
        country, asn, org = geo.lookup(ip)
        print(f"{ip:<18} {country or '--':<3} AS{asn or '-':<8} {org or ''}")


if __name__ == "__main__":
    main()

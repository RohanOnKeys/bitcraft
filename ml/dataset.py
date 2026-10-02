"""Download, verify and package the BitCraft datasets.

    python -m ml.dataset download            # every archive -> datasets/
    python -m ml.dataset download base geoip # only some archives
    python -m ml.dataset status              # what is present locally
    python -m ml.dataset pack                # maintainers: build the archives

The data ships as zip archives attached to a GitHub release, so no Kaggle
account or API token is needed. Every archive is checked against the
SHA-256 pinned in ml/references/dataset_manifest.json before it is
unpacked; a mismatch aborts without touching datasets/.

    base       the five base tables (elliptic_features, transactions,
               network, mapping, relationships)
    metadata   challenge-format metadata (CSV, JSON, XML, GeoIP-enriched
               versions, txid map and generator truth)
    geoip      DB-IP Lite country and ASN databases plus the IP pool cache

To build everything locally instead, see `python -m ml.synthetic`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_DIR = Path("datasets")
MANIFEST = Path(__file__).resolve().parent / "references" / "dataset_manifest.json"
# Archive contents, relative to the datasets folder.
ARCHIVES = {
    "base": [
        "elliptic_features.csv",
        "transactions.csv",
        "network.csv",
        "mapping.csv",
        "relationships.csv",
    ],
    "metadata": [
        "metadata/bitcoin_metadata.csv",
        "metadata/bitcoin_metadata.json",
        "metadata/bitcoin_metadata.xml",
        "metadata/bitcoin_metadata_enriched.csv",
        "metadata/bitcoin_metadata_enriched.json",
        "metadata/bitcoin_metadata_enriched.xml",
        "metadata/txid_map.csv",
        "metadata/generator_truth.csv",
    ],
    "geoip": [
        "geoip/dbip-country-lite.mmdb",
        "geoip/dbip-asn-lite.mmdb",
        "geoip/ip_pools.json",
    ],
}
# Shipped inside every archive so each one stands alone when redistributed.
LEGAL = ("LICENSE", "NOTICE")
# Fixed entry timestamp: repacking the same files gives the same bytes.
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
CHUNK = 1 << 20


def archive_name(name: str) -> str:
    return f"bitcraft-{name}.zip"


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def missing(name: str, directory: Path = DEFAULT_DIR) -> list[str]:
    """Files of an archive that are not present under directory."""
    return [rel for rel in ARCHIVES[name] if not (directory / rel).is_file()]


# --- Pack ----------------------------------------------------------------------


def pack(directory: Path = DEFAULT_DIR, out: Path = Path("dist/datasets"), names=tuple(ARCHIVES)) -> dict:
    """Zip each archive from directory into out and return the manifest entries."""
    out.mkdir(parents=True, exist_ok=True)
    entries = {}
    for name in names:
        absent = missing(name, directory)
        if absent:
            raise FileNotFoundError(f"{name}: missing {', '.join(absent)}")
        target = out / archive_name(name)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for rel in [*ARCHIVES[name], *LEGAL]:
                source = directory / rel
                if not source.is_file():
                    continue
                info = zipfile.ZipInfo(rel, ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(source, "rb") as src, archive.open(info, "w") as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
        entries[archive_name(name)] = {"sha256": sha256(target), "bytes": target.stat().st_size}
        print(f"packed {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return entries


# --- Download ------------------------------------------------------------------


def _fetch(url: str, target: Path, expected_bytes: int) -> None:
    """Stream url to target, printing progress on one line."""
    request = urllib.request.Request(url, headers={"User-Agent": "bitcraft-dataset"})
    done = 0
    with urllib.request.urlopen(request, timeout=120) as response, open(target, "wb") as out:
        while chunk := response.read(CHUNK):
            out.write(chunk)
            done += len(chunk)
            if expected_bytes:
                print(f"\r  {done / 1e6:7.1f} / {expected_bytes / 1e6:.1f} MB", end="", flush=True)
    print()


def _extract(archive_path: Path, name: str, directory: Path) -> None:
    """Unpack the data files; keep any LICENSE or NOTICE already in place."""
    with zipfile.ZipFile(archive_path) as archive:
        for rel in archive.namelist():
            if rel not in ARCHIVES[name] and rel not in LEGAL:
                raise ValueError(f"unexpected entry in {archive_path.name}: {rel}")
            target = directory / rel
            if rel in LEGAL and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(rel) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, CHUNK)


def download(
    names=tuple(ARCHIVES),
    directory: Path = DEFAULT_DIR,
    force: bool = False,
    keep: bool = False,
    manifest: dict | None = None,
) -> list[str]:
    """Fetch, verify and unpack archives. Returns the names actually fetched."""
    manifest = manifest or load_manifest()
    directory.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name in names:
        if not force and not missing(name, directory):
            print(f"{name}: already present, skipped (use --force to replace)")
            continue
        file = archive_name(name)
        entry = manifest["archives"][file]
        url = f"{manifest['base_url']}/{file}"
        part = directory / f"{file}.part"
        print(f"{name}: downloading {url}")
        try:
            _fetch(url, part, entry["bytes"])
            actual = sha256(part)
            if actual != entry["sha256"]:
                raise ValueError(f"{file}: SHA-256 mismatch (expected {entry['sha256']}, got {actual})")
            _extract(part, name, directory)
        finally:
            if keep and part.exists():
                part.replace(directory / file)
            part.unlink(missing_ok=True)
        print(f"{name}: verified and unpacked into {directory}")
        fetched.append(name)
    return fetched


def status(directory: Path = DEFAULT_DIR) -> dict[str, list[str]]:
    """Missing files per archive; an empty list means the archive is complete."""
    return {name: missing(name, directory) for name in ARCHIVES}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BitCraft datasets: download, status, pack")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="download and verify the dataset archives")
    dl.add_argument("names", nargs="*", metavar="ARCHIVE", help=f"any of: {', '.join(ARCHIVES)} (default: all)")
    dl.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    dl.add_argument("--force", action="store_true", help="replace files that are already present")
    dl.add_argument("--keep", action="store_true", help="keep the downloaded zip files")
    st = sub.add_parser("status", help="show which datasets are present")
    st.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    pk = sub.add_parser("pack", help="build the release archives and update the manifest")
    pk.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    pk.add_argument("--out", type=Path, default=Path("dist/datasets"))
    pk.add_argument("--release", help="release tag the archives are attached to, e.g. v0.1.3")
    args = parser.parse_args(argv)

    if args.command == "download":
        unknown = sorted(set(args.names) - set(ARCHIVES))
        if unknown:
            parser.error(f"unknown archive {', '.join(unknown)}; choose from {', '.join(ARCHIVES)}")
        download(args.names or list(ARCHIVES), args.dir, args.force, args.keep)
    elif args.command == "status":
        report = status(args.dir)
        for name, absent in report.items():
            print(f"{name:<9} {'complete' if not absent else 'missing: ' + ', '.join(absent)}")
        if any(report.values()):
            print("\nget them with: python -m ml.dataset download")
            sys.exit(1)
    else:
        manifest = load_manifest() if MANIFEST.exists() else {}
        if args.release:
            manifest["release"] = args.release
            manifest["base_url"] = f"https://github.com/RohanOnKeys/bitcraft/releases/download/{args.release}"
        manifest["archives"] = pack(args.dir, args.out)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        (args.out / "SHA256SUMS").write_text(
            "".join(f"{e['sha256']}  {f}\n" for f, e in manifest["archives"].items()), encoding="utf-8", newline="\n"
        )
        print(f"manifest written: {MANIFEST}")


if __name__ == "__main__":
    main()

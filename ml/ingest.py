"""Bulk ingestion of transaction/network metadata in CSV, JSON or XML.

    python -m ml.ingest datasets/metadata/bitcoin_metadata.xml

Accepts .csv, .json (array of objects), .jsonl/.ndjson (one object per line)
and .xml (<transactions><transaction>...</transaction></transactions>), or a
directory holding any of them. Every format normalises to the same table:
one row per transaction with list columns for addresses and amounts.

Validation never silently drops data: each rejected row is kept in the
report with the reason (bad IP, bad port, mismatched address/amount counts,
negative amounts, fee inconsistent with inputs minus outputs, duplicate
txid, missing field).
"""

from __future__ import annotations

import argparse
import ast
import ipaddress
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REQUIRED_FIELDS = (
    "timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
    "input_addresses", "output_addresses", "input_amounts", "output_amounts",
)
OPTIONAL_FIELDS = ("fee", "script_type")
LIST_FIELDS = ("input_addresses", "output_addresses", "input_amounts", "output_amounts")
SUPPORTED = (".csv", ".json", ".jsonl", ".ndjson", ".xml")
# Allowed gap between the stated fee and inputs - outputs (BTC).
FEE_TOLERANCE = 1e-6


@dataclass
class IngestReport:
    """What was read, kept and rejected."""

    files: list[str] = field(default_factory=list)
    rows_read: int = 0
    rows_kept: int = 0
    rejected: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        reasons: dict[str, int] = {}
        for item in self.rejected:
            reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
        return {
            "files": self.files,
            "rows_read": self.rows_read,
            "rows_kept": self.rows_kept,
            "rows_rejected": len(self.rejected),
            "rejections_by_reason": reasons,
        }


# --- Readers ----------------------------------------------------------------


def _parse_list(value) -> list:
    """List cell from CSV: JSON list, or ';' / '|' separated text."""
    if isinstance(value, list):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return list(ast.literal_eval(text))  # Python-style ['a', 'b']
    for sep in (";", "|"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text] if text else []


def read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"txid": str, "src_ip": str, "dst_ip": str})
    for column in LIST_FIELDS:
        if column in frame.columns:
            frame[column] = frame[column].map(_parse_list)
    return frame


def read_json(path: Path) -> pd.DataFrame:
    if path.suffix in (".jsonl", ".ndjson"):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("transactions", data) if isinstance(data, dict) else data
    return pd.DataFrame(rows)


def read_xml(path: Path) -> pd.DataFrame:
    rows = []
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "transaction":
            continue
        row = {}
        for child in elem:
            if child.tag in LIST_FIELDS:
                row[child.tag] = [item.text or "" for item in child]
            else:
                row[child.tag] = child.text
        rows.append(row)
        elem.clear()
    return pd.DataFrame(rows)


READERS = {".csv": read_csv, ".json": read_json, ".jsonl": read_json, ".ndjson": read_json, ".xml": read_xml}


def read_any(path: Path) -> pd.DataFrame:
    """Read one supported file into the raw (un-validated) table."""
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"unsupported format {path.suffix!r} (use {', '.join(SUPPORTED)})")
    return reader(path)


# --- Normalise and validate -------------------------------------------------


def _valid_ip(value) -> bool:
    try:
        ipaddress.ip_address(str(value))
        return True
    except ValueError:
        return False


def _check(row: dict) -> str | None:
    """Reason a row is rejected, or None if it is fine."""
    for name in REQUIRED_FIELDS:
        value = row.get(name)
        if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
            return f"missing {name}"
    if not (_valid_ip(row["src_ip"]) and _valid_ip(row["dst_ip"])):
        return "invalid ip"
    if not (0 < row["src_port"] < 65536 and 0 < row["dst_port"] < 65536):
        return "invalid port"
    if len(row["input_addresses"]) != len(row["input_amounts"]) or not row["input_addresses"]:
        return "input addresses/amounts mismatch"
    if len(row["output_addresses"]) != len(row["output_amounts"]) or not row["output_addresses"]:
        return "output addresses/amounts mismatch"
    if min(row["input_amounts"] + row["output_amounts"]) < 0:
        return "negative amount"
    fee = row.get("fee")
    if fee is not None and not pd.isna(fee):
        implied = sum(row["input_amounts"]) - sum(row["output_amounts"])
        if abs(implied - fee) > FEE_TOLERANCE + 1e-9 * sum(row["input_amounts"]):
            return "fee inconsistent with inputs minus outputs"
    return None


def normalise(raw: pd.DataFrame, source: str, report: IngestReport) -> pd.DataFrame:
    """Coerce types, compute fee when absent, and split off rejected rows."""
    frame = raw.copy()
    for column in LIST_FIELDS:
        if column not in frame.columns:
            frame[column] = [[] for _ in range(len(frame))]
        frame[column] = frame[column].map(_parse_list)
    for column in ("input_amounts", "output_amounts"):
        frame[column] = frame[column].map(lambda xs: [float(x) for x in xs])
    for column in ("src_port", "dst_port"):
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce").fillna(-1).astype(int)
    frame["fee"] = pd.to_numeric(frame["fee"], errors="coerce") if "fee" in frame.columns else float("nan")
    if "script_type" not in frame.columns:
        frame["script_type"] = None
    frame["txid"] = frame["txid"].astype(str).str.lower()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")

    keep = []
    for idx, row in enumerate(frame.to_dict("records")):
        if pd.isna(row["timestamp"]):
            reason = "invalid timestamp"
        else:
            try:
                reason = _check(row)
            except (TypeError, ValueError) as exc:
                reason = f"malformed row ({exc})"
        if reason:
            report.rejected.append({"source": source, "row": idx, "txid": row.get("txid"), "reason": reason})
        keep.append(reason is None)
    frame = frame.loc[keep].copy()
    implied = frame["input_amounts"].map(sum) - frame["output_amounts"].map(sum)
    frame["fee"] = frame["fee"].fillna(implied)
    frame["source_file"] = source
    return frame[[*REQUIRED_FIELDS, *OPTIONAL_FIELDS, "source_file"]]


def ingest(paths) -> tuple[pd.DataFrame, IngestReport]:
    """Read, normalise and validate one or more files / directories.

    Duplicate txids keep the first occurrence; later ones are rejected.
    """
    report = IngestReport()
    files: list[Path] = []
    for path in [Path(p) for p in ([paths] if isinstance(paths, (str, Path)) else paths)]:
        if path.is_dir():
            files += sorted(p for p in path.iterdir() if p.suffix.lower() in SUPPORTED)
        else:
            files.append(path)
    frames = []
    for path in files:
        raw = read_any(path)
        report.files.append(str(path))
        report.rows_read += len(raw)
        frames.append(normalise(raw, path.name, report))
    if not frames:
        raise ValueError("no supported metadata files found")
    combined = pd.concat(frames, ignore_index=True)
    dupes = combined["txid"].duplicated(keep="first")
    for row in combined.loc[dupes].itertuples():
        report.rejected.append({"source": row.source_file, "row": int(row.Index), "txid": row.txid, "reason": "duplicate txid"})
    combined = combined.loc[~dupes].sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    report.rows_kept = len(combined)
    return combined, report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest and validate Bitcoin metadata (CSV/JSON/XML)")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    frame, report = ingest(args.paths)
    print(json.dumps(report.summary(), indent=2))
    if len(frame):
        print(f"time span {frame['timestamp'].min()} .. {frame['timestamp'].max()}")


if __name__ == "__main__":
    main()

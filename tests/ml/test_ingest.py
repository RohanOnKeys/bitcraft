"""CSV / JSON / XML ingestion and validation."""

import json
from pathlib import Path

import pandas as pd
import pytest

from ml.ingest import ingest
from ml.metadata_generator import write_csv, write_json, write_xml

GOOD = {
    "timestamp": "2025-01-01T00:00:00Z",
    "src_ip": "8.8.8.8",
    "dst_ip": "1.1.1.1",
    "src_port": 50000,
    "dst_port": 8333,
    "txid": "a" * 64,
    "input_addresses": ["1BoatSLRHtKNngkdXEeobR76b53LETtpyT"],
    "output_addresses": ["bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"],
    "input_amounts": [1.0],
    "output_amounts": [0.6, 0.3999],
    "fee": 0.0001,
    "script_type": "p2pkh",
}


def _rows() -> pd.DataFrame:
    bad_ip = {**GOOD, "txid": "b" * 64, "src_ip": "999.1.1.1"}
    mismatch = {**GOOD, "txid": "c" * 64, "input_amounts": [0.5, 0.5]}
    bad_fee = {**GOOD, "txid": "d" * 64, "fee": 0.5}
    duplicate = dict(GOOD)
    no_fee = {**GOOD, "txid": "e" * 64}
    no_fee.pop("fee")
    rows = pd.DataFrame([GOOD, bad_ip, mismatch, bad_fee, duplicate])
    return pd.concat([rows, pd.DataFrame([{**no_fee, "fee": None}])], ignore_index=True)


@pytest.mark.parametrize("writer,suffix", [(write_csv, "csv"), (write_json, "json"), (write_xml, "xml")])
def test_every_format_validates_the_same_way(tmp_path: Path, writer, suffix) -> None:
    path = tmp_path / f"meta.{suffix}"
    writer(_rows(), path)
    frame, report = ingest(path)
    reasons = report.summary()["rejections_by_reason"]
    assert report.rows_read == 6 and report.rows_kept == 2
    assert reasons == {
        "invalid ip": 1,
        "input addresses/amounts mismatch": 1,
        "fee inconsistent with inputs minus outputs": 1,
        "duplicate txid": 1,
    }
    assert frame["input_addresses"].iloc[0] == GOOD["input_addresses"]
    # Missing fee is derived from inputs minus outputs.
    assert frame.set_index("txid").loc["e" * 64, "fee"] == pytest.approx(0.0001)


def test_jsonl_and_directory_ingest(tmp_path: Path) -> None:
    (tmp_path / "a.jsonl").write_text(json.dumps(GOOD) + "\n", encoding="utf-8")
    write_csv(pd.DataFrame([{**GOOD, "txid": "f" * 64}]), tmp_path / "b.csv")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    frame, report = ingest(tmp_path)
    assert len(report.files) == 2 and set(frame["txid"]) == {"a" * 64, "f" * 64}


def test_semicolon_lists_in_csv(tmp_path: Path) -> None:
    row = {**GOOD, "input_addresses": "x1;x2", "input_amounts": "0.5;0.5"}
    pd.DataFrame([row]).to_csv(tmp_path / "m.csv", index=False)
    frame, _ = ingest(tmp_path / "m.csv")
    assert frame["input_addresses"].iloc[0] == ["x1", "x2"]


def test_unsupported_format(tmp_path: Path) -> None:
    (tmp_path / "m.parquet").write_bytes(b"x")
    with pytest.raises(ValueError):
        ingest(tmp_path / "m.parquet")


@pytest.mark.parametrize("suffix", ["csv", "json", "xml"])
def test_export_round_trip(tmp_path: Path, suffix: str) -> None:
    from ml.ingest import export

    write_csv(pd.DataFrame([GOOD, {**GOOD, "txid": "f" * 64}]), tmp_path / "in.csv")
    frame, _ = ingest(tmp_path / "in.csv")
    frame["src_country"] = "US"
    out = export(frame, tmp_path / f"out.{suffix}")
    again, report = ingest(out)
    assert report.rows_kept == 2 and list(again["txid"]) == list(frame["txid"])
    assert again["input_addresses"].iloc[0] == GOOD["input_addresses"]

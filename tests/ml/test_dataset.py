"""Dataset packaging: pack, download from a local URL, verify hashes."""

from pathlib import Path

import pytest

from ml import dataset
from tests.ml.fixture_data import write_fixture_dataset


@pytest.fixture(scope="module")
def packed(tmp_path_factory) -> tuple[Path, dict]:
    data = write_fixture_dataset(tmp_path_factory.mktemp("data"), n_tx=300)
    (data / "LICENSE").write_text("license\n")
    out = tmp_path_factory.mktemp("dist")
    entries = dataset.pack(data, out, names=("base",))
    manifest = {"base_url": out.resolve().as_uri(), "archives": entries}
    return data, manifest


def test_pack_is_reproducible(packed, tmp_path) -> None:
    data, manifest = packed
    again = dataset.pack(data, tmp_path, names=("base",))
    assert again == manifest["archives"]


def test_download_verifies_and_unpacks(packed, tmp_path) -> None:
    data, manifest = packed
    assert dataset.download(("base",), tmp_path, manifest=manifest) == ["base"]
    for rel in dataset.ARCHIVES["base"]:
        assert (tmp_path / rel).read_bytes() == (data / rel).read_bytes()
    assert (tmp_path / "LICENSE").is_file()
    assert not list(tmp_path.glob("*.part"))
    assert dataset.status(tmp_path)["base"] == []
    # Present files are not fetched again.
    assert dataset.download(("base",), tmp_path, manifest=manifest) == []


def test_download_rejects_bad_hash(packed, tmp_path) -> None:
    _, manifest = packed
    entry = manifest["archives"]["bitcraft-base.zip"]
    tampered = {**manifest, "archives": {"bitcraft-base.zip": {**entry, "sha256": "0" * 64}}}
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        dataset.download(("base",), tmp_path, manifest=tampered)
    assert dataset.status(tmp_path)["base"] == dataset.ARCHIVES["base"]
    assert not list(tmp_path.iterdir())


def test_manifest_pins_every_archive() -> None:
    manifest = dataset.load_manifest()
    assert manifest["base_url"].endswith(manifest["release"])
    assert set(manifest["archives"]) == {dataset.archive_name(n) for n in dataset.ARCHIVES}
    for entry in manifest["archives"].values():
        assert len(entry["sha256"]) == 64 and entry["bytes"] > 0

"""Synthetic metadata generator and address encoding."""

import random
from pathlib import Path

import pytest

from ml.address import SCRIPT_TYPES, base58check_valid, bech32_valid, make_address, script_type_of
from ml.ingest import REQUIRED_FIELDS
from ml.metadata_generator import generate
from tests.ml.fixture_data import TEST_POOLS as POOLS
from tests.ml.fixture_data import write_fixture_dataset


def test_known_addresses_validate() -> None:
    assert base58check_valid("1BoatSLRHtKNngkdXEeobR76b53LETtpyT")
    assert not base58check_valid("1BoatSLRHtKNngkdXEeobR76b53LETtpyU")
    assert bech32_valid("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
    assert bech32_valid("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297")


@pytest.mark.parametrize("script", SCRIPT_TYPES)
def test_generated_addresses_are_well_formed(script: str) -> None:
    rng = random.Random(1)
    for _ in range(50):
        address = make_address(script, rng)
        assert script_type_of(address) == script
        assert bech32_valid(address) if address.startswith("bc1") else base58check_valid(address)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    data = write_fixture_dataset(tmp_path_factory.mktemp("gen"))
    return generate(data, pools=POOLS, seed=7)


def test_records_have_challenge_fields(generated) -> None:
    records, truth = generated
    assert tuple(records.columns) == (*REQUIRED_FIELDS, "fee", "script_type")
    assert records["txid"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert records["txid"].is_unique and len(truth) == len(records)
    sums = records["input_amounts"].map(sum) - records["output_amounts"].map(sum)
    assert (sums - records["fee"]).abs().max() < 1e-6


def test_illicit_owners_carry_injected_typologies(generated) -> None:
    _, truth = generated
    bad, good = truth[truth["owner_illicit"]], truth[~truth["owner_illicit"]]
    assert len(bad) and len(good)
    assert bad["peel_chain"].mean() > good["peel_chain"].mean()
    assert (bad["egress"] == "tor").mean() > (good["egress"] == "tor").mean()


def test_deterministic(tmp_path: Path) -> None:
    data = write_fixture_dataset(tmp_path, n_tx=400)
    a, _ = generate(data, pools=POOLS, seed=3)
    b, _ = generate(data, pools=POOLS, seed=3)
    assert a.equals(b)

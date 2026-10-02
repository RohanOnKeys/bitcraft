# Dataset Provenance

Status: draft. Owned by the Documentation and PM team member, due Milestone 1.

## Source

`bitcraft_consolidated_v1`, random seed 42.

Combines real, labeled Bitcoin transaction data from the Elliptic dataset
with synthetically generated transaction and P2P network layers.

## Tables

See `plans/plan.md` section 3.1 for shapes, primary keys, and linkage.

## Coverage

See `plans/plan.md` section 3.2 for coverage statistics.

## Metadata layer (challenge format)

`ml/metadata_generator.py` builds one record per transaction in
`transactions.csv` with the problem statement's minimum fields (timestamp,
src/dst IP and port, txid, input/output addresses and amounts, fee, script
type), written as CSV, JSON and XML under `datasets/metadata/`.

- Real (from the dataset): timestamps, input/output counts, BTC values,
  fees, labels, and the countries of observed P2P connections.
- Synthesised: wallet owners and their addresses (valid checksums), txids,
  routable IPs drawn from each country's real address blocks, ports, and
  per-address amounts.
- Planted with noise, mostly on illicit-labeled transactions: address
  reuse, peeling chains, CoinJoin-style mixing, Tor and hosting egress,
  multi-country IP hopping, non-standard ports, round payouts.
  `generator_truth.csv` records what was planted, for validation only.

## GeoIP

Country and ASN come from DB-IP Lite (country and ASN, MMDB format), used
offline after a one-time download (`python -m ml.geoip download`).
IP geolocation by DB-IP (https://db-ip.com), licensed CC BY 4.0. The
databases are not redistributed in this repository.

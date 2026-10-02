# Dataset Provenance

Status: draft. Owned by the Documentation and PM team member, due Milestone 1.

## Source

`bitcraft_consolidated_v1`, random seed 42.

Combines real, labeled Bitcoin transaction data from the Elliptic dataset
with synthetically generated transaction and P2P network layers.

## Sources

| Source | Used for | License |
| --- | --- | --- |
| [Bitcoin Transaction traffic](https://www.kaggle.com/datasets/rosalinnayak/bitcoin-transaction-traffic) (Rosalin Nayak, Kaggle) | The five base tables | Apache 2.0 (`datasets/LICENSE`) |
| [Elliptic Data Set](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set) | Transaction features, labels and graph | Upstream research terms |
| [blockchain-etl/bitcoin-etl](https://github.com/blockchain-etl/bitcoin-etl) | Transaction field schema (txid, inputs, outputs, values, fees, timestamps) | MIT |
| Schnoering and Vazirgiannis, [Bitcoin Research with a Transaction Graph Dataset](https://arxiv.org/abs/2411.10325) (2024) | Transaction graph research dataset | CC BY-SA 4.0 |
| [DB-IP Lite](https://db-ip.com) | GeoIP country and ASN | CC BY 4.0 |

Full attributions: `datasets/NOTICE`.

## Distribution

The data is attached to the GitHub release as three zip archives, each
carrying `datasets/LICENSE` and `datasets/NOTICE`:

| Archive | Contents |
| --- | --- |
| `bitcraft-base.zip` | The five base tables |
| `bitcraft-metadata.zip` | Metadata in CSV, JSON and XML, GeoIP-enriched versions, `txid_map.csv`, `generator_truth.csv` |
| `bitcraft-geoip.zip` | DB-IP Lite country and ASN databases, IP pool cache |

`python -m ml.dataset download` fetches them and verifies each against the
SHA-256 in `ml/references/dataset_manifest.json`. `python -m ml.synthetic`
generates an entirely synthetic dataset in the same format instead.

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
IP geolocation by DB-IP (<https://db-ip.com>), licensed CC BY 4.0. The
databases are not in the git repository; the release archive
`bitcraft-geoip.zip` redistributes them with this attribution.

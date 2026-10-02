# BitCraft Architecture

How data moves from raw files to ranked, explainable alerts in the
terminal. The diagrams render on GitHub (Mermaid).

## System overview

Three parts, joined only by files and a read-only API:

- `ml/` runs offline, once per dataset: ingestion, enrichment, graphs,
  models, fusion and explanations. It writes Parquet artifacts and exits.
- `backend/` loads the artifacts into SQLite or PostgreSQL and serves them
  through a read-only FastAPI service, with an optional Redis cache.
- `bitcraft/` is the Textual terminal interface. It reads the API, or
  built-in demo data when no API is running.

No model runs at request time, so the API stays fast and every number
the analyst sees can be traced back to one pipeline run.

```mermaid
flowchart LR
    subgraph Sources["datasets/"]
        BASE["Base tables<br/>5 CSVs"]
        META["Metadata<br/>CSV / JSON / XML"]
        GEO["DB-IP Lite<br/>country + ASN"]
    end
    subgraph ML["ml/ (offline pipeline)"]
        PIPE["python -m ml.pipeline"]
    end
    ART[("ml/artifacts/<br/>Parquet + JSON")]
    subgraph API["backend/"]
        LOAD["app.loader"]
        DB[("SQLite or<br/>PostgreSQL")]
        FAST["FastAPI<br/>read-only"]
        CACHE[("Redis<br/>optional")]
    end
    TUI["bitcraft<br/>terminal UI"]
    DEMO["Built-in<br/>demo data"]

    BASE --> PIPE
    META --> PIPE
    GEO --> PIPE
    PIPE --> ART
    ART --> LOAD --> DB
    DB --> FAST
    FAST <--> CACHE
    FAST -- "HTTP JSON" --> TUI
    DEMO -. "no API running" .-> TUI
```

Getting the data: `python -m ml.dataset download` fetches all of
`datasets/` from the GitHub release, and `python -m ml.synthetic`
generates a fully synthetic copy instead (see `docs/user_manual.md`,
section 3).

## Pipeline stages

`ml/pipeline.py` runs these stages in order. Each stage name is written
to `pipeline_status.json` as it starts, which `GET /pipeline/status` and
the boot screen read.

```mermaid
flowchart TD
    L["load<br/>data_loader: 5 CSVs, shape checks,<br/>master table of 203,769 rows"]
    G["graph<br/>graph_builder: transaction graph,<br/>degree, PageRank, Louvain communities"]
    F["features<br/>feature_pipeline: coverage-aware<br/>feature matrix + coverage flags"]
    A["anomaly<br/>anomaly_model: Isolation Forest"]
    R["risk_model<br/>risk_model: HistGradientBoosting,<br/>out-of-fold, temporal split"]
    M["metadata<br/>ingest, geoip, entity_graph,<br/>metadata_model, wallet alerts"]
    U["fusion<br/>ranker: composite score,<br/>rank, severity"]
    E["explain<br/>explainability: SHAP reasons,<br/>provenance-tagged evidence"]
    W["write<br/>Parquet artifacts, metrics.json,<br/>pipeline_status.json"]

    L --> G --> F --> A --> R --> M --> U --> E --> W
```

The metadata stage is skipped, with a log line, when `datasets/metadata/`
is missing; the rest of the pipeline still runs.

## Score fusion

Every transaction gets one composite score in [0, 1]. The weights live in
`ml/config.yaml`; `docs/model_card.md` explains why the supervised risk
model leads.

```mermaid
flowchart LR
    RISK["Risk model<br/>probability"] -- "0.65" --> C(("Composite<br/>score"))
    COMM["Community<br/>illicit ratio"] -- "0.20" --> C
    NET["Network and<br/>metadata signal"] -- "0.10" --> C
    ANOM["Isolation Forest<br/>anomaly score"] -- "0.05" --> C
    C --> RANK["Rank +<br/>severity"]
    RANK --> EXP["SHAP reasons +<br/>evidence items"]
```

Leakage guards: labels with timestep 34 or earlier train the risk model
and feed the community ratios; timesteps 35 to 49 are held out for
evaluation, and training scores are out-of-fold.

## Dataset relationships

The base dataset is five tables. `elliptic_features.csv` is the universe
of 203,769 transactions; the synthetic transaction layer covers 50,000 of
them through `mapping.csv`, and network observations hang off the
synthetic layer. The challenge-format metadata links back through
`txid_map.csv`.

```mermaid
erDiagram
    ELLIPTIC_FEATURES ||--o| MAPPING : "elliptic_tx_id"
    MAPPING |o--|| TRANSACTIONS : "synthetic_transaction_id"
    TRANSACTIONS ||--o{ NETWORK : "synthetic_transaction_id"
    ELLIPTIC_FEATURES ||--o{ RELATIONSHIPS : "source_tx_id / target_tx_id"
    TRANSACTIONS ||--o| TXID_MAP : "synthetic_transaction_id"
    TXID_MAP ||--|| BITCOIN_METADATA : "txid"

    ELLIPTIC_FEATURES {
        bigint elliptic_tx_id PK
        int timestep
        string class_label "1 illicit, 2 licit, unknown"
        float feature_0_to_164
    }
    MAPPING {
        string mapping_id PK
        bigint elliptic_tx_id FK
        string synthetic_transaction_id FK
        string mapping_method
    }
    TRANSACTIONS {
        string synthetic_transaction_id PK
        datetime timestamp
        int input_count
        int output_count
        float input_value_btc
        float fee_btc
        string source_country
    }
    NETWORK {
        string observation_id PK
        string synthetic_transaction_id FK
        string source_ip
        string destination_ip
        float connection_duration_sec
        int peer_count
    }
    RELATIONSHIPS {
        string relationship_id PK
        string source_tx_id
        string target_tx_id
        string relationship_type
    }
    TXID_MAP {
        string txid PK
        string synthetic_transaction_id FK
    }
    BITCOIN_METADATA {
        string txid PK
        datetime timestamp
        string src_ip
        int src_port
        string dst_ip
        int dst_port
        list input_addresses
        list output_addresses
        list input_amounts
        list output_amounts
        float fee
        string script_type
    }
```

| Table | Rows | Key |
| --- | ---: | --- |
| `elliptic_features.csv` | 203,769 | `elliptic_tx_id` |
| `transactions.csv` | 50,000 | `synthetic_transaction_id` |
| `network.csv` | 40,854 | `observation_id` |
| `mapping.csv` | 50,000 | `mapping_id` |
| `relationships.csv` | 245,856 | `relationship_id` |
| `metadata/bitcoin_metadata.*` | 50,000 | `txid` |

Two ID namespaces never mix: `elliptic_tx_id` (integers) and
`synthetic_transaction_id` (`SYN_TX_...`), joined only through
`mapping.csv`. Which fields are real and which are synthetic is in
`docs/dataset_provenance.md`.

## Entity graph

The metadata layer links IP addresses, transactions and Bitcoin addresses.
Addresses spent together as inputs of one transaction belong to the same
owner (common-input ownership, union-find in `ml/entity_graph.py`), which
groups them into wallet entities.

```mermaid
flowchart LR
    IP1(["IP 185.220.101.22<br/>DE, AS60729, Tor"])
    IP2(["IP 81.7.151.252<br/>peer node"])
    TX1["tx a1f3...<br/>2 inputs, 2 outputs"]
    TX2["tx 9c0e...<br/>1 input, 2 outputs"]
    A1{{"addr bc1q...x7"}}
    A2{{"addr 3J98...nY"}}
    A3{{"addr bc1q...k2"}}
    A4{{"addr 1BvB...qa"}}
    W1[["Wallet entity 17<br/>both inputs, one owner"]]

    IP1 -- "src_ip:9150" --> TX1
    TX1 -- "dst_ip:8333" --> IP2
    A1 -- "input" --> TX1
    A2 -- "input" --> TX1
    TX1 -- "output" --> A3
    TX1 -- "output" --> A4
    A3 -- "input" --> TX2
    A1 -.-> W1
    A2 -.-> W1
```

Wallet risk combines the riskiest transaction with a shrunk mean over all
of its transactions, so one bad transfer stands out without small
wallets swinging to extremes. Wallet features (Tor and hosting share,
countries per day, peel-chain length, round outputs, address reuse) feed
the metadata model; `GET /entities/{id}/graph` returns this graph for
one wallet.

## Database model

`backend/app/loader.py` recreates these tables from the artifacts on
every load. The transaction side is keyed by `elliptic_tx_id`, the
metadata side by `txid` and `entity_id`; `tx_metadata.elliptic_tx_id`
joins the two.

```mermaid
erDiagram
    transactions ||--o| alerts : "elliptic_tx_id"
    alerts ||--|| alert_evidence : "elliptic_tx_id"
    communities ||--o{ transactions : "community_id"
    transactions ||--o{ graph_edges : "source / target"
    transactions ||--o| tx_metadata : "elliptic_tx_id"
    entities ||--o{ tx_metadata : "entity_id"
    entities ||--o{ addresses : "entity_id"
    tx_metadata ||--o{ tx_io : "txid"
    addresses ||--o{ tx_io : "address"
    ip_nodes ||--o{ tx_metadata : "src_ip"

    transactions {
        bigint elliptic_tx_id PK
        smallint timestep
        smallint class_label
        int community_id
        float pagerank
        float anomaly_score
        float model_score
        float network_signal
        float composite_score
    }
    alerts {
        bigint elliptic_tx_id PK
        float composite_score
        int rank
        string severity
    }
    alert_evidence {
        bigint elliptic_tx_id PK
        json shap_reasons
        json evidence_items
        text evidence_text
    }
    communities {
        int community_id PK
        int size
        float illicit_ratio
        int alert_count
    }
    graph_edges {
        int id PK
        bigint source_tx_id
        bigint target_tx_id
        string relationship_type
    }
    entities {
        int entity_id PK
        int rank
        float risk_score
        string severity
        int n_addresses
        float tor_share
        int peel_chain_max
    }
    addresses {
        string address PK
        int entity_id
        string script_type
    }
    ip_nodes {
        string ip PK
        string country
        bigint asn
        bool tor_asn
        bool hosting_asn
    }
    tx_metadata {
        string txid PK
        bigint elliptic_tx_id
        int entity_id
        string src_ip
        int src_port
        string dst_ip
        int dst_port
        float metadata_score
    }
    tx_io {
        int id PK
        string txid
        string address
        string direction
        float amount
    }
```

## Request flow

The API answers from the cache when Redis is running and from the
database otherwise. Missing network evidence comes back as `null` and is
shown as `n/a`, never as low risk.

```mermaid
sequenceDiagram
    actor Analyst
    participant TUI as bitcraft TUI
    participant API as FastAPI
    participant R as Redis (optional)
    participant DB as SQLite / PostgreSQL

    Analyst->>TUI: Enter on an alert
    TUI->>API: GET /alerts/{tx_id}
    API->>R: cache lookup
    alt cached
        R-->>API: JSON
    else miss or no Redis
        API->>DB: alert + evidence + metadata
        DB-->>API: rows
        API->>R: store with TTL
    end
    API-->>TUI: score, drivers, evidence, SHAP
    TUI-->>Analyst: alert detail screen
```

API routes: `/alerts`, `/alerts/{tx_id}`, `/graph/{tx_id}`,
`/communities`, `/communities/{id}`, `/entities`, `/entities/{id}`,
`/entities/{id}/graph`, `/addresses/{address}`, `/ips/{ip}`,
`/metadata/{tx_id}`, `/stats/summary`, `/threats/overview`,
`/pipeline/status`, `/pipeline/metrics`. Interactive docs at `/docs`.

## Terminal interface

```mermaid
stateDiagram-v2
    [*] --> Splash
    Splash --> Boot: Enter
    Boot --> Pages: API and data checks pass
    state Pages {
        Dashboard
        Threats
        Graph
        Wallets
    }
    Pages --> Detail: Enter on an alert (dashboard, threats)
    Detail --> Pages: Esc back, g graph of this alert
    Pages --> Splash: Esc
    Pages --> [*]: q
```

On any page, `d`, `t`, `g` and `w` switch to the dashboard, threats,
graph explorer and wallets. When the API is unreachable, the boot screen
offers a retry or the demo data. Screen layouts and theme:
`docs/tui_design.md`.

## Deployment

`docker compose up --build` runs the whole stack on Linux. The `ml`
service runs the pipeline once and exits; the backend waits for it to
finish, loads the artifacts into PostgreSQL and serves on port 8000.

```mermaid
flowchart LR
    subgraph Host
        DS[("./datasets")]
        TUI["bitcraft<br/>(host terminal)"]
    end
    subgraph Compose["docker compose"]
        MLS["ml<br/>pipeline, exits"]
        VOL[("artifacts<br/>volume")]
        BE["backend<br/>loader + FastAPI :8000"]
        PG[("postgres:16")]
        RD[("redis:7")]
    end
    DS --> MLS
    MLS --> VOL --> BE
    BE --> PG
    BE <--> RD
    BE -- ":8000" --> TUI
```

For a machine with no network, `python packages/offline_bundle.py` builds
a folder with every wheel, Docker image and dataset, installed there with
`bash install.sh` (`docs/user_manual.md`, section 8).

## Repository map

| Path | Role |
| --- | --- |
| `ml/data_loader.py` | Load and validate the five CSVs, build the master table |
| `ml/graph_builder.py` | Transaction graph, PageRank, Louvain communities |
| `ml/feature_pipeline.py` | Coverage-aware feature matrix |
| `ml/anomaly_model.py` | Isolation Forest |
| `ml/risk_model.py` | Supervised risk model with temporal split |
| `ml/ingest.py` | CSV, JSON, JSON Lines and XML ingestion with validation |
| `ml/geoip.py` | Offline country and ASN lookups |
| `ml/entity_graph.py` | IP, address and transaction graph; wallet clustering |
| `ml/metadata_model.py` | Metadata model and wallet alerts |
| `ml/ranker.py` | Score fusion, ranking, severity |
| `ml/explainability.py` | SHAP reasons and evidence items |
| `ml/dataset.py`, `ml/synthetic.py` | Dataset download and synthetic generation |
| `backend/app/loader.py` | Artifacts into the database |
| `backend/app/api/` | Route handlers; `services/` holds the queries |
| `bitcraft/` | Terminal interface and the `bitcraft` command |

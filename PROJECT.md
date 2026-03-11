# Graphen — Project Specification

**Multi-chain blockchain graph analytics platform**
**Starting chain: SUI | Future chains: IOTA and others**

---

## 1. Vision

Graphen ingests raw blockchain data and stores it as a property graph in a graph database. This enables analytics that no competitor currently offers on SUI:

- Multi-hop wallet traversal ("find all wallets connected to this whale within 3 hops")
- Community detection (wallet clusters that move together)
- Pattern recognition (wash trading, insider coordination, rug pull risk)
- PageRank-style influence scoring across the network
- AML/compliance path tracing
- Bot detection via gas pattern analysis
- DeFi interaction mapping

**Competitive gap:** Nansen/Arkham use flat SQL. The Graph does event indexing, not graph traversal. No one does real graph analytics on SUI. SUI's object-based data model is natively a property graph — Graphen exploits this.

**Business model:** Subscription service. Open access during prototype/community phase, paid tiers introduced later via API gateway.

---

## 2. Why SUI is a Perfect Fit

SUI is object-based, not account-based like Ethereum. Every coin, NFT, and DeFi position is an **object** with an owner. Ownership transfers are **edges**. This means SUI's data model maps directly to a property graph — Memgraph is the most natural representation of SUI's architecture.

---

## 3. Target Customers

| Segment | What they need | Willingness to pay |
|---------|---------------|-------------------|
| Crypto funds / trading desks | Whale tracking, smart money following, early token accumulation detection | High |
| Compliance / AML teams | Path tracing, sanctions screening, risk scoring, audit trails | High |
| Protocol teams (DeFi on SUI) | User base analysis, wash trading detection in their pools | Medium-High |
| Retail power users / researchers | "SUI blockchain explorer on steroids" | Medium |

All segments will be served, but not all at once. Priority is determined by which queries we expose first.

---

## 4. Architecture

### 4.1 Production Architecture

```
SUI Full Node / Checkpoint Store
            |
     Indexer (Python)
            |
      Apache Pulsar
       |          |            |
  Graph DB     ClickHouse    S3/MinIO
  Writer       Writer        Archiver
       |          |
   Memgraph    ClickHouse
            |
     API Layer (Spring Boot)
            |
     [API Gateway — added when monetizing]
            |
     Dashboard (React + Neovis.js / Cytoscape.js)
```

### 4.2 Prototype Architecture (simplified)

```
SUI GraphQL API (public endpoint)
            |
     Indexer (Python) → Memgraph (direct write)
            |
     Spring Boot REST API
            |
     React + Neovis.js Dashboard
```

**Note:** No message broker in Phase 1. Indexer writes directly to Memgraph to reduce complexity. Message broker (Pulsar or lighter alternative) introduced in Phase 2 when multi-consumer patterns are needed.

### 4.3 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Graph DB | **Memgraph** | Free graph algorithms (PageRank, community detection via MAGE), higher write throughput than Neo4j, in-memory performance, Bolt protocol compatible with Neovis.js |
| Messaging (Phase 2+) | **Apache Pulsar** (or lighter alternative: Redpanda, Redis Streams) | Decouples indexer from DB, replay capability, multi-consumer support. Deferred from prototype to reduce complexity. Team has existing Pulsar experience. |
| API layer | **Java / Spring Boot** | Production stability, strong typing, mature ecosystem for long-running services |
| Indexer | **Python** | Fast prototyping, good SUI SDK support, natural for ETL pipelines |
| Warm storage | **ClickHouse** | Columnar analytics on full transaction history, time-series queries |
| Cold storage | **S3 / MinIO** | Raw checkpoint archival for replay and reprocessing |
| Frontend | **React + Neovis.js** (prototype) | Quick graph visualization via Bolt protocol. Production may graduate to Cytoscape.js or D3-force. |
| Auth | **Open access** (prototype) | Zero friction for community adoption. API gateway (Kong / Spring Cloud Gateway) added before monetization. |

### 4.4 Storage Tiers

| Tier | Storage | What lives here | Query speed |
|------|---------|----------------|-------------|
| Hot | Memgraph | Last 30-90 days, all high-value wallets, flagged entities | Milliseconds |
| Warm | ClickHouse | Full transaction history, aggregations, time-series analytics | Seconds |
| Cold | S3/MinIO | Raw checkpoint data, full archive for replay | Minutes |

---

## 5. Graph Schema

### 5.1 Layered Approach

The schema is built in layers. Each layer adds new node types and relationships without refactoring existing ones.

### 5.2 Layer 1 — Capital Flow (Prototype)

**Nodes:**

| Node | Properties |
|------|-----------|
| `Wallet` | address, label?, first_seen, last_seen |
| `Transaction` | digest, timestamp, gas_used, gas_price, gas_budget |
| `Object` | id, type, coin_type?, value?, value_usd? (Phase 2 — SUI-denominated only in prototype) |

**Relationships:**

| Relationship | Description |
|-------------|-------------|
| `(:Wallet)-[:SENT]->(:Transaction)` | Wallet initiated this transaction |
| `(:Transaction)-[:RECEIVED_BY]->(:Wallet)` | Transaction output received by wallet |
| `(:Wallet)-[:OWNS]->(:Object)` | Current ownership of an object |
| `(:Transaction)-[:CREATED]->(:Object)` | Transaction created this object |
| `(:Transaction)-[:MUTATED]->(:Object)` | Transaction modified this object |
| `(:Wallet)-[:TRANSACTED_WITH {count, volume_usd, last_at}]->(:Wallet)` | Aggregated wallet-to-wallet relationship |

**Key design notes:**
- `coin_type` on Object is critical (e.g., `0x2::sui::SUI`, USDC address) — needed for meaningful USD volume calculations
- Gas fields on Transaction are included from day one for bot detection and anomaly analysis
- `TRANSACTED_WITH` is a derived/materialized edge, computed periodically for fast traversal queries

### 5.3 Layer 2 — DeFi & Events (Month 2)

**Additional nodes:**

| Node | Properties |
|------|-----------|
| `Package` | id, name? |
| `Module` | name, package_id |
| `Event` | type, timestamp, data (JSON) |

**Additional relationships:**

| Relationship | Description |
|-------------|-------------|
| `(:Transaction)-[:CALLED]->(:Module)` | Transaction invoked a module function |
| `(:Module)-[:BELONGS_TO]->(:Package)` | Module is part of a package |
| `(:Transaction)-[:EMITTED]->(:Event)` | Transaction emitted this event |
| `(:Wallet)-[:INTERACTED_WITH]->(:Package)` | Derived: wallet has used this protocol |

**Unlocks:** DEX swap tracking, liquidity analysis, wash trading detection, protocol usage mapping.

### 5.4 Layer 3 — Staking & Governance (Month 3+)

**Additional nodes:**

| Node | Properties |
|------|-----------|
| `Validator` | address, name?, commission_rate |
| `Epoch` | number, start_timestamp, end_timestamp |
| `StakedSui` | id, amount, stake_activation_epoch |

**Additional relationships:**

| Relationship | Description |
|-------------|-------------|
| `(:Wallet)-[:STAKED_WITH]->(:Validator)` | Wallet delegated stake |
| `(:Transaction)-[:IN_EPOCH]->(:Epoch)` | Transaction occurred in this epoch |
| `(:Validator)-[:VALIDATED]->(:Epoch)` | Validator was active in epoch |

**Unlocks:** Staking flow analysis, validator influence mapping, epoch-based time traversal, governance participation tracking.

---

## 6. Data Ingestion Strategy

### 6.1 Scope: All Data

For a paid analytics service, **all transactions must be ingested** — no filtering. Selective ingestion creates blind spots that break graph traversal (e.g., mixer wallets deliberately use small amounts, rug-pull teams use fresh wallets).

### 6.2 Estimated Data Volume (SUI)

| Data type | 30 days | 1 year |
|-----------|---------|--------|
| Transactions | ~200-400M | ~3-5B |
| Objects (created/mutated) | ~500M-1B | ~6-12B |
| Unique wallets | ~5-10M | ~30-50M |
| Graph edges | ~1-2B | ~15-20B |

### 6.3 Indexer Design

The indexer uses a **pluggable source interface** so the data-fetching layer can be swapped without rewriting transformation logic.

```
indexer/
  sources/
    graphql_source.py      # Prototype: SUI public GraphQL endpoint
    fullnode_source.py      # Production: local SUI full node (later)
  transformers/
    transaction_transformer.py
    object_transformer.py
  loaders/
    pulsar_producer.py      # Writes to Pulsar topics
```

| Source | When | Throughput | Rate limits |
|--------|------|-----------|-------------|
| SUI GraphQL API (public) | Prototype | ~50-100 req/s | Yes |
| SUI Full Node (local RPC) | Production | Unlimited | No |
| SUI Indexer Framework | Production (if needed) | Very high (bulk) | No |

---

## 7. Infrastructure

### 7.1 Development

Dev machines (existing hardware). No cloud costs during development.

### 7.2 Production (Hetzner Dedicated Servers)

| Phase | Setup | Estimated cost |
|-------|-------|---------------|
| Early production | Single AX102 (128GB RAM, 8-core, 2x NVMe) | ~EUR 80-120/mo |
| Growth | 2-3 servers (Memgraph / Pulsar+ClickHouse / App) | ~EUR 200-350/mo |
| Scale | K3s cluster across multiple Hetzner boxes | Based on demand |

Memgraph's in-memory model fits perfectly on dedicated hardware — 128GB RAM holds 90+ days of SUI data comfortably.

### 7.3 Deployment

Kubernetes (K3s) for orchestration. Each component is a container:
- Memgraph
- Python indexer
- Spring Boot API
- React frontend
- Message broker (Phase 2+)
- ClickHouse (Phase 2+)
- MinIO (Phase 3+)

---

## 8. Project Phases

### Phase 0 — Discovery Sprint (2-3 days)

**Goal:** Map the SUI GraphQL API data model before writing indexer code.

- Query the public endpoint systematically
- Document every field available on checkpoints, transactions, objects, events
- Create a data dictionary: SUI API fields → Graphen graph schema mapping
- Identify gaps where the API doesn't expose what we need
- Benchmark rate limits on the public endpoint
- Determine if 30 days of data is feasible via public API or requires a full node

**Deliverable:** Data dictionary document and confirmed indexer source strategy.

### Phase 1 — Prototype (2-3 weeks)

**Goal:** Working end-to-end system with the killer visualization.

1. Indexer reads last 30 days of SUI data via GraphQL API
2. Indexer writes directly to Memgraph (no message broker in Phase 1)
3. Layer 1 graph schema (Wallets, Transactions, Objects)
4. Spring Boot API exposes 3-5 Cypher queries via REST
5. React + Neovis.js dashboard with force-directed whale cluster map
6. Open access, no auth

**Killer queries for prototype:**
- Find all wallets within N hops of a given address
- Whale cluster detection (wallets that frequently transact together)
- Top wallets by volume / transaction count
- Transaction path between two wallets
- Wallet activity timeline

### Phase 2 — DeFi Layer + Infrastructure Hardening (Month 2)

- Add Layer 2 schema (Packages, Modules, Events)
- Introduce message broker (Pulsar, Redpanda, or Redis Streams — evaluated at that point)
- USD price feed integration (CoinGecko API, DefiLlama)
- DEX swap tracking and visualization
- Wash trading detection algorithms
- Protocol interaction mapping
- ClickHouse integration for historical aggregations

### Phase 3 — Full Analytics Platform (Month 3+)

- Add Layer 3 schema (Staking, Validators, Epochs)
- PageRank and community detection via Memgraph MAGE
- AML path tracing queries
- API gateway with auth and rate limiting
- Subscription tier implementation
- Production UI upgrade (Cytoscape.js or similar)
- S3/MinIO archival tier
- Alerting system (via additional Pulsar consumer)

### Phase 4 — Multi-chain Expansion

- IOTA chain integration
- Chain-agnostic graph schema design
- Cross-chain wallet correlation

---

## 9. Project Structure

```
graphen/
|
|-- indexer/                        # Python
|   |-- sources/
|   |   |-- base_source.py          # Abstract source interface
|   |   |-- graphql_source.py       # SUI GraphQL API
|   |   |-- fullnode_source.py      # SUI Full Node (later)
|   |-- transformers/
|   |   |-- transaction_transformer.py
|   |   |-- object_transformer.py
|   |   |-- wallet_transformer.py
|   |-- loaders/
|   |   |-- memgraph_loader.py      # Phase 1: direct write
|   |   |-- pulsar_producer.py      # Phase 2: write to broker
|   |-- config/
|   |   |-- settings.py
|   |-- main.py
|   |-- requirements.txt
|   |-- Dockerfile
|
|-- api/                            # Java / Spring Boot
|   |-- src/main/java/.../
|   |   |-- controller/             # REST endpoints
|   |   |-- service/                # Business logic + Cypher queries
|   |   |-- model/                  # Graph node/relationship DTOs
|   |   |-- config/                 # Memgraph connection, CORS, etc.
|   |-- src/main/resources/
|   |   |-- application.yml
|   |-- pom.xml (or build.gradle)
|   |-- Dockerfile
|
|-- dashboard/                      # React
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- services/               # API client
|   |   |-- App.tsx
|   |-- package.json
|   |-- Dockerfile
|
|-- consumers/                      # Phase 2+: Pulsar/broker → Memgraph writer(s)
|   |-- graph_writer/
|   |   |-- consumer.py
|   |   |-- graph_loader.py
|   |   |-- Dockerfile
|
|-- infra/                          # Deployment
|   |-- k8s/                        # Kubernetes manifests
|   |-- docker-compose.yml          # Local development
|   |-- pulsar/                     # Pulsar configuration
|   |-- memgraph/                   # Memgraph configuration
|
|-- docs/                           # Documentation
|   |-- data-dictionary.md          # Phase 0 output
|   |-- schema.md                   # Graph schema details
|
|-- PROJECT.md                      # This document
|-- README.md
```

---

## 10. Tech Stack Summary

| Component | Technology | Language |
|-----------|-----------|----------|
| Blockchain data source | SUI GraphQL API → SUI Full Node | - |
| Indexer / ETL | Custom Python service | Python |
| Message broker (Phase 2+) | Apache Pulsar / Redpanda / Redis Streams (TBD) | - |
| Graph database | Memgraph (Community/Free) | Cypher |
| Graph algorithms | Memgraph MAGE (PageRank, community detection, etc.) | - |
| Warm analytics | ClickHouse (Phase 2+) | SQL |
| Cold storage | S3 / MinIO (Phase 3+) | - |
| API layer | Spring Boot | Java |
| Dashboard | React + Neovis.js (prototype) → Cytoscape.js (production) | TypeScript |
| Deployment | K3s (Kubernetes) on Hetzner dedicated servers | - |
| Auth (future) | API Gateway (Kong / Spring Cloud Gateway) | - |

---

## 11. Risk Analysis

See [RISK_ANALYSIS.md](RISK_ANALYSIS.md) for the full risk assessment, mitigation strategies, and decisions log.

---

## 12. Open Questions

- [ ] Phase 0 outcome: Does the SUI public GraphQL API expose all fields needed for Layer 1, or do we need a full node from the start?
- [ ] Exact Memgraph RAM requirements after benchmarking with real SUI data
- [ ] ClickHouse schema design (deferred to Phase 2)
- [ ] Production UI framework decision (deferred to Phase 3)
- [ ] Multi-chain schema abstraction design (deferred to Phase 4)
- [ ] Specific MAGE algorithms to use for whale clustering and influence scoring

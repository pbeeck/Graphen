# Graphen — Risk Analysis

---

## Critical Risks (could kill the project)

### R1. Memgraph RAM limits at scale
- **Risk:** Memgraph is in-memory. With 1-2B edges (30 days), you may hit 128GB RAM before you expect to. If the hot tier can't hold enough data, your core queries degrade or fail.
- **Likelihood:** Medium-High
- **Impact:** You'd need to either buy much larger servers (256-512GB RAM = higher cost), aggressively prune the graph, or switch databases entirely — all painful mid-flight.
- **Mitigation:** Phase 0 must include a **RAM benchmark**: load a sample of real SUI data (1 day) into Memgraph, measure memory consumption per node/edge, then extrapolate. Do this before committing to 30 days of ingestion.
- **Status:** MITIGATED — Strategy: load 7 days full detail (fits 128GB), run compaction job to aggregate older data into `TRANSACTED_WITH` edges (deleting Transaction/Object nodes after 7 days). This preserves wallet graph for analytics while keeping RAM bounded. Measure actual RAM after initial load to calibrate.

### R2. SUI GraphQL API doesn't expose enough data
- **Risk:** The public GraphQL endpoint may not return all fields you need (e.g., full object mutation details, inner transaction effects, coin type on transfers). You won't know until Phase 0.
- **Likelihood:** Medium
- **Impact:** If critical fields are missing, you're forced to run a SUI full node from day one — which adds significant complexity and delays the prototype by 1-2 weeks.
- **Mitigation:** Phase 0 discovery sprint. Have a fallback plan for running a full node on dev machines if needed. Know the disk/CPU requirements in advance.
- **Status:** RESOLVED — Phase 0 confirmed all Layer 1 fields available via public API. See `docs/data-dictionary.md`.

### R3. Solo developer bottleneck
- **Risk:** You're building Python ETL + Java API + React frontend + Memgraph + Kubernetes. That's at least 4 different technology domains. Any illness, burnout, or unexpected complexity in one area blocks everything.
- **Likelihood:** High
- **Impact:** Prototype slips from 3 weeks to 2-3 months. Momentum and motivation suffer.
- **Mitigation:** Ruthlessly cut scope for the prototype. Pulsar is deferred to Phase 2 — indexer writes directly to Memgraph in Phase 1. Every component deferred is a week saved.
- **Status:** ACCEPTED — prototype scope reduced (no Pulsar in Phase 1)

---

## High Risks (serious but manageable)

### R4. USD value calculation is harder than it looks
- **Risk:** `value_usd` on Objects and `volume_usd` on TRANSACTED_WITH edges require real-time or historical price feeds for every SUI token type. This is a non-trivial data pipeline on its own.
- **Likelihood:** High
- **Impact:** Without USD values, whale detection and volume metrics are incomplete. But building a price oracle is a project unto itself.
- **Mitigation:** Prototype uses **SUI-denominated values only** (no USD). Price feed integration (CoinGecko API, DefiLlama) added in Phase 2. `value_usd` remains nullable in the schema.
- **Status:** ACCEPTED — deferred to Phase 2

### R5. Memgraph MAGE algorithm performance at scale
- **Risk:** PageRank and community detection on a graph with hundreds of millions of nodes may be slow or memory-intensive. MAGE algorithms are free but not all are optimized for billion-edge graphs.
- **Likelihood:** Medium
- **Impact:** Core features (whale clusters, influence scoring) could take minutes instead of seconds, making them unusable in a real-time API.
- **Mitigation:** Run algorithms **offline/batch** (not on query), store results as node properties. E.g., compute PageRank nightly, write scores to wallet nodes. API reads pre-computed scores.
- **Status:** OPEN — validate when Layer 1 data is loaded

### R6. Message broker operational complexity
- **Risk:** Apache Pulsar is powerful but operationally heavy — ZooKeeper dependency, BookKeeper for persistence, topic management. Significant ops burden for early stages.
- **Likelihood:** Medium-High
- **Impact:** Time spent debugging broker infrastructure is time not spent on the actual product.
- **Mitigation:** Phase 1 has no message broker (direct indexer → Memgraph). Phase 2 introduces a messaging layer — Pulsar is the target, but lighter alternatives (Redpanda, Redis Streams) may be evaluated depending on operational needs at that point.
- **Status:** ACCEPTED — deferred to Phase 2, broker choice re-evaluated then

### R7. Competitive moat is time-limited
- **Risk:** If Graphen proves the concept, well-funded competitors (Nansen, Arkham, Chainalysis) could add SUI graph analytics within 6-12 months. They have more data, more engineers, and existing customers.
- **Likelihood:** Medium
- **Impact:** Window to build a user base and establish the brand is roughly 6-12 months from launch.
- **Mitigation:** Speed to market matters more than feature completeness. Launch the prototype publicly as soon as it works. Build community and brand loyalty before competitors react. Consider open-sourcing parts of the stack.
- **Status:** OPEN — ongoing concern

---

## Medium Risks (plan for them, don't lose sleep yet)

### R8. Graph data staleness
- **Risk:** If the indexer falls behind (network spikes, API downtime, processing lag), the graph becomes stale. Users querying "current" wallet balances get outdated data.
- **Likelihood:** Medium
- **Impact:** Trust erosion with paying customers. Compliance users especially cannot tolerate data gaps.
- **Mitigation:** Build a **lag monitoring dashboard** from day one. Track: latest indexed checkpoint vs latest SUI checkpoint. Alert when lag exceeds a threshold (e.g., 5 minutes). Expose data freshness to users in the API response.
- **Status:** OPEN

### R9. OWNS relationship maintenance
- **Risk:** `(:Wallet)-[:OWNS]->(:Object)` represents current ownership. Every time an object transfers, you need to delete the old OWNS edge and create a new one. At SUI's transaction volume, this is a high-frequency update pattern that can create write contention.
- **Likelihood:** Medium
- **Impact:** Stale ownership data, or write bottlenecks that slow down ingestion.
- **Mitigation:** Consider modeling ownership as **time-bounded** edges with `from_checkpoint` and `to_checkpoint` properties instead of delete-and-recreate. This also gives you historical ownership queries for free.
- **Status:** OPEN — design decision for Phase 1

### R10. No backup/recovery strategy for Memgraph
- **Risk:** Memgraph is in-memory. A server crash, OOM kill, or power failure loses everything that isn't snapshotted to disk.
- **Likelihood:** Low-Medium (but when it happens, it's catastrophic)
- **Impact:** Full data loss. Re-ingesting 30 days of SUI data could take days.
- **Mitigation:** Configure Memgraph's **periodic snapshots and WAL (write-ahead log)**. Test recovery time. In Phase 2 when Pulsar is added, keep retention long enough to replay data if needed.
- **Status:** OPEN — configure in Phase 1

### R11. Open access abuse
- **Risk:** With no auth on the prototype, anyone can hammer the API with expensive graph traversal queries. A single unbounded 10-hop query could consume all Memgraph's CPU.
- **Likelihood:** Medium
- **Impact:** Service downtime for everyone.
- **Mitigation:** Even without auth, add **query guards**: max hop depth (e.g., 5), query timeout (e.g., 10 seconds), and basic IP-based rate limiting at the Spring Boot level. Cheap to implement, prevents the worst cases.
- **Status:** OPEN — implement in Phase 1

---

## Low Risks (noted, deferred)

### R12. Multi-chain schema divergence
- SUI's object model is unique. IOTA/Ethereum have different primitives. The "chain-agnostic" schema in Phase 4 may require significant refactoring.
- **Mitigation:** Don't over-abstract now. Build for SUI. Abstract when you add chain #2.

### R13. Memgraph license change
- Memgraph uses BSL, which could change terms.
- **Mitigation:** Low probability. If it happens, Neo4j is a fallback since we use standard Cypher.

### R14. SUI network changes
- SUI is still evolving. Protocol upgrades could change data structures.
- **Mitigation:** Pluggable indexer design handles this — transformer logic is isolated.

---

## Risk Summary Matrix

| Risk | Severity | Likelihood | Priority | Status |
|------|----------|-----------|----------|--------|
| R1. Memgraph RAM limits | Critical | Medium-High | 7-day load + compaction | MITIGATED |
| R2. GraphQL API gaps | Critical | Medium | Validated in Phase 0 | RESOLVED |
| R3. Solo developer bottleneck | Critical | High | Cut prototype scope | ACCEPTED |
| R4. USD value complexity | High | High | Defer to Phase 2 | ACCEPTED |
| R5. MAGE algorithm performance | High | Medium | Batch, don't query-time | OPEN |
| R6. Broker ops complexity | High | Medium-High | Defer to Phase 2 | ACCEPTED |
| R7. Competitive moat | High | Medium | Speed to market | OPEN |
| R8. Data staleness | Medium | Medium | Lag monitoring | OPEN |
| R9. OWNS edge churn | Medium | Medium | Time-bounded edges | OPEN |
| R10. Memgraph crash recovery | Medium | Low-Medium | Snapshots + WAL | OPEN |
| R11. Open access abuse | Medium | Medium | Query guards | OPEN |

---

## Top 3 Actions Before Writing Code

1. **Phase 0 must validate R1 + R2** — benchmark Memgraph RAM with real SUI data, and confirm the GraphQL API returns what you need
2. **Add query guards from day one (R11)** — max hop depth, timeouts, basic rate limiting. Minimal effort, prevents catastrophic downtime.
3. **Configure Memgraph snapshots + WAL immediately (R10)** — don't lose days of ingested data to a crash

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-11 | Defer Pulsar to Phase 2 | Reduces prototype complexity (R3). Indexer writes directly to Memgraph in Phase 1. |
| 2026-03-11 | Defer USD values to Phase 2 | Price feed integration is a sub-project (R4). Prototype uses SUI-denominated values. |
| 2026-03-11 | Broker choice open for Phase 2 | Pulsar is the target but lighter alternatives (Redpanda, Redis Streams) will be evaluated (R6). |
| 2026-03-11 | R2 validated: Public GraphQL API sufficient | Phase 0 confirmed all Layer 1 fields available. No full node needed for prototype. |
| 2026-03-11 | 7-day initial load + compaction strategy (R1) | Start with 7 days full detail (~30M txs, fits 128GB). Build compaction job to aggregate older data into TRANSACTED_WITH edges, deleting Transaction/Object nodes after 7 days. Measure actual RAM before scaling to more days. |
| 2026-03-11 | No selective indexing | All transactions must be ingested — filtering creates blind spots that break graph traversal. |

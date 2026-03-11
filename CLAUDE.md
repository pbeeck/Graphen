# CLAUDE.md

## Project
Graphen — multi-chain blockchain graph analytics platform. See PROJECT.md for full spec, RISK_ANALYSIS.md for risks.

## Architecture (Phase 1 — Prototype)
- **Indexer**: Python — reads SUI checkpoints via GraphQL API, writes directly to Memgraph
- **API**: Java / Spring Boot — exposes Cypher queries via REST
- **Dashboard**: React + Neovis.js
- **Graph DB**: Memgraph (Cypher, Bolt protocol)
- No message broker in Phase 1 (added Phase 2)

## Code conventions
- Python: indexer/ directory
- Java: api/ directory (Spring Boot)
- TypeScript/React: dashboard/ directory
- All components are containerized (Dockerfile per component)

## Key decisions
- SUI-denominated values only (no USD) until Phase 2
- Gas data is always indexed (gas_used, gas_price, gas_budget)
- Graph schema is layered: Layer 1 (wallets/tx/objects) → Layer 2 (packages/events) → Layer 3 (staking)
- Memgraph over Neo4j (free MAGE algorithms)

## Language
- The developer communicates in Dutch and English. Both are fine.

## Don't
- Don't add auth/security layers — prototype is open access by design
- Don't add USD price calculations yet
- Don't introduce a message broker in Phase 1

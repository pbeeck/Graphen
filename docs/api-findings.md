# Graphen — SUI GraphQL API Findings

**Phase 0 Discovery Sprint Output**
**Date:** 2026-03-11
**Endpoint:** `https://graphql.mainnet.sui.io/graphql`

---

## 1. Service Configuration (Measured)

| Limit | Value |
|-------|-------|
| Max query depth | 20 |
| Max query nodes (fields) | 300 |
| Max output nodes | 1,000,000 |
| Query timeout | 40,000 ms |
| Mutation timeout | 74,000 ms |
| Max query payload size | 5,000 bytes |
| Max transaction payload | 174,763 bytes |
| Max type argument depth | 16 |
| Max type argument width | 32 |
| Max type nodes | 256 |
| Max Move value depth | 128 |
| Max Move value bound | 1,048,576 |
| Max multi-get size | 200 |
| Max rich queries | 21 |
| Checkpoint default page size | 20 |
| Checkpoint max page size | 50 |

---

## 2. Volume Data (Measured 2026-03-11)

| Metric | Value |
|--------|-------|
| Latest checkpoint | #253,353,572 |
| Total network transactions (all time) | ~4.92 billion |
| Transactions in last ~7 days | ~32.5 million |
| Checkpoints in last ~7 days | ~2.59 million |
| Average transactions per checkpoint | **12.5** |
| Checkpoint frequency | ~1 per second |

**Note:** The 2,592,000 checkpoint range only covered ~7 days (not 30 days as initially estimated). SUI produces ~1 checkpoint per ~0.27 seconds currently, not 1 per second. Actual 30-day estimate: **~10M checkpoints, ~125M transactions.**

### Updated Volume Estimates (30 days)

| Data type | Estimate |
|-----------|----------|
| Checkpoints | ~10M |
| Transactions (programmable only) | ~100-125M |
| Unique wallets | ~5-10M |
| Objects created/mutated | ~200-500M |
| Graph edges (est.) | ~500M-1B |

---

## 3. Throughput Benchmark (Measured)

### Test 1: Checkpoint-only pagination (no nested transactions)
- **250 checkpoints in 2.37s**
- **Rate: 105.6 checkpoints/sec**
- ~0.47s per request (50 checkpoints/page)

### Test 2: Checkpoints with nested transactions (balance changes included)
- **30 checkpoints with 30 transactions in 0.97s**
- **Rate: 30.9 checkpoints/sec, 30.9 txs/sec**
- 10 checkpoints per page, 50 txs per checkpoint page

**Note:** Test 2 fetched checkpoints from the earliest available range where most checkpoints had only 1 transaction. Production checkpoints average ~12.5 txs each, so real throughput will vary.

---

## 4. Ingestion Time Estimates

### Strategy: Checkpoint-first traversal

Assuming 10M checkpoints for 30 days:

| Scenario | Rate | Time | Notes |
|----------|------|------|-------|
| Conservative | 30 checkpoints/sec | ~92 hours (~3.8 days) | With nested txs + balance changes |
| Moderate | 50 checkpoints/sec | ~55 hours (~2.3 days) | Optimized queries |
| Optimistic | 100 checkpoints/sec | ~28 hours (~1.2 days) | Parallel requests |

### Bottlenecks
1. **Query payload limit (5KB):** Deep queries with many nested fields approach this limit. May need to split into checkpoint fetch + separate tx detail fetches.
2. **Max output nodes (1M):** Checkpoints with many transactions + their effects can hit this. Pagination handles it but adds requests.
3. **Rate limiting:** Per-IP rate limiting exists but exact numbers aren't published. Sustained high throughput may trigger throttling.

### Recommendation

**30 days of data is feasible via the public API** but will take 2-4 days of continuous ingestion. For the prototype this is acceptable — run initial ingestion once, then keep up with real-time (~12.5 txs/sec is easily achievable).

---

## 5. API Schema Differences vs Documentation

The actual API schema differs significantly from older documentation. Key differences found:

| Documented | Actual |
|-----------|--------|
| `transactionBlock` | `transaction` |
| `transactionBlocks` | `transactions` |
| `checkpoint(id: {sequenceNumber: N})` | `checkpoint(sequenceNumber: N)` |
| `Event.sendingModule` | `Event.transactionModule` |
| `Event.type` | `Event.contents.type` |
| `Event.json` | `Event.contents.json` |
| `Event.bcs` | `Event.contents.bcs` or `Event.eventBcs` |
| `AddressOwner.owner` | `AddressOwner.address` |
| `Transaction.signatures` (scalar) | `Transaction.signatures { signatureBytes }` |
| `address.objects` returns `ObjectConnection` | Returns `MoveObjectConnection` |
| `serviceConfig.requestTimeoutMs` | `serviceConfig.queryTimeoutMs` |
| `serviceConfig.maxDbQueryCost` | Not available |
| `serviceConfig.maxPageSize` (no args) | Requires `(type, field)` args |
| `Object.previousTransactionBlock` | `Object.previousTransaction` |

**Important:** Always introspect the schema before relying on documentation. The API is actively evolving (JSON-RPC deprecated, removal scheduled July 2026).

---

## 6. Key Observations

### System transactions (sender=null)
Every checkpoint contains 1-3 system transactions with `sender: null` and zero gas. These are:
- `ConsensusCommitPrologueTransaction`
- Epoch change transactions
- Other system operations

**Action:** Filter with `kind: PROGRAMMABLE_TX` to skip system transactions. They have no value for graph analytics.

### Gas prices observed
- Most transactions: **553 MIST** (base gas price)
- Some transactions: **663-4000 MIST** (priority/congested)
- Gas price alone is a useful signal for bot detection (bots often use exact base price)

### Object types observed
- `0x2::coin::Coin<0x2::sui::SUI>` — SUI coins
- `0x2::coin::Coin<...::usdc::USDC>` — USDC
- `0x2::coin::Coin<...::deep::DEEP>` — DEEP tokens
- DeFi pool objects (Cetus, DeepBook, etc.)
- Balance manager objects
- Dynamic fields

### Event types observed
- `OrderCanceled`, `OrderPlaced`, `OrderInfo` — DeepBook DEX events
- `PriceUpdated` — Oracle price feeds
- Events contain rich JSON data (pool IDs, amounts, trader addresses)

### Owner types observed
- `AddressOwner` — standard wallet ownership
- `ConsensusAddressOwner` — new consensus v2 type (treat similar to AddressOwner)
- `Shared` — shared objects (e.g., DEX pools)
- `Immutable` — immutable objects

---

## 7. Risk Validation

### R1: Memgraph RAM limits
**Status:** Cannot fully validate without loading data. But volume estimates suggest:
- 30 days = ~100-125M transactions, ~500M-1B edges
- At ~100-200 bytes per edge, this is ~100-200GB
- **128GB RAM server will likely NOT hold 30 days**
- Recommendation: Start with 7 days (~35M txs), measure actual memory usage, then scale

### R2: GraphQL API gaps
**Status: RESOLVED ✅**
The public GraphQL API exposes ALL fields needed for Layer 1:
- Sender addresses ✅
- Balance changes (who received what, how much, which coin) ✅
- Object changes (created/mutated/deleted) ✅
- Gas details (price, budget, computation cost, storage cost) ✅
- Object ownership (address owner, shared, etc.) ✅
- Timestamps, checkpoints, epochs ✅

**No full node required for the prototype.**

---

## 8. Confirmed Indexer Source Strategy

### Phase 1 (Prototype)
- **Source:** SUI GraphQL API (public endpoint)
- **Approach:** Checkpoint-first traversal with nested transaction fetching
- **Initial load:** Start with 7 days of data (not 30) to validate RAM usage
- **Real-time:** After initial load, poll latest checkpoints continuously
- **Filtering:** Only `PROGRAMMABLE_TX` transactions (skip system txs)

### Phase 2+ (Production)
- Consider SUI Full Node for unlimited throughput
- Or multiple API endpoints for parallel ingestion
- Evaluate SUI Indexer Framework for bulk historical data

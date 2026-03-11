# Graphen — Data Dictionary

**Phase 0 Discovery Sprint Output**
**Date:** 2026-03-11
**Source:** SUI GraphQL API (mainnet) — `https://graphql.mainnet.sui.io/graphql`

---

## 1. SUI API → Graphen Graph Schema Mapping

### Layer 1: Capital Flow

#### Wallet Node

| Graphen Property | SUI API Source | Type | Notes |
|-----------------|---------------|------|-------|
| `address` | `transaction.sender.address` / `balanceChange.owner.address` | String | Primary key. 0x-prefixed hex, 66 chars |
| `label` | — | String? | Not from API. Added manually or via heuristics |
| `first_seen` | Derived: earliest `effects.timestamp` for this address | DateTime | Computed during ingestion |
| `last_seen` | Derived: latest `effects.timestamp` for this address | DateTime | Computed during ingestion |

**Source queries:** `transactions`, `checkpoint.transactions`, `balanceChanges`

#### Transaction Node

| Graphen Property | SUI API Source | Type | Notes |
|-----------------|---------------|------|-------|
| `digest` | `transaction.digest` | String | Primary key. Base58-encoded |
| `timestamp` | `transaction.effects.timestamp` | DateTime | From the checkpoint containing this tx |
| `gas_used` | `effects.gasEffects.gasSummary.computationCost` | BigInt | In MIST (1 SUI = 10^9 MIST) |
| `gas_price` | `transaction.gasInput.gasPrice` | BigInt | Tokens per gas unit, in MIST |
| `gas_budget` | `transaction.gasInput.gasBudget` | BigInt | Max gas allowed |
| `gas_storage_cost` | `effects.gasEffects.gasSummary.storageCost` | BigInt | Storage cost in MIST |
| `gas_storage_rebate` | `effects.gasEffects.gasSummary.storageRebate` | BigInt | Storage rebate in MIST |
| `status` | `transaction.effects.status` | Enum | `SUCCESS` or `FAILURE` |
| `checkpoint` | `effects.checkpoint.sequenceNumber` | UInt53 | Checkpoint sequence number |
| `epoch` | `effects.epoch.epochId` | UInt53 | Epoch ID |
| `kind` | `transaction.kind.__typename` | String | e.g., `ProgrammableTransaction` |

**Source queries:** `transactions(filter: {kind: PROGRAMMABLE_TX})`, `checkpoint.transactions`

#### Object Node

| Graphen Property | SUI API Source | Type | Notes |
|-----------------|---------------|------|-------|
| `id` | `objectChange.address` / `object.address` | String | Primary key. 0x-prefixed hex |
| `type` | `object.asMoveObject.contents.type.repr` | String | Full Move type, e.g. `0x2::coin::Coin<0x2::sui::SUI>` |
| `coin_type` | Extracted from `type` when type matches `Coin<T>` | String? | e.g., `0x2::sui::SUI` |
| `value` | `object.asMoveObject.contents.json.balance` | BigInt? | Only for Coin objects. In MIST for SUI |
| `version` | `object.version` | UInt53 | Object version (increments on mutation) |
| `owner_type` | `object.owner.__typename` | String | `AddressOwner`, `Shared`, `Immutable`, `ObjectOwner`, `ConsensusAddressOwner` |

**Source queries:** `object(address)`, `objectChange.outputState`

### Relationships

#### SENT (Wallet → Transaction)

| Source | Mapping |
|--------|---------|
| `transaction.sender.address` | `(:Wallet {address: sender})-[:SENT]->(:Transaction {digest})` |

**Notes:** `sender` can be `null` for system transactions (genesis, epoch change, consensus prologue). Filter with `kind: PROGRAMMABLE_TX` to skip these.

#### RECEIVED_BY (Transaction → Wallet)

| Source | Mapping |
|--------|---------|
| `effects.balanceChanges` where `amount > 0` | `(:Transaction)-[:RECEIVED_BY {amount, coin_type}]->(:Wallet)` |

**Notes:**
- `balanceChanges.owner.address` = receiving wallet
- `balanceChanges.amount` = positive for received, negative for sent (BigInt string)
- `balanceChanges.coinType.repr` = full coin type string
- A single transaction can have multiple balance changes (multiple recipients, multiple coin types)

#### OWNS (Wallet → Object)

| Source | Mapping |
|--------|---------|
| `object.owner` (AddressOwner) | `(:Wallet)-[:OWNS]->(:Object)` |
| `objectChange.outputState.owner` (AddressOwner) | Updated per transaction |

**Notes:**
- `AddressOwner.address.address` = owning wallet address
- Shared and Immutable objects have no single owner
- `ConsensusAddressOwner` is a new owner type (consensus v2)
- OWNS is mutable — when an object transfers, delete old edge, create new one
- Consider time-bounded edges (`from_checkpoint`, `to_checkpoint`) per RISK_ANALYSIS R9

#### CREATED (Transaction → Object)

| Source | Mapping |
|--------|---------|
| `objectChange` where `idCreated = true` | `(:Transaction)-[:CREATED]->(:Object)` |

#### MUTATED (Transaction → Object)

| Source | Mapping |
|--------|---------|
| `objectChange` where `idCreated = false` AND `idDeleted = false` | `(:Transaction)-[:MUTATED]->(:Object)` |

#### DELETED (Transaction → Object)

| Source | Mapping |
|--------|---------|
| `objectChange` where `idDeleted = true` | `(:Transaction)-[:DELETED]->(:Object)` |

**Note:** Not in original schema but available from API. Worth tracking.

#### TRANSACTED_WITH (Wallet → Wallet, derived)

| Source | Mapping |
|--------|---------|
| Derived from SENT + RECEIVED_BY | `(:Wallet)-[:TRANSACTED_WITH {count, volume, last_at}]->(:Wallet)` |

**Notes:** Materialized edge, computed periodically. Not directly from API.

---

### Layer 2: DeFi & Events (Preview)

#### Event Node

| Graphen Property | SUI API Source | Type | Notes |
|-----------------|---------------|------|-------|
| `type` | `event.contents.type.repr` | String | Full event type string |
| `timestamp` | `event.timestamp` | DateTime | |
| `data` | `event.contents.json` | JSON | Event-specific fields |
| `sequence_number` | `event.sequenceNumber` | UInt53 | Event index within transaction |

#### Package / Module Nodes

| Graphen Property | SUI API Source | Type | Notes |
|-----------------|---------------|------|-------|
| Package `id` | `event.transactionModule.package.address` | String | Package address |
| Module `name` | `event.transactionModule.name` | String | Module name |

---

## 2. API Field Availability Summary

### Available for Layer 1 ✅

| Need | Available | Field Path |
|------|-----------|------------|
| Transaction digest | ✅ | `transaction.digest` |
| Sender address | ✅ | `transaction.sender.address` |
| Transaction timestamp | ✅ | `effects.timestamp` |
| Gas used (computation) | ✅ | `effects.gasEffects.gasSummary.computationCost` |
| Gas price | ✅ | `gasInput.gasPrice` |
| Gas budget | ✅ | `gasInput.gasBudget` |
| Transaction status | ✅ | `effects.status` |
| Balance changes (who received what) | ✅ | `effects.balanceChanges` |
| Object changes (created/mutated/deleted) | ✅ | `effects.objectChanges` |
| Object type | ✅ | `outputState.asMoveObject.contents.type.repr` |
| Object owner | ✅ | `outputState.owner` (AddressOwner/Shared/etc.) |
| Coin type on objects | ✅ | Extracted from Move type string |
| Object value (for coins) | ✅ | Via `object.asMoveObject.contents.json.balance` |
| Checkpoint sequence number | ✅ | `effects.checkpoint.sequenceNumber` |
| Epoch ID | ✅ | `effects.epoch.epochId` |
| Gas sponsor (sponsored tx) | ✅ | `gasInput.gasSponsor.address` |

### Gaps / Limitations ⚠️

| Need | Status | Workaround |
|------|--------|------------|
| Object value in objectChange | ⚠️ Partial | `outputState` has object info but no balance field directly. Need separate `object()` query or extract from `contents.json` |
| Historical object state | ⚠️ | `object(address, version)` can fetch historical versions, but costly |
| USD values | ❌ Not in API | External price feed (Phase 2) |
| Wallet labels | ❌ Not in API | Manual / community labeling |

### Conclusion

**The SUI GraphQL API provides ALL fields needed for Layer 1.** No full node required for the prototype. Every field in the Graphen graph schema can be populated from the public API.

---

## 3. Key Type Mappings

### Owner Types

| SUI Owner Type | Graphen Handling |
|---------------|-----------------|
| `AddressOwner` | Creates OWNS edge to Wallet |
| `ObjectOwner` | Object owned by another object (skip OWNS to wallet) |
| `Shared` | No single owner. Track as shared object |
| `Immutable` | Never changes. No OWNS edge needed |
| `ConsensusAddressOwner` | New type (consensus v2). Treat like AddressOwner for graph |

### Transaction Kinds

| SUI Kind | Include? |
|----------|---------|
| `ProgrammableTransaction` | ✅ Yes — user transactions |
| `GenesisTransaction` | ❌ Skip — one-time setup |
| `ConsensusCommitPrologueTransaction` | ❌ Skip — system (sender=null, gas=0) |
| `ChangeEpochTransaction` | ⚠️ Optional — epoch boundaries |
| `AuthenticatorStateUpdateTransaction` | ❌ Skip — system |
| `RandomnessStateUpdateTransaction` | ❌ Skip — system |
| `EndOfEpochTransaction` | ⚠️ Optional — epoch boundaries |

**Recommendation:** Filter with `kind: PROGRAMMABLE_TX` for Layer 1. System transactions have no sender, no gas, and pollute the graph.

### Coin Type Extraction

The Move type string for coins follows the pattern:
```
0x2::coin::Coin<COIN_TYPE>
```

Example: `0x2::coin::Coin<0x2::sui::SUI>` → coin_type = `0x2::sui::SUI`

Parse with regex: `Coin<(.+)>` to extract the inner coin type.

---

## 4. Pagination Model

All paginated fields use **Relay Cursor Connection** spec:

| Parameter | Direction | Description |
|-----------|-----------|-------------|
| `first: Int` | Forward | Take first N |
| `after: String` | Forward | After this cursor |
| `last: Int` | Backward | Take last N |
| `before: String` | Backward | Before this cursor |

Response includes:
```graphql
pageInfo {
  hasNextPage
  hasPreviousPage
  startCursor
  endCursor
}
```

**Cursors are opaque** — never construct them manually.

---

## 5. Ingestion Strategy

**Recommended approach:** Iterate checkpoints forward, pull nested transactions per checkpoint.

```
for each checkpoint (oldest → newest):
    fetch checkpoint.transactions (paginate if >50 txs)
    for each transaction:
        extract sender → Wallet node + SENT edge
        extract balanceChanges → Wallet nodes + RECEIVED_BY edges
        extract objectChanges → Object nodes + CREATED/MUTATED/DELETED edges
        extract gasEffects → Transaction gas properties
```

This ensures:
1. Sequential processing (no gaps)
2. Checkpoint-consistent data
3. Natural ordering for time-based queries

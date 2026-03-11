"""Explore SUI GraphQL API limits and benchmark throughput.

Queries serviceConfig, tests pagination limits, and measures request throughput.
"""

import time
from common import graphql_query, pretty_print

# Query: Service configuration / limits
SERVICE_CONFIG = """
query {
  serviceConfig {
    maxQueryDepth
    maxQueryNodes
    maxOutputNodes
    queryTimeoutMs
    mutationTimeoutMs
    maxQueryPayloadSize
    maxTransactionPayloadSize
    maxTypeArgumentDepth
    maxTypeArgumentWidth
    maxTypeNodes
    maxMoveValueDepth
    maxMoveValueBound
    maxMultiGetSize
    maxRichQueries
    checkpointDefaultPageSize: defaultPageSize(type: "Query", field: "checkpoints")
    checkpointMaxPageSize: maxPageSize(type: "Query", field: "checkpoints")
    txDefaultPageSize: defaultPageSize(type: "Checkpoint", field: "transactionBlocks")
    txMaxPageSize: maxPageSize(type: "Checkpoint", field: "transactionBlocks")
  }
}
"""

# Query: Latest checkpoint number (to calculate volume)
LATEST_CHECKPOINT = """
query {
  checkpoints(last: 1) {
    nodes {
      sequenceNumber
      networkTotalTransactions
      timestamp
    }
  }
}
"""

# Query: Checkpoint 30 days ago (approximate)
CHECKPOINT_AT_TIME = """
query ($seqNum: UInt53!) {
  checkpoint(sequenceNumber: $seqNum) {
    sequenceNumber
    networkTotalTransactions
    timestamp
  }
}
"""

# Query: Simple checkpoint fetch for throughput testing
CHECKPOINTS_PAGE = """
query ($first: Int!, $after: String) {
  checkpoints(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      sequenceNumber
      digest
      timestamp
      networkTotalTransactions
    }
  }
}
"""

# Query: Checkpoint with transactions for throughput testing
CHECKPOINT_WITH_TXS_PAGE = """
query ($first: Int!, $after: String) {
  checkpoints(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      sequenceNumber
      transactions(first: 50) {
        pageInfo {
          hasNextPage
        }
        nodes {
          digest
          sender {
            address
          }
          effects {
            status
            balanceChanges {
              nodes {
                owner {
                  address
                }
                amount
                coinType {
                  repr
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def explore_service_config():
    print("=" * 60)
    print("1. SERVICE CONFIGURATION")
    print("=" * 60)
    result = graphql_query(SERVICE_CONFIG)
    pretty_print(result)
    return result.get("data", {}).get("serviceConfig", {})


def explore_volume():
    print("\n" + "=" * 60)
    print("2. VOLUME ESTIMATION")
    print("=" * 60)

    # Get latest checkpoint
    result = graphql_query(LATEST_CHECKPOINT)
    latest = result.get("data", {}).get("checkpoints", {}).get("nodes", [{}])[0]
    latest_seq = int(latest.get("sequenceNumber", 0))
    latest_txs = int(latest.get("networkTotalTransactions", 0))
    latest_time = latest.get("timestamp", "N/A")
    print(f"Latest checkpoint: #{latest_seq}")
    print(f"Total network transactions: {latest_txs:,}")
    print(f"Timestamp: {latest_time}")

    # Try to get a checkpoint from ~30 days ago
    # SUI produces ~1 checkpoint per second, so 30 days ≈ 2,592,000 checkpoints back
    days_30_ago_seq = max(1, latest_seq - 2_592_000)
    result_old = graphql_query(CHECKPOINT_AT_TIME, {"seqNum": days_30_ago_seq})
    old = result_old.get("data", {}).get("checkpoint", {})

    if old:
        old_txs = int(old.get("networkTotalTransactions", 0))
        old_time = old.get("timestamp", "N/A")
        tx_in_30_days = latest_txs - old_txs
        checkpoints_in_30_days = latest_seq - days_30_ago_seq
        avg_txs_per_checkpoint = tx_in_30_days / checkpoints_in_30_days if checkpoints_in_30_days > 0 else 0

        print(f"\n30 days ago (approx) checkpoint: #{days_30_ago_seq}")
        print(f"Timestamp then: {old_time}")
        print(f"Transactions in last 30 days: {tx_in_30_days:,}")
        print(f"Checkpoints in last 30 days: {checkpoints_in_30_days:,}")
        print(f"Avg transactions per checkpoint: {avg_txs_per_checkpoint:.1f}")
    else:
        print("Could not fetch old checkpoint")

    return latest_seq


def benchmark_throughput(start_seq: int):
    print("\n" + "=" * 60)
    print("3. THROUGHPUT BENCHMARK")
    print("=" * 60)

    # Test 1: Simple checkpoint pagination (no nested txs)
    print("\nTest 1: Checkpoint-only pagination (50 per page, 5 pages)...")
    cursor = None
    total_checkpoints = 0
    t0 = time.time()
    for i in range(5):
        variables = {"first": 50}
        if cursor:
            variables["after"] = cursor
        result = graphql_query(CHECKPOINTS_PAGE, variables)
        page = result.get("data", {}).get("checkpoints", {})
        nodes = page.get("nodes", [])
        total_checkpoints += len(nodes)
        cursor = page.get("pageInfo", {}).get("endCursor")
        if not page.get("pageInfo", {}).get("hasNextPage"):
            break
    t1 = time.time()
    elapsed = t1 - t0
    print(f"  Fetched {total_checkpoints} checkpoints in {elapsed:.2f}s")
    print(f"  Rate: {total_checkpoints / elapsed:.1f} checkpoints/sec")
    print(f"  Requests: 5, {elapsed / 5:.2f}s per request")

    # Test 2: Checkpoints with nested transactions
    print("\nTest 2: Checkpoints with nested transactions (10 per page, 3 pages)...")
    cursor = None
    total_checkpoints = 0
    total_txs = 0
    t0 = time.time()
    for i in range(3):
        variables = {"first": 10}
        if cursor:
            variables["after"] = cursor
        result = graphql_query(CHECKPOINT_WITH_TXS_PAGE, variables)
        page = result.get("data", {}).get("checkpoints", {})
        nodes = page.get("nodes", [])
        total_checkpoints += len(nodes)
        for cp in nodes:
            txs = cp.get("transactions", {}).get("nodes", [])
            total_txs += len(txs)
        cursor = page.get("pageInfo", {}).get("endCursor")
        if not page.get("pageInfo", {}).get("hasNextPage"):
            break
    t1 = time.time()
    elapsed = t1 - t0
    print(f"  Fetched {total_checkpoints} checkpoints with {total_txs} transactions in {elapsed:.2f}s")
    print(f"  Rate: {total_checkpoints / elapsed:.1f} checkpoints/sec, {total_txs / elapsed:.1f} txs/sec")
    print(f"  Avg txs per checkpoint: {total_txs / total_checkpoints if total_checkpoints else 0:.1f}")


def estimate_ingestion_time(latest_seq: int):
    print("\n" + "=" * 60)
    print("4. INGESTION TIME ESTIMATE")
    print("=" * 60)

    checkpoints_30d = 2_592_000  # ~1 per second * 30 days
    print(f"Estimated checkpoints in 30 days: ~{checkpoints_30d:,}")
    print(f"\nAssuming achievable rates:")
    for rate in [50, 100, 200]:
        hours = checkpoints_30d / rate / 3600
        print(f"  At {rate} checkpoints/sec: {hours:.1f} hours ({hours / 24:.1f} days)")


if __name__ == "__main__":
    config = explore_service_config()
    latest = explore_volume()
    if latest:
        benchmark_throughput(latest)
        estimate_ingestion_time(latest)

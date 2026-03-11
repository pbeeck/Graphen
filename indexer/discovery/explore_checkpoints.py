"""Explore SUI checkpoints via GraphQL API.

Fetches recent checkpoints and inspects their structure,
including nested transactions.
"""

from common import graphql_query, pretty_print

# Query 1: Fetch latest checkpoints with basic info
LATEST_CHECKPOINTS = """
query ($first: Int!, $after: String) {
  checkpoints(last: $first, before: $after) {
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
    nodes {
      sequenceNumber
      digest
      timestamp
      networkTotalTransactions
      previousCheckpointDigest
      rollingGasSummary {
        computationCost
        storageCost
        storageRebate
        nonRefundableStorageFee
      }
      epoch {
        epochId
      }
    }
  }
}
"""

# Query 2: Fetch a single checkpoint with nested transactions
CHECKPOINT_WITH_TXS = """
query ($seqNum: UInt53!, $txFirst: Int!, $txAfter: String) {
  checkpoint(sequenceNumber: $seqNum) {
    sequenceNumber
    digest
    timestamp
    networkTotalTransactions
    epoch {
      epochId
    }
    transactions(first: $txFirst, after: $txAfter) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        digest
        sender {
          address
        }
        gasInput {
          gasPrice
          gasBudget
        }
        effects {
          status
          timestamp
          gasEffects {
            gasSummary {
              computationCost
              storageCost
              storageRebate
              nonRefundableStorageFee
            }
          }
          epoch {
            epochId
          }
          checkpoint {
            sequenceNumber
          }
        }
      }
    }
  }
}
"""


def explore_latest_checkpoints():
    print("=" * 60)
    print("1. LATEST CHECKPOINTS (last 5)")
    print("=" * 60)
    result = graphql_query(LATEST_CHECKPOINTS, {"first": 5})
    pretty_print(result)

    nodes = result.get("data", {}).get("checkpoints", {}).get("nodes", [])
    if nodes:
        print(f"\nFound {len(nodes)} checkpoints")
        print(f"Sequence range: {nodes[0]['sequenceNumber']} - {nodes[-1]['sequenceNumber']}")
        print(f"Latest timestamp: {nodes[-1]['timestamp']}")
        return int(nodes[-1]["sequenceNumber"])
    return None


def explore_checkpoint_with_transactions(seq_num: int):
    print("\n" + "=" * 60)
    print(f"2. CHECKPOINT {seq_num} WITH TRANSACTIONS")
    print("=" * 60)
    result = graphql_query(CHECKPOINT_WITH_TXS, {
        "seqNum": seq_num,
        "txFirst": 10,
    })
    pretty_print(result)

    checkpoint = result.get("data", {}).get("checkpoint", {})
    txs = checkpoint.get("transactions", {}).get("nodes", [])
    has_more = checkpoint.get("transactions", {}).get("pageInfo", {}).get("hasNextPage", False)
    print(f"\nTransactions in this checkpoint page: {len(txs)}")
    print(f"Has more transactions: {has_more}")

    for tx in txs[:3]:
        print(f"\n  TX: {tx['digest']}")
        print(f"  Sender: {(tx.get('sender') or {}).get('address', 'N/A')}")
        print(f"  Gas price: {tx.get('gasInput', {}).get('gasPrice', 'N/A')}")
        print(f"  Status: {tx.get('effects', {}).get('status', 'N/A')}")


if __name__ == "__main__":
    seq = explore_latest_checkpoints()
    if seq:
        explore_checkpoint_with_transactions(seq)

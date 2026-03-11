"""Explore SUI transaction blocks via GraphQL API.

Fetches transactions with full effects: balanceChanges, objectChanges, gasEffects.
This is the most critical exploration for mapping to our graph schema.
"""

from common import graphql_query, pretty_print

# Query: Recent transactions with full effects
RECENT_TRANSACTIONS = """
query ($first: Int!, $after: String) {
  transactions(last: $first, before: $after, filter: {kind: PROGRAMMABLE_TX}) {
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
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
        gasSponsor {
          address
        }
        gasPayment {
          nodes {
            address
            version
            digest
          }
        }
      }
      kind {
        __typename
      }
      signatures { signatureBytes }
      effects {
        status
        timestamp
        lamportVersion

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

        objectChanges {
          nodes {
            address
            idCreated
            idDeleted
            inputState {
              address
              version
              digest
              owner {
                __typename
                ... on AddressOwner {
                  address {
                    address
                  }
                }
                ... on Shared {
                  initialSharedVersion
                }
              }
            }
            outputState {
              address
              version
              digest
              owner {
                __typename
                ... on AddressOwner {
                  address {
                    address
                  }
                }
                ... on Shared {
                  initialSharedVersion
                }
              }
              asMoveObject {
                contents {
                  type {
                    repr
                  }
                }
              }
            }
          }
        }

        gasEffects {
          gasObject {
            address
            version
          }
          gasSummary {
            computationCost
            storageCost
            storageRebate
            nonRefundableStorageFee
          }
        }

        checkpoint {
          sequenceNumber
        }
        epoch {
          epochId
        }
      }
      expiration {
        epochId
      }
    }
  }
}
"""

# Query: Transaction by specific digest
TX_BY_DIGEST = """
query ($digest: String!) {
  transaction(digest: $digest) {
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
      objectChanges {
        nodes {
          address
          idCreated
          idDeleted
          outputState {
            owner {
              __typename
              ... on AddressOwner {
                address {
                  address
                }
              }
            }
            asMoveObject {
              contents {
                type {
                  repr
                }
              }
            }
          }
        }
      }
      gasEffects {
        gasSummary {
          computationCost
          storageCost
          storageRebate
          nonRefundableStorageFee
        }
      }
    }
  }
}
"""


def explore_recent_transactions():
    print("=" * 60)
    print("1. RECENT PROGRAMMABLE TRANSACTIONS (last 5)")
    print("=" * 60)
    result = graphql_query(RECENT_TRANSACTIONS, {"first": 5})
    pretty_print(result)

    nodes = result.get("data", {}).get("transactions", {}).get("nodes", [])
    print(f"\nFetched {len(nodes)} transactions")

    for tx in nodes:
        digest = tx["digest"]
        sender = tx.get("sender", {}).get("address", "N/A")
        status = tx.get("effects", {}).get("status", "N/A")
        balance_changes = tx.get("effects", {}).get("balanceChanges", {}).get("nodes", [])
        object_changes = tx.get("effects", {}).get("objectChanges", {}).get("nodes", [])
        gas = tx.get("effects", {}).get("gasEffects", {}).get("gasSummary", {})

        print(f"\n  TX: {digest}")
        print(f"  Sender: {sender}")
        print(f"  Status: {status}")
        print(f"  Balance changes: {len(balance_changes)}")
        for bc in balance_changes:
            owner = bc.get("owner", {}).get("address", "N/A")
            amount = bc.get("amount", "N/A")
            coin = bc.get("coinType", {}).get("repr", "N/A")
            print(f"    {owner}: {amount} ({coin})")
        print(f"  Object changes: {len(object_changes)}")
        for oc in object_changes:
            addr = oc.get("address", "N/A")
            created = oc.get("idCreated", False)
            deleted = oc.get("idDeleted", False)
            action = "CREATED" if created else "DELETED" if deleted else "MUTATED"
            obj_type = "unknown"
            output = oc.get("outputState")
            if output and output.get("asMoveObject"):
                contents = output["asMoveObject"].get("contents")
                if contents:
                    obj_type = contents.get("type", {}).get("repr", "unknown")
            print(f"    {addr}: {action} (type: {obj_type})")
        print(f"  Gas: computation={gas.get('computationCost', 'N/A')}, storage={gas.get('storageCost', 'N/A')}")

    return nodes[0]["digest"] if nodes else None


if __name__ == "__main__":
    explore_recent_transactions()

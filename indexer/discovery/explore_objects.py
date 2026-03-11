"""Explore SUI objects via GraphQL API.

Fetches objects to inspect ownership, types, and contents.
"""

from common import graphql_query, pretty_print

# Query: Objects owned by an address
# address.objects returns MoveObjectConnection (nodes are MoveObject, not Object)
OBJECTS_BY_OWNER = """
query ($owner: SuiAddress!, $first: Int!, $after: String) {
  address(address: $owner) {
    address
    balances {
      nodes {
        totalBalance
        coinType {
          repr
        }
      }
    }
    objects(first: $first, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        address
        version
        digest
        storageRebate
        owner {
          __typename
          ... on AddressOwner {
            address {
              address
            }
          }
        }
        contents {
          type {
            repr
          }
          json
        }
        hasPublicTransfer
        previousTransaction {
          digest
        }
      }
    }
  }
}
"""

# Query: Single object by address (returns Object, needs asMoveObject)
OBJECT_BY_ID = """
query ($address: SuiAddress!) {
  object(address: $address) {
    address
    version
    digest
    storageRebate
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
        json
      }
      hasPublicTransfer
    }
    previousTransaction {
      digest
    }
  }
}
"""

# Query: Find a recent active wallet for testing
FIND_ACTIVE_WALLET = """
query {
  transactions(last: 1, filter: {kind: PROGRAMMABLE_TX}) {
    nodes {
      sender {
        address
      }
      digest
    }
  }
}
"""


def find_active_wallet() -> str | None:
    """Find a recently active wallet to use for object exploration."""
    result = graphql_query(FIND_ACTIVE_WALLET)
    nodes = result.get("data", {}).get("transactions", {}).get("nodes", [])
    if nodes:
        addr = nodes[0]["sender"]["address"]
        print(f"Found active wallet: {addr}")
        return addr
    return None


def explore_objects_by_owner(owner: str):
    print("=" * 60)
    print(f"1. OBJECTS OWNED BY {owner[:20]}...")
    print("=" * 60)
    result = graphql_query(OBJECTS_BY_OWNER, {
        "owner": owner,
        "first": 10,
    })
    pretty_print(result)

    address_data = result.get("data", {}).get("address", {})

    # Balances
    balances = address_data.get("balances", {}).get("nodes", [])
    print(f"\nBalances ({len(balances)} coin types):")
    for b in balances:
        coin = b.get("coinType", {}).get("repr", "N/A")
        total = b.get("totalBalance", "N/A")
        print(f"  {coin}: {total}")

    # Objects (these are MoveObject — contents is directly on them)
    objects = address_data.get("objects", {}).get("nodes", [])
    has_more = address_data.get("objects", {}).get("pageInfo", {}).get("hasNextPage", False)
    print(f"\nObjects (showing {len(objects)}, has more: {has_more}):")
    for obj in objects:
        addr = obj.get("address", "N/A")
        obj_type = "unknown"
        contents = obj.get("contents")
        if contents:
            obj_type = contents.get("type", {}).get("repr", "unknown")
        owner_info = obj.get("owner", {})
        print(f"  {addr}: type={obj_type}, owner_type={owner_info.get('__typename', 'N/A')}")

    return objects[0]["address"] if objects else None


def explore_single_object(object_id: str):
    print("\n" + "=" * 60)
    print(f"2. SINGLE OBJECT: {object_id}")
    print("=" * 60)
    result = graphql_query(OBJECT_BY_ID, {"address": object_id})
    pretty_print(result)


if __name__ == "__main__":
    wallet = find_active_wallet()
    if wallet:
        obj_id = explore_objects_by_owner(wallet)
        if obj_id:
            explore_single_object(obj_id)
    else:
        print("Could not find an active wallet. Try providing one manually.")

"""Explore SUI events via GraphQL API.

Fetches events to inspect types, data, and emitting modules.
Important for Layer 2 (DeFi & Events).
"""

from common import graphql_query, pretty_print

# Query: Recent events
RECENT_EVENTS = """
query ($first: Int!, $after: String) {
  events(last: $first, before: $after) {
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
    nodes {
      timestamp
      sequenceNumber
      transactionModule {
        package {
          address
        }
        name
      }
      contents {
        type {
          repr
        }
        json
        bcs
      }
      sender {
        address
      }
      transaction {
        digest
      }
    }
  }
}
"""

# Query: Events from a specific transaction
EVENTS_FROM_TX = """
query ($digest: String!) {
  transaction(digest: $digest) {
    digest
    effects {
      events {
        nodes {
          timestamp
          transactionModule {
            package {
              address
            }
            name
          }
          contents {
            type {
              repr
            }
            json
          }
        }
      }
    }
  }
}
"""


def explore_recent_events():
    print("=" * 60)
    print("1. RECENT EVENTS (last 10)")
    print("=" * 60)
    result = graphql_query(RECENT_EVENTS, {"first": 10})
    pretty_print(result)

    nodes = result.get("data", {}).get("events", {}).get("nodes", [])
    print(f"\nFetched {len(nodes)} events")

    # Collect unique event types and packages
    event_types = set()
    packages = set()
    for event in nodes:
        contents = event.get("contents", {}) or {}
        evt_type = contents.get("type", {}).get("repr", "unknown")
        event_types.add(evt_type)
        module = event.get("transactionModule", {}) or {}
        if module:
            pkg = module.get("package", {}).get("address", "N/A")
            mod_name = module.get("name", "N/A")
            packages.add(f"{pkg}::{mod_name}")

    print(f"\nUnique event types ({len(event_types)}):")
    for t in sorted(event_types):
        print(f"  {t}")
    print(f"\nEmitting packages::modules ({len(packages)}):")
    for p in sorted(packages):
        print(f"  {p}")

    # Return a digest that has events
    for event in nodes:
        tx = event.get("transaction", {}) or {}
        if tx.get("digest"):
            return tx["digest"]
    return None


def explore_events_from_tx(digest: str):
    print("\n" + "=" * 60)
    print(f"2. EVENTS FROM TX: {digest}")
    print("=" * 60)
    result = graphql_query(EVENTS_FROM_TX, {"digest": digest})
    pretty_print(result)

    events = (result.get("data", {}).get("transaction", {})
              .get("effects", {}).get("events", {}).get("nodes", []))
    print(f"\nEvents in this transaction: {len(events)}")
    for event in events:
        contents = event.get("contents", {}) or {}
        print(f"  Type: {contents.get('type', {}).get('repr', 'N/A')}")
        print(f"  Module: {(event.get('transactionModule') or {}).get('name', 'N/A')}")
        json_data = contents.get("json")
        if json_data:
            print(f"  Data keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'raw'}")


if __name__ == "__main__":
    digest = explore_recent_events()
    if digest:
        explore_events_from_tx(digest)

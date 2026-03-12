import logging
import time

import requests

from config.settings import (
    SUI_GRAPHQL_URL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    TX_PAGE_SIZE,
)
from sources.base_source import BaseSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GraphQL query: fetch a single checkpoint with paginated transactions
# ---------------------------------------------------------------------------
CHECKPOINT_TX_QUERY = """
query ($seqNum: UInt53!, $txFirst: Int!, $txAfter: String) {
  checkpoint(sequenceNumber: $seqNum) {
    sequenceNumber
    timestamp
    epoch { epochId }
    transactions(first: $txFirst, after: $txAfter) {
      pageInfo { hasNextPage endCursor }
      nodes {
        digest
        sender { address }
        kind { __typename }
        gasInput {
          gasPrice
          gasBudget
          gasSponsor { address }
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
          checkpoint { sequenceNumber }
          epoch { epochId }
          balanceChanges {
            nodes {
              owner { address }
              amount
              coinType { repr }
            }
          }
          objectChanges {
            nodes {
              address
              idCreated
              idDeleted
              outputState {
                address
                version
                owner {
                  __typename
                  ... on AddressOwner {
                    address { address }
                  }
                  ... on Shared {
                    initialSharedVersion
                  }
                }
                asMoveObject {
                  contents {
                    type { repr }
                  }
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

LATEST_CHECKPOINT_QUERY = """
{
  checkpoints(last: 1) {
    nodes {
      sequenceNumber
    }
  }
}
"""


class GraphQLSource(BaseSource):
    """Fetches SUI blockchain data via the GraphQL API."""

    def __init__(
        self,
        url: str = SUI_GRAPHQL_URL,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        retry_delay: float = RETRY_DELAY,
    ):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query with retry logic and back-off."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    self.url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                if "errors" in data:
                    if "data" not in data or data["data"] is None:
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay * (attempt + 1)
                            logger.warning(
                                "GraphQL errors (attempt %d/%d), retrying in %.1fs: %s",
                                attempt + 1,
                                self.max_retries,
                                delay,
                                data["errors"],
                            )
                            time.sleep(delay)
                            continue
                        raise RuntimeError(f"GraphQL query failed: {data['errors']}")
                    # Partial data with errors — log but return what we have
                    logger.warning("GraphQL partial errors: %s", data["errors"])

                return data

            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (attempt + 1)
                    logger.warning(
                        "Request error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        self.max_retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                else:
                    raise

        # Should not be reached, but satisfy the type checker.
        raise RuntimeError("Exhausted retries without success or exception")

    # ------------------------------------------------------------------
    # Public interface (BaseSource)
    # ------------------------------------------------------------------

    def get_latest_checkpoint_number(self) -> int:
        """Return the sequence number of the most recent checkpoint."""
        data = self._execute_query(LATEST_CHECKPOINT_QUERY)
        nodes = data["data"]["checkpoints"]["nodes"]
        return int(nodes[0]["sequenceNumber"])

    def fetch_checkpoint_transactions(self, seq_num: int) -> list[dict]:
        """Fetch all transactions for a checkpoint, handling pagination."""
        all_transactions: list[dict] = []
        tx_after: str | None = None

        while True:
            variables: dict = {
                "seqNum": seq_num,
                "txFirst": TX_PAGE_SIZE,
            }
            if tx_after is not None:
                variables["txAfter"] = tx_after

            data = self._execute_query(CHECKPOINT_TX_QUERY, variables)
            checkpoint = data["data"]["checkpoint"]
            tx_connection = checkpoint["transactions"]

            all_transactions.extend(tx_connection["nodes"])

            page_info = tx_connection["pageInfo"]
            if page_info["hasNextPage"]:
                tx_after = page_info["endCursor"]
            else:
                break

        logger.debug(
            "Checkpoint %d: fetched %d transactions", seq_num, len(all_transactions)
        )
        return all_transactions

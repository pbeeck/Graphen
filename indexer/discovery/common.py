"""Shared GraphQL client for SUI API exploration."""

import json
import time
import requests

MAINNET_URL = "https://graphql.mainnet.sui.io/graphql"
DEFAULT_TIMEOUT = 40
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def graphql_query(query: str, variables: dict | None = None, url: str = MAINNET_URL) -> dict:
    """Execute a GraphQL query with retry logic."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                print(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
                if "data" not in data or data["data"] is None:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    raise RuntimeError(f"GraphQL query failed: {data['errors']}")

            return data

        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Request failed (attempt {attempt + 1}): {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise

    raise RuntimeError("Max retries exceeded")


def pretty_print(data: dict) -> None:
    """Print JSON data formatted."""
    print(json.dumps(data, indent=2, default=str))

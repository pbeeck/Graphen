import os

# SUI GraphQL API
SUI_GRAPHQL_URL = os.environ.get("SUI_GRAPHQL_URL", "https://graphql.mainnet.sui.io/graphql")

# Memgraph connection
MEMGRAPH_HOST = os.environ.get("MEMGRAPH_HOST", "localhost")
MEMGRAPH_PORT = int(os.environ.get("MEMGRAPH_PORT", 7687))

# Batching
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 10))
TX_PAGE_SIZE = int(os.environ.get("TX_PAGE_SIZE", 50))

# HTTP / retry
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 40))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", 2))

# Optional: override starting checkpoint (None = resume from last indexed)
_start_cp = os.environ.get("START_CHECKPOINT")
START_CHECKPOINT = int(_start_cp) if _start_cp is not None else None

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

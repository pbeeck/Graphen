"""
Memgraph writer for the Graphen indexer.

Uses the neo4j Python driver (Bolt protocol) which is compatible with Memgraph.
"""

import logging
import time

from neo4j import GraphDatabase

from config.settings import MEMGRAPH_HOST, MEMGRAPH_PORT

logger = logging.getLogger(__name__)


class MemgraphLoader:
    """Writes parsed SUI blockchain data into Memgraph as a property graph."""

    def __init__(self, host: str = MEMGRAPH_HOST, port: int = MEMGRAPH_PORT):
        uri = f"bolt://{host}:{port}"
        logger.info("Connecting to Memgraph at %s", uri)
        self._driver = GraphDatabase.driver(uri, auth=("", ""))
        self._setup_schema()

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------

    def _setup_schema(self) -> None:
        """Create constraints and indexes. Tolerates 'already exists' errors."""
        statements = [
            "CREATE CONSTRAINT ON (w:Wallet) ASSERT w.address IS UNIQUE;",
            "CREATE CONSTRAINT ON (t:Transaction) ASSERT t.digest IS UNIQUE;",
            "CREATE CONSTRAINT ON (o:Object) ASSERT o.id IS UNIQUE;",
            "CREATE INDEX ON :Transaction(checkpoint);",
            "CREATE INDEX ON :Transaction(timestamp);",
            "CREATE INDEX ON :Wallet(last_seen);",
        ]
        with self._driver.session() as session:
            for stmt in statements:
                try:
                    session.run(stmt)
                    logger.debug("Schema applied: %s", stmt.strip())
                except Exception as exc:
                    logger.debug("Schema statement skipped (already exists): %s — %s", stmt.strip(), exc)

    # ------------------------------------------------------------------
    # State tracking
    # ------------------------------------------------------------------

    def get_last_checkpoint(self) -> int | None:
        """Return the last successfully indexed checkpoint, or None."""
        query = "MATCH (s:_State {key: 'indexer'}) RETURN s.last_checkpoint AS cp"
        with self._driver.session() as session:
            result = session.run(query)
            record = result.single()
            if record and record["cp"] is not None:
                return int(record["cp"])
        return None

    def save_state(self, checkpoint_number: int) -> None:
        """Persist the last indexed checkpoint number."""
        query = "MERGE (s:_State {key: 'indexer'}) SET s.last_checkpoint = $checkpoint"
        with self._driver.session() as session:
            session.run(query, checkpoint=checkpoint_number)
        logger.debug("State saved: last_checkpoint=%d", checkpoint_number)

    # ------------------------------------------------------------------
    # Batch write
    # ------------------------------------------------------------------

    def write_batch(self, batch: dict) -> None:
        """Write an entire parsed batch (nodes + edges) in a single transaction."""
        start = time.time()

        wallets = batch.get("wallets", [])
        transactions = batch.get("transactions", [])
        objects = batch.get("objects", [])
        sent_edges = batch.get("sent_edges", [])
        received_by_edges = batch.get("received_by_edges", [])
        transferred_edges = batch.get("transferred_edges", [])
        created_edges = batch.get("created_edges", [])
        mutated_edges = batch.get("mutated_edges", [])
        deleted_edges = batch.get("deleted_edges", [])
        owns_edges = batch.get("owns_edges", [])

        logger.info(
            "Writing batch — wallets=%d, txs=%d, objects=%d, "
            "sent=%d, received=%d, transferred=%d, created=%d, mutated=%d, deleted=%d, owns=%d",
            len(wallets), len(transactions), len(objects),
            len(sent_edges), len(received_by_edges), len(transferred_edges),
            len(created_edges), len(mutated_edges), len(deleted_edges), len(owns_edges),
        )

        with self._driver.session() as session:
            with session.begin_transaction() as tx:
                # ---- Nodes ----
                if wallets:
                    tx.run(
                        """
                        UNWIND $wallets AS w
                        MERGE (wallet:Wallet {address: w.address})
                        ON CREATE SET wallet.first_seen = w.timestamp,
                                      wallet.last_seen = w.timestamp
                        ON MATCH SET wallet.last_seen = CASE WHEN w.timestamp > wallet.last_seen
                                                             THEN w.timestamp ELSE wallet.last_seen END,
                                     wallet.first_seen = CASE WHEN w.timestamp < wallet.first_seen
                                                              THEN w.timestamp ELSE wallet.first_seen END
                        """,
                        wallets=wallets,
                    )

                if transactions:
                    tx.run(
                        """
                        UNWIND $transactions AS tx
                        MERGE (t:Transaction {digest: tx.digest})
                        SET t.timestamp = tx.timestamp,
                            t.gas_used = tx.gas_used,
                            t.gas_price = tx.gas_price,
                            t.gas_budget = tx.gas_budget,
                            t.gas_storage_cost = tx.gas_storage_cost,
                            t.gas_storage_rebate = tx.gas_storage_rebate,
                            t.status = tx.status,
                            t.checkpoint = tx.checkpoint,
                            t.epoch = tx.epoch,
                            t.kind = tx.kind
                        """,
                        transactions=transactions,
                    )

                if objects:
                    tx.run(
                        """
                        UNWIND $objects AS o
                        MERGE (obj:Object {id: o.id})
                        SET obj.type = o.type,
                            obj.coin_type = o.coin_type,
                            obj.version = o.version,
                            obj.owner_type = o.owner_type
                        """,
                        objects=objects,
                    )

                # ---- Edges ----
                if sent_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (w:Wallet {address: e.sender_address})
                        MATCH (t:Transaction {digest: e.tx_digest})
                        MERGE (w)-[:SENT]->(t)
                        """,
                        edges=sent_edges,
                    )

                if received_by_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (t:Transaction {digest: e.tx_digest})
                        MATCH (w:Wallet {address: e.wallet_address})
                        MERGE (t)-[r:RECEIVED_BY]->(w)
                        SET r.amount = e.amount, r.coin_type = e.coin_type
                        """,
                        edges=received_by_edges,
                    )

                if transferred_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (s:Wallet {address: e.sender_address})
                        MATCH (r:Wallet {address: e.receiver_address})
                        CREATE (s)-[:TRANSFERRED {
                            amount: e.amount,
                            coin_type: e.coin_type,
                            tx_digest: e.tx_digest,
                            timestamp: e.timestamp
                        }]->(r)
                        """,
                        edges=transferred_edges,
                    )

                if created_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (t:Transaction {digest: e.tx_digest})
                        MATCH (o:Object {id: e.object_id})
                        MERGE (t)-[:CREATED]->(o)
                        """,
                        edges=created_edges,
                    )

                if mutated_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (t:Transaction {digest: e.tx_digest})
                        MATCH (o:Object {id: e.object_id})
                        MERGE (t)-[:MUTATED]->(o)
                        """,
                        edges=mutated_edges,
                    )

                if deleted_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (t:Transaction {digest: e.tx_digest})
                        MATCH (o:Object {id: e.object_id})
                        MERGE (t)-[:DELETED]->(o)
                        """,
                        edges=deleted_edges,
                    )

                if owns_edges:
                    tx.run(
                        """
                        UNWIND $edges AS e
                        MATCH (o:Object {id: e.object_id})
                        OPTIONAL MATCH ()-[old:OWNS]->(o)
                        DELETE old
                        WITH o, e
                        MATCH (w:Wallet {address: e.wallet_address})
                        MERGE (w)-[:OWNS]->(o)
                        """,
                        edges=owns_edges,
                    )

                tx.commit()

        elapsed = time.time() - start
        logger.info("Batch written in %.3fs", elapsed)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the Memgraph driver connection."""
        self._driver.close()
        logger.info("Memgraph connection closed")

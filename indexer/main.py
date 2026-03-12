import logging
import signal
import sys
import time

from config.settings import (
    BATCH_SIZE, START_CHECKPOINT, LOG_LEVEL, SUI_GRAPHQL_URL,
    MEMGRAPH_HOST, MEMGRAPH_PORT
)
from sources.graphql_source import GraphQLSource
from transformers.transaction_transformer import TransactionTransformer
from transformers.wallet_transformer import WalletTransformer
from transformers.object_transformer import ObjectTransformer
from loaders.memgraph_loader import MemgraphLoader

logger = logging.getLogger("graphen.indexer")


class Indexer:
    def __init__(self):
        self.source = GraphQLSource()
        self.tx_transformer = TransactionTransformer()
        self.wallet_transformer = WalletTransformer()
        self.object_transformer = ObjectTransformer()
        self.loader = MemgraphLoader()
        self.running = True

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info("Received signal %d, initiating graceful shutdown", signum)
        self.running = False

    def _process_checkpoint(self, seq_num: int) -> dict:
        batch = {
            "transactions": [],
            "wallets": [],
            "objects": [],
            "sent_edges": [],
            "received_by_edges": [],
            "transferred_edges": [],
            "created_edges": [],
            "mutated_edges": [],
            "deleted_edges": [],
            "owns_edges": []
        }

        raw_transactions = self.source.fetch_checkpoint_transactions(seq_num)

        for raw_tx in raw_transactions:
            tx_data = self.tx_transformer.transform(raw_tx)
            if tx_data is None:
                continue

            wallet_data = self.wallet_transformer.extract(raw_tx, tx_data["timestamp"])
            object_data = self.object_transformer.extract(raw_tx)

            batch["transactions"].append(tx_data)
            batch["wallets"].extend(wallet_data.get("wallets", []))
            batch["objects"].extend(object_data.get("objects", []))

            batch["sent_edges"].append({
                "sender_address": tx_data["sender_address"],
                "tx_digest": tx_data["digest"]
            })
            batch["received_by_edges"].extend(wallet_data.get("received_by_edges", []))
            batch["transferred_edges"].extend(wallet_data.get("transferred_edges", []))
            batch["created_edges"].extend(object_data.get("created_edges", []))
            batch["mutated_edges"].extend(object_data.get("mutated_edges", []))
            batch["deleted_edges"].extend(object_data.get("deleted_edges", []))
            batch["owns_edges"].extend(object_data.get("owns_edges", []))

        return batch

    def _merge_batches(self, target: dict, source: dict):
        for key in target:
            target[key].extend(source[key])

    def run(self):
        # Determine start checkpoint
        if START_CHECKPOINT is not None:
            current_checkpoint = START_CHECKPOINT
        else:
            last = self.loader.get_last_checkpoint()
            if last is not None:
                current_checkpoint = last + 1
            else:
                latest = self.source.get_latest_checkpoint_number()
                current_checkpoint = latest - 100

        latest = self.source.get_latest_checkpoint_number()
        logger.info(
            "Starting indexer from checkpoint %d (latest: %d, behind: %d)",
            current_checkpoint, latest, latest - current_checkpoint
        )

        while self.running:
            # Polling mode when caught up
            if current_checkpoint > latest:
                time.sleep(0.5)
                latest = self.source.get_latest_checkpoint_number()
                continue

            # Process a batch of checkpoints
            combined_batch = {
                "transactions": [],
                "wallets": [],
                "objects": [],
                "sent_edges": [],
                "received_by_edges": [],
                "transferred_edges": [],
                "created_edges": [],
                "mutated_edges": [],
                "deleted_edges": [],
                "owns_edges": []
            }

            batch_start = time.time()
            batch_end_checkpoint = min(current_checkpoint + BATCH_SIZE, latest + 1)

            for seq_num in range(current_checkpoint, batch_end_checkpoint):
                if not self.running:
                    break
                try:
                    checkpoint_batch = self._process_checkpoint(seq_num)
                    self._merge_batches(combined_batch, checkpoint_batch)
                except Exception:
                    logger.exception("Failed to process checkpoint %d, skipping", seq_num)

            # Flush to Memgraph
            try:
                self.loader.write_batch(combined_batch)
            except Exception:
                logger.warning("Memgraph write failed, retrying once")
                try:
                    self.loader.write_batch(combined_batch)
                except Exception:
                    logger.exception("Memgraph write failed on retry, exiting for data integrity")
                    self.running = False
                    break

            last_in_batch = batch_end_checkpoint - 1
            self.loader.save_state(last_in_batch)

            elapsed = time.time() - batch_start
            checkpoints_done = batch_end_checkpoint - current_checkpoint
            rate = checkpoints_done / elapsed if elapsed > 0 else 0
            tx_count = len(combined_batch["transactions"])
            lag = latest - last_in_batch

            logger.info(
                "Processed checkpoints %d-%d (%d txs) at %.1f cp/s | lag: %d",
                current_checkpoint, last_in_batch, tx_count, rate, lag
            )

            current_checkpoint = batch_end_checkpoint

    def shutdown(self):
        logger.info("Shutting down...")
        self.loader.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    indexer = Indexer()
    try:
        indexer.run()
    except KeyboardInterrupt:
        pass
    finally:
        indexer.shutdown()

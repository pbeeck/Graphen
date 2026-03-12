from abc import ABC, abstractmethod


class BaseSource(ABC):
    """Abstract base class for blockchain data sources."""

    @abstractmethod
    def get_latest_checkpoint_number(self) -> int:
        """Return the sequence number of the most recent checkpoint."""
        ...

    @abstractmethod
    def fetch_checkpoint_transactions(self, seq_num: int) -> list[dict]:
        """Return all transactions for a checkpoint, handling pagination internally."""
        ...

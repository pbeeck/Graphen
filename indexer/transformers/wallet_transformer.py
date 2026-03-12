class WalletTransformer:
    """Extracts wallet nodes and received_by edges from raw SUI transaction data."""

    def extract(self, raw_tx: dict, timestamp: str) -> dict:
        """Extract unique wallets and received_by edges from a raw transaction.

        Args:
            raw_tx: Raw transaction dict from SUI GraphQL API.
            timestamp: ISO datetime string for first_seen/last_seen tracking.

        Returns:
            Dict with 'wallets' list and 'received_by_edges' list.
        """
        wallets_seen: set[str] = set()
        received_by_edges: list[dict] = []

        # Sender wallet
        sender = raw_tx.get("sender") or {}
        sender_address = sender.get("address")
        if sender_address:
            wallets_seen.add(sender_address)

        # Digest for edges
        digest = raw_tx.get("digest")

        # Balance changes — receivers have positive amounts
        effects = raw_tx.get("effects") or {}
        balance_changes = effects.get("balanceChanges") or {}
        balance_nodes = balance_changes.get("nodes") or []

        for node in balance_nodes:
            amount = node.get("amount")
            if amount is None:
                continue

            try:
                amount_int = int(amount)
            except (ValueError, TypeError):
                continue

            if amount_int <= 0:
                continue

            owner = node.get("owner") or {}
            owner_address = owner.get("address")
            if not owner_address:
                continue

            wallets_seen.add(owner_address)

            coin_type_obj = node.get("coinType") or {}
            coin_type = coin_type_obj.get("repr") if isinstance(coin_type_obj, dict) else str(coin_type_obj)

            received_by_edges.append({
                "tx_digest": digest,
                "wallet_address": owner_address,
                "amount": str(amount),
                "coin_type": coin_type,
            })

        wallets = [{"address": addr, "timestamp": timestamp} for addr in wallets_seen]

        # Direct wallet-to-wallet TRANSFERRED edges for clean graph traversal
        transferred_edges: list[dict] = []
        if sender_address:
            for edge in received_by_edges:
                if edge["wallet_address"] != sender_address:
                    transferred_edges.append({
                        "sender_address": sender_address,
                        "receiver_address": edge["wallet_address"],
                        "amount": edge["amount"],
                        "coin_type": edge["coin_type"],
                        "tx_digest": edge["tx_digest"],
                        "timestamp": timestamp,
                    })

        return {
            "wallets": wallets,
            "received_by_edges": received_by_edges,
            "transferred_edges": transferred_edges,
        }

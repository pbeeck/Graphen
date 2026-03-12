class TransactionTransformer:
    """Transforms raw SUI GraphQL transaction responses into flat dicts for Memgraph ingestion."""

    def transform(self, raw_tx: dict) -> dict | None:
        """Extract a flat dict from a raw API transaction response.

        Returns None if the transaction should be skipped (non-ProgrammableTransaction or missing sender).
        """
        kind = raw_tx.get("kind") or {}
        kind_typename = kind.get("__typename")
        if kind_typename != "ProgrammableTransaction":
            return None

        sender = raw_tx.get("sender") or {}
        sender_address = sender.get("address")
        if sender_address is None:
            return None

        effects = raw_tx.get("effects") or {}
        gas_input = raw_tx.get("gasInput") or {}
        gas_effects = effects.get("gasEffects") or {}
        gas_summary = gas_effects.get("gasSummary") or {}
        checkpoint = effects.get("checkpoint") or {}
        epoch = effects.get("epoch") or {}

        gas_sponsor_obj = gas_input.get("gasSponsor") or {}
        gas_sponsor_address = gas_sponsor_obj.get("address")
        if gas_sponsor_address == sender_address:
            gas_sponsor_address = None

        return {
            "digest": raw_tx.get("digest"),
            "timestamp": effects.get("timestamp"),
            "gas_used": gas_summary.get("computationCost"),
            "gas_price": gas_input.get("gasPrice"),
            "gas_budget": gas_input.get("gasBudget"),
            "gas_storage_cost": gas_summary.get("storageCost"),
            "gas_storage_rebate": gas_summary.get("storageRebate"),
            "status": effects.get("status"),
            "checkpoint": int(checkpoint.get("sequenceNumber")) if checkpoint.get("sequenceNumber") is not None else None,
            "epoch": int(epoch.get("epochId")) if epoch.get("epochId") is not None else None,
            "kind": kind_typename,
            "sender_address": sender_address,
            "gas_sponsor": gas_sponsor_address,
        }

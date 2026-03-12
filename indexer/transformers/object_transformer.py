import re

COIN_TYPE_PATTERN = re.compile(r'Coin<(.+)>')


class ObjectTransformer:
    """Extracts object nodes and relationship edges from raw SUI transaction data."""

    def extract(self, raw_tx: dict) -> dict:
        """Extract objects and edges (created/mutated/deleted/owns) from a raw transaction.

        Args:
            raw_tx: Raw transaction dict from SUI GraphQL API.

        Returns:
            Dict with 'objects', 'created_edges', 'mutated_edges', 'deleted_edges', 'owns_edges'.
        """
        digest = raw_tx.get("digest")
        effects = raw_tx.get("effects") or {}
        object_changes = effects.get("objectChanges") or {}
        change_nodes = object_changes.get("nodes") or []

        objects: list[dict] = []
        created_edges: list[dict] = []
        mutated_edges: list[dict] = []
        deleted_edges: list[dict] = []
        owns_edges: list[dict] = []

        for node in change_nodes:
            address = node.get("address")
            if not address:
                continue

            id_created = node.get("idCreated", False)
            id_deleted = node.get("idDeleted", False)

            if id_deleted:
                deleted_edges.append({"tx_digest": digest, "object_id": address})
                continue

            # Created or mutated — extract from outputState
            output_state = node.get("outputState") or {}
            obj_id = output_state.get("address") or address

            # Type extraction via asMoveObject
            as_move_object = output_state.get("asMoveObject") or {}
            contents = as_move_object.get("contents") or {}
            type_obj = contents.get("type") or {}
            type_repr = type_obj.get("repr")

            # Coin type extraction
            coin_type = None
            if type_repr:
                match = COIN_TYPE_PATTERN.search(type_repr)
                if match:
                    coin_type = match.group(1)

            version_raw = output_state.get("version")
            version = int(version_raw) if version_raw is not None else None

            owner = output_state.get("owner") or {}
            owner_type = owner.get("__typename")

            obj = {
                "id": obj_id,
                "type": type_repr,
                "coin_type": coin_type,
                "version": version,
                "owner_type": owner_type,
            }
            objects.append(obj)

            if id_created:
                created_edges.append({"tx_digest": digest, "object_id": obj_id})
            else:
                mutated_edges.append({"tx_digest": digest, "object_id": obj_id})

            # Owns edge for AddressOwner
            if owner_type == "AddressOwner":
                owner_address_obj = owner.get("address") or {}
                owner_address = owner_address_obj.get("address")
                if owner_address:
                    owns_edges.append({"wallet_address": owner_address, "object_id": obj_id})

        return {
            "objects": objects,
            "created_edges": created_edges,
            "mutated_edges": mutated_edges,
            "deleted_edges": deleted_edges,
            "owns_edges": owns_edges,
        }

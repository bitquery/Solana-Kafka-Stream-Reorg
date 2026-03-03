"""
Reorg buffer: collect blocks, sort by slot, yield batches for ordered processing.
"""
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solana import parsed_idl_block_message_pb2

REORG_BUFFER_SIZE = 10

# (block_hash, parent_hash, slot, tx_block)
BatchItem = tuple[bytes, bytes, int, "parsed_idl_block_message_pb2.ParsedIdlBlockMessage"]


class ReorgBuffer:
    """Thread-safe buffer of blocks; when full or on flush, returns batch sorted by slot."""

    __slots__ = ("_size", "_items", "_lock")

    def __init__(self, size: int = REORG_BUFFER_SIZE):
        self._size = size
        self._items: list[BatchItem] = []
        self._lock = threading.Lock()

    def add(
        self,
        block_hash: bytes,
        parent_hash: bytes,
        slot: int,
        tx_block: "parsed_idl_block_message_pb2.ParsedIdlBlockMessage",
    ) -> list[BatchItem] | None:
        """
        Append one block. If buffer reaches size, return sorted batch and clear; else None.
        """
        with self._lock:
            self._items.append((block_hash, parent_hash, slot, tx_block))
            if len(self._items) >= self._size:
                batch = sorted(self._items, key=lambda x: x[2])
                self._items = []
                return batch
        return None

    def flush(self) -> list[BatchItem]:
        """Return remaining items sorted by slot and clear the buffer."""
        with self._lock:
            if not self._items:
                return []
            batch = sorted(self._items, key=lambda x: x[2])
            self._items = []
            return batch

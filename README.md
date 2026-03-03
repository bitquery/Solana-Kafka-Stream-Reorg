# Solana Kafka consumer (reorg-aware)

Kafka consumer for Solana block messages with **reorg detection and rollback**. Uses block **hash** as identity so chain reversals are handled correctly.

## Reorg logic

### Why hashes, not slots?

On Solana, the same slot can be produced by different blocks (forks). **Block identity is the block hash.** Confirmed blocks can be reverted; the only stable identifier is `Hash`, never `Slot`. So the consumer tracks a chain keyed by hash and detects reorgs by comparing parent hashes to the current tip.

### In-memory chain model

- **`_chain`**: `dict[bytes, BlockInfo]` — map from block hash → `BlockInfo(slot, parent_hash)`.
- **`_tip_hash`**: hash of the current chain tip (head), or `None` before the first block.

Each block is stored once by its `Header.Hash`. `BlockInfo` holds `slot` and `parent_hash` so we can walk backwards to find the fork point.

### When is it a reorg?

A **reorg** is when the next block’s **parent** is not our current **tip**:

```
is_reorg(new_parent_hash, tip_hash)  →  (tip_hash is not None) and (new_parent_hash != tip_hash)
```

- First block (`tip_hash is None`): not a reorg; we just extend.
- Next block’s parent equals our tip: normal extend; not a reorg.
- Next block’s parent ≠ our tip: we’re on a different fork → reorg.

Comparing only slots would miss these cases.

### Reorg handling (three steps)

1. **Detect**  
   Incoming block’s `parent_hash` ≠ our `_tip_hash` → reorg.

2. **Find fork point (common ancestor)**  
   Walk backwards from our tip, collecting hashes. If the incoming block’s `parent_hash` is in that set, it’s the common ancestor (fork point). If not (e.g. gap or unknown parent), we still add the block but don’t roll back.

3. **Orphan and roll back**  
   Every block from our tip back to (but not including) the fork point is “orphaned.” Those hashes are removed from `_chain`, and `_tip_hash` is updated. In this repo, `rollback_orphaned()` only logs the orphaned hashes; in production you would delete DB rows by those hashes (e.g. `DELETE FROM transactions WHERE block_hash IN (...)`).

### Flow in code

- **`apply_block_to_chain(block_hash, parent_hash, slot)`**  
  - If no tip yet → add block, no reorg.  
  - If `parent_hash == tip` → extend chain, no reorg.  
  - If reorg → `find_fork_point()` → `get_orphaned_hashes()` → remove orphaned entries from `_chain`, add the new block, set new tip, return the list of orphaned hashes.

- **`rollback_orphaned(orphaned_hashes)`**  
  Called by the message processor when `apply_block_to_chain` returns a non-empty list. Here it only logs; you can override to perform DB deletes by hash.

### Single ordered stream

Reorg logic assumes a **single ordered stream** of blocks. Multiple consumers in the same group see interleaved messages and can produce false reorgs, so this consumer uses `NUM_CONSUMERS = 1`.

## Running

1. Install dependencies (from `protobuf/`):

   ```bash
   pip install -r requirements.txt
   ```

2. Provide credentials via a local `config` module (e.g. `config.py` in `protobuf/` with `solana_username` and `solana_password`).

3. Run the consumer:

   ```bash
   cd protobuf && python consumer.py
   ```

Schema: [ParsedIdlBlockMessage](https://github.com/bitquery/streaming_protobuf/blob/main/solana/parsed_idl_block_message.proto). Python `pb2` package: [bitquery-pb2-kafka-package](https://pypi.org/project/bitquery-pb2-kafka-package/).

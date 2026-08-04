"""TRUST-3 batched bulk execution with abort + pacing."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.bulk_suite.transitions import PerRecordResult


def execute_in_batches(
    record_ids: list[int],
    execute_chunk: Callable[[list[int]], list[PerRecordResult]],
    *,
    batch_size: int,
    sleep_ms: int,
    should_abort: Callable[[], bool] | None = None,
    on_mutations: Callable[[int], None] | None = None,
) -> tuple[list[PerRecordResult], bool, list[int]]:
    """Run record ids in batches. Returns (results, aborted, unprocessed_ids)."""
    if not record_ids:
        return [], False, []

    size = max(1, int(batch_size or 1))
    results: list[PerRecordResult] = []
    processed = 0

    for start in range(0, len(record_ids), size):
        if should_abort and should_abort():
            return results, True, record_ids[processed:]
        chunk = record_ids[start : start + size]
        chunk_results = execute_chunk(chunk)
        results.extend(chunk_results)
        processed += len(chunk)
        if on_mutations:
            on_mutations(len(chunk))
        if start + size < len(record_ids):
            if should_abort and should_abort():
                return results, True, record_ids[processed:]
            delay = max(0, int(sleep_ms or 0))
            if delay:
                time.sleep(delay / 1000.0)

    return results, False, []

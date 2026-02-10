"""Integration tests for chunk execution with provider-like failures."""

from __future__ import annotations

import pytest

from synccraft.chunking import ChunkMetadata, execute_chunk_plan, plan_chunks


class _MockChunkProvider:
    """Provider-like fake that can fail on specific chunk indices."""

    def __init__(self, *, failed_indices: set[int]) -> None:
        self.failed_indices = failed_indices
        self.calls: list[int] = []

    def transcribe_chunk(self, chunk: ChunkMetadata) -> dict[str, str]:
        self.calls.append(chunk.index)
        if chunk.index in self.failed_indices:
            raise RuntimeError(f"provider rejected chunk {chunk.index}")
        return {"transcript": f"ok-{chunk.index}"}


@pytest.mark.integration
def test_execute_chunk_plan_stop_policy_halts_provider_calls_after_failure() -> None:
    chunks = plan_chunks(total_seconds=120, chunk_seconds=30)
    provider = _MockChunkProvider(failed_indices={2})

    result = execute_chunk_plan(chunks=chunks, transcribe_chunk=provider.transcribe_chunk, on_chunk_failure="stop")

    assert provider.calls == [0, 1, 2]
    assert [chunk.index for chunk, _ in result.successes] == [0, 1]
    assert [failure.chunk.index for failure in result.failures] == [2]
    assert result.aborted_early is True


@pytest.mark.integration
def test_execute_chunk_plan_continue_policy_attempts_all_chunks() -> None:
    chunks = plan_chunks(total_seconds=120, chunk_seconds=30)
    provider = _MockChunkProvider(failed_indices={1, 3})

    result = execute_chunk_plan(chunks=chunks, transcribe_chunk=provider.transcribe_chunk, on_chunk_failure="continue")

    assert provider.calls == [0, 1, 2, 3]
    assert [chunk.index for chunk, _ in result.successes] == [0, 2]
    assert [failure.chunk.index for failure in result.failures] == [1, 3]
    assert result.aborted_early is False

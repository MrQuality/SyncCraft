"""Unit tests for chunk planning and execution logic."""

from __future__ import annotations

import pytest

from synccraft.chunking import (
    ChunkMetadata,
    chunk_template_values,
    execute_chunk_plan,
    plan_chunks,
)


@pytest.mark.unit
def test_plan_chunks_without_chunk_seconds_returns_single_chunk() -> None:
    chunks = plan_chunks(total_seconds=61)
    assert chunks == [ChunkMetadata(index=0, start_second=0, end_second=61)]


@pytest.mark.unit
def test_plan_chunks_exact_multiple_boundaries() -> None:
    chunks = plan_chunks(total_seconds=60, chunk_seconds=30)
    assert chunks == [
        ChunkMetadata(index=0, start_second=0, end_second=30),
        ChunkMetadata(index=1, start_second=30, end_second=60),
    ]


@pytest.mark.unit
def test_plan_chunks_with_remainder_chunk() -> None:
    chunks = plan_chunks(total_seconds=61, chunk_seconds=30)
    assert chunks == [
        ChunkMetadata(index=0, start_second=0, end_second=30),
        ChunkMetadata(index=1, start_second=30, end_second=60),
        ChunkMetadata(index=2, start_second=60, end_second=61),
    ]


@pytest.mark.unit
def test_plan_chunks_tiny_file_single_chunk() -> None:
    chunks = plan_chunks(total_seconds=1, chunk_seconds=30)
    assert chunks == [ChunkMetadata(index=0, start_second=0, end_second=1)]


@pytest.mark.unit
def test_plan_chunks_invalid_chunk_size_has_fix_hint() -> None:
    with pytest.raises(ValueError, match="what: chunk_seconds must be positive.*how-to-fix"):
        plan_chunks(total_seconds=61, chunk_seconds=0)


@pytest.mark.unit
def test_plan_chunks_negative_total_has_fix_hint() -> None:
    with pytest.raises(ValueError, match="what: total_seconds cannot be negative.*how-to-fix"):
        plan_chunks(total_seconds=-1, chunk_seconds=10)


@pytest.mark.unit
def test_execute_chunk_plan_stop_aborts_at_first_failure() -> None:
    chunks = plan_chunks(total_seconds=90, chunk_seconds=30)

    def _transcribe(chunk: ChunkMetadata) -> dict[str, str]:
        if chunk.index == 1:
            raise RuntimeError("chunk failed")
        return {"transcript": f"chunk-{chunk.index}"}

    result = execute_chunk_plan(chunks=chunks, transcribe_chunk=_transcribe, on_chunk_failure="stop")

    assert [chunk.index for chunk, _ in result.successes] == [0]
    assert [failure.chunk.index for failure in result.failures] == [1]
    assert result.aborted_early is True


@pytest.mark.unit
def test_execute_chunk_plan_continue_collects_failures() -> None:
    chunks = plan_chunks(total_seconds=120, chunk_seconds=30)

    def _transcribe(chunk: ChunkMetadata) -> dict[str, str]:
        if chunk.index in {1, 3}:
            raise RuntimeError(f"chunk-{chunk.index} failed")
        return {"transcript": f"chunk-{chunk.index}"}

    result = execute_chunk_plan(chunks=chunks, transcribe_chunk=_transcribe, on_chunk_failure="continue")

    assert [chunk.index for chunk, _ in result.successes] == [0, 2]
    assert [failure.chunk.index for failure in result.failures] == [1, 3]
    assert result.aborted_early is False


@pytest.mark.unit
def test_chunk_template_values_exposes_metadata_for_naming() -> None:
    chunk = ChunkMetadata(index=2, start_second=60, end_second=90)
    assert chunk_template_values(chunk=chunk) == {"index": 2, "chunk_start": 60, "chunk_end": 90}

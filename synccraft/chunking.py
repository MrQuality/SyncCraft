"""Chunk planning and execution helpers for media segmentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from synccraft.errors import format_user_error

_ALLOWED_FAILURE_POLICIES = {"stop", "continue"}


@dataclass(frozen=True, slots=True)
class ChunkMetadata:
    """Deterministic metadata describing a single chunk interval."""

    index: int
    start_second: int
    end_second: int


@dataclass(frozen=True, slots=True)
class ChunkFailure:
    """Failure metadata for a chunk provider invocation."""

    chunk: ChunkMetadata
    error: Exception


@dataclass(slots=True)
class ChunkExecutionResult:
    """Result of processing all chunks under a configured failure policy."""

    successes: list[tuple[ChunkMetadata, dict[str, Any]]]
    failures: list[ChunkFailure]
    aborted_early: bool


def plan_chunks(*, total_seconds: int, chunk_seconds: int | None = None) -> list[ChunkMetadata]:
    """Split total duration into contiguous deterministic chunk intervals.

    When ``chunk_seconds`` is ``None``, chunking is disabled and a single chunk
    spanning the full duration is returned.
    """
    if total_seconds < 0:
        raise ValueError(
            format_user_error(
                what="total_seconds cannot be negative.",
                why="duration must represent elapsed seconds",
                how_to_fix="set total_seconds to 0 or a positive integer",
            )
        )

    if total_seconds == 0:
        return []

    if chunk_seconds is None:
        return [ChunkMetadata(index=0, start_second=0, end_second=total_seconds)]

    if chunk_seconds <= 0:
        raise ValueError(
            format_user_error(
                what="chunk_seconds must be positive.",
                why="zero or negative chunk sizes create invalid ranges",
                how_to_fix="provide a chunk size greater than 0",
            )
        )

    chunks: list[ChunkMetadata] = []
    start = 0
    index = 0
    while start < total_seconds:
        end = min(start + chunk_seconds, total_seconds)
        chunks.append(ChunkMetadata(index=index, start_second=start, end_second=end))
        start = end
        index += 1
    return chunks


def chunk_template_values(*, chunk: ChunkMetadata) -> dict[str, int]:
    """Expose chunk metadata fields used by logging and output naming."""
    return {
        "index": chunk.index,
        "chunk_start": chunk.start_second,
        "chunk_end": chunk.end_second,
    }


def execute_chunk_plan(
    *,
    chunks: list[ChunkMetadata],
    transcribe_chunk: Callable[[ChunkMetadata], dict[str, Any]],
    on_chunk_failure: str = "stop",
) -> ChunkExecutionResult:
    """Execute provider transcriptions for each chunk using a failure policy."""
    if on_chunk_failure not in _ALLOWED_FAILURE_POLICIES:
        options = ", ".join(sorted(_ALLOWED_FAILURE_POLICIES))
        raise ValueError(
            format_user_error(
                what=f"on_chunk_failure must be one of: {options}.",
                why="unsupported chunk failure handling policy was provided",
                how_to_fix=f"choose one of {options}",
            )
        )

    successes: list[tuple[ChunkMetadata, dict[str, Any]]] = []
    failures: list[ChunkFailure] = []

    for chunk in chunks:
        try:
            payload = transcribe_chunk(chunk)
            successes.append((chunk, payload))
        except Exception as exc:  # pragma: no cover - branch behavior tested externally
            failures.append(ChunkFailure(chunk=chunk, error=exc))
            if on_chunk_failure == "stop":
                return ChunkExecutionResult(successes=successes, failures=failures, aborted_early=True)

    return ChunkExecutionResult(successes=successes, failures=failures, aborted_early=False)

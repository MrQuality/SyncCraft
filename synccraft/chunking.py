"""Chunk planning for media segmentation."""

from __future__ import annotations

from synccraft.errors import format_user_error



def plan_chunks(*, total_seconds: int, chunk_seconds: int) -> list[tuple[int, int]]:
    """Split total duration into contiguous chunk intervals."""
    if chunk_seconds <= 0:
        raise ValueError(
            format_user_error(
                what="chunk_seconds must be positive.",
                why="zero or negative chunk sizes create invalid ranges",
                how_to_fix="provide a chunk size greater than 0",
            )
        )
    if total_seconds < 0:
        raise ValueError(
            format_user_error(
                what="total_seconds cannot be negative.",
                why="duration must represent elapsed seconds",
                how_to_fix="set total_seconds to 0 or a positive integer",
            )
        )

    chunks: list[tuple[int, int]] = []
    start = 0
    while start < total_seconds:
        end = min(start + chunk_seconds, total_seconds)
        chunks.append((start, end))
        start = end
    return chunks

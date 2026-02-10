"""Unit tests for chunk planning logic."""

import pytest

from synccraft.chunking import plan_chunks


@pytest.mark.unit
def test_plan_chunks_splits_durations_evenly() -> None:
    chunks = plan_chunks(total_seconds=61, chunk_seconds=30)
    assert chunks == [(0, 30), (30, 60), (60, 61)]


@pytest.mark.unit
def test_plan_chunks_invalid_chunk_size_has_fix_hint() -> None:
    with pytest.raises(ValueError, match="what: chunk_seconds must be positive.*how-to-fix"):
        plan_chunks(total_seconds=61, chunk_seconds=0)

@pytest.mark.unit
def test_plan_chunks_negative_total_has_fix_hint() -> None:
    with pytest.raises(ValueError, match="what: total_seconds cannot be negative.*how-to-fix"):
        plan_chunks(total_seconds=-1, chunk_seconds=10)

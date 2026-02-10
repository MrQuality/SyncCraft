"""Provider adapter implementations and contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synccraft.errors import format_user_error

if TYPE_CHECKING:
    from synccraft.chunking import ChunkMetadata


class MockProviderAdapter:
    """Test-friendly provider adapter backed by a local JSON payload."""

    def __init__(self, *, payload_file: str | Path) -> None:
        self.payload_file = Path(payload_file)

    def transcribe(self, *, audio_path: str | Path, chunk: ChunkMetadata | None = None) -> dict[str, Any]:
        """Return transcript data from fixture payload while validating contract.

        The optional ``chunk`` parameter enables deterministic failure simulation
        and chunk-specific transcript values for integration tests.
        """
        path = Path(audio_path)
        if not path.exists():
            raise ValueError(
                format_user_error(
                    what=f"audio file not found: {path}",
                    why="CLI was given a path that does not exist",
                    how_to_fix="provide an existing audio path under tests/fixtures/audio or your media directory",
                )
            )

        data = self._load_payload()
        result = dict(data)

        if chunk is not None:
            if chunk.index in self._failed_chunk_indices(data):
                raise ValueError(
                    format_user_error(
                        what=f"provider failed for chunk index {chunk.index}.",
                        why="mock payload requested a deterministic chunk failure",
                        how_to_fix="remove this index from fail_on_chunk_indices or change failure policy",
                    )
                )

            chunk_transcripts = data.get("chunk_transcripts")
            if isinstance(chunk_transcripts, dict):
                candidate = chunk_transcripts.get(str(chunk.index))
                if isinstance(candidate, str):
                    result["transcript"] = candidate

        if "transcript" not in result:
            raise ValueError(
                format_user_error(
                    what="provider response missing 'transcript'.",
                    why="adapter contract requires a transcript field",
                    how_to_fix="ensure provider response JSON includes a non-empty transcript value",
                )
            )
        return result

    def get_max_audio_seconds(self) -> int | None:
        """Return provider-side max duration limit when declared in payload."""
        if not self.payload_file.exists():
            return None
        data = json.loads(self.payload_file.read_text(encoding="utf-8"))
        limit = data.get("max_audio_seconds")
        if isinstance(limit, int) and limit > 0:
            return limit
        return None

    def validate_chunking_payload_schema(self) -> None:
        """Validate chunk-related mock payload keys before execution."""
        data = self._load_payload()

        fail_on_chunk_indices = data.get("fail_on_chunk_indices")
        if fail_on_chunk_indices is not None:
            if not isinstance(fail_on_chunk_indices, list):
                raise ValueError(
                    format_user_error(
                        what="provider.fail_on_chunk_indices must be a list of non-negative integers.",
                        why="chunk failure simulation requires explicit chunk indices",
                        how_to_fix="set fail_on_chunk_indices like [0, 2] or remove it",
                    )
                )
            if any(not isinstance(value, int) or value < 0 for value in fail_on_chunk_indices):
                raise ValueError(
                    format_user_error(
                        what="provider.fail_on_chunk_indices contains invalid values.",
                        why="all chunk indices must be non-negative integers",
                        how_to_fix="use only integer indices >= 0, for example [1, 3]",
                    )
                )

        chunk_transcripts = data.get("chunk_transcripts")
        if chunk_transcripts is not None:
            if not isinstance(chunk_transcripts, dict):
                raise ValueError(
                    format_user_error(
                        what="provider.chunk_transcripts must be a mapping of chunk index to transcript.",
                        why="chunk-specific transcript overrides require key/value pairs",
                        how_to_fix="set chunk_transcripts like {'0': 'intro', '1': 'middle'} or remove it",
                    )
                )

            for key, value in chunk_transcripts.items():
                if not isinstance(key, str) or not key.isdigit():
                    raise ValueError(
                        format_user_error(
                            what="provider.chunk_transcripts contains an invalid key.",
                            why="chunk transcript keys must be numeric strings like '0' or '2'",
                            how_to_fix="replace keys with numeric strings only",
                        )
                    )
                if not isinstance(value, str):
                    raise ValueError(
                        format_user_error(
                            what=f"provider.chunk_transcripts['{key}'] must be a string transcript.",
                            why="chunk transcript overrides require text values",
                            how_to_fix="set each chunk_transcripts value to a string",
                        )
                    )

    def _load_payload(self) -> dict[str, Any]:
        """Load payload JSON and enforce basic file and shape invariants."""
        if not self.payload_file.exists():
            raise ValueError(
                format_user_error(
                    what=f"provider payload file not found: {self.payload_file}",
                    why="adapter expects a JSON payload file",
                    how_to_fix="create a JSON fixture with transcript/confidence fields and pass its path",
                )
            )

        data = json.loads(self.payload_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(
                format_user_error(
                    what="provider payload must be a JSON object.",
                    why="the adapter expects named fields like transcript and max_audio_seconds",
                    how_to_fix="use JSON object syntax, for example {'transcript': '...'}",
                )
            )
        return data

    @staticmethod
    def _failed_chunk_indices(data: dict[str, Any]) -> set[int]:
        """Parse configured chunk failure indices from payload fixtures."""
        raw = data.get("fail_on_chunk_indices")
        if not isinstance(raw, list):
            return set()

        parsed: set[int] = set()
        for value in raw:
            if isinstance(value, int) and value >= 0:
                parsed.add(value)
        return parsed

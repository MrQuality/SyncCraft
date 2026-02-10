"""Provider adapter implementations and contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from synccraft.errors import format_user_error


class MockProviderAdapter:
    """Test-friendly provider adapter backed by a local JSON payload."""

    def __init__(self, *, payload_file: str | Path) -> None:
        self.payload_file = Path(payload_file)

    def transcribe(self, *, audio_path: str | Path) -> dict[str, Any]:
        """Return transcript data from fixture payload while validating contract."""
        path = Path(audio_path)
        if not path.exists():
            raise ValueError(
                format_user_error(
                    what=f"audio file not found: {path}",
                    why="CLI was given a path that does not exist",
                    how_to_fix="provide an existing audio path under tests/fixtures/audio or your media directory",
                )
            )

        if not self.payload_file.exists():
            raise ValueError(
                format_user_error(
                    what=f"provider payload file not found: {self.payload_file}",
                    why="adapter expects a JSON payload file",
                    how_to_fix="create a JSON fixture with transcript/confidence fields and pass its path",
                )
            )

        data = json.loads(self.payload_file.read_text(encoding="utf-8"))
        if "transcript" not in data:
            raise ValueError(
                format_user_error(
                    what="provider response missing 'transcript'.",
                    why="adapter contract requires a transcript field",
                    how_to_fix="ensure provider response JSON includes a non-empty transcript value",
                )
            )
        return data

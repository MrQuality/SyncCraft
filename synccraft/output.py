"""Output writer utilities."""

from __future__ import annotations

from pathlib import Path



def write_transcript(*, output_path: str | Path, transcript: str) -> None:
    """Write transcript text to disk with trailing newline."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{transcript}\n", encoding="utf-8")

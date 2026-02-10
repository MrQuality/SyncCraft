"""SyncCraft command line entrypoint."""

from __future__ import annotations

import argparse
import sys

from synccraft.errors import format_user_error
from synccraft.output import write_transcript
from synccraft.provider import MockProviderAdapter



def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for transcribe command."""
    parser = argparse.ArgumentParser(prog="synccraft")
    parser.add_argument("--audio", required=True, help="Path to source audio file")
    parser.add_argument("--provider-payload", required=True, help="Mock provider JSON payload file")
    parser.add_argument("--output", required=True, help="Output transcript file")
    return parser



def main(argv: list[str] | None = None) -> int:
    """Run CLI command and return process status code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        adapter = MockProviderAdapter(payload_file=args.provider_payload)
        result = adapter.transcribe(audio_path=args.audio)
        write_transcript(output_path=args.output, transcript=result["transcript"])
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive guard
        print(
            format_user_error(
                what="unexpected runtime failure.",
                why=str(exc),
                how_to_fix="inspect stack trace and re-run with validated inputs",
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

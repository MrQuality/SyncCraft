"""SyncCraft command line entrypoint."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from synccraft.errors import format_user_error
from synccraft.media import WaveDurationExtractor, validate_audio_path, validate_image_path
from synccraft.output import write_transcript
from synccraft.provider import MockProviderAdapter

_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for transcribe command."""
    parser = argparse.ArgumentParser(prog="synccraft")
    parser.add_argument("image", help="Path to source image file")
    parser.add_argument("audio", help="Path to source audio file")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--verbose", action="store_true", help="Enable INFO logging")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print execution summary")
    parser.add_argument("--version", action="store_true", help="Print SyncCraft version and exit")
    return parser


def _configure_logging(*, debug: bool, verbose: bool) -> None:
    """Configure global logging level based on CLI flags."""
    level = logging.WARNING
    if verbose:
        level = logging.INFO
    if debug:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", force=True)


def _load_config(*, path: str | Path) -> dict[str, Any]:
    """Read YAML configuration from disk."""
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(
            format_user_error(
                what=f"config file not found: {config_path}",
                why="--config must point to a readable YAML file",
                how_to_fix="create the config file and provide its path to --config",
            )
        )

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if content is None:
        content = {}
    if not isinstance(content, dict):
        raise ValueError(
            format_user_error(
                what="config content must be a mapping.",
                why="SyncCraft requires named options under top-level keys",
                how_to_fix="use YAML object format, for example: provider_payload: ...",
            )
        )
    return content


def _validate_path_exists(*, value: str, field_name: str) -> None:
    """Validate a path exists on disk."""
    if not Path(value).exists():
        raise ValueError(
            format_user_error(
                what=f"{field_name} not found: {value}",
                why="the provided path does not exist",
                how_to_fix=f"provide an existing file path for {field_name}",
            )
        )


def _validate_execution_inputs(*, image: str, audio: str, config: dict[str, Any]) -> tuple[str, str]:
    """Validate required CLI and config inputs before execution."""
    validate_image_path(image)
    validate_audio_path(audio)

    provider_payload = config.get("provider_payload")
    output_path = config.get("output")

    if not provider_payload:
        raise ValueError(
            format_user_error(
                what="missing required config key: provider_payload.",
                why="provider payload path is needed for mock transcription",
                how_to_fix="add provider_payload: <json-file> to your config",
            )
        )

    if not output_path:
        raise ValueError(
            format_user_error(
                what="missing required config key: output.",
                why="SyncCraft needs an output destination for transcript text",
                how_to_fix="add output: <transcript-file> to your config",
            )
        )

    _validate_path_exists(value=provider_payload, field_name="provider_payload")
    return str(provider_payload), str(output_path)


def _validate_duration_against_provider_limit(*, audio: str, config: dict[str, Any], adapter: MockProviderAdapter) -> None:
    """Fail fast when the source duration exceeds provider limit without chunking."""
    max_audio_seconds = adapter.get_max_audio_seconds()
    if max_audio_seconds is None:
        return

    audio_seconds = WaveDurationExtractor().duration_seconds(audio)
    if audio_seconds <= max_audio_seconds:
        return

    chunk_seconds = config.get("chunk_seconds")
    chunking_configured = isinstance(chunk_seconds, int) and chunk_seconds > 0
    if chunking_configured:
        return

    snippet = "audio:\n  chunk_seconds: 30\n  on_chunk_failure: abort"
    raise ValueError(
        format_user_error(
            what=(
                "audio duration exceeds provider limit with no chunking configured "
                f"(duration={audio_seconds}s, provider_limit={max_audio_seconds}s)."
            ),
            why="provider rejected long-form audio unless chunking is enabled",
            how_to_fix=(
                "configure chunking in YAML, for example:\n"
                f"{snippet}"
            ),
        )
    )


def _print_execution_summary(*, image: str, audio: str, config_path: str, output: str, provider_payload: str) -> None:
    """Print a concise execution summary for dry-run and transparency."""
    print("SyncCraft execution summary")
    print(f"  image: {image}")
    print(f"  audio: {audio}")
    print(f"  config: {config_path}")
    print(f"  provider_payload: {provider_payload}")
    print(f"  output: {output}")


def main(argv: list[str] | None = None) -> int:
    """Run CLI command and return process status code."""
    raw_argv = argv if argv is not None else sys.argv[1:]
    if "--version" in raw_argv:
        print(f"synccraft {_VERSION}")
        return 0

    parser = build_parser()
    args = parser.parse_args(raw_argv)
    _configure_logging(debug=args.debug, verbose=args.verbose)

    try:
        config = _load_config(path=args.config)
        provider_payload, output_path = _validate_execution_inputs(image=args.image, audio=args.audio, config=config)
        _print_execution_summary(
            image=args.image,
            audio=args.audio,
            config_path=args.config,
            output=output_path,
            provider_payload=provider_payload,
        )

        if args.dry_run:
            logging.getLogger(__name__).info("Dry-run mode enabled; skipping provider calls")
            return 0

        adapter = MockProviderAdapter(payload_file=provider_payload)
        _validate_duration_against_provider_limit(audio=args.audio, config=config, adapter=adapter)
        result = adapter.transcribe(audio_path=args.audio)
        write_transcript(output_path=output_path, transcript=result["transcript"])
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

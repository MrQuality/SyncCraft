"""SyncCraft command line entrypoint."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from synccraft.chunking import ChunkMetadata, chunk_template_values, execute_chunk_plan, plan_chunks
from synccraft.errors import format_user_error
from synccraft.media import WaveDurationExtractor, validate_audio_path, validate_image_path
from synccraft.output import write_transcript
from synccraft.provider import MockProviderAdapter, ProviderAdapter, build_provider_adapter
from synccraft.templating import render_filename

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


def _validate_execution_inputs(*, image: str, audio: str, config: dict[str, Any]) -> tuple[str | None, str]:
    """Validate required CLI and config inputs before execution."""
    validate_image_path(image)
    validate_audio_path(audio)

    provider_name = str(config.get("provider", "omni")).strip().lower()
    provider_payload = config.get("provider_payload")
    output_path = config.get("output")

    if provider_name == "mock" and not provider_payload:
        raise ValueError(
            format_user_error(
                what="missing required config key: provider_payload.",
                why="provider payload path is needed for mock transcription",
                how_to_fix="add provider_payload: <json-file> to your config or use provider: omni",
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

    if provider_name == "mock":
        _validate_path_exists(value=str(provider_payload), field_name="provider_payload")
    _validate_chunk_output_template_config(config=config, output_path=str(output_path))
    return (str(provider_payload) if provider_payload else None), str(output_path)


def _validate_chunk_output_template_config(*, config: dict[str, Any], output_path: str) -> None:
    """Fail fast on invalid chunk output template configuration."""
    template = config.get("output_chunk_template")
    if template is None:
        return

    if not isinstance(template, str) or not template.strip():
        raise ValueError(
            format_user_error(
                what="output_chunk_template must be a non-empty string.",
                why="chunk output file naming requires a valid template",
                how_to_fix="set output_chunk_template to a string like '{stem}_{index}.{ext}'",
            )
        )

    output = Path(output_path)
    ext = output.suffix.lstrip(".")
    stem = output.stem
    try:
        rendered = render_filename(
            template,
            stem=stem,
            ext=ext,
            index=0,
            chunk_start=0,
            chunk_end=1,
        )
        _validate_chunk_output_filename(filename=rendered)
    except ValueError as exc:
        raise ValueError(
            format_user_error(
                what="output_chunk_template is invalid.",
                why=str(exc),
                how_to_fix=(
                    "use only known tokens: {stem}, {ext}, {index}, {chunk_start}, {chunk_end}; "
                    "example '{stem}_{index}_{chunk_start}_{chunk_end}.{ext}'"
                ),
            )
        ) from exc


def _validate_chunk_output_filename(*, filename: str) -> None:
    """Ensure rendered chunk output filename stays within output directory."""
    candidate = Path(filename)
    if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.name in {"", ".", ".."}:
        raise ValueError(
            format_user_error(
                what="output_chunk_template produced an unsafe path.",
                why="chunk output files must be plain filenames under the output directory",
                how_to_fix="remove path separators and traversal segments from output_chunk_template",
            )
        )



def _validate_duration_against_provider_limit(*, audio: str, config: dict[str, Any], adapter: ProviderAdapter) -> None:
    """Fail fast when the source duration exceeds provider limit without chunking."""
    max_audio_seconds = adapter.limits().max_audio_seconds
    if max_audio_seconds is None:
        return

    audio_seconds = WaveDurationExtractor().duration_seconds(audio)
    if audio_seconds <= max_audio_seconds:
        return

    chunk_seconds = config.get("chunk_seconds")
    chunking_configured = isinstance(chunk_seconds, int) and chunk_seconds > 0
    if chunking_configured:
        return

    snippet = "audio:\n  chunk_seconds: 30\n  on_chunk_failure: stop"
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


def _print_execution_summary(*, image: str, audio: str, config_path: str, output: str, provider: str, provider_payload: str | None) -> None:
    """Print a concise execution summary for dry-run and transparency."""
    print("SyncCraft execution summary")
    print(f"  image: {image}")
    print(f"  audio: {audio}")
    print(f"  config: {config_path}")
    print(f"  provider: {provider}")
    if provider_payload is not None:
        print(f"  provider_payload: {provider_payload}")
    print(f"  output: {output}")


def _write_chunk_outputs_if_configured(
    *,
    output_path: str,
    chunk_output_template: str | None,
    chunk_results: list[tuple[ChunkMetadata, dict[str, Any]]],
) -> None:
    """Write optional per-chunk output files using deterministic chunk metadata."""
    if not chunk_output_template:
        return

    output = Path(output_path)
    ext = output.suffix.lstrip(".")
    stem = output.stem

    for chunk, payload in chunk_results:
        filename = render_filename(
            chunk_output_template,
            stem=stem,
            ext=ext,
            **chunk_template_values(chunk=chunk),
        )
        _validate_chunk_output_filename(filename=filename)
        write_transcript(output_path=output.parent / filename, transcript=payload["transcript"])


def _run_chunked_transcription(*, image_path: str, audio_path: str, output_path: str, config: dict[str, Any], adapter: ProviderAdapter) -> None:
    """Execute chunked transcription flow with configurable failure policy."""
    logger = logging.getLogger(__name__)
    total_seconds = WaveDurationExtractor().duration_seconds(audio_path)
    chunk_seconds = int(config["chunk_seconds"])
    on_chunk_failure = str(config.get("on_chunk_failure", "stop"))
    chunks = plan_chunks(total_seconds=total_seconds, chunk_seconds=chunk_seconds)

    def _transcribe(chunk: ChunkMetadata) -> dict[str, Any]:
        logger.info(
            "Transcribing chunk index=%s start=%ss end=%ss",
            chunk.index,
            chunk.start_second,
            chunk.end_second,
        )
        return adapter.generate(image=image_path, audio_chunk=audio_path, chunk=chunk)

    result = execute_chunk_plan(chunks=chunks, transcribe_chunk=_transcribe, on_chunk_failure=on_chunk_failure)

    if result.failures and on_chunk_failure == "stop":
        failed_index = result.failures[0].chunk.index
        raise ValueError(
            format_user_error(
                what=f"chunked transcription failed at chunk index {failed_index}.",
                why="on_chunk_failure was set to stop and the provider returned an error",
                how_to_fix="fix the provider/chunking issue or set on_chunk_failure: continue",
            )
        )

    if not result.successes:
        raise ValueError(
            format_user_error(
                what="chunked transcription produced no successful chunks.",
                why="all chunk requests failed",
                how_to_fix="check provider payload and chunk settings",
            )
        )

    transcript = " ".join(payload["transcript"] for _, payload in result.successes).strip()
    write_transcript(output_path=output_path, transcript=transcript)
    _write_chunk_outputs_if_configured(
        output_path=output_path,
        chunk_output_template=config.get("output_chunk_template"),
        chunk_results=result.successes,
    )


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
        provider_name = str(config.get("provider", "omni")).strip().lower()
        _print_execution_summary(
            image=args.image,
            audio=args.audio,
            config_path=args.config,
            output=output_path,
            provider=provider_name,
            provider_payload=provider_payload,
        )

        if args.dry_run:
            logging.getLogger(__name__).info("Dry-run mode enabled; skipping provider calls")
            return 0

        adapter = build_provider_adapter(config=config)
        if isinstance(adapter, MockProviderAdapter):
            adapter.validate_chunking_payload_schema()
        _validate_duration_against_provider_limit(audio=args.audio, config=config, adapter=adapter)

        chunk_seconds = config.get("chunk_seconds")
        chunking_configured = isinstance(chunk_seconds, int) and chunk_seconds > 0
        if chunking_configured:
            _run_chunked_transcription(image_path=args.image, audio_path=args.audio, output_path=output_path, config=config, adapter=adapter)
            return 0

        result = adapter.generate(image=args.image, audio_chunk=args.audio)
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

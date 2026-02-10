"""SyncCraft command line entrypoint."""

from __future__ import annotations

import argparse
import logging
import string
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from synccraft.chunking import ChunkMetadata, chunk_template_values, execute_chunk_plan, plan_chunks
from synccraft.errors import (
    ConfigError,
    ExitCode,
    ProcessingError,
    SyncCraftError,
    ValidationError,
    format_user_error,
    parse_user_error_message,
)
from synccraft.media import WaveDurationExtractor, validate_audio_path, validate_image_path
from synccraft.output import write_transcript
from synccraft.provider import MockProviderAdapter, ProviderAdapter, build_provider_adapter
from synccraft.templating import render_filename

_VERSION = "0.1.0"
_ALLOWED_CHUNK_OUTPUT_PLACEHOLDERS = {"index", "start", "end", "audio_basename"}


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


def _emit_progress(*, event: str, detail: str) -> None:
    """Emit friendly human-readable progress events."""
    print(f"progress: {event} - {detail}")


def _emit_timing_if_enabled(*, args: argparse.Namespace, phase: str, elapsed_seconds: float) -> None:
    """Emit timing events in verbose/debug modes."""
    if args.verbose or args.debug:
        print(f"timing: {phase}={elapsed_seconds:.3f}s")


def _emit_chunk_debug_if_enabled(*, args: argparse.Namespace, chunk: ChunkMetadata) -> None:
    """Emit chunk metadata in debug mode."""
    if args.debug:
        print(
            "chunk-meta: "
            f"index={chunk.index} start={chunk.start_second}s end={chunk.end_second}s duration={chunk.end_second - chunk.start_second}s"
        )


def _load_config(*, path: str | Path) -> dict[str, Any]:
    """Read YAML configuration from disk."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(
            what=f"config file not found: {config_path}",
            why="--config must point to a readable YAML file",
            remediation="create the config file and provide its path to --config",
        )

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if content is None:
        content = {}
    if not isinstance(content, dict):
        raise ConfigError(
            what="config content must be a mapping.",
            why="SyncCraft requires named options under top-level keys",
            remediation="use YAML object format, for example: provider_payload: ...",
        )
    return content


def _validate_path_exists(*, value: str, field_name: str) -> None:
    """Validate a path exists on disk."""
    if not Path(value).exists():
        raise ValidationError(
            what=f"{field_name} not found: {value}",
            why="the provided path does not exist",
            remediation=f"provide an existing file path for {field_name}",
        )


def _validate_execution_inputs(*, image: str, audio: str, config: dict[str, Any]) -> tuple[str | None, str]:
    """Validate required CLI and config inputs before execution."""
    validate_image_path(image)
    validate_audio_path(audio)

    provider_name = str(config.get("provider", "omni")).strip().lower()
    provider_payload = config.get("provider_payload")
    output_path = config.get("output")

    if provider_name == "mock" and not provider_payload:
        raise ConfigError(
            what="missing required config key: provider_payload.",
            why="provider payload path is needed for mock transcription",
            remediation="add provider_payload: <json-file> to your config or use provider: omni",
        )

    if not output_path:
        raise ConfigError(
            what="missing required config key: output.",
            why="SyncCraft needs an output destination for transcript text",
            remediation="add output: <transcript-file> to your config",
        )

    if provider_name == "mock":
        _validate_path_exists(value=str(provider_payload), field_name="provider_payload")
    _validate_chunk_output_template_config(config=config, output_path=str(output_path))
    return (str(provider_payload) if provider_payload else None), str(output_path)


def _validate_chunk_output_template_config(*, config: dict[str, Any], output_path: str) -> None:
    """Fail fast on invalid chunk output template configuration."""
    _ = output_path
    template = config.get("output_chunk_template")
    if template is None:
        return

    if not isinstance(template, str) or not template.strip():
        raise ConfigError(
            what="output_chunk_template must be a non-empty string.",
            why="chunk output file naming requires a valid template",
            remediation="set output_chunk_template to a string like '{audio_basename}_{index}_{start}_{end}.txt'",
        )

    _validate_chunk_output_template_placeholders(template=template)

    audio_basename = "audio"
    try:
        rendered = render_filename(template, audio_basename=audio_basename, index=0, start=0, end=1)
        _validate_chunk_output_filename(filename=rendered)
    except ValueError as exc:
        raise ConfigError(
            what="output_chunk_template is invalid.",
            why=str(exc),
            remediation=(
                "use only known tokens: {index}, {start}, {end}, {audio_basename}; "
                "example '{audio_basename}_{index}_{start}_{end}.txt'"
            ),
        ) from exc


def _validate_chunk_output_template_placeholders(*, template: str) -> None:
    """Validate user-provided placeholders and provide fix guidance."""
    formatter = string.Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if not field_name:
            continue
        token_name = field_name.split("!", 1)[0].split(":", 1)[0]
        if token_name not in _ALLOWED_CHUNK_OUTPUT_PLACEHOLDERS:
            allowed = ", ".join(sorted(_ALLOWED_CHUNK_OUTPUT_PLACEHOLDERS))
            raise ConfigError(
                what=f"output_chunk_template uses unsupported placeholder '{token_name}'.",
                why="chunk output rendering supports only deterministic placeholder values",
                remediation=f"replace it with one of: {allowed}",
            )


def _validate_chunk_output_filename(*, filename: str) -> None:
    """Ensure rendered chunk output filename stays within output directory."""
    candidate = Path(filename)
    if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.name in {"", ".", ".."}:
        raise ConfigError(
            what="output_chunk_template produced an unsafe path.",
            why="chunk output files must be plain filenames under the output directory",
            remediation="remove path separators and traversal segments from output_chunk_template",
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
    raise ValidationError(
        what=(
            "audio duration exceeds provider limit with no chunking configured "
            f"(duration={audio_seconds}s, provider_limit={max_audio_seconds}s)."
        ),
        why="provider rejected long-form audio unless chunking is enabled",
        remediation=(
            "configure chunking in YAML, for example:\n"
            f"{snippet}"
        ),
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
    audio_path: str,
    chunk_output_template: str | None,
    chunk_results: list[tuple[ChunkMetadata, dict[str, Any]]],
) -> None:
    """Write optional per-chunk output files using deterministic chunk metadata."""
    if not chunk_output_template:
        return

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    audio_basename = Path(audio_path).stem
    allocated_names: dict[str, int] = {}

    for chunk, payload in sorted(chunk_results, key=lambda item: item[0].index):
        filename = render_filename(
            chunk_output_template,
            audio_basename=audio_basename,
            **chunk_template_values(chunk=chunk),
        )
        _validate_chunk_output_filename(filename=filename)
        resolved_filename = _resolve_output_filename_collision(
            base_filename=filename,
            output_directory=output.parent,
            allocated_names=allocated_names,
        )
        write_transcript(output_path=output.parent / resolved_filename, transcript=payload["transcript"])


def _resolve_output_filename_collision(*, base_filename: str, output_directory: Path, allocated_names: dict[str, int]) -> str:
    """Resolve collisions deterministically using numbered suffixes."""
    base_path = Path(base_filename)
    stem = base_path.stem
    suffix = base_path.suffix

    collision_index = allocated_names.get(base_filename, 0)
    while True:
        candidate = base_filename if collision_index == 0 else f"{stem}__{collision_index}{suffix}"
        candidate_path = output_directory / candidate
        if candidate not in allocated_names and not candidate_path.exists():
            allocated_names[candidate] = 1
            allocated_names[base_filename] = collision_index + 1
            return candidate
        collision_index += 1


def _run_chunked_transcription(
    *,
    image_path: str,
    audio_path: str,
    output_path: str,
    config: dict[str, Any],
    adapter: ProviderAdapter,
    args: argparse.Namespace,
) -> None:
    """Execute chunked transcription flow with configurable failure policy."""
    logger = logging.getLogger(__name__)
    total_seconds = WaveDurationExtractor().duration_seconds(audio_path)
    chunk_seconds = int(config["chunk_seconds"])
    on_chunk_failure = str(config.get("on_chunk_failure", "stop"))
    chunks = plan_chunks(total_seconds=total_seconds, chunk_seconds=chunk_seconds)

    def _transcribe(chunk: ChunkMetadata) -> dict[str, Any]:
        _emit_chunk_debug_if_enabled(args=args, chunk=chunk)
        logger.info("Transcribing chunk index=%s start=%ss end=%ss", chunk.index, chunk.start_second, chunk.end_second)
        return adapter.generate(image=image_path, audio_chunk=audio_path, chunk=chunk)

    result = execute_chunk_plan(chunks=chunks, transcribe_chunk=_transcribe, on_chunk_failure=on_chunk_failure)

    if result.failures and on_chunk_failure == "stop":
        failed_index = result.failures[0].chunk.index
        raise ProcessingError(
            what=f"chunked transcription failed at chunk index {failed_index}.",
            why="on_chunk_failure was set to stop and the provider returned an error",
            remediation="fix the provider/chunking issue or set on_chunk_failure: continue",
        )

    if not result.successes:
        raise ProcessingError(
            what="chunked transcription produced no successful chunks.",
            why="all chunk requests failed",
            remediation="check provider payload and chunk settings",
        )

    transcript = " ".join(payload["transcript"] for _, payload in result.successes).strip()
    write_transcript(output_path=output_path, transcript=transcript)
    _write_chunk_outputs_if_configured(
        output_path=output_path,
        audio_path=audio_path,
        chunk_output_template=config.get("output_chunk_template"),
        chunk_results=result.successes,
    )


def main(argv: list[str] | None = None) -> int:
    """Run CLI command and return process status code."""
    raw_argv = argv if argv is not None else sys.argv[1:]
    if "--version" in raw_argv:
        print(f"synccraft {_VERSION}")
        return int(ExitCode.OK)

    parser = build_parser()
    args = parser.parse_args(raw_argv)
    _configure_logging(debug=args.debug, verbose=args.verbose)

    started = time.perf_counter()
    try:
        load_start = time.perf_counter()
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
        _emit_progress(event="loaded", detail="inputs and configuration validated")
        _emit_timing_if_enabled(args=args, phase="loaded", elapsed_seconds=time.perf_counter() - load_start)

        if args.dry_run:
            logging.getLogger(__name__).info("Dry-run mode enabled; skipping provider calls")
            return int(ExitCode.OK)

        process_start = time.perf_counter()
        _emit_progress(event="processing", detail="starting transcription")
        adapter = build_provider_adapter(config=config)
        if isinstance(adapter, MockProviderAdapter):
            adapter.validate_chunking_payload_schema()
        _validate_duration_against_provider_limit(audio=args.audio, config=config, adapter=adapter)

        chunk_seconds = config.get("chunk_seconds")
        chunking_configured = isinstance(chunk_seconds, int) and chunk_seconds > 0
        if chunking_configured:
            _run_chunked_transcription(
                image_path=args.image,
                audio_path=args.audio,
                output_path=output_path,
                config=config,
                adapter=adapter,
                args=args,
            )
        else:
            result = adapter.generate(image=args.image, audio_chunk=args.audio)
            write_transcript(output_path=output_path, transcript=result["transcript"])
        _emit_timing_if_enabled(args=args, phase="processing", elapsed_seconds=time.perf_counter() - process_start)

        _emit_progress(event="saved", detail=f"transcript saved to {output_path}")
        _emit_timing_if_enabled(args=args, phase="total", elapsed_seconds=time.perf_counter() - started)
        return int(ExitCode.OK)
    except SyncCraftError as exc:
        print(str(exc), file=sys.stderr)
        return int(exc.exit_code)
    except ValueError as exc:
        parsed = parse_user_error_message(str(exc))
        if parsed is not None:
            what, why, remediation = parsed
            structured = ValidationError(what=what, why=why, remediation=remediation)
            print(str(structured), file=sys.stderr)
            return int(structured.exit_code)
        print(
            str(
                ValidationError(
                    what="invalid runtime input.",
                    why=str(exc),
                    remediation="review your inputs/config and try again",
                )
            ),
            file=sys.stderr,
        )
        return int(ExitCode.VALIDATION)
    except Exception as exc:  # pragma: no cover - defensive guard
        print(
            format_user_error(
                what="unexpected runtime failure.",
                why=str(exc),
                how_to_fix="inspect stack trace and re-run with validated inputs",
            ),
            file=sys.stderr,
        )
        return int(ExitCode.INTERNAL)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

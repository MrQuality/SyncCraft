"""Unit tests covering CLI orchestration and output writing."""

from __future__ import annotations

import json
import wave

import pytest

from synccraft.cli import _validate_duration_against_provider_limit, main
from synccraft.errors import ValidationError
from synccraft.output import write_transcript
from synccraft.provider import MockProviderAdapter, OmniProviderAdapter, build_provider_adapter


def _write_wav_with_duration(path, *, seconds: int, frame_rate: int = 8000) -> None:
    """Create a deterministic silent WAV file for duration-driven tests."""
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(frame_rate)
        wav_file.writeframes(b"\x00\x00" * frame_rate * seconds)


@pytest.mark.unit
def test_write_transcript_creates_parent_and_newline(tmp_path) -> None:
    output_file = tmp_path / "nested" / "file.txt"
    write_transcript(output_path=output_file, transcript="hello")
    assert output_file.read_text(encoding="utf-8") == "hello\n"


@pytest.mark.unit
def test_cli_main_success_path(tmp_path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "confidence": 0.2}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "ok\n"


@pytest.mark.unit
def test_cli_main_handles_provider_error_with_user_message(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {tmp_path / 'output.txt'}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 3
    assert "what:" in stderr and "why:" in stderr and "how-to-fix:" in stderr


@pytest.mark.unit
def test_cli_main_dry_run_skips_provider_calls(tmp_path, monkeypatch, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text("not-json", encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    def _should_not_be_called(self, *, audio_path):  # pragma: no cover - defensive
        raise AssertionError("provider call should be skipped during dry-run")

    monkeypatch.setattr(MockProviderAdapter, "transcribe", _should_not_be_called)

    rc = main([str(image), str(audio), "--config", str(config), "--dry-run"])

    std = capsys.readouterr().out
    assert rc == 0
    assert "execution summary" in std.lower()
    assert not output.exists()


@pytest.mark.unit
def test_cli_main_version_flag_exits_immediately(capsys) -> None:
    rc = main(["--version"])

    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == "synccraft 0.1.0"


@pytest.mark.unit
def test_provider_limit_validation_allows_under_limit_without_chunking(tmp_path) -> None:
    audio = tmp_path / "short.wav"
    _write_wav_with_duration(audio, seconds=5)
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "max_audio_seconds": 10}), encoding="utf-8")

    adapter = MockProviderAdapter(payload_file=payload)
    _validate_duration_against_provider_limit(audio=str(audio), config={}, adapter=adapter)


@pytest.mark.unit
def test_provider_limit_validation_blocks_over_limit_without_chunking(tmp_path) -> None:
    audio = tmp_path / "long.wav"
    _write_wav_with_duration(audio, seconds=15)
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "max_audio_seconds": 10}), encoding="utf-8")

    adapter = MockProviderAdapter(payload_file=payload)
    with pytest.raises(ValidationError, match="what: audio duration exceeds provider limit with no chunking configured"):
        _validate_duration_against_provider_limit(audio=str(audio), config={}, adapter=adapter)


@pytest.mark.unit
def test_cli_main_fails_fast_on_invalid_output_chunk_template(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "confidence": 0.9}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "output_chunk_template: 123\n",
        encoding="utf-8",
    )

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 2
    assert "output_chunk_template must be a non-empty string" in stderr


@pytest.mark.unit
def test_cli_main_fails_fast_on_invalid_fail_on_chunk_indices_schema(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "fail_on_chunk_indices": ["1"]}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 3
    assert "provider.fail_on_chunk_indices contains invalid values" in stderr


@pytest.mark.unit
def test_cli_main_fails_fast_on_invalid_chunk_transcripts_schema(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps({"transcript": "ok", "chunk_transcripts": {"first": "segment"}}),
        encoding="utf-8",
    )
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 3
    assert "provider.chunk_transcripts contains an invalid key" in stderr


@pytest.mark.unit
def test_cli_main_rejects_output_chunk_template_with_path_separator(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok"}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "output_chunk_template: '{audio_basename}/chunk_{index}.txt'\n",
        encoding="utf-8",
    )

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 2
    assert "output_chunk_template produced an unsafe path" in stderr


@pytest.mark.unit
def test_cli_main_rejects_output_chunk_template_with_parent_traversal(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok"}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "output_chunk_template: '../chunk_{index}.txt'\n",
        encoding="utf-8",
    )

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 2
    assert "output_chunk_template produced an unsafe path" in stderr




@pytest.mark.unit
def test_cli_main_rejects_output_chunk_template_with_unsupported_placeholder(tmp_path, capsys) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok"}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "output_chunk_template: '{audio_basename}_{chunk_start}.txt'\n",
        encoding="utf-8",
    )

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 2
    assert "unsupported placeholder 'chunk_start'" in stderr
    assert "replace it with one of" in stderr

@pytest.mark.unit
def test_build_provider_adapter_defaults_to_omni() -> None:
    """Provider factory uses omni when no provider is configured."""
    adapter = build_provider_adapter(config={})

    assert isinstance(adapter, OmniProviderAdapter)


@pytest.mark.unit
def test_cli_main_uses_default_omni_provider_without_payload(tmp_path) -> None:
    """CLI can execute with default omni provider and no payload fixture."""
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"output: {output}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "omni transcript\n"


@pytest.mark.unit
def test_cli_progress_snapshot_default_mode(tmp_path, capsys) -> None:
    """Default mode prints friendly progress events without timing details."""
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok"}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    out = capsys.readouterr().out
    assert rc == 0
    expected_lines = [
        "progress: loaded - inputs and configuration validated",
        "progress: processing - starting transcription",
        f"progress: saved - transcript saved to {output}",
    ]
    for line in expected_lines:
        assert line in out
    assert "timing:" not in out


@pytest.mark.unit
def test_cli_progress_snapshot_verbose_mode_includes_timing(tmp_path, capsys, monkeypatch) -> None:
    """Verbose mode includes timing lines for loaded/processing/total phases."""
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok"}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    counter = {"value": -0.1}
    def _tick() -> float:
        counter["value"] += 0.1
        return round(counter["value"], 1)
    monkeypatch.setattr("synccraft.cli.time.perf_counter", _tick)

    rc = main([str(image), str(audio), "--config", str(config), "--verbose"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "timing: loaded=" in out
    assert "timing: processing=" in out
    assert "timing: total=" in out


@pytest.mark.unit
def test_cli_progress_snapshot_debug_mode_includes_chunk_metadata(tmp_path, capsys) -> None:
    """Debug mode emits chunk metadata in chunked transcription paths."""
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "chunked.wav"
    _write_wav_with_duration(audio, seconds=6)
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "confidence": 0.9}), encoding="utf-8")
    output = tmp_path / "output.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\noutput: {output}\nchunk_seconds: 3\n",
        encoding="utf-8",
    )

    rc = main([str(image), str(audio), "--config", str(config), "--debug"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "chunk-meta: index=0 start=0s end=3s duration=3s" in out
    assert "chunk-meta: index=1 start=3s end=6s duration=3s" in out


@pytest.mark.unit
def test_exit_code_categories_for_major_failure_types(tmp_path, capsys) -> None:
    """CLI maps major fatal categories to deterministic non-zero exit codes."""
    image = tmp_path / "image.png"
    image.write_bytes(b"img")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "chunk_transcripts": {"0": "zero", "1": "one"}, "fail_on_chunk_indices": [0]}), encoding="utf-8")

    config_missing_output = tmp_path / "config_missing_output.yaml"
    config_missing_output.write_text(f"provider: mock\nprovider_payload: {payload}\n", encoding="utf-8")
    assert main([str(image), str(audio), "--config", str(config_missing_output)]) == 2

    assert main([str(tmp_path / 'missing.png'), str(audio), "--config", str(config_missing_output)]) == 3

    config_processing = tmp_path / "config_processing.yaml"
    config_processing.write_text(
        f"provider: mock\nprovider_payload: {payload}\noutput: {tmp_path / 'out.txt'}\nchunk_seconds: 1\non_chunk_failure: stop\n",
        encoding="utf-8",
    )
    _write_wav_with_duration(audio, seconds=2)
    assert main([str(image), str(audio), "--config", str(config_processing)]) == 5
    assert "how-to-fix:" in capsys.readouterr().err

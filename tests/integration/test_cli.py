"""Integration tests for CLI and filesystem outcomes."""

import json
import subprocess
import sys
import wave

import pytest


def _write_wav_with_duration(path, *, seconds: int, frame_rate: int = 8000) -> None:
    """Create a deterministic silent WAV fixture for integration tests."""
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(frame_rate)
        wav_file.writeframes(b"\x00\x00" * frame_rate * seconds)


@pytest.mark.integration
def test_cli_generates_output_file(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text(json.dumps({"transcript": "integration works", "confidence": 0.95}), encoding="utf-8")
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "synccraft.cli",
        "tests/fixtures/image/sample.png",
        "tests/fixtures/audio/tone.wav",
        "--config",
        str(config),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.returncode == 0, proc.stderr
    assert output.read_text(encoding="utf-8") == "integration works\n"


@pytest.mark.integration
def test_cli_invalid_image_path_exits_with_validation_error(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text(json.dumps({"transcript": "integration works", "confidence": 0.95}), encoding="utf-8")
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "synccraft.cli",
        "tests/fixtures/image/missing.png",
        "tests/fixtures/audio/tone.wav",
        "--config",
        str(config),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.returncode == 2
    assert "what:" in proc.stderr


@pytest.mark.integration
def test_cli_dry_run_validates_and_skips_provider_execution(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text("not-json", encoding="utf-8")
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "synccraft.cli",
        "tests/fixtures/image/sample.png",
        "tests/fixtures/audio/tone.wav",
        "--config",
        str(config),
        "--dry-run",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.returncode == 0, proc.stderr
    assert "execution summary" in proc.stdout.lower()
    assert not output.exists()


@pytest.mark.integration
def test_cli_version_flag_returns_immediately() -> None:
    cmd = [sys.executable, "-m", "synccraft.cli", "--version"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.returncode == 0
    assert proc.stdout.strip() == "synccraft 0.1.0"


@pytest.mark.integration
def test_cli_over_limit_without_chunking_returns_actionable_chunking_error(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text(
        json.dumps({"transcript": "integration works", "confidence": 0.95, "max_audio_seconds": 10}),
        encoding="utf-8",
    )
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider_payload: {payload}\noutput: {output}\n", encoding="utf-8")
    audio = tmp_path / "long.wav"
    _write_wav_with_duration(audio, seconds=15)

    cmd = [
        sys.executable,
        "-m",
        "synccraft.cli",
        "tests/fixtures/image/sample.png",
        str(audio),
        "--config",
        str(config),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    expected = (
        "what: audio duration exceeds provider limit with no chunking configured (duration=15s, provider_limit=10s).; "
        "why: provider rejected long-form audio unless chunking is enabled; "
        "how-to-fix: configure chunking in YAML, for example:\n"
        "audio:\n"
        "  chunk_seconds: 30\n"
        "  on_chunk_failure: abort"
    )
    assert proc.returncode == 2
    assert proc.stderr.strip() == expected

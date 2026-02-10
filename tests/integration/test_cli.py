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
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

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
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

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

    assert proc.returncode == 3
    assert "what:" in proc.stderr


@pytest.mark.integration
def test_cli_dry_run_validates_and_skips_provider_execution(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text("not-json", encoding="utf-8")
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

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
    config.write_text(f"provider: mock\nprovider_payload: {payload}\noutput: {output}\n", encoding="utf-8")
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
        "  on_chunk_failure: stop"
    )
    assert proc.returncode == 3
    assert proc.stderr.strip() == expected


@pytest.mark.integration
def test_cli_chunked_stop_policy_aborts_on_first_failed_chunk(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text(
        json.dumps(
            {
                "transcript": "fallback",
                "chunk_transcripts": {"0": "zero", "1": "one", "2": "two"},
                "fail_on_chunk_indices": [1],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "chunk_seconds: 5\n"
        "on_chunk_failure: stop\n",
        encoding="utf-8",
    )
    audio = tmp_path / "chunked.wav"
    _write_wav_with_duration(audio, seconds=12)

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

    assert proc.returncode == 5
    assert "chunked transcription failed at chunk index 1" in proc.stderr
    assert not output.exists()


@pytest.mark.integration
def test_cli_chunked_continue_policy_writes_successful_chunk_transcripts(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text(
        json.dumps(
            {
                "transcript": "fallback",
                "chunk_transcripts": {"0": "zero", "1": "one", "2": "two"},
                "fail_on_chunk_indices": [1],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "chunk_seconds: 5\n"
        "on_chunk_failure: continue\n"
        "output_chunk_template: '{audio_basename}_{index}_{start}_{end}.txt'\n",
        encoding="utf-8",
    )
    audio = tmp_path / "chunked.wav"
    _write_wav_with_duration(audio, seconds=12)

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

    assert proc.returncode == 0, proc.stderr
    assert output.read_text(encoding="utf-8") == "zero two\n"
    assert (tmp_path / "chunked_0_0_5.txt").read_text(encoding="utf-8") == "zero\n"
    assert (tmp_path / "chunked_2_10_12.txt").read_text(encoding="utf-8") == "two\n"


@pytest.mark.integration
def test_cli_chunked_output_collisions_use_deterministic_suffixes(tmp_path) -> None:
    payload = tmp_path / "provider.json"
    payload.write_text(
        json.dumps(
            {
                "transcript": "fallback",
                "chunk_transcripts": {"0": "zero", "1": "one", "2": "two"},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "result.txt"
    config = tmp_path / "config.yaml"
    config.write_text(
        f"provider: mock\nprovider_payload: {payload}\n"
        f"output: {output}\n"
        "chunk_seconds: 5\n"
        "on_chunk_failure: continue\n"
        "output_chunk_template: '{audio_basename}.txt'\n",
        encoding="utf-8",
    )
    audio = tmp_path / "chunked.wav"
    _write_wav_with_duration(audio, seconds=12)

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

    assert proc.returncode == 0, proc.stderr
    expected_files = [tmp_path / "chunked.txt", tmp_path / "chunked__1.txt", tmp_path / "chunked__2.txt"]
    assert [path.name for path in expected_files if path.exists()] == [
        "chunked.txt",
        "chunked__1.txt",
        "chunked__2.txt",
    ]
    assert [path.read_text(encoding="utf-8") for path in expected_files] == ["zero\n", "one\n", "two\n"]

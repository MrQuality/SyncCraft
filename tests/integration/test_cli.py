"""Integration tests for CLI and filesystem outcomes."""

import json
import subprocess
import sys

import pytest


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

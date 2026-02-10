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

    cmd = [
        sys.executable,
        "-m",
        "synccraft.cli",
        "--audio",
        "tests/fixtures/audio/tone.wav",
        "--provider-payload",
        str(payload),
        "--output",
        str(output),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.returncode == 0, proc.stderr
    assert output.read_text(encoding="utf-8") == "integration works\n"


@pytest.mark.integration
def test_cli_user_facing_error_has_what_why_fix(tmp_path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "synccraft.cli",
        "--audio",
        "tests/fixtures/audio/missing.wav",
        "--provider-payload",
        str(tmp_path / "provider.json"),
        "--output",
        str(tmp_path / "result.txt"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.returncode == 2
    assert "what:" in proc.stderr
    assert "why:" in proc.stderr
    assert "how-to-fix:" in proc.stderr

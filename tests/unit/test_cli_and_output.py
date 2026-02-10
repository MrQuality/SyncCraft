"""Unit tests covering CLI orchestration and output writing."""

from __future__ import annotations

import json

import pytest

from synccraft.cli import main
from synccraft.output import write_transcript


@pytest.mark.unit
def test_write_transcript_creates_parent_and_newline(tmp_path) -> None:
    output_file = tmp_path / "nested" / "file.txt"
    write_transcript(output_path=output_file, transcript="hello")
    assert output_file.read_text(encoding="utf-8") == "hello\n"


@pytest.mark.unit
def test_cli_main_success_path(tmp_path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"fake")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"transcript": "ok", "confidence": 0.2}), encoding="utf-8")
    output = tmp_path / "output.txt"

    rc = main([
        "--audio",
        str(audio),
        "--provider-payload",
        str(payload),
        "--output",
        str(output),
    ])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "ok\n"


@pytest.mark.unit
def test_cli_main_handles_provider_error_with_user_message(tmp_path, capsys) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")

    rc = main([
        "--audio",
        str(tmp_path / "missing.wav"),
        "--provider-payload",
        str(payload),
        "--output",
        str(tmp_path / "output.txt"),
    ])

    stderr = capsys.readouterr().err
    assert rc == 2
    assert "what:" in stderr and "why:" in stderr and "how-to-fix:" in stderr

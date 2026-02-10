"""Unit tests covering CLI orchestration and output writing."""

from __future__ import annotations

import json

import pytest

from synccraft.cli import main
from synccraft.output import write_transcript
from synccraft.provider import MockProviderAdapter


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
    config.write_text(f"provider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

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
    config.write_text(f"provider_payload: {payload}\noutput: {tmp_path / 'output.txt'}\n", encoding="utf-8")

    rc = main([str(image), str(audio), "--config", str(config)])

    stderr = capsys.readouterr().err
    assert rc == 2
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
    config.write_text(f"provider_payload: {payload}\noutput: {output}\n", encoding="utf-8")

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

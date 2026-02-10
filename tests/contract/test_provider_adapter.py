"""Contract tests for provider adapter behavior."""

import json

import pytest

from synccraft.provider import MockProviderAdapter


@pytest.mark.contract
def test_mock_provider_contract_uses_expected_response_shape(tmp_path) -> None:
    payload_path = tmp_path / "response.json"
    payload_path.write_text(json.dumps({"transcript": "hello world", "confidence": 0.9}), encoding="utf-8")

    adapter = MockProviderAdapter(payload_file=payload_path)
    result = adapter.transcribe(audio_path="tests/fixtures/audio/tone.wav")

    assert result["transcript"] == "hello world"
    assert "confidence" in result


@pytest.mark.contract
def test_mock_provider_contract_errors_with_helpful_message(tmp_path) -> None:
    payload_path = tmp_path / "bad.json"
    payload_path.write_text("{}", encoding="utf-8")
    adapter = MockProviderAdapter(payload_file=payload_path)

    with pytest.raises(ValueError, match="what: provider response missing 'transcript'.*how-to-fix"):
        adapter.transcribe(audio_path="tests/fixtures/audio/tone.wav")


@pytest.mark.contract
def test_mock_provider_contract_exposes_optional_duration_limit(tmp_path) -> None:
    payload_path = tmp_path / "response.json"
    payload_path.write_text(json.dumps({"transcript": "hello world", "max_audio_seconds": 120}), encoding="utf-8")

    adapter = MockProviderAdapter(payload_file=payload_path)

    assert adapter.get_max_audio_seconds() == 120

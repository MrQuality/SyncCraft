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


@pytest.mark.contract
def test_mock_provider_contract_supports_chunk_specific_behavior(tmp_path) -> None:
    payload_path = tmp_path / "response.json"
    payload_path.write_text(
        json.dumps(
            {
                "transcript": "fallback",
                "chunk_transcripts": {"0": "chunk zero"},
                "fail_on_chunk_indices": [1],
            }
        ),
        encoding="utf-8",
    )

    adapter = MockProviderAdapter(payload_file=payload_path)

    class _Chunk:
        def __init__(self, index: int) -> None:
            self.index = index

    ok = adapter.transcribe(audio_path="tests/fixtures/audio/tone.wav", chunk=_Chunk(index=0))
    assert ok["transcript"] == "chunk zero"

    with pytest.raises(ValueError, match="what: provider failed for chunk index 1"):
        adapter.transcribe(audio_path="tests/fixtures/audio/tone.wav", chunk=_Chunk(index=1))


@pytest.mark.contract
def test_mock_provider_contract_validates_chunking_payload_schema(tmp_path) -> None:
    payload_path = tmp_path / "response.json"
    payload_path.write_text(
        json.dumps({"transcript": "ok", "fail_on_chunk_indices": [0, 2], "chunk_transcripts": {"0": "a"}}),
        encoding="utf-8",
    )

    adapter = MockProviderAdapter(payload_file=payload_path)

    adapter.validate_chunking_payload_schema()

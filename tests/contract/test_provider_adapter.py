"""Contract tests for provider adapter behavior."""

import json
from pathlib import Path

import pytest

from synccraft.provider import MockProviderAdapter, OmniProviderAdapter, ProviderAdapter, ProviderLimits


@pytest.fixture
def mock_adapter(tmp_path: Path) -> MockProviderAdapter:
    """Build a mock adapter with a valid payload fixture."""
    payload_path = tmp_path / "response.json"
    payload_path.write_text(json.dumps({"transcript": "hello world", "confidence": 0.9}), encoding="utf-8")
    return MockProviderAdapter(payload_file=payload_path)


@pytest.fixture
def omni_adapter() -> OmniProviderAdapter:
    """Build an omni adapter using deterministic defaults for contract assertions."""
    return OmniProviderAdapter(default_params={"temperature": 0.4}, limits=ProviderLimits(max_audio_seconds=180))


@pytest.mark.contract
@pytest.mark.parametrize("adapter_fixture", ["mock_adapter", "omni_adapter"])
def test_provider_contract_generate_returns_transcript_and_supports_params(
    request: pytest.FixtureRequest, adapter_fixture: str
) -> None:
    """Every adapter returns transcript data and accepts provider params."""
    adapter: ProviderAdapter = request.getfixturevalue(adapter_fixture)

    result = adapter.generate(
        image="tests/fixtures/image/sample.png",
        audio_chunk="tests/fixtures/audio/tone.wav",
        params={"request_id": "req-123", "custom_knob": True},
    )

    assert isinstance(result["transcript"], str)
    if adapter_fixture == "omni_adapter":
        assert result["params"]["custom_knob"] is True


@pytest.mark.contract
def test_mock_provider_contract_errors_with_helpful_message(tmp_path: Path) -> None:
    payload_path = tmp_path / "bad.json"
    payload_path.write_text("{}", encoding="utf-8")
    adapter = MockProviderAdapter(payload_file=payload_path)

    with pytest.raises(ValueError, match="what: provider response missing 'transcript'.*how-to-fix"):
        adapter.transcribe(audio_path="tests/fixtures/audio/tone.wav")


@pytest.mark.contract
@pytest.mark.parametrize(
    ("adapter_fixture", "expected_limit"),
    [("mock_adapter", None), ("omni_adapter", 180)],
)
def test_provider_contract_exposes_limits(
    request: pytest.FixtureRequest, adapter_fixture: str, expected_limit: int | None
) -> None:
    """Every adapter surfaces limits through the shared API."""
    adapter: ProviderAdapter = request.getfixturevalue(adapter_fixture)
    assert adapter.limits().max_audio_seconds == expected_limit


@pytest.mark.contract
def test_mock_provider_contract_supports_chunk_specific_behavior(tmp_path: Path) -> None:
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
def test_mock_provider_contract_validates_chunking_payload_schema(tmp_path: Path) -> None:
    payload_path = tmp_path / "response.json"
    payload_path.write_text(
        json.dumps({"transcript": "ok", "fail_on_chunk_indices": [0, 2], "chunk_transcripts": {"0": "a"}}),
        encoding="utf-8",
    )

    adapter = MockProviderAdapter(payload_file=payload_path)

    adapter.validate_chunking_payload_schema()

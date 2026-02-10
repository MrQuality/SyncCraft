"""Unit tests for Omni provider adapter behavior."""

import logging

from synccraft.provider import OmniProviderAdapter, ProviderLimits


def test_omni_adapter_passes_through_params_without_hardcoding() -> None:
    """Omni adapter forwards custom provider params as-is."""
    adapter = OmniProviderAdapter(default_params={"temperature": 0.2, "top_p": 0.95})

    response = adapter.generate(
        image="tests/fixtures/image/sample.png",
        audio_chunk="tests/fixtures/audio/tone.wav",
        params={"request_id": "req-42", "temperature": 0.6, "vendor_knob": "raw-value"},
    )

    assert response["request_id"] == "req-42"
    assert response["params"]["temperature"] == 0.6
    assert response["params"]["top_p"] == 0.95
    assert response["params"]["vendor_knob"] == "raw-value"


def test_omni_adapter_reports_limits() -> None:
    """Omni adapter exposes configured limits via the shared API."""
    adapter = OmniProviderAdapter(limits=ProviderLimits(max_audio_seconds=240))

    limits = adapter.limits()

    assert limits.max_audio_seconds == 240


def test_omni_debug_logging_sanitizes_secrets_and_keeps_request_identifier(caplog) -> None:
    """Debug logs keep request identifiers visible while redacting secrets."""
    caplog.set_level(logging.DEBUG)
    adapter = OmniProviderAdapter()

    adapter.generate(
        image="tests/fixtures/image/sample.png",
        audio_chunk="tests/fixtures/audio/tone.wav",
        params={
            "request_id": "req-visible",
            "api_key": "super-secret",
            "nested": {"access_token": "nested-secret"},
        },
    )

    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "req-visible" in joined
    assert "super-secret" not in joined
    assert "nested-secret" not in joined
    assert "***REDACTED***" in joined
